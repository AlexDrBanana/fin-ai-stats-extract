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
                    "ai_infrastructure": {
                        "ai_infra_binary": 1,
                        "ai_infra_types": ["GPU clusters"],
                        "ai_infra_count": 1,
                        "ai_infra_dollar": None,
                    }
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

            self.assertEqual(result.ai_infrastructure.ai_infra_binary, 1)
            self.assertIs(client.responses.last_text_format, response_model)
