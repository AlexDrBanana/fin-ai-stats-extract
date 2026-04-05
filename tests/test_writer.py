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

[[output.groups]]
key = "ai_infrastructure"
title = "AI Infrastructure"
description = "Data centers, chips, hardware, cloud compute, etc."

[[output.groups.fields]]
name = "ai_infra_binary"
type = "integer"
description = "1 if the firm mentions AI infrastructure investment, 0 otherwise"

[[output.groups.fields]]
name = "ai_infra_types"
type = "string_array"
description = "List of unique AI infrastructure types mentioned"

[[output.groups.fields]]
name = "ai_infra_count"
type = "integer"
description = "Count of unique AI infrastructure types mentioned"

[[output.groups.fields]]
name = "ai_infra_dollar"
type = "number"
nullable = true
description = "Dollar value invested in AI infrastructure, or null if not disclosed"

[[output.groups]]
key = "tech_talent"
title = "Tech Human Capital"
description = "Software engineers and related roles."

[[output.groups.fields]]
name = "tech_talent_binary"
type = "integer"
description = "1 if the firm mentions non-AI tech talent investment, 0 otherwise"

[[output.groups.fields]]
name = "tech_talent_headcount"
type = "number"
nullable = true
description = "Number of non-AI tech workers mentioned, or null if not disclosed"
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
                    "ai_infra_binary",
                    "ai_infra_types",
                    "ai_infra_count",
                    "ai_infra_dollar",
                    "tech_talent_binary",
                    "tech_talent_headcount",
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
                    "ai_infrastructure": {
                        "ai_infra_binary": 1,
                        "ai_infra_types": ["GPU clusters", "custom chips"],
                        "ai_infra_count": 2,
                        "ai_infra_dollar": 2500000,
                    },
                    "tech_talent": {
                        "tech_talent_binary": 1,
                        "tech_talent_headcount": None,
                    },
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
            self.assertEqual(rows[0]["ai_infra_types"], "GPU clusters; custom chips")
            self.assertEqual(rows[0]["ai_infra_dollar"], "2500000")
            self.assertEqual(rows[0]["tech_talent_headcount"], "")
