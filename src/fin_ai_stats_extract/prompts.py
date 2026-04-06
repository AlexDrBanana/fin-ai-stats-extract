from pathlib import Path

from fin_ai_stats_extract.config import ExtractConfig, load_config


def build_output_contract_lines(config: ExtractConfig) -> list[str]:
    contract_lines = [
        "## Output Contract",
        "Return a single flat JSON object using the exact field names below.",
    ]

    for field in config.output.format:
        contract_lines.append(f"- {field.name}: {field.description}")

    return contract_lines


def render_system_prompt(config: ExtractConfig) -> str:
    prompt_sections = [
        config.llm.instructions.strip(),
        *build_output_contract_lines(config),
    ]

    prompt_sections.append("## Output Rules")
    prompt_sections.append("- Use the exact field names shown above.")
    prompt_sections.append("- Return every configured extraction field as a string.")
    prompt_sections.append(
        "- Use an empty string when a configured field has no applicable value."
    )

    return "\n\n".join(prompt_sections).strip()


def load_system_prompt(
    config_path: Path | None = None,
    working_directory: Path | None = None,
) -> str:
    if config_path is None:
        config = load_config(working_directory=working_directory or Path.cwd())
    else:
        config = load_config(config_path=config_path)
    return render_system_prompt(config)
