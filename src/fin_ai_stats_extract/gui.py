"""pywebview-backed GUI for editing the TOML config and launching a run.

The GUI's job is to configure the on-disk TOML file. Every edit is written back
to the config file live (see :mod:`fin_ai_stats_extract.toml_io`). CLI override
flags such as ``--temperature`` are applied *after* the GUI closes, in
:func:`fin_ai_stats_extract.cli.main`, so they win over the file without being
persisted to it.

Pure helpers (state building, run-option parsing, review summary) are kept free
of any ``webview`` import so they can be unit-tested headlessly. Only
:func:`launch_gui` and the file-dialog methods touch pywebview.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from fin_ai_stats_extract.config import ExtractConfig, load_config
from fin_ai_stats_extract.cost import estimate_total_cost
from fin_ai_stats_extract.pipeline import PreparedRun, prepare_run
from fin_ai_stats_extract.prompts import render_system_prompt
from fin_ai_stats_extract.toml_io import (
    build_config_from_values,
    write_config,
)

_REASONING_EFFORT_CHOICES = ("", "none", "minimal", "low", "medium", "high", "xhigh")
_VERBOSITY_CHOICES = ("", "low", "medium", "high")

_WEBUI_DIR = Path(__file__).parent / "resources" / "webui"


@dataclass
class GuiRunResult:
    """Runtime options collected from the GUI (config lives in the TOML file)."""

    input_path: Path | None
    output_path: Path
    api_key: str | None
    max_concurrency: int
    sample: float | int | None
    dry_run: bool
    resume: bool
    verbose: bool
    prepared_run: PreparedRun | None = None


def _as_text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)


def _parse_optional_float(raw: Any, field_name: str) -> float | None:
    value = str(raw).strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a number") from exc


def build_config_state(config: ExtractConfig) -> dict[str, Any]:
    """Return the JSON-serializable config section of the GUI state."""
    return {
        "instructions": config.llm.instructions,
        "model": config.llm.model,
        "api_key_env": config.llm.api_key_env,
        "base_url": _as_text(config.llm.base_url),
        "temperature": _as_text(config.llm.temperature),
        "top_p": _as_text(config.llm.top_p),
        "max_output_tokens": _as_text(config.llm.max_output_tokens),
        "reasoning_effort": _as_text(config.llm.reasoning_effort),
        "verbosity": _as_text(config.llm.verbosity),
        "output_format": [
            {"name": field.name, "description": field.description}
            for field in config.output.format
        ],
    }


def build_initial_state(
    config: ExtractConfig, args: Any, config_path: Path
) -> dict[str, Any]:
    """Return the full initial GUI state (config + runtime options + metadata)."""
    return {
        "config": build_config_state(config),
        "runtime": {
            "input": _as_text(getattr(args, "input", None)),
            "output": _as_text(getattr(args, "output", None) or "output.csv"),
            "api_key": _as_text(getattr(args, "api_key", None)),
            "max_concurrency": _as_text(getattr(args, "max_concurrency", 100)),
            "sample": _as_text(getattr(args, "sample", None)),
            "dry_run": bool(getattr(args, "dry_run", False)),
            "resume": bool(getattr(args, "resume", False)),
            "verbose": bool(getattr(args, "verbose", False)),
        },
        "meta": {
            "config_path": str(config_path),
            "reasoning_effort_choices": list(_REASONING_EFFORT_CHOICES),
            "verbosity_choices": list(_VERBOSITY_CHOICES),
        },
    }


def build_run_result(runtime: dict[str, Any]) -> GuiRunResult:
    """Parse the GUI's runtime-option payload into a :class:`GuiRunResult`."""
    input_value = str(runtime.get("input", "")).strip()
    input_path = Path(input_value).expanduser() if input_value else None
    output_value = str(runtime.get("output", "")).strip() or "output.csv"
    output_path = Path(output_value).expanduser()
    api_key = str(runtime.get("api_key", "")).strip() or None

    concurrency_raw = str(runtime.get("max_concurrency", "")).strip()
    try:
        max_concurrency = int(concurrency_raw) if concurrency_raw else 0
    except ValueError as exc:
        raise ValueError("max_concurrency must be an integer") from exc

    sample = _parse_optional_float(runtime.get("sample", ""), "sample")

    return GuiRunResult(
        input_path=input_path,
        output_path=output_path,
        api_key=api_key,
        max_concurrency=max_concurrency,
        sample=sample,
        dry_run=bool(runtime.get("dry_run")),
        resume=bool(runtime.get("resume")),
        verbose=bool(runtime.get("verbose")),
    )


