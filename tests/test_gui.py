import argparse
import tempfile
import unittest
from pathlib import Path

from fin_ai_stats_extract.config import load_config
from fin_ai_stats_extract.gui import (
    apply_gui_values,
    build_initial_gui_values,
    build_output_format_preview,
    build_review_summary,
    select_preferred_theme,
)
from fin_ai_stats_extract.pipeline import PreparedRun


def _write_config(workdir: Path) -> Path:
    config_path = workdir / "extract.toml"
    config_path.write_text(
        '''
[llm]
instructions = """
Use transcript evidence only.
"""
model = "gpt-4o-mini"
api_key_env = "OPENAI_API_KEY"

[output]
format = [
    { name = "ai_mentioned", description = "Whether at least one core AI keyword appears" },
    { name = "keyword_hit_count", description = "Total count of AI keyword matches" },
]
'''.strip(),
        encoding="utf-8",
    )
    return config_path


class GuiTests(unittest.TestCase):
    def test_select_preferred_theme_prefers_native_aqua(self) -> None:
        theme = select_preferred_theme(("aqua", "clam"), windowing_system="aqua")

        self.assertEqual(theme, "aqua")

    def test_select_preferred_theme_falls_back_to_clam(self) -> None:
        theme = select_preferred_theme(("alt", "clam"), windowing_system="x11")

        self.assertEqual(theme, "clam")

    def test_build_initial_gui_values_leaves_none_fields_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config = load_config(_write_config(workdir))
            args = argparse.Namespace(
                input=None,
                output=Path("output.csv"),
                api_key=None,
                max_concurrency=100,
                dry_run=False,
                resume=False,
                sample=None,
                verbose=False,
            )

            values = build_initial_gui_values(config, args)

            self.assertEqual(values["instructions"], "Use transcript evidence only.")
            self.assertEqual(values["model"], "gpt-4o-mini")
            self.assertEqual(values["temperature"], "")
            self.assertEqual(values["top_p"], "")
            self.assertEqual(values["max_output_tokens"], "")
            self.assertEqual(values["reasoning_effort"], "")
            self.assertEqual(values["verbosity"], "")
            self.assertEqual(values["input"], "")

    def test_build_output_format_preview_renders_flat_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config = load_config(_write_config(workdir))

            preview = build_output_format_preview(config)

            self.assertIn(
                "- ai_mentioned: Whether at least one core AI keyword appears", preview
            )
            self.assertIn("Whether at least one core AI keyword appears", preview)

    def test_build_review_summary_includes_estimated_cost_without_button_step(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            xml_path = workdir / "sample.xml"
            xml_path.write_text(
                """
<Transcript Id="123">
  <EventStory>
    <Headline>Edited Transcript of Example Co earnings call 01-Jan-25</Headline>
    <Body>Q1 2025\nWe invested in engineers.</Body>
  </EventStory>
</Transcript>
""".strip(),
                encoding="utf-8",
            )
            config = load_config(_write_config(workdir))
            resolved = apply_gui_values(
                config,
                {
                    "instructions": "Updated instructions",
                    "model": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "base_url": "",
                    "temperature": "",
                    "top_p": "",
                    "max_output_tokens": "",
                    "reasoning_effort": "",
                    "verbosity": "",
                    "input": str(xml_path),
                    "output": str(workdir / "custom.csv"),
                    "api_key": "",
                    "max_concurrency": "25",
                    "sample": "",
                    "dry_run": False,
                    "resume": False,
                    "verbose": False,
                },
            )
            prepared = PreparedRun(
                parsed=[],
                discovered_count=1,
                parse_errors=0,
                resume_skipped=0,
                applied_sample=None,
                overwrite_output=False,
            )
            prepared.parsed.append(
                (
                    xml_path,
                    None,
                    "We invested in engineers.",
                )
            )

            summary = build_review_summary(resolved, prepared)

            self.assertIn("Files discovered: 1", summary)
            self.assertIn("Files ready to process: 1", summary)
            self.assertIn("Estimated cost:", summary)

    def test_apply_gui_values_converts_empty_strings_to_none(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config = load_config(_write_config(workdir))

            resolved = apply_gui_values(
                config,
                {
                    "instructions": "Updated instructions",
                    "model": "gpt-5.4-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "base_url": "",
                    "temperature": "",
                    "top_p": "0.85",
                    "max_output_tokens": "2048",
                    "reasoning_effort": "medium",
                    "verbosity": "",
                    "input": str(workdir / "data.xml"),
                    "output": str(workdir / "custom.csv"),
                    "api_key": "",
                    "max_concurrency": "25",
                    "sample": "",
                    "dry_run": True,
                    "resume": False,
                    "verbose": True,
                },
            )

            self.assertEqual(resolved.config.llm.instructions, "Updated instructions")
            self.assertEqual(resolved.config.llm.model, "gpt-5.4-mini")
            self.assertIsNone(resolved.config.llm.temperature)
            self.assertEqual(resolved.config.llm.top_p, 0.85)
            self.assertEqual(resolved.config.llm.max_output_tokens, 2048)
            self.assertEqual(resolved.config.llm.reasoning_effort, "medium")
            self.assertIsNone(resolved.config.llm.verbosity)
            self.assertEqual(resolved.input_path, workdir / "data.xml")
            self.assertEqual(resolved.output_path, workdir / "custom.csv")
            self.assertIsNone(resolved.api_key)
            self.assertEqual(resolved.max_concurrency, 25)
            self.assertIsNone(resolved.sample)
            self.assertTrue(resolved.dry_run)
            self.assertTrue(resolved.verbose)
