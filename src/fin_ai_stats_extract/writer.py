import csv
import io
from pathlib import Path

from pydantic import BaseModel

from fin_ai_stats_extract.config import OutputConfig
from fin_ai_stats_extract.parser import TranscriptMetadata

_METADATA_COLUMNS = [
    # Metadata
    "event_id",
    "company_name",
    "quarter",
    "date",
    "headline",
    "source_file",
]


def build_csv_columns(output_config: OutputConfig) -> list[str]:
    columns = list(_METADATA_COLUMNS)
    for group in output_config.groups:
        columns.extend(field.name for field in group.fields)
    return columns


def _flatten_row(
    meta: TranscriptMetadata,
    extraction: BaseModel,
    output_config: OutputConfig,
) -> dict[str, str]:
    """Flatten metadata + nested Pydantic model into a flat dict for CSV."""
    row: dict[str, str] = {
        "event_id": meta.event_id,
        "company_name": meta.company_name,
        "quarter": meta.quarter,
        "date": meta.date,
        "headline": meta.headline,
        "source_file": meta.source_file,
    }

    for group in output_config.groups:
        group_value = getattr(extraction, group.key)
        for field in group.fields:
            value = getattr(group_value, field.name)
            if isinstance(value, list):
                row[field.name] = "; ".join(str(item) for item in value)
            elif isinstance(value, (int, float)) or value is None:
                row[field.name] = _fmt_num(value)
            else:
                row[field.name] = str(value)

    return row


def _fmt_num(val: float | None) -> str:
    if val is None:
        return ""
    if val == int(val):
        return str(int(val))
    return str(val)


def write_csv(
    results: list[tuple[TranscriptMetadata, BaseModel]],
    output_path: Path,
    output_config: OutputConfig,
) -> None:
    """Write extraction results to a CSV file."""
    columns = build_csv_columns(output_config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for meta, extraction in results:
            writer.writerow(_flatten_row(meta, extraction, output_config))


def load_processed_ids(output_path: Path) -> set[str]:
    """Load already-processed event IDs from an existing CSV for resumption."""
    if not output_path.exists():
        return set()
    ids: set[str] = set()
    with open(output_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ids.add(row.get("event_id", ""))
    return ids


def load_processed_source_files(output_path: Path) -> set[str]:
    """Load already-processed source file names from an existing CSV for resumption."""
    if not output_path.exists():
        return set()
    source_files: set[str] = set()
    with open(output_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source_file = (row.get("source_file") or "").strip()
            if source_file:
                source_files.add(source_file)
    return source_files


def initialize_output_csv(
    output_path: Path,
    output_config: OutputConfig,
    overwrite: bool = False,
) -> None:
    """Create the CSV with a header, optionally overwriting any existing file."""
    columns = build_csv_columns(output_config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and output_path.exists():
        output_path.unlink()

    if output_path.exists():
        return

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()


def append_csv(
    results: list[tuple[TranscriptMetadata, BaseModel]],
    output_path: Path,
    output_config: OutputConfig,
) -> None:
    """Append extraction results to an existing CSV (for resumption)."""
    columns = build_csv_columns(output_config)
    file_exists = output_path.exists()
    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if not file_exists:
            writer.writeheader()
        for meta, extraction in results:
            writer.writerow(_flatten_row(meta, extraction, output_config))


def results_to_rows(
    results: list[tuple[TranscriptMetadata, BaseModel]],
    output_config: OutputConfig,
) -> list[dict[str, str]]:
    """Convert extraction results into flat CSV rows without writing to disk."""
    return [
        _flatten_row(meta, extraction, output_config) for meta, extraction in results
    ]


def results_to_csv_bytes(
    results: list[tuple[TranscriptMetadata, BaseModel]],
    output_config: OutputConfig,
) -> bytes:
    """Serialize extraction results to CSV bytes in memory."""
    columns = build_csv_columns(output_config)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for row in results_to_rows(results, output_config):
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")
