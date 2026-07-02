import argparse
import tempfile
import threading
import unittest
from pathlib import Path

from fin_ai_stats_extract.config import load_config
from fin_ai_stats_extract.gui import (
    build_config_state,
    build_initial_state,
    build_output_format_preview,
    build_review_summary,
    build_run_result,
    prepare_review,
    _run_close_watcher,
)
from fin_ai_stats_extract.pipeline import PreparedRun


def _write_config(workdir: Path) -> Path:
    config_path = workdir / "config.toml"
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


def _runtime(**overrides: object) -> dict[str, object]:
    runtime: dict[str, object] = {
        "input": "",
        "output": "output.csv",
        "api_key": "",
        "max_concurrency": "100",
        "sample": "",
        "dry_run": False,
        "resume": False,
        "verbose": False,
    }
    runtime.update(overrides)
    return runtime


class BuildStateTests(unittest.TestCase):
    def test_build_config_state_leaves_optional_fields_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(_write_config(Path(temp_dir)))

            state = build_config_state(config)

            self.assertEqual(state["instructions"], "Use transcript evidence only.")
            self.assertEqual(state["model"], "gpt-4o-mini")
            self.assertEqual(state["api_key_env"], "OPENAI_API_KEY")
            self.assertEqual(state["base_url"], "")
            self.assertEqual(state["temperature"], "")
            self.assertEqual(state["top_p"], "")
            self.assertEqual(state["max_output_tokens"], "")
            self.assertEqual(state["reasoning_effort"], "")
            self.assertEqual(state["verbosity"], "")
            self.assertEqual(
                state["output_format"],
                [
                    {
                        "name": "ai_mentioned",
                        "description": "Whether at least one core AI keyword appears",
                    },
                    {
                        "name": "keyword_hit_count",
                        "description": "Total count of AI keyword matches",
                    },
                ],
            )

    def test_build_initial_state_carries_runtime_and_meta(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config_path = _write_config(workdir)
            config = load_config(config_path)
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

            state = build_initial_state(config, args, config_path)

            self.assertEqual(state["runtime"]["input"], "")
            self.assertEqual(state["runtime"]["output"], "output.csv")
            self.assertEqual(state["runtime"]["max_concurrency"], "100")
            self.assertFalse(state["runtime"]["dry_run"])
            self.assertEqual(state["meta"]["config_path"], str(config_path))
            self.assertIn("", state["meta"]["reasoning_effort_choices"])
            self.assertIn("high", state["meta"]["reasoning_effort_choices"])
            self.assertIn("", state["meta"]["verbosity_choices"])


class BuildRunResultTests(unittest.TestCase):
    def test_parses_runtime_payload(self) -> None:
        result = build_run_result(
            _runtime(
                input="/data/input.xml",
                output="/data/out.csv",
                api_key="sk-test",
                max_concurrency="25",
                sample="0.5",
                dry_run=True,
                verbose=True,
            )
        )

        self.assertEqual(result.input_path, Path("/data/input.xml"))
        self.assertEqual(result.output_path, Path("/data/out.csv"))
        self.assertEqual(result.api_key, "sk-test")
        self.assertEqual(result.max_concurrency, 25)
        self.assertEqual(result.sample, 0.5)
        self.assertTrue(result.dry_run)
        self.assertTrue(result.verbose)

    def test_blank_input_is_none_and_output_defaults(self) -> None:
        result = build_run_result(_runtime(input="", output=""))

        self.assertIsNone(result.input_path)
        self.assertEqual(result.output_path, Path("output.csv"))
        self.assertIsNone(result.api_key)

    def test_invalid_concurrency_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_run_result(_runtime(max_concurrency="abc"))


class ReviewTests(unittest.TestCase):
    def test_build_output_format_preview_renders_flat_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(_write_config(Path(temp_dir)))

            preview = build_output_format_preview(config)

            self.assertIn(
                "- ai_mentioned: Whether at least one core AI keyword appears", preview
            )

    def test_build_review_summary_includes_estimated_cost(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            xml_path = workdir / "sample.xml"
            xml_path.write_text("<Transcript/>", encoding="utf-8")
            config = load_config(_write_config(workdir))
            prepared = PreparedRun(
                parsed=[(xml_path, None, "We invested in engineers.")],
                discovered_count=1,
                parse_errors=0,
                resume_skipped=0,
                applied_sample=None,
                overwrite_output=False,
            )

            summary = build_review_summary(config, dry_run=False, prepared=prepared)

            self.assertIn("Files discovered: 1", summary)
            self.assertIn("Files ready to process: 1", summary)
            self.assertIn("Estimated cost:", summary)

    def test_build_review_summary_skips_cost_on_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(_write_config(Path(temp_dir)))
            prepared = PreparedRun(
                parsed=[],
                discovered_count=2,
                parse_errors=0,
                resume_skipped=0,
                applied_sample=None,
                overwrite_output=False,
            )

            summary = build_review_summary(config, dry_run=True, prepared=prepared)

            self.assertIn("dry run", summary)

    def test_prepare_review_requires_existing_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(_write_config(Path(temp_dir)))

            ok, message, result = prepare_review(
                config, _runtime(input="/does/not/exist.xml")
            )

            self.assertFalse(ok)
            self.assertIsNone(result)
            self.assertIn("does not exist", message)

    def test_prepare_review_succeeds_for_folder_of_xml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config = load_config(_write_config(workdir))
            (workdir / "a.xml").write_text("<Transcript/>", encoding="utf-8")

            ok, _message, result = prepare_review(
                config,
                _runtime(input=str(workdir), output=str(workdir / "out.csv")),
            )

            self.assertTrue(ok)
            self.assertIsNotNone(result)
            self.assertIsNotNone(result.prepared_run)


class _FakeEvents:
    def __init__(self) -> None:
        self.closed = threading.Event()


class _FakeWindow:
    """Minimal stand-in for a pywebview window used by the close watcher."""

    def __init__(self) -> None:
        self.events = _FakeEvents()
        self.destroy_calls = 0

    def destroy(self) -> None:
        self.destroy_calls += 1
        # Real pywebview fires the ``closed`` event when the window is destroyed.
        self.events.closed.set()


class CloseWatcherTests(unittest.TestCase):
    def test_run_or_cancel_action_destroys_window(self) -> None:
        window = _FakeWindow()
        close_requested = threading.Event()
        close_requested.set()  # A Run/Cancel action asked the window to close.

        _run_close_watcher(window, close_requested, flush_delay=0)

        self.assertEqual(window.destroy_calls, 1)

    def test_native_close_does_not_call_destroy(self) -> None:
        window = _FakeWindow()
        window.events.closed.set()  # User already closed the window natively.
        close_requested = threading.Event()
        close_requested.set()

        _run_close_watcher(window, close_requested, flush_delay=0)

        self.assertEqual(window.destroy_calls, 0)


if __name__ == "__main__":
    unittest.main()
