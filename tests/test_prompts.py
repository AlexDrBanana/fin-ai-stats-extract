import tempfile
import unittest
from pathlib import Path

from fin_ai_stats_extract.prompts import ensure_system_prompt_file, load_system_prompt


class PromptLoadingTests(unittest.TestCase):
    def test_explicit_prompt_path_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            custom_prompt = workdir / "custom_prompt.md"
            custom_prompt.write_text("custom instructions", encoding="utf-8")

            prompt_text = load_system_prompt(
                prompt_path=custom_prompt,
                working_directory=workdir,
            )

            self.assertEqual(prompt_text, "custom instructions")
            self.assertFalse((workdir / "system_prompt.md").exists())

    def test_missing_workdir_prompt_is_copied_from_package_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)

            prompt_path = ensure_system_prompt_file(workdir)
            prompt_text = load_system_prompt(working_directory=workdir)

            self.assertEqual(prompt_path, workdir / "system_prompt.md")
            self.assertTrue(prompt_path.exists())
            self.assertEqual(prompt_text, prompt_path.read_text(encoding="utf-8"))
            self.assertIn("financial analyst AI", prompt_text)
            self.assertIn("financial analyst AI", prompt_text)
