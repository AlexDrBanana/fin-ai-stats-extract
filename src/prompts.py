from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_system_prompt() -> str:
    prompt_file = _PROMPTS_DIR / "system_prompt.md"
    return prompt_file.read_text(encoding="utf-8")
