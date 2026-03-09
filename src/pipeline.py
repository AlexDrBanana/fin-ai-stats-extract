import asyncio
import logging
from pathlib import Path

from openai import AsyncOpenAI
from tqdm import tqdm

from src.cost import confirm_cost
from src.extractor import extract_one
from src.parser import TranscriptMetadata, parse_xml_with_source
from src.prompts import load_system_prompt
from src.schema import EarningsCallExtraction
from src.writer import (
    append_csv,
    initialize_output_csv,
    load_processed_ids,
    load_processed_source_files,
)

logger = logging.getLogger(__name__)


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


async def run_pipeline(
    input_path: Path,
    output_path: Path,
    model: str,
    max_concurrency: int,
    base_url: str | None = None,
    api_key: str | None = None,
    dry_run: bool = False,
    sample: int | None = None,
    skip_confirm: bool = False,
    resume: bool = False,
) -> None:
    xml_files = discover_xml_files(input_path)
    if not xml_files:
        logger.error("No XML files found at %s", input_path)
        return

    logger.info("Found %d XML file(s) to process", len(xml_files))

    # Parse all XMLs first
    parsed: list[tuple[Path, TranscriptMetadata, str]] = []
    parse_errors = 0
    for f in xml_files:
        try:
            meta, body = parse_xml_with_source(
                f,
                build_source_file_label(input_path, f),
            )
            parsed.append((f, meta, body))
        except Exception:
            parse_errors += 1
            logger.exception("Failed to parse %s", f.name)

    if parse_errors:
        logger.warning("%d file(s) failed to parse", parse_errors)

    overwrite_output = False

    if resume:
        if not output_path.exists():
            logger.error("--resume requires an existing output CSV: %s", output_path)
            raise SystemExit(1)

        processed_files = load_processed_source_files(output_path)
        if not processed_files:
            processed_ids = load_processed_ids(output_path)
            before = len(parsed)
            parsed = [
                (f, m, b) for f, m, b in parsed if m.event_id not in processed_ids
            ]
        else:
            before = len(parsed)
            parsed = [
                (f, m, b) for f, m, b in parsed if m.source_file not in processed_files
            ]

        logger.info(
            "Resume mode: skipping %d already-processed file(s), %d remaining",
            before - len(parsed),
            len(parsed),
        )
    elif output_path.exists() and not dry_run:
        overwrite_output = True

    if not parsed:
        logger.info("Nothing to process — all files already in output")
        return

    # Optional sampling
    if sample is not None and sample < len(parsed):
        import random

        parsed = random.sample(parsed, sample)
        logger.info("Sampling %d file(s) for processing", sample)

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
        system_prompt = load_system_prompt()
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
    initialize_output_csv(output_path, overwrite=overwrite_output)

    semaphore = asyncio.Semaphore(max_concurrency)
    write_lock = asyncio.Lock()
    results_written = 0
    errors: list[str] = []
    total = len(parsed)

    async def process_one(
        idx: int,
        meta: TranscriptMetadata,
        body: str,
    ) -> tuple[TranscriptMetadata, EarningsCallExtraction | None]:
        async with semaphore:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "[%d/%d] Processing %s (%s)",
                    idx + 1,
                    total,
                    meta.source_file,
                    meta.company_name,
                )

            extraction = await extract_one(client, model, body, meta.event_id)
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
                    append_csv([(meta, extraction)], output_path)
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
