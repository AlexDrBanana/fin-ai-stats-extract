from pathlib import Path

from fin_ai_stats_extract.config import ExtractConfig, load_config


def _field_type_label(field_type: str, nullable: bool) -> str:
    labels = {
        "integer": "integer",
        "number": "number",
        "string": "string",
        "string_array": "string[]",
    }
    label = labels[field_type]
    if nullable:
        return f"{label} | null"
    return label


def build_output_contract_lines(config: ExtractConfig) -> list[str]:
    contract_lines = [
        "## Output Contract",
        "Return a JSON object using the exact top-level group keys and field names below.",
    ]

    for group in config.output.groups:
        contract_lines.append(f"### {group.key}")
        contract_lines.append(f"{group.title}: {group.description}")
        for field in group.fields:
            contract_lines.append(
                f"- {field.name} ({_field_type_label(field.type, field.nullable)}): {field.description}"
            )

    return contract_lines


def render_system_prompt(config: ExtractConfig) -> str:
    prompt_sections = [
        config.llm.instructions.strip(),
        *build_output_contract_lines(config),
    ]

    prompt_sections.append("## Output Rules")
    prompt_sections.append("- Use the exact group keys and field names shown above.")
    prompt_sections.append(
        "- Use null for nullable fields when the transcript does not disclose a value."
    )
    prompt_sections.append("- Use unique items in list fields and keep labels concise.")

    if any(field.count_of for group in config.output.groups for field in group.fields):
        prompt_sections.append(
            "- Count fields must equal the number of items in the list they reference."
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
