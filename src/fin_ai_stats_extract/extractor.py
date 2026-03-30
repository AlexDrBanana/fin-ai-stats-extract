import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Literal

from openai import AsyncOpenAI

from fin_ai_stats_extract.prompts import load_system_prompt
from fin_ai_stats_extract.schema import EarningsCallExtraction

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0

ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]
VerbosityLevel = Literal["low", "medium", "high"]

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)```\s*$", re.DOTALL)


@dataclass(frozen=True, slots=True)
class ExtractionModelSettings:
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    reasoning_effort: ReasoningEffort | None = None
    verbosity: VerbosityLevel | None = None

    def to_responses_api_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {}

        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.top_p is not None:
            kwargs["top_p"] = self.top_p
        if self.max_output_tokens is not None:
            kwargs["max_output_tokens"] = self.max_output_tokens
        if self.reasoning_effort is not None:
            kwargs["reasoning"] = {"effort": self.reasoning_effort}
        if self.verbosity is not None:
            kwargs["text"] = {"verbosity": self.verbosity}

        return kwargs


def _clean_json(text: str) -> str:
    """Strip markdown code fences and leading/trailing whitespace."""
    text = text.strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()
    return text


async def extract_one(
    client: AsyncOpenAI,
    model: str,
    transcript: str,
    event_id: str,
    system_prompt: str | None = None,
    model_settings: ExtractionModelSettings | None = None,
) -> EarningsCallExtraction | None:
    """Extract structured AI investment data from a single transcript.

    Uses the OpenAI Responses API with structured output (text_format).
    Returns None if the model refuses or all retries fail.
    """
    prompt_text = system_prompt or load_system_prompt()
    request_kwargs = (
        model_settings.to_responses_api_kwargs() if model_settings is not None else {}
    )

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await client.responses.parse(
                model=model,
                input=[
                    {"role": "system", "content": prompt_text},
                    {"role": "user", "content": transcript},
                ],
                text_format=EarningsCallExtraction,
                **request_kwargs,
            )

            parsed = response.output_parsed
            if parsed is not None:
                return parsed

            # Check for refusal
            for item in response.output:
                if hasattr(item, "content"):
                    for part in item.content:
                        if hasattr(part, "refusal") and part.refusal:
                            logger.warning(
                                "Model refused for event %s: %s", event_id, part.refusal
                            )
                            return None

            # Fallback: try manual parsing from raw text content
            raw = ""
            for item in response.output:
                if hasattr(item, "content"):
                    for part in item.content:
                        if hasattr(part, "text"):
                            raw += part.text
            logger.debug("Raw response for event %s: %.500s", event_id, raw)
            if raw:
                raw = _clean_json(raw)
                return EarningsCallExtraction.model_validate_json(raw)

            return None

        except Exception:
            if attempt == _MAX_RETRIES:
                logger.exception(
                    "Failed after %d retries for event %s", _MAX_RETRIES, event_id
                )
                return None
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "Error for event %s (attempt %d), retrying in %.1fs",
                event_id,
                attempt,
                delay,
                exc_info=True,
            )
            await asyncio.sleep(delay)

    return None