def build_output_format_preview(config: ExtractConfig) -> str:
    lines = [f"- {field.name}: {field.description}" for field in config.output.format]
    return "\n".join(lines).strip()


def build_review_summary(
    config: ExtractConfig, dry_run: bool, prepared: PreparedRun
) -> str:
    lines = [
        f"Files discovered: {prepared.discovered_count}",
        f"Files ready to process: {len(prepared.parsed)}",
    ]
    if prepared.parse_errors:
        lines.append(f"Parse errors: {prepared.parse_errors}")
    if prepared.resume_skipped:
        lines.append(f"Skipped by resume: {prepared.resume_skipped}")
    if prepared.applied_sample is not None:
        lines.append(f"Sample size: {prepared.applied_sample}")

    if dry_run:
        lines.append("Estimated cost: none, because dry run is enabled.")
    elif config.llm.base_url:
        lines.append(
            "Estimated cost: skipped, because a custom base URL is configured."
        )
    else:
        bodies = [body for _, _, body in prepared.parsed]
        total_tokens, estimated_cost, cost_label = estimate_total_cost(
            render_system_prompt(config),
            bodies,
            config.llm.model,
        )
        lines.append(f"Total input tokens: {total_tokens:,}")
        if cost_label is None or estimated_cost is None:
            lines.append("Estimated cost: unknown for this model.")
        else:
            lines.append(f"Model cost: {cost_label}")
            lines.append(f"Estimated cost: ${estimated_cost:.4f} USD")

    return "\n".join(lines)


def prepare_review(
    config: ExtractConfig, runtime: dict[str, Any]
) -> tuple[bool, str, GuiRunResult | None]:
    """Validate runtime options and build a run/cost summary.

    Returns ``(ok, message, run_result)``. When ``ok`` is ``True`` the returned
    :class:`GuiRunResult` carries a computed :class:`PreparedRun`.
    """
    try:
        result = build_run_result(runtime)
    except ValueError as exc:
        return False, str(exc), None

    if result.input_path is None:
        return False, "Select an input file or folder to compute the run summary.", None

    if not result.input_path.exists():
        return False, f"Input path does not exist: {result.input_path}", None

    if result.max_concurrency < 1:
        return False, "Max concurrency must be at least 1.", None

    if result.resume and not result.output_path.exists():
        return (
            False,
            f"Resume needs an existing output CSV: {result.output_path}",
            None,
        )

    prepared = prepare_run(
        input_path=result.input_path,
        output_path=result.output_path,
        dry_run=result.dry_run,
        sample=result.sample,
        resume=result.resume,
    )

    if prepared.discovered_count == 0:
        return False, "No XML files were found at the selected input path.", None

    result.prepared_run = prepared
    return True, build_review_summary(config, result.dry_run, prepared), result


def _format_config_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", ()))
        message = first.get("msg", "invalid value")
        return f"{location}: {message}" if location else message
    return str(exc)


