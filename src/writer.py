import csv
import io
from pathlib import Path

from src.parser import TranscriptMetadata
from src.schema import EarningsCallExtraction

# Flat CSV column order matching required_output.md
_COLUMNS = [
    # Metadata
    "event_id",
    "company_name",
    "quarter",
    "date",
    "headline",
    "source_file",
    # 1a. AI Infrastructure
    "ai_infra_binary",
    "ai_infra_types",
    "ai_infra_count",
    "ai_infra_dollar",
    # 1b. AI Analytics
    "ai_analytics_binary",
    "ai_analytics_types",
    "ai_analytics_count",
    "ai_analytics_dollar",
    # 1c. AI Talent
    "ai_talent_binary",
    "ai_talent_types",
    "ai_talent_count",
    "ai_talent_dollar",
    "ai_talent_headcount",
    # 1d. AI Risk
    "ai_risk_binary",
    "ai_risk_types",
    "ai_risk_count",
    "ai_risk_sentiment",
    # 2a. Tech Physical
    "tech_phys_binary",
    "tech_phys_dollar",
    # 2b. Tech Talent
    "tech_talent_binary",
    "tech_talent_headcount",
    "tech_talent_dollar",
]


def _flatten_row(
    meta: TranscriptMetadata, extraction: EarningsCallExtraction
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

    ai = extraction.ai_infrastructure
    row["ai_infra_binary"] = str(ai.ai_infra_binary)
    row["ai_infra_types"] = "; ".join(ai.ai_infra_types)
    row["ai_infra_count"] = str(ai.ai_infra_count)
    row["ai_infra_dollar"] = _fmt_num(ai.ai_infra_dollar)

    an = extraction.ai_analytics
    row["ai_analytics_binary"] = str(an.ai_analytics_binary)
    row["ai_analytics_types"] = "; ".join(an.ai_analytics_types)
    row["ai_analytics_count"] = str(an.ai_analytics_count)
    row["ai_analytics_dollar"] = _fmt_num(an.ai_analytics_dollar)

    at = extraction.ai_talent
    row["ai_talent_binary"] = str(at.ai_talent_binary)
    row["ai_talent_types"] = "; ".join(at.ai_talent_types)
    row["ai_talent_count"] = str(at.ai_talent_count)
    row["ai_talent_dollar"] = _fmt_num(at.ai_talent_dollar)
    row["ai_talent_headcount"] = _fmt_num(at.ai_talent_headcount)

    ar = extraction.ai_risk
    row["ai_risk_binary"] = str(ar.ai_risk_binary)
    row["ai_risk_types"] = "; ".join(ar.ai_risk_types)
    row["ai_risk_count"] = str(ar.ai_risk_count)
    row["ai_risk_sentiment"] = ar.ai_risk_sentiment or ""

    tp = extraction.tech_physical
    row["tech_phys_binary"] = str(tp.tech_phys_binary)
    row["tech_phys_dollar"] = _fmt_num(tp.tech_phys_dollar)

    tt = extraction.tech_talent
    row["tech_talent_binary"] = str(tt.tech_talent_binary)
    row["tech_talent_headcount"] = _fmt_num(tt.tech_talent_headcount)
    row["tech_talent_dollar"] = _fmt_num(tt.tech_talent_dollar)

    return row


def _fmt_num(val: float | None) -> str:
    if val is None:
        return ""
    if val == int(val):
        return str(int(val))
    return str(val)


def write_csv(
    results: list[tuple[TranscriptMetadata, EarningsCallExtraction]],
    output_path: Path,
) -> None:
    """Write extraction results to a CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNS)
        writer.writeheader()
        for meta, extraction in results:
            writer.writerow(_flatten_row(meta, extraction))


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


def initialize_output_csv(output_path: Path, overwrite: bool = False) -> None:
    """Create the CSV with a header, optionally overwriting any existing file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and output_path.exists():
        output_path.unlink()

    if output_path.exists():
        return

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNS)
        writer.writeheader()


def append_csv(
    results: list[tuple[TranscriptMetadata, EarningsCallExtraction]],
    output_path: Path,
) -> None:
    """Append extraction results to an existing CSV (for resumption)."""
    file_exists = output_path.exists()
    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNS)
        if not file_exists:
            writer.writeheader()
        for meta, extraction in results:
            writer.writerow(_flatten_row(meta, extraction))


def results_to_rows(
    results: list[tuple[TranscriptMetadata, EarningsCallExtraction]],
) -> list[dict[str, str]]:
    """Convert extraction results into flat CSV rows without writing to disk."""
    return [_flatten_row(meta, extraction) for meta, extraction in results]


def results_to_csv_bytes(
    results: list[tuple[TranscriptMetadata, EarningsCallExtraction]],
) -> bytes:
    """Serialize extraction results to CSV bytes in memory."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_COLUMNS)
    writer.writeheader()
    for row in results_to_rows(results):
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")
