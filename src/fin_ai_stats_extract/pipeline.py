import asyncio
import logging
import random
from dataclasses import dataclass
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel
from tqdm import tqdm

from fin_ai_stats_extract.config import OutputConfig
from fin_ai_stats_extract.cost import confirm_cost
from fin_ai_stats_extract.extractor import ExtractionModelSettings, extract_one
from fin_ai_stats_extract.parser import TranscriptMetadata, parse_xml_with_source
from fin_ai_stats_extract.writer import (
    append_csv,
    initialize_output_csv,
    load_processed_ids,
    load_processed_source_files,
)

logger = logging.getLogger(__name__)


@dataclass
class PreparedRun:
    parsed: list[tuple[Path, TranscriptMetadata, str]]
    discovered_count: int
    parse_errors: int
    resume_skipped: int
    applied_sample: int | None
    overwrite_output: bool


def discover_xml_files(input_path: Path) -> list[Path]:
    """Return a list of XML files to process. Accepts a file or directory."""
    if input_path.is_file():
        return [input_path]
    return sorted(path for path in input_path.rglob("*.xml") if path.is_file())


def build_source_file_label(input_path: Path, file_path: Path) -> str:
    """Return the CSV source_file value, preserving subfolder structure."""
    if input_path.is_file():
        return file_path.name
    return file_path.relative_to(input_path).as_posix()


def prepare_run(
    input_path: Path,
    output_path: Path,
    dry_run: bool = False,
    sample: int | None = None,
    resume: bool = False,
) -> PreparedRun:
    xml_files = discover_xml_files(input_path)
    if not xml_files:
        return PreparedRun(
            parsed=[],
            discovered_count=0,
            parse_errors=0,
            resume_skipped=0,
            applied_sample=None,
            overwrite_output=False,
        )

    parsed: list[tuple[Path, TranscriptMetadata, str]] = []
    parse_errors = 0
    for file_path in xml_files:
        try:
            meta, body = parse_xml_with_source(
                file_path,
                build_source_file_label(input_path, file_path),
            )
            parsed.append((file_path, meta, body))
        except Exception:
            parse_errors += 1
            logger.exception("Failed to parse %s", file_path.name)

    overwrite_output = False
    resume_skipped = 0

    if resume:
        if not output_path.exists():
            logger.error("--resume requires an existing output CSV: %s", output_path)
            raise SystemExit(1)

        processed_files = load_processed_source_files(output_path)
        if not processed_files:
            processed_ids = load_processed_ids(output_path)
            before = len(parsed)
            parsed = [
                (file_path, meta, body)
                for file_path, meta, body in parsed
                if meta.event_id not in processed_ids
            ]
        else:
            before = len(parsed)
            parsed = [
                (file_path, meta, body)
                for file_path, meta, body in parsed
                if meta.source_file not in processed_files
            ]
        resume_skipped = before - len(parsed)
    elif output_path.exists() and not dry_run:
        overwrite_output = True

    applied_sample: int | None = None
    if sample is not None and sample < len(parsed):
        parsed = random.sample(parsed, sample)
        applied_sample = sample

    return PreparedRun(
        parsed=parsed,
        discovered_count=len(xml_files),
        parse_errors=parse_errors,
        resume_skipped=resume_skipped,
        applied_sample=applied_sample,
        overwrite_output=overwrite_output,
    )


async def run_pipeline(
    input_path: Path,
    output_path: Path,
    system_prompt: str,
    model: str,
    model_settings: ExtractionModelSettings | None,
    max_concurrency: int,
    response_model: type[BaseModel],
    output_config: OutputConfig,
    base_url: str | None = None,
    api_key: str | None = None,
    dry_run: bool = False,
    sample: int | None = None,
    skip_confirm: bool = False,
    resume: bool = False,
    prepared_run: PreparedRun | None = None,
) -> None:
    planned_run = prepared_run or prepare_run(
        input_path=input_path,
        output_path=output_path,
        dry_run=dry_run,
        sample=sample,
        resume=resume,
    )

    if planned_run.discovered_count == 0:
        logger.error("No XML files found at %s", input_path)
        return

    logger.info("Found %d XML file(s) to process", planned_run.discovered_count)

    if planned_run.parse_errors:
        logger.warning("%d file(s) failed to parse", planned_run.parse_errors)

    parsed = planned_run.parsed

    if resume:
        logger.info(
            "Resume mode: skipping %d already-processed file(s), %d remaining",
            planned_run.resume_skipped,
            len(parsed),
        )

    if not parsed:
        logger.info("Nothing to process — all files already in output")
        return

    if planned_run.applied_sample is not None:
        logger.info("Sampling %d file(s) for processing", planned_run.applied_sample)

    if dry_run:
        logger.info("Dry run: parsed %d files successfully", len(parsed))
        for _, meta, body in parsed[:5]:
            logger.info(
                "  %s | %s | %s | %s | body=%d chars",
                meta.event_id,
                meta.company_name,
                meta.quarter,
                meta.date,
                len(body),
            )
        if len(parsed) > 5:
            logger.info("  ... and %d more", len(parsed) - 5)
        return

    # Cost estimation when using OpenAI's API (no custom base_url)
    if base_url is None and not skip_confirm:
        bodies = [b for _, _, b in parsed]
        if not confirm_cost(system_prompt, bodies, model):
            logger.info("Aborted by user.")
            return

    if not dry_run and not api_key:
        logger.error("OpenAI API key not set. Pass --api-key or set OPENAI_API_KEY.")
        raise SystemExit(1)

    if overwrite_output:
        logger.info(
            "Starting fresh run: overwriting existing output CSV %s", output_path
        )

    client = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
    )
    initialize_output_csv(
        output_path,
        output_config=output_config,
        overwrite=planned_run.overwrite_output,
    )

    semaphore = asyncio.Semaphore(max_concurrency)
    write_lock = asyncio.Lock()
    results_written = 0
    errors: list[str] = []
    total = len(parsed)

    async def process_one(
        idx: int,
        meta: TranscriptMetadata,
        body: str,
    ) -> tuple[TranscriptMetadata, BaseModel | None]:
        async with semaphore:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "[%d/%d] Processing %s (%s)",
                    idx + 1,
                    total,
                    meta.source_file,
                    meta.company_name,
                )

            extraction = await extract_one(
                client,
                model,
                body,
                meta.event_id,
                response_model=response_model,
                system_prompt=system_prompt,
                model_settings=model_settings,
            )
            return meta, extraction

    tasks = [
        asyncio.create_task(process_one(i, meta, body))
        for i, (_, meta, body) in enumerate(parsed)
    ]

    with tqdm(total=total, desc="Processing", unit="file") as progress_bar:
        for task in asyncio.as_completed(tasks):
            meta, extraction = await task

            if extraction is not None:
                async with write_lock:
                    append_csv([(meta, extraction)], output_path, output_config)
                    results_written += 1
            else:
                errors.append(meta.source_file)

            progress_bar.update(1)

    if results_written:
        logger.info("Wrote %d result(s) to %s", results_written, output_path)

    if errors:
        logger.warning(
            "%d file(s) failed extraction: %s", len(errors), ", ".join(errors[:10])
        )

    logger.info(
        "Done: %d succeeded, %d failed out of %d total",
        results_written,
        len(errors),
        total,
    )
