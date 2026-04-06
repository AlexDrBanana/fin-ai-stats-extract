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

[output]
format = [
    { name = "ai_mentioned", description = "Whether at least one core AI keyword appears" },
    { name = "keyword_hit_count", description = "Total count of AI keyword matches" },
    { name = "top_sentences", description = "Up to 3 most AI-keyword-dense sentences joined by pipe, or null" },
    { name = "confidence_label", description = "Confidence level label" },
    { name = "hedge_score", description = "Count of AI sentences with future or conditional language" },
]
'''.strip(),
        encoding="utf-8",
    )
    return config_path


class ConfigTests(unittest.TestCase):
    def test_load_config_parses_llm_runtime_and_flat_output_format(self) -> None:
        from fin_ai_stats_extract.config import load_config

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config_path = _write_config(workdir)

            config = load_config(config_path)

            self.assertEqual(config.llm.model, "gpt-4o-mini")
            self.assertEqual(len(config.output.format), 5)
            self.assertEqual(config.output.format[0].name, "ai_mentioned")
            self.assertEqual(
                config.output.format[0].description,
                "Whether at least one core AI keyword appears",
            )
            self.assertEqual(config.output.format[2].name, "top_sentences")
            self.assertEqual(
                config.output.format[2].description,
                "Up to 3 most AI-keyword-dense sentences joined by pipe, or null",
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
            self.assertIn("ai_mentioned", prompt)
            self.assertIn("confidence_label", prompt)
            self.assertIn("Whether at least one core AI keyword appears", prompt)
        self.assertNotIn("### ai_mention", prompt)

    def test_build_extraction_model_uses_top_level_field_names_without_type_inference(
        self,
    ) -> None:
        from fin_ai_stats_extract.config import load_config
        from fin_ai_stats_extract.schema import build_extraction_model

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config_path = _write_config(workdir)

            config = load_config(config_path)
            extraction_model = build_extraction_model(config)
            instance = extraction_model.model_validate(
                {
                    "ai_mentioned": "yes",
                    "keyword_hit_count": "12",
                    "top_sentences": "We invested in GPU clusters. | Our AI strategy is working.",
                    "confidence_label": "confident",
                    "hedge_score": "3",
                }
            )

            self.assertEqual(instance.ai_mentioned, "yes")
            self.assertEqual(instance.keyword_hit_count, "12")
            self.assertEqual(instance.confidence_label, "confident")

    def test_build_extraction_model_emits_string_json_schema_types(self) -> None:
        from fin_ai_stats_extract.config import load_config
        from fin_ai_stats_extract.schema import build_extraction_model

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config_path = _write_config(workdir)

            config = load_config(config_path)
            extraction_model = build_extraction_model(config)
            schema = extraction_model.model_json_schema()

            self.assertEqual(schema["properties"]["ai_mentioned"]["type"], "string")
            self.assertEqual(
                schema["properties"]["keyword_hit_count"]["type"], "string"
            )
