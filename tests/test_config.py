import tempfile
import unittest
from pathlib import Path


def _write_config(workdir: Path) -> Path:
    config_path = workdir / "extract.toml"
    config_path.write_text(
        '''
[llm]
instructions = """
You are a careful extraction system.
Only use evidence from the transcript.
"""
model = "gpt-4o-mini"

[[output.groups]]
key = "ai_infrastructure"
title = "AI Infrastructure"
description = "Data centers, chips, hardware, cloud compute, etc."

[[output.groups.fields]]
name = "ai_infra_binary"
type = "integer"
description = "1 if the firm mentions AI infrastructure investment, 0 otherwise"

[[output.groups.fields]]
name = "ai_infra_types"
type = "string_array"
description = "List of unique AI infrastructure types mentioned"

[[output.groups.fields]]
name = "ai_infra_count"
type = "integer"
description = "Count of unique AI infrastructure types mentioned"
count_of = "ai_infra_types"

[[output.groups.fields]]
name = "ai_infra_dollar"
type = "number"
nullable = true
description = "Dollar value invested in AI infrastructure, or null if not disclosed"

[[output.groups]]
key = "tech_talent"
title = "Tech Human Capital"
description = "Software engineers, IT staff, and non-AI technical roles."

[[output.groups.fields]]
name = "tech_talent_binary"
type = "integer"
description = "1 if the firm mentions non-AI tech talent investment, 0 otherwise"

[[output.groups.fields]]
name = "tech_talent_headcount"
type = "number"
nullable = true
description = "Number of non-AI tech workers mentioned, or null if not disclosed"
'''.strip(),
        encoding="utf-8",
    )
    return config_path


class ConfigTests(unittest.TestCase):
    def test_load_config_parses_llm_runtime_and_output_groups(self) -> None:
        from fin_ai_stats_extract.config import load_config

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config_path = _write_config(workdir)

            config = load_config(config_path)

            self.assertEqual(config.llm.model, "gpt-4o-mini")
            self.assertEqual(len(config.output.groups), 2)
            self.assertEqual(
                config.output.groups[0].fields[2].count_of, "ai_infra_types"
            )

    def test_render_system_prompt_appends_output_contract(self) -> None:
        from fin_ai_stats_extract.config import load_config
        from fin_ai_stats_extract.prompts import render_system_prompt

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config_path = _write_config(workdir)

            config = load_config(config_path)
            prompt = render_system_prompt(config)

            self.assertIn("You are a careful extraction system.", prompt)
            self.assertIn("## Output Contract", prompt)
            self.assertIn("ai_infrastructure", prompt)
            self.assertIn("ai_infra_binary", prompt)
            self.assertIn("string[]", prompt)
            self.assertIn("Count fields must equal the number of items", prompt)

    def test_build_extraction_model_uses_group_and_field_names(self) -> None:
        from fin_ai_stats_extract.config import load_config
        from fin_ai_stats_extract.schema import build_extraction_model

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config_path = _write_config(workdir)

            config = load_config(config_path)
            extraction_model = build_extraction_model(config)
            instance = extraction_model.model_validate(
                {
                    "ai_infrastructure": {
                        "ai_infra_binary": 1,
                        "ai_infra_types": ["GPU clusters"],
                        "ai_infra_count": 1,
                        "ai_infra_dollar": None,
                    },
                    "tech_talent": {
                        "tech_talent_binary": 0,
                        "tech_talent_headcount": None,
                    },
                }
            )

            self.assertEqual(instance.ai_infrastructure.ai_infra_binary, 1)
            self.assertEqual(
                instance.ai_infrastructure.ai_infra_types, ["GPU clusters"]
            )
            self.assertIsNone(instance.tech_talent.tech_talent_headcount)
