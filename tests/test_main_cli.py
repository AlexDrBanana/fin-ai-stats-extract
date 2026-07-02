import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from fin_ai_stats_extract.cli import (
    apply_cli_overrides,
    build_parser,
    resolve_missing_config,
)
from fin_ai_stats_extract.config import load_config, load_packaged_config_text
from fin_ai_stats_extract.toml_io import write_config


def _write_config(workdir: Path) -> Path:
    config_path = workdir / "config.toml"
    config_path.write_text(
        '''
[llm]
instructions = """
Use transcript evidence only.
"""
model = "gpt-4o-mini"
temperature = 0.2

[output]
format = [
    { name = "tech_talent_binary", description = "1 if the firm mentions non-AI tech talent investment, 0 otherwise" },
]
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
                "custom_config.toml",
            ]
        )

        self.assertEqual(str(args.config), "custom_config.toml")

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

    def test_gui_edit_persists_but_cli_override_wins_at_runtime(self) -> None:
        """The core precedence requirement.

        A GUI edit is written to the TOML file, but a CLI flag applied afterwards
        wins for the run and is never persisted back to the file.
        """
        parser = build_parser()

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config_path = _write_config(workdir)

            # Simulate the GUI persisting temperature = 1.0 to the file.
            write_config(
                config_path,
                {
                    "instructions": "Use transcript evidence only.",
                    "model": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "base_url": "",
                    "temperature": "1.0",
                    "top_p": "",
                    "max_output_tokens": "",
                    "reasoning_effort": "",
                    "verbosity": "",
                    "output_format": [
                        {"name": "tech_talent_binary", "description": "d"},
                    ],
                },
            )

            # The file now holds the GUI value.
            self.assertEqual(load_config(config_path).llm.temperature, 1.0)

            # CLI passes --temperature 0.1 on top of the GUI-edited file.
            args = parser.parse_args(
                [
                    "--input",
                    "sample.xml",
                    "--config",
                    str(config_path),
                    "--temperature",
                    "0.1",
                ]
            )
            resolved, warnings = apply_cli_overrides(load_config(config_path), args)

            # Runtime uses the CLI value (0.1), overriding the GUI value (1.0)...
            self.assertEqual(resolved.llm.temperature, 0.1)
            self.assertEqual(
                warnings, ["CLI --temperature 0.1 overrides config 1.0"]
            )
            # ...but the file still holds the GUI value (0.1 was not persisted).
            self.assertEqual(load_config(config_path).llm.temperature, 1.0)


def _confirm_with(answer: bool):
    def _confirm(_question: str, **_kwargs: object) -> bool:
        return answer

    return _confirm


class ResolveMissingConfigTests(unittest.TestCase):
    def test_existing_config_is_offered_and_used_when_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            existing = workdir / "config.toml"
            existing.write_text('[llm]\nmodel = "gpt-4o-mini"\n', encoding="utf-8")

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                result = resolve_missing_config(workdir, confirm=_confirm_with(True))

            self.assertEqual(result, existing)
            self.assertIn("config.toml file was detected", buffer.getvalue())

    def test_existing_config_declined_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            (workdir / "config.toml").write_text("[llm]\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                result = resolve_missing_config(workdir, confirm=_confirm_with(False))

            self.assertIsNone(result)

    def test_missing_config_is_created_from_defaults_when_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                result = resolve_missing_config(workdir, confirm=_confirm_with(True))

            created = workdir / "config.toml"
            self.assertEqual(result, created)
            self.assertTrue(created.exists())
            self.assertEqual(
                created.read_text(encoding="utf-8"), load_packaged_config_text()
            )
            self.assertIn("no config.toml was found", buffer.getvalue())

    def test_missing_config_declined_returns_none_and_creates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)

            with contextlib.redirect_stdout(io.StringIO()):
                result = resolve_missing_config(workdir, confirm=_confirm_with(False))

            self.assertIsNone(result)
            self.assertFalse((workdir / "config.toml").exists())


if __name__ == "__main__":
    unittest.main()
