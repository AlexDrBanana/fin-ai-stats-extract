from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from fin_ai_stats_extract.config import ExtractConfig
from fin_ai_stats_extract.cost import estimate_total_cost
from fin_ai_stats_extract.pipeline import PreparedRun, prepare_run
from fin_ai_stats_extract.prompts import render_system_prompt

_REASONING_EFFORT_CHOICES = ("", "none", "minimal", "low", "medium", "high", "xhigh")
_VERBOSITY_CHOICES = ("", "low", "medium", "high")


def select_preferred_theme(
    theme_names: tuple[str, ...] | list[str],
    windowing_system: str | None,
) -> str | None:
    available = tuple(theme_names)

    if windowing_system == "aqua" and "aqua" in available:
        return "aqua"

    if windowing_system == "win32":
        for candidate in ("vista", "xpnative", "winnative"):
            if candidate in available:
                return candidate

    for candidate in ("clam", "alt", "default"):
        if candidate in available:
            return candidate

    return available[0] if available else None


@dataclass
class GuiRunResult:
    config: ExtractConfig
    input_path: Path | None
    output_path: Path
    api_key: str | None
    max_concurrency: int
    sample: int | None
    dry_run: bool
    resume: bool
    verbose: bool
    prepared_run: PreparedRun | None = None


def build_output_format_preview(config: ExtractConfig) -> str:
    lines: list[str] = []
    for field in config.output.format:
        lines.append(f"- {field.name}: {field.description}")
    return "\n".join(lines).strip()


def build_review_summary(resolved: GuiRunResult, prepared: PreparedRun) -> str:
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

    if resolved.dry_run:
        lines.append("Estimated cost: none, because dry run is enabled.")
    elif resolved.config.llm.base_url:
        lines.append(
            "Estimated cost: skipped, because a custom base URL is configured."
        )
    else:
        bodies = [body for _, _, body in prepared.parsed]
        total_tokens, estimated_cost, cost_label = estimate_total_cost(
            render_system_prompt(resolved.config),
            bodies,
            resolved.config.llm.model,
        )
        lines.append(f"Total input tokens: {total_tokens:,}")
        if cost_label is None or estimated_cost is None:
            lines.append("Estimated cost: unknown for this model.")
        else:
            lines.append(f"Model cost: {cost_label}")
            lines.append(f"Estimated cost: ${estimated_cost:.4f} USD")

    return "\n".join(lines)


def _as_text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)


def _parse_optional_float(raw: str, field_name: str) -> float | None:
    value = raw.strip()
    if not value:
        return None
    return float(value)


def _parse_optional_int(raw: str, field_name: str) -> int | None:
    value = raw.strip()
    if not value:
        return None
    return int(value)


def build_initial_gui_values(config: ExtractConfig, args: Any) -> dict[str, Any]:
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
        "input": _as_text(getattr(args, "input", None)),
        "output": _as_text(getattr(args, "output", Path("output.csv"))),
        "api_key": _as_text(getattr(args, "api_key", None)),
        "max_concurrency": _as_text(getattr(args, "max_concurrency", 100)),
        "sample": _as_text(getattr(args, "sample", None)),
        "dry_run": bool(getattr(args, "dry_run", False)),
        "resume": bool(getattr(args, "resume", False)),
        "verbose": bool(getattr(args, "verbose", False)),
    }


def apply_gui_values(config: ExtractConfig, values: dict[str, Any]) -> GuiRunResult:
    resolved_config = config.model_copy(deep=True)
    resolved_config.llm.instructions = values["instructions"].strip()
    resolved_config.llm.model = values["model"].strip()
    resolved_config.llm.api_key_env = values["api_key_env"].strip()
    resolved_config.llm.base_url = values["base_url"].strip() or None
    resolved_config.llm.temperature = _parse_optional_float(
        values["temperature"], "temperature"
    )
    resolved_config.llm.top_p = _parse_optional_float(values["top_p"], "top_p")
    resolved_config.llm.max_output_tokens = _parse_optional_int(
        values["max_output_tokens"],
        "max_output_tokens",
    )
    resolved_config.llm.reasoning_effort = values["reasoning_effort"].strip() or None
    resolved_config.llm.verbosity = values["verbosity"].strip() or None
    resolved_config = ExtractConfig.model_validate(resolved_config.model_dump())

    input_value = values["input"].strip()
    input_path = Path(input_value).expanduser() if input_value else None
    output_value = values["output"].strip() or "output.csv"
    output_path = Path(output_value).expanduser()
    api_key = values["api_key"].strip() or None
    max_concurrency = int(values["max_concurrency"])
    sample = _parse_optional_int(values["sample"], "sample")

    return GuiRunResult(
        config=resolved_config,
        input_path=input_path,
        output_path=output_path,
        api_key=api_key,
        max_concurrency=max_concurrency,
        sample=sample,
        dry_run=bool(values["dry_run"]),
        resume=bool(values["resume"]),
        verbose=bool(values["verbose"]),
    )


