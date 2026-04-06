import asyncio
import tempfile
import unittest
from pathlib import Path

from fin_ai_stats_extract.config import load_config
from fin_ai_stats_extract.extractor import ExtractionModelSettings, extract_one
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
]
'''.strip(),
        encoding="utf-8",
    )
    return config_path


class _FakeResponse:
    def __init__(self, parsed):
        self.output_parsed = parsed
        self.output = []


class _FakeResponsesAPI:
    def __init__(self, parsed):
        self._parsed = parsed
        self.last_text_format = None

    async def parse(self, *, text_format, **kwargs):
        self.last_text_format = text_format
        return _FakeResponse(self._parsed)


class _FakeClient:
    def __init__(self, parsed):
        self.responses = _FakeResponsesAPI(parsed)


class ExtractionModelSettingsTests(unittest.TestCase):
    def test_builds_responses_api_kwargs(self) -> None:
        settings = ExtractionModelSettings(
            temperature=0.2,
            top_p=0.85,
            max_output_tokens=1536,
            reasoning_effort="medium",
            verbosity="high",
        )

        self.assertEqual(
            settings.to_responses_api_kwargs(),
            {
                "temperature": 0.2,
                "top_p": 0.85,
                "max_output_tokens": 1536,
                "reasoning": {"effort": "medium"},
                "text": {"verbosity": "high"},
            },
        )

    def test_extract_one_uses_runtime_generated_response_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config = load_config(_write_config(workdir))
            response_model = build_extraction_model(config)
            parsed = response_model.model_validate(
                {
                    "ai_mentioned": "yes",
                    "keyword_hit_count": "5",
                    "top_sentences": "We invested in GPUs.",
                }
            )
            client = _FakeClient(parsed)

            result = asyncio.run(
                extract_one(
                    client,
                    "gpt-4o-mini",
                    "example transcript",
                    "event-1",
                    response_model=response_model,
                    system_prompt="Use transcript evidence only.",
                )
            )

            self.assertEqual(result.ai_mentioned, "yes")
            self.assertIs(client.responses.last_text_format, response_model)
