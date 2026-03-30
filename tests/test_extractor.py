import unittest

from fin_ai_stats_extract.extractor import ExtractionModelSettings


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