def launch_gui(config: ExtractConfig, args: Any) -> GuiRunResult | None:
    import tkinter as tk
    from tkinter import filedialog, ttk

    initial = build_initial_gui_values(config, args)
    root = tk.Tk()
    root.title("fin-ai-stats-extract")
    root.geometry("1000x840")
    root.minsize(860, 680)

    style = ttk.Style(root)
    theme_name = select_preferred_theme(
        style.theme_names(),
        root.tk.call("tk", "windowingsystem"),
    )
    if theme_name is not None:
        style.theme_use(theme_name)

    container = ttk.Frame(root, padding=16)
    container.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(1, weight=1)

    ttk.Label(
        container,
        text="Review extraction settings before running",
        font=("Helvetica", 16, "bold"),
    ).grid(row=0, column=0, sticky="w")

    notebook = ttk.Notebook(container)
    notebook.grid(row=1, column=0, sticky="nsew", pady=(12, 12))

    run_tab = ttk.Frame(notebook, padding=12)
    model_tab = ttk.Frame(notebook, padding=12)
    instructions_tab = ttk.Frame(notebook, padding=12)
    output_tab = ttk.Frame(notebook, padding=12)
    notebook.add(run_tab, text="Run")
    notebook.add(model_tab, text="AI Settings")
    notebook.add(instructions_tab, text="Instructions")
    notebook.add(output_tab, text="Output Format")

    for tab in (run_tab, model_tab, instructions_tab, output_tab):
        tab.columnconfigure(1, weight=1)

    string_vars = {
        key: tk.StringVar(value=value)
        for key, value in initial.items()
        if isinstance(value, str)
    }
    bool_vars = {
        key: tk.BooleanVar(value=value)
        for key, value in initial.items()
        if isinstance(value, bool)
    }

    instructions_text = tk.Text(
        instructions_tab,
        wrap="word",
        font=("Menlo", 12),
        padx=10,
        pady=10,
    )
    instructions_text.insert("1.0", initial["instructions"])
    instructions_text.grid(row=0, column=0, sticky="nsew")
    instructions_text.edit_modified(False)
    instructions_tab.rowconfigure(0, weight=1)
    instructions_tab.columnconfigure(0, weight=1)

    output_text = tk.Text(
        output_tab,
        wrap="word",
        font=("Menlo", 12),
        padx=10,
        pady=10,
    )
    output_text.insert("1.0", build_output_format_preview(config))
    output_text.configure(state="disabled")
    output_text.grid(row=0, column=0, sticky="nsew")
    output_tab.rowconfigure(0, weight=1)
    output_tab.columnconfigure(0, weight=1)

    def add_labeled_entry(
        parent: Any, row: int, label: str, key: str, *, width: int = 40
    ) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky="w", pady=6, padx=(0, 12)
        )
        entry = ttk.Entry(parent, textvariable=string_vars[key], width=width)
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        return entry

    add_labeled_entry(run_tab, 0, "Input path", "input")
    browse_frame = ttk.Frame(run_tab)
    browse_frame.grid(row=0, column=2, sticky="e", padx=(8, 0))

    def choose_input_file() -> None:
        selected = filedialog.askopenfilename(
            title="Select XML file",
            filetypes=(("XML files", "*.xml"), ("All files", "*.*")),
        )
        if selected:
            string_vars["input"].set(selected)

    def choose_input_folder() -> None:
        selected = filedialog.askdirectory(title="Select XML folder")
        if selected:
            string_vars["input"].set(selected)

    ttk.Button(browse_frame, text="File…", command=choose_input_file).grid(
        row=0, column=0, padx=(0, 6)
    )
    ttk.Button(browse_frame, text="Folder…", command=choose_input_folder).grid(
        row=0, column=1
    )

    add_labeled_entry(run_tab, 1, "Output CSV", "output")

    def choose_output_file() -> None:
        selected = filedialog.asksaveasfilename(
            title="Select output CSV",
            defaultextension=".csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
        )
        if selected:
            string_vars["output"].set(selected)

    ttk.Button(run_tab, text="Browse…", command=choose_output_file).grid(
        row=1, column=2, sticky="e", padx=(8, 0)
    )
    add_labeled_entry(run_tab, 2, "API key override", "api_key")
    add_labeled_entry(run_tab, 3, "Max concurrency", "max_concurrency")
    add_labeled_entry(run_tab, 4, "Sample size", "sample")

    checkbox_frame = ttk.Frame(run_tab)
    checkbox_frame.grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))
    ttk.Checkbutton(checkbox_frame, text="Dry run", variable=bool_vars["dry_run"]).grid(
        row=0, column=0, padx=(0, 12)
    )
    ttk.Checkbutton(checkbox_frame, text="Resume", variable=bool_vars["resume"]).grid(
        row=0, column=1, padx=(0, 12)
    )
    ttk.Checkbutton(
        checkbox_frame, text="Verbose logging", variable=bool_vars["verbose"]
    ).grid(row=0, column=2)

    add_labeled_entry(model_tab, 0, "Model", "model")
    add_labeled_entry(model_tab, 1, "API key env var", "api_key_env")
    add_labeled_entry(model_tab, 2, "Base URL", "base_url")
    add_labeled_entry(model_tab, 3, "Temperature", "temperature")
    add_labeled_entry(model_tab, 4, "Top-p", "top_p")
    add_labeled_entry(model_tab, 5, "Max output tokens", "max_output_tokens")

    ttk.Label(model_tab, text="Reasoning effort").grid(
        row=6, column=0, sticky="w", pady=6, padx=(0, 12)
    )
    reasoning_combo = ttk.Combobox(
        model_tab,
        textvariable=string_vars["reasoning_effort"],
        values=_REASONING_EFFORT_CHOICES,
        state="readonly",
    )
    reasoning_combo.grid(row=6, column=1, sticky="ew", pady=6)

    ttk.Label(model_tab, text="Verbosity").grid(
        row=7, column=0, sticky="w", pady=6, padx=(0, 12)
    )
    verbosity_combo = ttk.Combobox(
        model_tab,
        textvariable=string_vars["verbosity"],
        values=_VERBOSITY_CHOICES,
        state="readonly",
    )
    verbosity_combo.grid(row=7, column=1, sticky="ew", pady=6)

    cost_frame = ttk.LabelFrame(container, text="Run Review", padding=12)
    cost_frame.grid(row=2, column=0, sticky="ew")
    cost_frame.columnconfigure(0, weight=1)
    cost_message = tk.StringVar(
        value="Review cost to prepare the exact run set, then click Run to confirm."
    )
    ttk.Label(cost_frame, textvariable=cost_message, justify="left").grid(
        row=0, column=0, sticky="w"
    )

    button_frame = ttk.Frame(container)
    button_frame.grid(row=3, column=0, sticky="e", pady=(12, 0))

    state: dict[str, Any] = {
        "pending_result": None,
        "result": None,
    }

    run_button = ttk.Button(button_frame, text="Run")
    run_button.grid(row=0, column=1, padx=(8, 0))

    def mark_dirty(*_args: object) -> None:
        refresh_review_summary()

    for variable in string_vars.values():
        variable.trace_add("write", mark_dirty)
    for variable in bool_vars.values():
        variable.trace_add("write", mark_dirty)
    instructions_text.bind(
        "<<Modified>>",
        lambda _event: (instructions_text.edit_modified(False), mark_dirty()),
    )

    def collect_values() -> dict[str, Any]:
        values = {key: variable.get() for key, variable in string_vars.items()}
        values.update({key: variable.get() for key, variable in bool_vars.items()})
        values["instructions"] = instructions_text.get("1.0", "end").strip()
        return values

    def refresh_output_preview(current_config: ExtractConfig) -> None:
        output_text.configure(state="normal")
        output_text.delete("1.0", "end")
        output_text.insert("1.0", build_output_format_preview(current_config))
        output_text.configure(state="disabled")

    def refresh_review_summary() -> bool:
        values = collect_values()
        try:
            resolved = apply_gui_values(config, values)
        except ValueError as exc:
            state["pending_result"] = None
            cost_message.set(f"Invalid settings: {exc}")
            return False

        refresh_output_preview(resolved.config)

        if resolved.input_path is None:
            state["pending_result"] = None
            cost_message.set(
                "Select an input file or folder to compute the run summary."
            )
            return False

        if not resolved.input_path.exists():
            state["pending_result"] = None
            cost_message.set(f"Input path does not exist: {resolved.input_path}")
            return False

        if resolved.max_concurrency < 1:
            state["pending_result"] = None
            cost_message.set("Max concurrency must be at least 1.")
            return False

        prepared = prepare_run(
            input_path=resolved.input_path,
            output_path=resolved.output_path,
            dry_run=resolved.dry_run,
            sample=resolved.sample,
            resume=resolved.resume,
        )

        if prepared.discovered_count == 0:
            state["pending_result"] = None
            cost_message.set("No XML files were found at the selected input path.")
            return False

        cost_message.set(build_review_summary(resolved, prepared))
        state["pending_result"] = replace(resolved, prepared_run=prepared)
        return True

    def on_run() -> None:
        if state["pending_result"] is None and not refresh_review_summary():
            return
        state["result"] = state["pending_result"]
        root.destroy()

    def on_cancel() -> None:
        state["result"] = None
        root.destroy()

    run_button.configure(command=on_run)
    ttk.Button(button_frame, text="Cancel", command=on_cancel).grid(
        row=0, column=2, padx=(8, 0)
    )
    root.protocol("WM_DELETE_WINDOW", on_cancel)
    refresh_review_summary()
    root.mainloop()
    return state["result"]
