# fin-ai-stats-extract

## Overview

`fin-ai-stats-extract` extracts structured AI and technology investment data from XML earnings-call transcripts and writes the results to CSV.

It supports:

- a single XML file or a folder tree of XML files via `--input`
- OpenAI-hosted models
- OpenAI-compatible local endpoints via `--base-url`
- explicit resume mode via `--resume` using an existing output CSV
- concurrent async extraction with a live progress bar
- dry-run parsing to validate XML input without making API calls
- a Streamlit UI for drag-and-drop uploads, model discovery, and in-memory CSV download

The output schema is based on `required_output.md`.

## Requirements

- Python 3.14+
- `uv`

## Install And Run

For one-off usage without creating a local environment:

```bash
uvx fin-ai-stats-extract --input ./data/Current --output ./output.csv
```

For local development in this repository:

```bash
uv sync
```

## Environment

Create an environment file for API-backed runs:

```bash
cp .env.example .env
```

Example values:

```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
CONCURRENCY_LIMIT=100
```

## Basic Usage

Run on a folder of transcripts:

```bash
uvx fin-ai-stats-extract --input ./data/Current --output ./output.csv
```

Run on a single transcript:

```bash
uvx fin-ai-stats-extract --input ./data/Current/11473715_T.xml --output ./output.csv
```

Validate XML parsing only, without calling a model:

```bash
uvx fin-ai-stats-extract --input ./data/Current --dry-run
```

Process only a sample of files:

```bash
uvx fin-ai-stats-extract --input ./data/Current --sample 25 --output ./sample.csv
```

Enable verbose logging:

```bash
uvx fin-ai-stats-extract --input ./data/Current --output ./output.csv --verbose
```

Tune common model sampling settings:

```bash
uvx fin-ai-stats-extract \
  --input ./data/Current/11473715_T.xml \
  --output ./output.csv \
  --temperature 0.2 \
  --top-p 0.9 \
  --max-output-tokens 2500 \
  --reasoning-effort medium \
  --verbosity low
```

Resume an interrupted run from an existing CSV:

```bash
uvx fin-ai-stats-extract --input ./data/Current --output ./output.csv --resume
```

## Prompt Selection

The CLI supports a custom prompt file:

```bash
uvx fin-ai-stats-extract \
  --input ./data/Current \
  --output ./output.csv \
  --prompt ./my_prompt.md
```

Prompt resolution works like this:

1. If `--prompt PATH` is provided, that file is used.
2. Otherwise the CLI looks for `./system_prompt.md` in the current working directory.
3. If `./system_prompt.md` does not exist, the packaged default prompt is copied there and then used.

The packaged default prompt shipped with the distribution lives at `src/fin_ai_stats_extract/resources/system_prompt.md` in this repository.

## Local OpenAI-Compatible Endpoints

You can point the tool at a local or self-hosted OpenAI-compatible server by passing `--base-url`.

Example with LM Studio:

```bash
uvx fin-ai-stats-extract \
  --input ./data/Current/11473715_T.xml \
  --output ./output.csv \
  --model google/gemma-3-4b \
  --base-url http://127.0.0.1:1234/v1
```

You can also pass an API key explicitly:

```bash
uvx fin-ai-stats-extract \
  --input ./data/Current \
  --output ./output.csv \
  --model gpt-4o-mini \
  --api-key "$OPENAI_API_KEY"
```

If `--base-url` is provided and no API key is set, the tool automatically uses `lm-studio` as a fallback key for local servers that require a non-empty value.

## Command-Line Arguments

- `--input`: Required. Path to one XML file or a folder tree containing XML files. Folder scans are recursive.
- `--output`: Output CSV path. Defaults to `output.csv`.
- `--prompt`: Optional path to a custom system prompt markdown file. Without it, the CLI uses `./system_prompt.md`, creating it from the packaged default if needed.
- `--model`: Model name. Defaults to `OPENAI_MODEL` or `gpt-4o-mini`.
- `--base-url`: Optional OpenAI-compatible API base URL. Defaults to `OPENAI_BASE_URL`.
- `--api-key`: Optional API key. Defaults to `OPENAI_API_KEY`.
- `--temperature`: Responses API sampling temperature from `0` to `2`.
- `--top-p`: Responses API nucleus sampling mass from `0` to `1`.
- `--max-output-tokens`: Maximum output tokens, including reasoning tokens.
- `--reasoning-effort`: Reasoning effort for supported `gpt-5` and `o`-series models: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`.
- `--verbosity`: Output verbosity for supported models: `low`, `medium`, or `high`.
- `--max-concurrency`: Maximum number of concurrent extraction jobs. Also accepts `--max-async-jobs` and `--concurrency`. Defaults to `CONCURRENCY_LIMIT` or `100`.
- `--resume`: Resume from an existing output CSV. Requires an explicit `--output path.csv`. Already processed `source_file` values are skipped.
- `--dry-run`: Parse XML only. No API calls are made.
- `--sample`: Randomly process only `N` files from the input set.
- `--yes`, `-y`: Skip the cost confirmation prompt when using OpenAI-hosted models.
- `--verbose`: Enable debug logging.

For the current OpenAI Responses API path used by this project, the commonly exposed researcher-facing controls are `temperature`, `top_p`, `max_output_tokens`, `reasoning_effort`, and `verbosity`. We recommend changing `temperature` or `top_p`, but not both at the same time.

## Streamlit UI

For repository development, launch the Streamlit app with:

```bash
uv run streamlit run src/fin_ai_stats_extract/streamlit_app.py
```

The UI lets you:

- drag and drop one or more XML files
- choose OpenAI or a custom OpenAI-compatible endpoint
- automatically load available models from the endpoint's `/models` API
- edit the default system prompt before running extraction
- adjust max concurrency
- view the generated CSV directly in a table
- download the generated CSV directly from memory without writing a CSV file to disk

## Output

The tool writes one CSV row per transcript with:

- transcript metadata: `event_id`, `company_name`, `quarter`, `date`, `headline`, `source_file`
- AI infrastructure fields
- AI analytics fields
- AI talent fields
- AI risk fields
- non-AI physical technology investment fields
- non-AI tech talent fields

List-valued fields are serialized using a semicolon-space separator.

When the input is a folder, `source_file` preserves the relative subfolder path, for example `subdir/12345_T.xml`.

## Notes On Local Models

OpenAI-compatible endpoints vary in how well they support strict structured outputs.

In particular:

- some local models may fail on long transcripts because of context-window limits
- some local models may return non-compliant JSON even when a schema is provided

If you use a local endpoint and see parsing or validation failures, try:

- a model with a larger context window
- smaller inputs using `--sample` or a single file first
- an OpenAI-hosted model for the most reliable structured-output behavior
