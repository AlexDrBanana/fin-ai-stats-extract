# fin-ai-stats-extract

## Overview

`fin-ai-stats-extract` detects and classifies AI-related discussion in XML earnings-call transcripts and writes the results to CSV.

The tool implements a five-stage methodology via LLM extraction:

1. **AI Mention Detection** — keyword-based yes/no decision and hit count
2. **Representative Sentence Selection** — up to 3 most keyword-dense sentences
3. **Attitude Classification** — excited / concerned / neutral tone label
4. **Initiator Attribution** — who raised AI first (management, analyst, both, unclear)
5. **Confidence Classification** — hopeful / confident / transformational / authoritative

The tool is driven by a single TOML config file, `extract.toml`, which defines:

- the base extraction instructions sent to the model
- model and endpoint settings
- the ordered output field list

That same config drives three things at once:

- the final system instructions sent to the model
- the structured JSON schema used for Responses API parsing
- the CSV column order used for output

CLI flags remain available for fast tuning and one-off overrides. When a CLI flag conflicts with a TOML value, the CLI value wins and the tool logs a warning.

## Requirements

- Python 3.14+
- `uv`

## Install

For local development in this repository:

```bash
uv sync
```

For one-off usage without creating a local environment:

```bash
uvx fin-ai-stats-extract
```

## Configuration

The default config file is `./extract.toml`.

If you run the tool without `--config` and `extract.toml` does not exist in the current working directory, the packaged default config is copied there automatically.

The default config includes:

- commented-out optional settings such as `temperature`, `top_p`, and `reasoning_effort`
- the full methodology for AI mention detection, attitude classification, initiator attribution, and confidence classification

Edit `extract.toml` directly to change AI instructions, AI model settings, or output fields.

The output contract now uses a flat ordered list:

```toml
[output]
format = [
  { name = "ai_mentioned", description = "Whether at least one core AI keyword appears" },
  { name = "keyword_hit_count", description = "Total count of AI keyword matches" },
]
```

Descriptions are passed through directly into the rendered LLM instructions. The program does not parse or validate description text beyond requiring it to be non-empty.

## Environment

Create an environment file for API-backed runs:

```bash
cp .env.example .env
```

Example values:

```env
OPENAI_API_KEY=sk-your-key-here
```

By default, `extract.toml` reads the API key from `OPENAI_API_KEY` via `api_key_env = "OPENAI_API_KEY"`.

## Basic Usage

Run using the defaults in `extract.toml`:

```bash
uv run fin-ai-stats-extract --input ./data/Current
```

Run on a single transcript:

```bash
uv run fin-ai-stats-extract --input ./data/Current/11473715_T.xml
```

Write to a different CSV for one run:

```bash
uv run fin-ai-stats-extract --output ./sample.csv
```

Validate XML parsing only, without calling a model:

```bash
uv run fin-ai-stats-extract --dry-run
```

Process only a sample of files:

```bash
uv run fin-ai-stats-extract --sample 25
```

Enable verbose logging:

```bash
uv run fin-ai-stats-extract --verbose
```

Tune common model settings for one run:

```bash
uv run fin-ai-stats-extract \
  --temperature 0.2 \
  --top-p 0.9 \
  --max-output-tokens 2500 \
  --reasoning-effort medium \
  --verbosity low
```

Resume an interrupted run from an existing CSV:

```bash
uv run fin-ai-stats-extract --resume
```

Use a different config file:

```bash
uv run fin-ai-stats-extract --config ./custom_extract.toml
```

Open the Tkinter review window instead of supplying all settings on the command line:

```bash
uv run fin-ai-stats-extract --gui
```

The GUI lets you edit the prompt instructions, model settings, input/output paths, runtime options, see the TOML-driven output format in a dedicated tab, and review the exact run cost automatically before confirming or cancelling.

## Local OpenAI-Compatible Endpoints

You can point the tool at a local or self-hosted OpenAI-compatible server with either:

- `base_url` in `extract.toml`
- `--base-url` for a one-off override

Example with LM Studio:

```bash
uv run fin-ai-stats-extract \
  --base-url http://127.0.0.1:1234/v1 \
  --model google/gemma-3-4b
```

You can also pass an API key explicitly:

```bash
uv run fin-ai-stats-extract --api-key "$OPENAI_API_KEY"
```

If `base_url` is set and no API key is available, the tool uses `lm-studio` as a fallback key for local endpoints that require a non-empty value.

## Command-Line Arguments

- `--config`: Path to a TOML config file. Defaults to `./extract.toml`.
- `--gui`: Open a Tkinter settings window for editing values and confirming the run.
- `--input`: Required unless `--gui` is used. Path to one XML file or a folder tree containing XML files.
- `--output`: Output CSV path. Defaults to `output.csv`.
- `--model`: Override the configured model.
- `--base-url`: Override the configured OpenAI-compatible API base URL.
- `--api-key`: Override the API key from the configured environment variable.
- `--temperature`: Override the configured Responses API temperature from `0` to `2`.
- `--top-p`: Override the configured nucleus sampling mass from `0` to `1`.
- `--max-output-tokens`: Override the configured maximum output tokens.
- `--reasoning-effort`: Override the configured reasoning effort: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`.
- `--verbosity`: Override the configured output verbosity: `low`, `medium`, or `high`.
- `--max-concurrency`, `--max-async-jobs`, `--concurrency`: Maximum number of concurrent extraction jobs. Defaults to `CONCURRENCY_LIMIT` or `100`.
- `--dry-run`: Parse XML only. No API calls are made.
- `--resume`: Resume from an existing output CSV.
- `--sample`: Randomly process only `N` files from the input set.
- `--verbose`: Enable debug logging.
- `--yes`, `-y`: Skip cost confirmation.

The most common researcher-facing controls remain `temperature`, `top_p`, `max_output_tokens`, `reasoning_effort`, and `verbosity`. In most cases, change `temperature` or `top_p`, but not both at the same time.

## Output Schema

The `[output]` section of `extract.toml` is the extraction contract.

Each item in `format` defines:

- the exact field name
- the output order used in both the JSON contract and CSV columns
- a freeform description that is copied directly into the model instructions

The tool uses that same schema to:

- build the structured output model at runtime
- append an Output Contract section to the final instructions sent to the LLM
- generate CSV headers in the same order

## Output

The tool writes one CSV row per transcript.

The CSV always begins with transcript metadata:

- `event_id`
- `company_name`
- `quarter`
- `date`
- `headline`
- `source_file`

Configured extraction fields follow in the order defined in `extract.toml`.

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
