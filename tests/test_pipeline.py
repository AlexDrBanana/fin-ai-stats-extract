import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

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

[output]
format = [
    { name = "ai_mentioned", description = "Whether at least one core AI keyword appears" },
    { name = "keyword_hit_count", description = "Total count of AI keyword matches" },
]
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

    def test_run_pipeline_overwrites_existing_output_without_name_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config = load_config(_write_config(workdir))
            xml_path = _write_xml(workdir)
            output_path = workdir / "output.csv"
            output_path.write_text("existing-output\n", encoding="utf-8")
            response_model = build_extraction_model(config)
            extraction = response_model.model_validate(
                {
                    "ai_mentioned": "yes",
                    "keyword_hit_count": "1",
                }
            )

            with (
                patch("fin_ai_stats_extract.pipeline.AsyncOpenAI"),
                patch(
                    "fin_ai_stats_extract.pipeline.initialize_output_csv"
                ) as mock_initialize,
                patch("fin_ai_stats_extract.pipeline.append_csv") as mock_append,
                patch(
                    "fin_ai_stats_extract.pipeline.extract_one",
                    new=AsyncMock(return_value=extraction),
                ),
            ):
                asyncio.run(
                    run_pipeline(
                        input_path=xml_path,
                        output_path=output_path,
                        system_prompt="Use transcript evidence only.",
                        model="gpt-4o-mini",
                        model_settings=None,
                        max_concurrency=1,
                        response_model=response_model,
                        output_config=config.output,
                        api_key="test-key",
                        dry_run=False,
                        skip_confirm=True,
                    )
                )

            mock_initialize.assert_called_once_with(
                output_path,
                output_config=config.output,
                overwrite=True,
            )
            mock_append.assert_called_once()
