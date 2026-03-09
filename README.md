# fin-ai-extract

## Overview

This tool extracts structured AI and technology investment data from XML
earnings-call transcripts and writes the results to a CSV file.

It supports:

- a single XML file or a folder tree of XML files via `--input`
- OpenAI-hosted models
- OpenAI-compatible local endpoints via `--base-url`
- explicit resume mode via `--resume` using an existing output CSV
- concurrent async extraction with a live progress bar
- a Streamlit UI for drag-and-drop uploads, model discovery, and in-memory CSV download
- dry-run parsing to validate XML input without making API calls

The output schema is based on `required_output.md`.

## Requirements

- Python 3.14+
- `uv`

## Setup

1. Install dependencies:

```bash
uv sync
```

1. Create an environment file:

```bash
cp .env.example .env
```

1. Edit `.env` as needed:

```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
CONCURRENCY_LIMIT=100
```

## Basic usage

Run on a folder of transcripts:

```bash
uv run python main.py --input ./Current --output ./output.csv
```

The folder scan is recursive, so XML files inside nested subfolders are also included.

Run on a single transcript:

```bash
uv run python main.py --input ./Current/11473715_T.xml --output ./output.csv
```

Validate XML parsing only, without calling a model:

```bash
uv run python main.py --input ./Current --dry-run
```

Process only a sample of files:

```bash
uv run python main.py --input ./Current --sample 25 --output ./sample.csv
```

Enable verbose logging:

```bash
uv run python main.py --input ./Current --output ./output.csv --verbose
```

Resume an interrupted run from an existing CSV:

```bash
uv run python main.py --input ./Current --output ./output.csv --resume
```

## Streamlit UI

You can also use the built-in Streamlit app for an interactive workflow.

Launch it with:

```bash
uv run streamlit run streamlit_app.py
```

The UI lets you:

- drag and drop one or more XML files
- choose OpenAI or a custom OpenAI-compatible endpoint
- automatically load available models from the endpoint's `/models` API
- edit the system prompt before running extraction
- adjust max concurrency
- view the generated CSV directly in a table
- download the generated CSV directly from memory without writing a CSV file to disk

## Local OpenAI-compatible endpoints

You can point the tool at a local or self-hosted OpenAI-compatible server by
passing `--base-url`.

Example with LM Studio:

```bash
uv run python main.py \
  --input ./Current/11473715_T.xml \
  --output ./output.csv \
  --model google/gemma-3-4b \
  --base-url http://127.0.0.1:1234/v1
```

You can also pass an API key explicitly:

```bash
uv run python main.py \
  --input ./Current \
  --output ./output.csv \
  --model gpt-4o-mini \
  --api-key "$OPENAI_API_KEY"
```

If `--base-url` is provided and no API key is set, the tool automatically uses
`lm-studio` as a fallback key for local servers that require a non-empty value.

## Command-line arguments

| Argument | Description |
| --- | --- |
| `--input` | Required. Path to one XML file or a folder tree containing XML files. Folder scans are recursive. |
| `--output` | Output CSV path. Defaults to `output.csv`. |
| `--model` | Model name. Defaults to `OPENAI_MODEL` or `gpt-4o-mini`. |
| `--base-url` | Optional OpenAI-compatible API base URL. Defaults to `OPENAI_BASE_URL`. |
| `--api-key` | Optional API key. Defaults to `OPENAI_API_KEY`. |
| `--max-concurrency` | Maximum number of concurrent extraction jobs. Also accepts `--max-async-jobs` and `--concurrency`. Defaults to `CONCURRENCY_LIMIT` or `100`. |
| `--resume` | Resume from an existing output CSV. Requires an explicit `--output path.csv`. Already processed `source_file` values are skipped. |
| `--dry-run` | Parse XML only. No API calls are made. |
| `--sample` | Randomly process only `N` files from the input set. |
| `--yes`, `-y` | Skip the cost confirmation prompt when using OpenAI-hosted models. |
| `--verbose` | Enable debug logging. |

## Output

The tool writes one CSV row per transcript with:

- transcript metadata: `event_id`, `company_name`, `quarter`, `date`,
  `headline`, `source_file`
- AI infrastructure fields
- AI analytics fields
- AI talent fields
- AI risk fields
- non-AI physical technology investment fields
- non-AI tech talent fields

List-valued fields are serialized using a semicolon-space separator.

When the input is a folder, `source_file` preserves the relative subfolder path (for example, `subdir/12345_T.xml`).

## Resuming interrupted runs

Use `--resume` together with an explicit existing `--output` CSV to skip files
that have already been written to the CSV.

Example:

```bash
uv run python main.py --input ./Current --output ./output.csv --resume
```

Without `--resume`, the tool starts a fresh run and overwrites the output CSV.

During extraction, successful results are appended incrementally, so interrupted
runs can be resumed safely without losing already completed files.

## Prompts and extraction logic

The system prompt is stored in:

- `prompts/system_prompt.md`

You can edit that file to refine extraction behavior without changing Python
code.

## Notes on local models

OpenAI-compatible endpoints vary in how well they support strict structured
outputs.

In particular:

- some local models may fail on long transcripts because of context-window
  limits
- some local models may return non-compliant JSON even when a schema is
  provided

If you use a local endpoint and see parsing or validation failures, try:

- a model with a larger context window
- smaller inputs using `--sample` or a single file first
- an OpenAI-hosted model for the most reliable structured-output behavior
