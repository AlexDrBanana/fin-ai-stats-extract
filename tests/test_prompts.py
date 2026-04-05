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

[[output.groups]]
key = "ai_talent"
title = "AI Human Capital"
description = "Hiring AI and ML staff."

[[output.groups.fields]]
name = "ai_talent_binary"
type = "integer"
description = "1 if the firm mentions AI talent investment, 0 otherwise"

[[output.groups.fields]]
name = "ai_talent_types"
type = "string_array"
description = "List of unique AI talent roles or areas mentioned"

[[output.groups.fields]]
name = "ai_talent_count"
type = "integer"
description = "Count of unique AI talent types mentioned"
count_of = "ai_talent_types"
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
            self.assertIn("ai_talent_binary", prompt_text)
            self.assertNotIn("system_prompt.md", prompt_text)

    def test_workdir_extract_toml_is_used_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            _write_config(workdir)

            prompt_text = load_system_prompt(working_directory=workdir)

            self.assertIn("## Output Contract", prompt_text)
            self.assertIn("ai_talent", prompt_text)
            self.assertIn("Count fields must equal the number of items", prompt_text)

    def test_missing_workdir_extract_toml_is_copied_from_package_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)

            prompt_text = load_system_prompt(working_directory=workdir)

            self.assertTrue((workdir / "extract.toml").exists())
            self.assertIn("## Output Contract", prompt_text)
            self.assertIn("ai_infrastructure", prompt_text)
