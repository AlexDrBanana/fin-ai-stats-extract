import asyncio
import logging
from typing import Any

import pandas as pd
import streamlit as st
from openai import AsyncOpenAI

from src.cost import estimate_total_cost
from src.extractor import extract_one
from src.openai_utils import list_available_models, resolve_api_key
from src.parser import TranscriptMetadata, parse_xml_bytes
from src.prompts import load_system_prompt
from src.schema import EarningsCallExtraction
from src.writer import results_to_rows

for logger_name in ("openai", "openai._base_client", "httpx", "httpcore"):
    logging.getLogger(logger_name).setLevel(logging.WARNING)

st.set_page_config(page_title="fin-ai-extract", page_icon="📄", layout="wide")

st.markdown(
    """
    <style>
    div[data-testid="stFileUploaderDropzone"] {
        min-height: 420px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    div[data-testid="stFileUploaderDropzoneInstructions"] {
        padding: 1.5rem 0;
    }

    /* Visible scrollbars in dataframes for mouse users */
    [data-testid="stDataFrame"] div {
        scrollbar-width: thin;
        scrollbar-color: rgba(128,128,128,.5) transparent;
    }
    [data-testid="stDataFrame"] div::-webkit-scrollbar {
        height: 8px;
        width: 8px;
    }
    [data-testid="stDataFrame"] div::-webkit-scrollbar-thumb {
        background: rgba(128,128,128,.5);
        border-radius: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def load_models_into_session(base_url: str | None, api_key: str | None) -> None:
    try:
        models = list_available_models(base_url=base_url, api_key=api_key)
    except Exception as exc:  # pragma: no cover - UI feedback path
        st.session_state["available_models"] = []
        st.session_state["models_error"] = str(exc)
        return

    st.session_state["available_models"] = models
    st.session_state["models_error"] = ""
    if models and st.session_state.get("selected_model") not in models:
        st.session_state["selected_model"] = models[0]


def maybe_refresh_models(base_url: str | None, api_key: str | None) -> None:
    endpoint_signature = (base_url or "__openai__", api_key or "")
    if st.session_state.get("last_endpoint_signature") == endpoint_signature:
        return

    st.session_state["last_endpoint_signature"] = endpoint_signature
    load_models_into_session(base_url, api_key)


def parse_uploaded_files(
    uploaded_files: list[Any],
) -> tuple[list[tuple[TranscriptMetadata, str]], list[str]]:
    """Parse uploaded XML files into metadata/body pairs."""
    parsed: list[tuple[TranscriptMetadata, str]] = []
    parse_errors: list[str] = []

    for uploaded_file in sorted(uploaded_files, key=lambda file: file.name):
        try:
            meta, body = parse_xml_bytes(uploaded_file.getvalue(), uploaded_file.name)
            parsed.append((meta, body))
        except Exception as exc:
            parse_errors.append(f"{uploaded_file.name}: {exc}")

    return parsed, parse_errors


async def process_uploaded_files(
    parsed_inputs: list[tuple[TranscriptMetadata, str]],
    model: str,
    base_url: str | None,
    api_key: str | None,
    system_prompt: str,
    max_concurrency: int,
    progress_bar: Any,
    status_box: Any,
) -> tuple[
    list[tuple[TranscriptMetadata, EarningsCallExtraction]],
    list[str],
    list[str],
]:
    parse_errors: list[str] = []

    if not parsed_inputs:
        return [], parse_errors, []

    semaphore = asyncio.Semaphore(max_concurrency)
    resolved_key = resolve_api_key(base_url, api_key)
    results: list[tuple[TranscriptMetadata, EarningsCallExtraction]] = []
    errors: list[str] = []
    total = len(parsed_inputs)

    status_box.info(f"Parsed {total} XML file(s). Starting extraction…")
    progress_bar.progress(0.0, text=f"0/{total} complete")

    async with AsyncOpenAI(base_url=base_url, api_key=resolved_key) as client:

        async def process_one(
            meta: TranscriptMetadata,
            body: str,
        ) -> tuple[TranscriptMetadata, EarningsCallExtraction | None]:
            async with semaphore:
                extraction = await extract_one(
                    client,
                    model,
                    body,
                    meta.event_id,
                    system_prompt=system_prompt,
                )
                return meta, extraction

        tasks = [
            asyncio.create_task(process_one(meta, body)) for meta, body in parsed_inputs
        ]

        completed = 0
        for task in asyncio.as_completed(tasks):
            meta, extraction = await task
            completed += 1
            progress_bar.progress(
                completed / total, text=f"{completed}/{total} complete"
            )
            if extraction is None:
                errors.append(meta.source_file)
            else:
                results.append((meta, extraction))

    status_box.success(
        f"Finished extraction: {len(results)} succeeded, {len(errors)} failed, "
        f"{len(parse_errors)} parse errors."
    )
    return results, parse_errors, errors


def render_sidebar() -> tuple[str | None, str | None, int, str]:
    st.sidebar.header("Connection")
    endpoint_choice = st.sidebar.radio(
        "Endpoint",
        options=["OpenAI", "Custom base URL"],
        index=0,
    )
    default_base_url = st.session_state.get("base_url", "")
    base_url = None
    if endpoint_choice == "Custom base URL":
        base_url_input = st.sidebar.text_input(
            "Base URL",
            value=default_base_url,
            placeholder="http://127.0.0.1:1234/v1",
        ).strip()
        base_url = base_url_input or None
    else:
        base_url = None

    api_key = (
        st.sidebar.text_input(
            "API key",
            type="password",
            value=st.session_state.get("api_key", ""),
            help="Leave blank for local endpoints that accept a placeholder key.",
        ).strip()
        or None
    )

    max_concurrency = st.sidebar.number_input(
        "Max concurrency",
        min_value=1,
        max_value=500,
        value=25,
        step=1,
    )

    maybe_refresh_models(base_url, api_key)

    st.sidebar.header("Model")

    available_models = st.session_state.get("available_models", [])
    models_error = st.session_state.get("models_error", "")
    if models_error:
        st.sidebar.error(models_error)

    model_options = available_models or ["No models available"]
    selected_index = 0
    selected_model = st.session_state.get("selected_model")
    if available_models and selected_model in available_models:
        selected_index = available_models.index(selected_model)

    model = st.sidebar.selectbox(
        "Available models",
        options=model_options,
        index=selected_index,
        key="selected_model_picker",
        disabled=not available_models,
    )

    if available_models:
        st.session_state["selected_model"] = model
    else:
        model = ""

    return base_url, api_key, int(max_concurrency), model


def main() -> None:
    st.title("📄 fin-ai-extract")
    st.caption(
        "Upload XML earnings-call transcripts, select an endpoint and model, "
        "edit the system prompt, and download the extracted CSV in memory."
    )

    base_url, api_key, max_concurrency, model = render_sidebar()

    left, right = st.columns([1.1, 1])
    with left:
        uploaded_files = st.file_uploader(
            "Drag and drop XML files",
            type=["xml"],
            accept_multiple_files=True,
            help="You can upload one or many XML transcripts.",
        )

    with right:
        prompt_text = st.text_area(
            "System prompt",
            value=load_system_prompt(),
            height=480,
            help="Adjust the extraction prompt before running the batch.",
        )

    # ── Inline cost estimate (OpenAI endpoint only) ──
    if uploaded_files and model and base_url is None:
        parsed_inputs, parse_errors = parse_uploaded_files(uploaded_files)
        if parsed_inputs:
            bodies = [body for _, body in parsed_inputs]
            total_input_tokens, estimated_cost, cost_label = estimate_total_cost(
                prompt_text,
                bodies,
                model,
            )
            parts = [
                f"**{len(parsed_inputs)}** file(s)",
                f"**{total_input_tokens:,}** input tokens",
            ]
            if cost_label:
                parts.append(f"{cost_label}")
            if estimated_cost is not None:
                parts.append(f"est. **${estimated_cost:.4f}** USD")
            st.caption(" · ".join(parts))

    run_button = st.button("Run extraction", type="primary", use_container_width=True)

    if not run_button:
        return

    # ── Validate inputs ──
    if not uploaded_files:
        st.error("Please upload at least one XML file.")
        return

    if not model:
        st.error("Please choose a model name.")
        return

    if base_url is None and not api_key:
        st.error("OpenAI-hosted runs require an API key.")
        return

    parsed_inputs, parse_errors = parse_uploaded_files(uploaded_files)
    if not parsed_inputs:
        st.warning("Some files could not be parsed:")
        st.code("\n".join(parse_errors))
        return

    # ── Run extraction ──
    progress_bar = st.progress(0.0, text="Waiting to start…")
    status_box = st.empty()

    results, extra_parse_errors, extraction_errors = asyncio.run(
        process_uploaded_files(
            parsed_inputs=parsed_inputs,
            model=model,
            base_url=base_url,
            api_key=api_key,
            system_prompt=prompt_text,
            max_concurrency=max_concurrency,
            progress_bar=progress_bar,
            status_box=status_box,
        )
    )

    all_parse_errors = [*parse_errors, *extra_parse_errors]

    if all_parse_errors:
        st.warning("Some files could not be parsed:")
        st.code("\n".join(all_parse_errors))

    if extraction_errors:
        st.warning("Some files failed during extraction:")
        st.code("\n".join(extraction_errors))

    if not results:
        st.info("No CSV output was generated.")
        return

    csv_rows = results_to_rows(results)
    df = pd.DataFrame(csv_rows)
    st.subheader("CSV content")
    display_h = max(min(38 + 35 * len(df) + 2, 800), 100)
    st.dataframe(df, use_container_width=True, hide_index=True, height=display_h)


if __name__ == "__main__":
    main()
