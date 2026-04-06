import tempfile
import unittest
from pathlib import Path

from fin_ai_stats_extract.config import load_config
from fin_ai_stats_extract.parser import TranscriptMetadata
from fin_ai_stats_extract.schema import build_extraction_model


def _write_config(workdir: Path) -> Path:
    config_path = workdir / "extract.toml"
    config_path.write_text(
        '''
[llm]
instructions = """
Use transcript evidence only.
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


class WriterTests(unittest.TestCase):
    def test_build_csv_columns_uses_configured_group_order(self) -> None:
        from fin_ai_stats_extract.writer import build_csv_columns

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config = load_config(_write_config(workdir))

            columns = build_csv_columns(config.output)

            self.assertEqual(
                columns,
                [
                    "event_id",
                    "company_name",
                    "quarter",
                    "date",
                    "headline",
                    "source_file",
                    "ai_mentioned",
                    "keyword_hit_count",
                    "top_sentences",
                    "confidence_label",
                    "hedge_score",
                ],
            )

    def test_results_to_rows_flattens_dynamic_model_using_config(self) -> None:
        from fin_ai_stats_extract.writer import results_to_rows

        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config = load_config(_write_config(workdir))
            extraction_model = build_extraction_model(config)
            extraction = extraction_model.model_validate(
                {
                    "ai_mentioned": "yes",
                    "keyword_hit_count": "10",
                    "top_sentences": "We deploy GPUs. | AI is transformative.",
                    "confidence_label": "hopeful",
                    "hedge_score": "4",
                }
            )
            metadata = TranscriptMetadata(
                event_id="123",
                headline="Example headline",
                company_name="Example Co",
                quarter="Q1 2025",
                date="01-Jan-25",
                source_file="example.xml",
            )

            rows = results_to_rows([(metadata, extraction)], config.output)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["event_id"], "123")
            self.assertEqual(rows[0]["ai_mentioned"], "yes")
            self.assertEqual(rows[0]["keyword_hit_count"], "10")
            self.assertEqual(
                rows[0]["top_sentences"],
                "We deploy GPUs. | AI is transformative.",
            )
            self.assertEqual(rows[0]["confidence_label"], "hopeful")
            self.assertEqual(rows[0]["hedge_score"], "4")
