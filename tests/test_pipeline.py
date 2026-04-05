import asyncio
import tempfile
import unittest
from pathlib import Path

from fin_ai_stats_extract.config import load_config
from fin_ai_stats_extract.pipeline import run_pipeline
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


def _write_xml(workdir: Path) -> Path:
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
    return xml_path


class PipelineTests(unittest.TestCase):
    def test_run_pipeline_accepts_dynamic_schema_and_output_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config = load_config(_write_config(workdir))
            xml_path = _write_xml(workdir)
            output_path = workdir / "output.csv"
            response_model = build_extraction_model(config)

            asyncio.run(
                run_pipeline(
                    input_path=xml_path,
                    output_path=output_path,
                    system_prompt="",
                    model="gpt-4o-mini",
                    model_settings=None,
                    max_concurrency=1,
                    response_model=response_model,
                    output_config=config.output,
                    dry_run=True,
                )
            )

            self.assertFalse(output_path.exists())
