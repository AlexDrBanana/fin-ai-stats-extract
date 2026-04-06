import tempfile
import unittest
from pathlib import Path

from fin_ai_stats_extract.prompts import load_system_prompt


def _write_config(workdir: Path) -> Path:
    config_path = workdir / "extract.toml"
    config_path.write_text(
        '''
[llm]
instructions = """
You are a domain extraction system.
"""
model = "gpt-4o-mini"

[output]
format = [
    { name = "ai_mentioned", description = "Whether at least one core AI keyword appears" },
    { name = "keyword_hit_count", description = "Total count of AI keyword matches" },
]
'''.strip(),
        encoding="utf-8",
    )
    return config_path


class PromptLoadingTests(unittest.TestCase):
    def test_explicit_config_path_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config_path = _write_config(workdir)

            prompt_text = load_system_prompt(
                config_path=config_path,
                working_directory=workdir,
            )

            self.assertIn("You are a domain extraction system.", prompt_text)
            self.assertIn("ai_mentioned", prompt_text)
            self.assertIn("Whether at least one core AI keyword appears", prompt_text)
            self.assertNotIn("system_prompt.md", prompt_text)

    def test_workdir_extract_toml_is_used_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            _write_config(workdir)

            prompt_text = load_system_prompt(working_directory=workdir)

            self.assertIn("## Output Contract", prompt_text)
            self.assertIn("ai_mentioned", prompt_text)

    def test_missing_workdir_extract_toml_is_copied_from_package_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)

            prompt_text = load_system_prompt(working_directory=workdir)

            self.assertTrue((workdir / "extract.toml").exists())
            self.assertIn("## Output Contract", prompt_text)
            self.assertIn("ai_mentioned", prompt_text)