class _GuiApi:
    """The object exposed to JavaScript as ``window.pywebview.api``."""

    def __init__(self, config_path: Path, args: Any) -> None:
        self._config_path = config_path
        self._args = args
        self._window: Any = None
        self.result: GuiRunResult | None = None
        # Set by run()/cancel() to ask the watcher thread in launch_gui() to
        # close the window. We deliberately do NOT call window.destroy() from
        # inside these JS API methods: doing so stops the GUI loop before
        # pywebview delivers this call's return value, which strands the
        # bridge's (non-daemon) worker thread and hangs the whole process.
        self._close_requested = threading.Event()

    def get_state(self) -> dict[str, Any]:
        config = load_config(config_path=self._config_path)
        return build_initial_state(config, self._args, self._config_path)

    def save_config(self, config_values: dict[str, Any]) -> dict[str, Any]:
        try:
            write_config(self._config_path, config_values)
        except (ValueError, ValidationError) as exc:
            return {"ok": False, "message": _format_config_error(exc)}
        return {"ok": True}

    def compute_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            config = build_config_from_values(payload.get("config", {}))
        except (ValueError, ValidationError) as exc:
            return {
                "ok": False,
                "message": f"Invalid settings: {_format_config_error(exc)}",
            }
        ok, message, _ = prepare_review(config, payload.get("runtime", {}))
        return {"ok": ok, "message": message}

    def browse_input_file(self) -> str:
        import webview

        selected = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("XML files (*.xml)", "All files (*.*)"),
        )
        return selected[0] if selected else ""

    def browse_input_folder(self) -> str:
        import webview

        selected = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        return selected[0] if selected else ""

    def browse_output_file(self) -> str:
        import webview

        selected = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename="output.csv",
            file_types=("CSV files (*.csv)", "All files (*.*)"),
        )
        if not selected:
            return ""
        return selected if isinstance(selected, str) else selected[0]

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            config = write_config(self._config_path, payload.get("config", {}))
        except (ValueError, ValidationError) as exc:
            return {"ok": False, "message": _format_config_error(exc)}

        ok, message, result = prepare_review(config, payload.get("runtime", {}))
        if not ok or result is None:
            return {"ok": False, "message": message}

        self.result = result
        self._close_requested.set()
        return {"ok": True}

    def cancel(self) -> dict[str, Any]:
        self.result = None
        self._close_requested.set()
        return {"ok": True}


def _resolve_ui_url() -> str:
    dev_url = os.getenv("FIN_AI_GUI_DEV_URL")
    if dev_url:
        return dev_url

    index_path = _WEBUI_DIR / "index.html"
    if not index_path.exists():
        raise RuntimeError(
            "GUI assets are not built. Expected them at "
            f"{index_path}. Build the frontend (cd frontend && pnpm install && "
            "pnpm build) or set FIN_AI_GUI_DEV_URL to a running dev server."
        )
    return str(index_path)


# Grace period that lets pywebview deliver a Run/Cancel return value to the UI
# before the GUI loop is stopped. Without it the bridge worker thread blocked in
# evaluate_js() would never be released and the process would hang on exit.
_CLOSE_FLUSH_DELAY = 0.15


def _run_close_watcher(
    window: Any,
    close_requested: threading.Event,
    flush_delay: float = _CLOSE_FLUSH_DELAY,
) -> None:
    """Close ``window`` once a Run/Cancel action asks for it.

    Closing the window from inside a JS API method would stop the GUI loop
    before pywebview returns that call's value, stranding its (non-daemon)
    bridge thread and hanging the process. Instead the API methods signal
    ``close_requested`` and this watcher — running on a neutral thread — closes
    the window after the return value has been flushed.
    """
    close_requested.wait()
    if window.events.closed.is_set():
        return  # Window already gone (e.g. closed via the native close button).
    time.sleep(flush_delay)
    try:
        window.destroy()
    except Exception:
        logging.getLogger(__name__).debug("Failed to destroy GUI window", exc_info=True)


def launch_gui(config_path: Path, args: Any) -> GuiRunResult | None:
    """Open the config editor and return the run options, or ``None`` if cancelled.

    Config edits are persisted to ``config_path`` while the window is open.
    """
    import webview

    api = _GuiApi(config_path, args)
    window = webview.create_window(
        "fin-ai-stats-extract",
        url=_resolve_ui_url(),
        js_api=api,
        width=1180,
        height=940,
        min_size=(940, 720),
    )
    api._window = window

    # A native window close (the red traffic-light button) must also release
    # the watcher so it never blocks the process from exiting.
    def _on_window_closed() -> None:
        api._close_requested.set()

    window.events.closed += _on_window_closed

    webview.start(lambda: _run_close_watcher(window, api._close_requested))
    return api.result
