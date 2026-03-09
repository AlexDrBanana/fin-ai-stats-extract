from openai import OpenAI


def resolve_api_key(base_url: str | None, api_key: str | None) -> str | None:
    """Return the API key to use for a given endpoint.

    Some local OpenAI-compatible endpoints require a non-empty placeholder key.
    """
    if base_url and not api_key:
        return "lm-studio"
    return api_key


def list_available_models(
    base_url: str | None = None,
    api_key: str | None = None,
) -> list[str]:
    """Fetch model IDs from the endpoint's /models API."""
    client = OpenAI(
        base_url=base_url,
        api_key=resolve_api_key(base_url, api_key),
    )
    models = client.models.list()
    return sorted({model.id for model in models.data})