import asyncio
import logging
import re

from openai import AsyncOpenAI

from src.prompts import load_system_prompt
from src.schema import EarningsCallExtraction

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)```\s*$", re.DOTALL)


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
) -> EarningsCallExtraction | None:
    """Extract structured AI investment data from a single transcript.

    Uses the OpenAI Responses API with structured output (text_format).
    Returns None if the model refuses or all retries fail.
    """
    prompt_text = system_prompt or load_system_prompt()

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await client.responses.parse(
                model=model,
                input=[
                    {"role": "system", "content": prompt_text},
                    {"role": "user", "content": transcript},
                ],
                text_format=EarningsCallExtraction,
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
