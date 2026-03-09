import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.pipeline import run_pipeline


def main() -> None:
    load_dotenv()
    raw_args = sys.argv[1:]

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

    asyncio.run(
        run_pipeline(
            input_path=input_path,
            output_path=args.output,
            model=args.model,
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
