import logging

logger = logging.getLogger(__name__)

# OpenAI text input pricing: USD per 1 million input tokens.
# Source: https://developers.openai.com/api/docs/pricing (retrieved 2026-03-09)
MODEL_INPUT_PRICING: dict[str, float] = {
    "gpt-5.4": 2.50,
    "gpt-5.4-pro": 30.00,
    "gpt-5.2": 1.75,
    "gpt-5.2-pro": 21.00,
    "gpt-5.1": 1.25,
    "gpt-5": 1.25,
    "gpt-5-pro": 15.00,
    "gpt-5-mini": 0.25,
    "gpt-5-nano": 0.05,
    "gpt-5.3-chat-latest": 1.75,
    "gpt-5.2-chat-latest": 1.75,
    "gpt-5.1-chat-latest": 1.25,
    "gpt-5-chat-latest": 1.25,
    "gpt-5.3-codex": 1.75,
    "gpt-5.2-codex": 1.75,
    "gpt-5.1-codex-max": 1.25,
    "gpt-5.1-codex": 1.25,
    "gpt-5-codex": 1.25,
    "gpt-5.1-codex-mini": 0.25,
    "gpt-5-search-api": 1.25,
    "gpt-4.1": 2.00,
    "gpt-4.1-mini": 0.40,
    "gpt-4.1-nano": 0.10,
    "gpt-4o": 2.50,
    "gpt-4o-2024-05-13": 5.00,
    "gpt-4o-2024-08-06": 2.50,
    "gpt-4o-2024-11-20": 2.50,
    "gpt-4o-mini": 0.15,
    "gpt-4o-mini-search-preview": 0.15,
    "gpt-4o-search-preview": 2.50,
    "o1": 15.00,
    "o1-pro": 150.00,
    "o1-mini": 1.10,
    "o3": 2.00,
    "o3-pro": 20.00,
    "o3-deep-research": 10.00,
    "o3-mini": 1.10,
    "o4-mini": 1.10,
    "o4-mini-deep-research": 2.00,
    "codex-mini-latest": 1.50,
    "gpt-4-turbo": 10.00,
    "gpt-4": 30.00,
}

# GPT-5.4 and GPT-5.4-pro have higher pricing when a single request exceeds
# 272K input tokens. That threshold applies per request/session, not globally.
LONG_CONTEXT_THRESHOLD = 272_000
LONG_CONTEXT_MODEL_INPUT_PRICING: dict[str, float] = {
    "gpt-5.4": 5.00,
    "gpt-5.4-pro": 60.00,
}


def count_tokens(text: str, model: str) -> int:
    """Count tokens in *text* using tiktoken, falling back to len/4."""
    try:
        import tiktoken

        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return len(text) // 4


def get_model_input_price(model: str, input_tokens: int | None = None) -> float | None:
    """Return the applicable input price in USD per 1M tokens for a model."""
    if (
        input_tokens is not None
        and input_tokens > LONG_CONTEXT_THRESHOLD
        and model in LONG_CONTEXT_MODEL_INPUT_PRICING
    ):
        return LONG_CONTEXT_MODEL_INPUT_PRICING[model]
    return MODEL_INPUT_PRICING.get(model)


def get_model_price_label(
    model: str, request_tokens: list[int] | None = None
) -> str | None:
    """Return a human-friendly pricing label for display in the confirmation prompt."""
    if request_tokens is None:
        price = get_model_input_price(model)
        return None if price is None else f"{price:.2f} USD/MT"

    prices = {get_model_input_price(model, tokens) for tokens in request_tokens}
    if None in prices:
        return None

    if len(prices) == 1:
        price = next(iter(prices))
        if model in LONG_CONTEXT_MODEL_INPUT_PRICING:
            if request_tokens and max(request_tokens) > LONG_CONTEXT_THRESHOLD:
                return f"{price:.2f} USD/MT (>272K input per request)"
            return f"{price:.2f} USD/MT (<272K input per request)"
        return f"{price:.2f} USD/MT"

    standard_price = MODEL_INPUT_PRICING[model]
    long_price = LONG_CONTEXT_MODEL_INPUT_PRICING[model]
    return (
        f"mixed: {standard_price:.2f}/{long_price:.2f} USD/MT "
        "(depends on per-request input >272K)"
    )


def estimate_total_input_tokens(
    system_prompt: str,
    transcripts: list[str],
    model: str,
) -> int:
    """Return estimated total input tokens across all files.

    Each API call sends the system prompt + one transcript.
    """
    sys_tokens = count_tokens(system_prompt, model)
    total = 0
    for body in transcripts:
        total += sys_tokens + count_tokens(body, model)
    return total


def estimate_total_cost(
    system_prompt: str,
    transcripts: list[str],
    model: str,
) -> tuple[int, float | None, str | None]:
    """Estimate total input tokens and total input cost across all requests."""
    sys_tokens = count_tokens(system_prompt, model)
    request_tokens = [sys_tokens + count_tokens(body, model) for body in transcripts]
    total_input_tokens = sum(request_tokens)

    total_cost = 0.0
    for tokens in request_tokens:
        price = get_model_input_price(model, tokens)
        if price is None:
            return total_input_tokens, None, None
        total_cost += (tokens / 1_000_000) * price

    return total_input_tokens, total_cost, get_model_price_label(model, request_tokens)


def confirm_cost(system_prompt: str, transcripts: list[str], model: str) -> bool:
    """Print cost estimate and ask the user to confirm.

    Returns True if the user types 'y'; False otherwise (default: n).
    """
    total_input_tokens, estimated_cost, cost_label = estimate_total_cost(
        system_prompt,
        transcripts,
        model,
    )

    if estimated_cost is None or cost_label is None:
        logger.warning(
            "No pricing info for model '%s' — cannot estimate cost. "
            "Add it to MODEL_INPUT_PRICING in src/cost.py if needed.",
            model,
        )
        print(f"\nTotal input tokens: {total_input_tokens:,}")
        print(f"Model '{model}' is not in the pricing table — cost unknown.")
        response = input("Continue? [n/y] (default: n): ").strip().lower()
        return response == "y"

    print(f"\nTotal input tokens: {total_input_tokens:,}")
    print(f"Model's cost:       {cost_label}")
    print(f"Estimated cost:     ${estimated_cost:.4f} USD")
    response = input("Continue? [n/y] (default: n): ").strip().lower()
    return response == "y"
