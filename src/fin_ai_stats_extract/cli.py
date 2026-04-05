import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from fin_ai_stats_extract.config import ExtractConfig, load_config
from fin_ai_stats_extract.extractor import ExtractionModelSettings
from fin_ai_stats_extract.gui import launch_gui
from fin_ai_stats_extract.pipeline import run_pipeline
from fin_ai_stats_extract.prompts import render_system_prompt
from fin_ai_stats_extract.schema import build_extraction_model

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
        "--config",
        type=Path,
        default=None,
        help=(
            "Path to the TOML config file. Defaults to ./extract.toml in the "
            "current working directory."
        ),
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Open a Tkinter window to review settings and confirm the run.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
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
        default=None,
        help="OpenAI model name.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="OpenAI-compatible API base URL.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI-compatible API key.",
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
        dest="skip_confirm",
        help="Skip cost-estimation confirmation (auto-accept).",
    )
    return parser


def _warn_override(
    warnings: list[str],
    flag_name: str,
    cli_value: object,
    config_value: object,
) -> None:
    warnings.append(f"CLI {flag_name} {cli_value} overrides config {config_value}")


def apply_cli_overrides(
    config: ExtractConfig,
    args: argparse.Namespace,
) -> tuple[ExtractConfig, list[str]]:
    resolved = config.model_copy(deep=True)
    warnings: list[str] = []

    if args.model is not None:
        if resolved.llm.model != args.model:
            _warn_override(warnings, "--model", args.model, resolved.llm.model)
            resolved.llm.model = args.model

    if args.base_url is not None:
        if resolved.llm.base_url != args.base_url:
            _warn_override(warnings, "--base-url", args.base_url, resolved.llm.base_url)
            resolved.llm.base_url = args.base_url

    if args.temperature is not None:
        if resolved.llm.temperature != args.temperature:
            if resolved.llm.temperature is not None:
                _warn_override(
                    warnings,
                    "--temperature",
                    args.temperature,
                    resolved.llm.temperature,
                )
            resolved.llm.temperature = args.temperature

    if args.top_p is not None:
        if resolved.llm.top_p != args.top_p:
            if resolved.llm.top_p is not None:
                _warn_override(warnings, "--top-p", args.top_p, resolved.llm.top_p)
            resolved.llm.top_p = args.top_p

    if args.max_output_tokens is not None:
        if resolved.llm.max_output_tokens != args.max_output_tokens:
            if resolved.llm.max_output_tokens is not None:
                _warn_override(
                    warnings,
                    "--max-output-tokens",
                    args.max_output_tokens,
                    resolved.llm.max_output_tokens,
                )
            resolved.llm.max_output_tokens = args.max_output_tokens

    if args.reasoning_effort is not None:
        if resolved.llm.reasoning_effort != args.reasoning_effort:
            if resolved.llm.reasoning_effort is not None:
                _warn_override(
                    warnings,
                    "--reasoning-effort",
                    args.reasoning_effort,
                    resolved.llm.reasoning_effort,
                )
            resolved.llm.reasoning_effort = args.reasoning_effort

    if args.verbosity is not None:
        if resolved.llm.verbosity != args.verbosity:
            if resolved.llm.verbosity is not None:
                _warn_override(
                    warnings,
                    "--verbosity",
                    args.verbosity,
                    resolved.llm.verbosity,
                )
            resolved.llm.verbosity = args.verbosity

    return resolved, warnings


def main() -> None:
    load_dotenv()

    parser = build_parser()
    args = parser.parse_args()

    if not args.gui and args.input is None:
        parser.error("the following arguments are required: --input")

    try:
        if args.config is not None:
            config = load_config(config_path=args.config)
        else:
            config = load_config(working_directory=Path.cwd())
    except FileNotFoundError:
        logging.basicConfig(level=logging.ERROR, format="%(message)s")
        logging.error("Config file does not exist: %s", args.config)
        sys.exit(1)

    resolved_config, warnings = apply_cli_overrides(config, args)

    prepared_run = None
    if args.gui:
        gui_result = launch_gui(resolved_config, args)
        if gui_result is None:
            return
        resolved_config = gui_result.config
        args.input = gui_result.input_path
        args.output = gui_result.output_path
        args.api_key = gui_result.api_key
        args.max_concurrency = gui_result.max_concurrency
        args.sample = gui_result.sample
        args.dry_run = gui_result.dry_run
        args.resume = gui_result.resume
        args.verbose = gui_result.verbose
        args.skip_confirm = True
        prepared_run = gui_result.prepared_run

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    for warning in warnings:
        logging.warning(warning)

    # Keep the tqdm progress bar clean by silencing routine third-party INFO logs.
    if not args.verbose:
        for logger_name in ("openai", "openai._base_client", "httpx", "httpcore"):
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    input_path = args.input

    if not input_path.exists():
        logging.error("Input path does not exist: %s", input_path)
        sys.exit(1)

    if args.max_concurrency < 1:
        logging.error("--max-concurrency must be at least 1")
        sys.exit(1)

    api_key = args.api_key
    if not api_key:
        api_key = os.getenv(resolved_config.llm.api_key_env)

    if resolved_config.llm.base_url and not api_key:
        api_key = "lm-studio"

    model_settings = ExtractionModelSettings(
        temperature=resolved_config.llm.temperature,
        top_p=resolved_config.llm.top_p,
        max_output_tokens=resolved_config.llm.max_output_tokens,
        reasoning_effort=resolved_config.llm.reasoning_effort,
        verbosity=resolved_config.llm.verbosity,
    )

    system_prompt = ""
    if not args.dry_run:
        system_prompt = render_system_prompt(resolved_config)

    response_model = build_extraction_model(resolved_config)

    asyncio.run(
        run_pipeline(
            input_path=input_path,
            output_path=args.output,
            system_prompt=system_prompt,
            model=resolved_config.llm.model,
            model_settings=model_settings,
            max_concurrency=args.max_concurrency,
            response_model=response_model,
            output_config=resolved_config.output,
            base_url=resolved_config.llm.base_url,
            api_key=api_key,
            dry_run=args.dry_run,
            sample=args.sample,
            skip_confirm=args.skip_confirm,
            resume=args.resume,
            prepared_run=prepared_run,
        )
    )


if __name__ == "__main__":
    main()
