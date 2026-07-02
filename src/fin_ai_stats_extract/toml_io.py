"""Comment-preserving TOML persistence used by the GUI config editor.

The GUI edits the ``[llm]`` and ``[output]`` sections of the config file live.
We use :mod:`tomlkit` (rather than serializing the pydantic model with a plain
TOML writer) so that user comments, key ordering, and general formatting in the
config file survive every edit.
"""

from pathlib import Path
from typing import Any

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.items import Table

from fin_ai_stats_extract.config import ExtractConfig, LLMConfig, OutputConfig

# LLM keys that are optional in TOML: when the GUI clears them we delete the key
# entirely instead of writing an empty value.
_LLM_OPTIONAL_KEYS = (
    "base_url",
    "temperature",
    "top_p",
    "max_output_tokens",
    "reasoning_effort",
    "verbosity",
)


def _parse_optional_float(raw: Any, field_name: str) -> float | None:
    value = str(raw).strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a number") from exc


def _parse_optional_int(raw: Any, field_name: str) -> int | None:
    value = str(raw).strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


def normalize_config_values(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse the GUI's string/records payload into a config-shaped dict.

    Raises ``ValueError`` when a numeric field cannot be parsed.
    """
    output_format: list[dict[str, str]] = []
    for entry in raw.get("output_format", []) or []:
        output_format.append(
            {
                "name": str(entry.get("name", "")).strip(),
                "description": str(entry.get("description", "")).strip(),
            }
        )

    return {
        "llm": {
            "instructions": str(raw.get("instructions", "")).strip(),
            "model": str(raw.get("model", "")).strip(),
            "api_key_env": str(raw.get("api_key_env", "")).strip(),
            "base_url": str(raw.get("base_url", "")).strip() or None,
            "temperature": _parse_optional_float(
                raw.get("temperature", ""), "temperature"
            ),
            "top_p": _parse_optional_float(raw.get("top_p", ""), "top_p"),
            "max_output_tokens": _parse_optional_int(
                raw.get("max_output_tokens", ""), "max_output_tokens"
            ),
            "reasoning_effort": str(raw.get("reasoning_effort", "")).strip() or None,
            "verbosity": str(raw.get("verbosity", "")).strip() or None,
        },
        "output": {"format": output_format},
    }


def build_config_from_values(raw: dict[str, Any]) -> ExtractConfig:
    """Validate GUI values and return an :class:`ExtractConfig`.

    Raises ``ValueError`` (from parsing) or ``pydantic.ValidationError`` (from
    the model) when the values are not a valid config.
    """
    return ExtractConfig.model_validate(normalize_config_values(raw))


def _ensure_table(doc: TOMLDocument, name: str) -> Table:
    existing = doc.get(name)
    if isinstance(existing, Table):
        return existing
    new_table = tomlkit.table()
    doc[name] = new_table
    return new_table


def _set_scalar(table: Table, key: str, value: Any) -> None:
    if value is None:
        if key in table:
            del table[key]
        return
    if isinstance(value, str) and "\n" in value:
        table[key] = tomlkit.string(value, multiline=True)
    else:
        table[key] = value


def _apply_llm(doc: TOMLDocument, llm: LLMConfig) -> None:
    table = _ensure_table(doc, "llm")
    _set_scalar(table, "instructions", llm.instructions)
    _set_scalar(table, "model", llm.model)
    _set_scalar(table, "api_key_env", llm.api_key_env)
    for key in _LLM_OPTIONAL_KEYS:
        _set_scalar(table, key, getattr(llm, key))


def _apply_output(doc: TOMLDocument, output: OutputConfig) -> None:
    table = _ensure_table(doc, "output")
    array = tomlkit.array().multiline(True)
    for field in output.format:
        entry = tomlkit.inline_table()
        entry["name"] = field.name
        entry["description"] = field.description
        array.append(entry)
    table["format"] = array


def render_config_document(config: ExtractConfig, existing_text: str = "") -> str:
    """Return TOML text for ``config`` merged into ``existing_text``.

    Existing comments and formatting are preserved; only the managed ``[llm]``
    and ``[output]`` values are updated.
    """
    doc = tomlkit.parse(existing_text) if existing_text else tomlkit.document()
    _apply_llm(doc, config.llm)
    _apply_output(doc, config.output)
    return tomlkit.dumps(doc)


def write_config(config_path: Path, raw: dict[str, Any]) -> ExtractConfig:
    """Validate ``raw`` GUI values and persist them to ``config_path``.

    The config file's comments and formatting are preserved. Returns the
    validated :class:`ExtractConfig`. Raises on invalid input *before* writing,
    so a bad edit never corrupts the file.
    """
    config = build_config_from_values(raw)
    existing_text = (
        config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    )
    rendered = render_config_document(config, existing_text)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(rendered, encoding="utf-8")
    return config
