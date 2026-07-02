import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from fin_ai_stats_extract.config import load_config
from fin_ai_stats_extract.toml_io import (
    build_config_from_values,
    render_config_document,
    write_config,
)


def _values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "instructions": "Use transcript evidence only.",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "",
        "temperature": "",
        "top_p": "",
        "max_output_tokens": "",
        "reasoning_effort": "",
        "verbosity": "",
        "output_format": [
            {"name": "ai_mentioned", "description": "Whether AI is mentioned"},
        ],
    }
    values.update(overrides)
    return values


_CONFIG_WITH_COMMENTS = '''
# Top-level config for the extractor.
[llm]
# The system instructions sent to the model.
instructions = """
Use transcript evidence only.
"""
model = "gpt-4o-mini"  # inline comment on model
api_key_env = "OPENAI_API_KEY"
# temperature = 0.2  # commented-out default

[output]
format = [
    { name = "ai_mentioned", description = "Whether AI is mentioned" },
]
'''.strip()


class TomlIoTests(unittest.TestCase):
    def test_build_config_from_values_parses_optionals(self) -> None:
        config = build_config_from_values(
            _values(temperature="0.5", top_p="0.9", max_output_tokens="2048")
        )

        self.assertEqual(config.llm.temperature, 0.5)
        self.assertEqual(config.llm.top_p, 0.9)
        self.assertEqual(config.llm.max_output_tokens, 2048)

    def test_build_config_from_values_rejects_bad_number(self) -> None:
        with self.assertRaises(ValueError):
            build_config_from_values(_values(temperature="hot"))

    def test_write_config_preserves_comments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(_CONFIG_WITH_COMMENTS, encoding="utf-8")

            write_config(config_path, _values(model="gpt-5.4-mini"))

            text = config_path.read_text(encoding="utf-8")
            self.assertIn("# Top-level config for the extractor.", text)
            self.assertIn("# The system instructions sent to the model.", text)
            self.assertIn("# commented-out default", text)
            self.assertIn('model = "gpt-5.4-mini"', text)

    def test_write_config_round_trips_through_load_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(_CONFIG_WITH_COMMENTS, encoding="utf-8")

            write_config(
                config_path,
                _values(
                    temperature="1.0",
                    reasoning_effort="high",
                    output_format=[
                        {"name": "col_a", "description": "first"},
                        {"name": "col_b", "description": "second"},
                    ],
                ),
            )

            reloaded = load_config(config_path)
            self.assertEqual(reloaded.llm.temperature, 1.0)
            self.assertEqual(reloaded.llm.reasoning_effort, "high")
            self.assertEqual(
                [field.name for field in reloaded.output.format],
                ["col_a", "col_b"],
            )

    def test_write_config_removes_cleared_optional_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                _CONFIG_WITH_COMMENTS.replace(
                    "# temperature = 0.2  # commented-out default",
                    "temperature = 0.2",
                ),
                encoding="utf-8",
            )

            # Clearing temperature in the GUI removes the key from the file.
            write_config(config_path, _values(temperature=""))

            text = config_path.read_text(encoding="utf-8")
            self.assertNotIn("temperature =", text)
            self.assertIsNone(load_config(config_path).llm.temperature)

    def test_write_config_validates_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(_CONFIG_WITH_COMMENTS, encoding="utf-8")
            original = config_path.read_text(encoding="utf-8")

            with self.assertRaises((ValueError, ValidationError)):
                write_config(config_path, _values(model=""))

            # A rejected edit must not corrupt the on-disk file.
            self.assertEqual(config_path.read_text(encoding="utf-8"), original)

    def test_render_multiline_instructions_uses_block_string(self) -> None:
        config = build_config_from_values(
            _values(instructions="line one\nline two")
        )

        rendered = render_config_document(config)

        self.assertIn('"""', rendered)
        self.assertIn("line one", rendered)
        self.assertIn("line two", rendered)


if __name__ == "__main__":
    unittest.main()
