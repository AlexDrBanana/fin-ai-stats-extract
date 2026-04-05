import tempfile
import unittest
from pathlib import Path

from fin_ai_stats_extract.cli import apply_cli_overrides, build_parser
from fin_ai_stats_extract.config import load_config


def _write_config(workdir: Path) -> Path:
    config_path = workdir / "extract.toml"
    config_path.write_text(
        '''
[llm]
instructions = """
Use transcript evidence only.
"""
model = "gpt-4o-mini"
temperature = 0.2

[[output.groups]]
key = "tech_talent"
title = "Tech Human Capital"
description = "Software engineers and related roles."

[[output.groups.fields]]
name = "tech_talent_binary"
type = "integer"
description = "1 if the firm mentions non-AI tech talent investment, 0 otherwise"
'''.strip(),
        encoding="utf-8",
    )
    return config_path


class MainCliTests(unittest.TestCase):
    def test_accepts_config_path_flag(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "--input",
                "sample.xml",
                "--config",
                "custom_extract.toml",
            ]
        )

        self.assertEqual(str(args.config), "custom_extract.toml")

    def test_accepts_gui_without_input(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["--gui"])

        self.assertTrue(args.gui)
        self.assertIsNone(args.input)

    def test_accepts_common_responses_tuning_flags(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "--input",
                "sample.xml",
                "--temperature",
                "0.35",
                "--top-p",
                "0.9",
                "--max-output-tokens",
                "2048",
                "--reasoning-effort",
                "high",
                "--verbosity",
                "low",
            ]
        )

        self.assertEqual(args.temperature, 0.35)
        self.assertEqual(args.top_p, 0.9)
        self.assertEqual(args.max_output_tokens, 2048)
        self.assertEqual(args.reasoning_effort, "high")
        self.assertEqual(args.verbosity, "low")

    def test_cli_overrides_config_and_reports_conflicts(self) -> None:
        parser = build_parser()

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config_path = _write_config(workdir)
            config = load_config(config_path)
            args = parser.parse_args(
                [
                    "--input",
                    "sample.xml",
                    "--config",
                    str(config_path),
                    "--temperature",
                    "0.35",
                    "--model",
                    "gpt-5.4-mini",
                ]
            )

            resolved, warnings = apply_cli_overrides(config, args)

            self.assertEqual(resolved.llm.temperature, 0.35)
            self.assertEqual(resolved.llm.model, "gpt-5.4-mini")
            self.assertEqual(
                warnings,
                [
                    "CLI --model gpt-5.4-mini overrides config gpt-4o-mini",
                    "CLI --temperature 0.35 overrides config 0.2",
                ],
            )

    def test_rejects_out_of_range_temperature(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["--input", "sample.xml", "--temperature", "2.5"])
