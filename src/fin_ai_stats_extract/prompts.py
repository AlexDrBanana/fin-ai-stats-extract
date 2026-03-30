from importlib.resources import files
from pathlib import Path

DEFAULT_PROMPT_FILENAME = "system_prompt.md"


def load_packaged_system_prompt() -> str:
    return (
        files("fin_ai_stats_extract.resources")
        .joinpath(DEFAULT_PROMPT_FILENAME)
        .read_text(encoding="utf-8")
    )


def ensure_system_prompt_file(working_directory: Path | None = None) -> Path:
    directory = working_directory or Path.cwd()
    prompt_path = directory / DEFAULT_PROMPT_FILENAME
    if not prompt_path.exists():
        prompt_path.write_text(load_packaged_system_prompt(), encoding="utf-8")
    return prompt_path


def load_system_prompt(
    prompt_path: Path | None = None,
    working_directory: Path | None = None,
) -> str:
    resolved_path = prompt_path or ensure_system_prompt_file(working_directory)
    return resolved_path.read_text(encoding="utf-8")
