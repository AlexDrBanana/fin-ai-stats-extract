import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from fin_ai_stats_extract.extractor import ExtractionModelSettings
from fin_ai_stats_extract.pipeline import run_pipeline
from fin_ai_stats_extract.prompts import load_system_prompt

_REASONING_EFFORT_CHOICES = ("none", "minimal", "low", "medium", "high", "xhigh")
_VERBOSITY_CHOICES = ("low", "medium", "high")


def _float_in_range(name: str, minimum: float, maximum: float):
    def parse(value: str) -> float:
        number = float(value)
        if number < minimum or number > maximum:
            raise argparse.ArgumentTypeError(
                f"{name} must be between {minimum:g} and {maximum:g}"
            )
        return number

    return parse


def _positive_int(name: str):
    def parse(value: str) -> int:
        number = int(value)
        if number < 1:
            raise argparse.ArgumentTypeError(f"{name} must be at least 1")
        return number

    return parse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract AI/tech investment data from earnings-call transcripts.",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to a single XML file or a folder of XML files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output.csv"),
        help="Path for the output CSV (default: output.csv).",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        default=None,
        help=(
            "Path to a custom system prompt markdown file. If omitted, the CLI "
            "uses ./system_prompt.md and creates it from the packaged default if missing."
        ),
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        help="OpenAI model name (default: gpt-4o-mini or OPENAI_MODEL env).",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("OPENAI_BASE_URL"),
        help="OpenAI-compatible API base URL (default: OPENAI_BASE_URL env).",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY"),
        help="OpenAI-compatible API key (default: OPENAI_API_KEY env).",
    )
    parser.add_argument(
        "--temperature",
        type=_float_in_range("temperature", 0.0, 2.0),
        default=None,
        help="Sampling temperature for the Responses API (0 to 2).",
    )
    parser.add_argument(
        "--top-p",
        dest="top_p",
        type=_float_in_range("top_p", 0.0, 1.0),
        default=None,
        help="Nucleus sampling mass for the Responses API (0 to 1).",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=_positive_int("max_output_tokens"),
        default=None,
        help="Maximum number of output tokens, including reasoning tokens.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=_REASONING_EFFORT_CHOICES,
        default=None,
        help="Reasoning effort for supported gpt-5 and o-series models.",
    )
    parser.add_argument(
        "--verbosity",
        choices=_VERBOSITY_CHOICES,
        default=None,
        help="Text verbosity for supported models: low, medium, or high.",
    )
    parser.add_argument(
        "--max-concurrency",
        "--max-async-jobs",
        "--concurrency",
        dest="max_concurrency",
        type=int,
        default=int(os.getenv("CONCURRENCY_LIMIT", "100")),
        help="Maximum number of concurrent extraction jobs (default: 100).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse XMLs without calling the API.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from an existing output CSV by skipping already processed source files.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Process only N randomly sampled files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip cost-estimation confirmation (auto-accept).",
    )
    return parser


def main() -> None:
    load_dotenv()
    raw_args = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Keep the tqdm progress bar clean by silencing routine third-party INFO logs.
    if not args.verbose:
        for logger_name in ("openai", "openai._base_client", "httpx", "httpcore"):
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    input_path: Path = args.input
    if not input_path.exists():
        logging.error("Input path does not exist: %s", input_path)
        sys.exit(1)

    output_explicitly_set = any(
        arg == "--output" or arg.startswith("--output=") for arg in raw_args
    )

    if args.resume and not output_explicitly_set:
        logging.error("--resume requires an explicit --output XXX.csv argument")
        sys.exit(1)

    if args.max_concurrency < 1:
        logging.error("--max-concurrency must be at least 1")
        sys.exit(1)

    api_key = args.api_key
    if args.base_url and not api_key:
        api_key = "lm-studio"

    model_settings = ExtractionModelSettings(
        temperature=args.temperature,
        top_p=args.top_p,
        max_output_tokens=args.max_output_tokens,
        reasoning_effort=args.reasoning_effort,
        verbosity=args.verbosity,
    )

    system_prompt = ""
    if not args.dry_run:
        try:
            system_prompt = load_system_prompt(prompt_path=args.prompt)
        except FileNotFoundError as exc:
            logging.error("Prompt file does not exist: %s", exc.filename)
            sys.exit(1)

    asyncio.run(
        run_pipeline(
            input_path=input_path,
            output_path=args.output,
            system_prompt=system_prompt,
            model=args.model,
            model_settings=model_settings,
            max_concurrency=args.max_concurrency,
            base_url=args.base_url,
            api_key=api_key,
            dry_run=args.dry_run,
            sample=args.sample,
            skip_confirm=args.yes,
            resume=args.resume,
        )
    )


if __name__ == "__main__":
    main()
