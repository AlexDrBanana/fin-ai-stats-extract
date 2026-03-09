import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TranscriptMetadata:
    event_id: str
    headline: str
    company_name: str
    quarter: str
    date: str
    source_file: str


def parse_xml(file_path: Path) -> tuple[TranscriptMetadata, str]:
    """Parse an earnings call XML file and return (metadata, transcript_text)."""
    return parse_xml_with_source(file_path, file_path.name)


def parse_xml_with_source(
    file_path: Path,
    source_file: str,
) -> tuple[TranscriptMetadata, str]:
    """Parse an earnings call XML file and attach the provided source path label."""
    tree = ET.parse(file_path)  # noqa: S314
    return _parse_root(tree.getroot(), source_file)


def parse_xml_bytes(data: bytes, source_file: str) -> tuple[TranscriptMetadata, str]:
    """Parse uploaded XML bytes and attach the provided source path label."""
    root = ET.fromstring(data)  # noqa: S314
    return _parse_root(root, source_file)


def _parse_root(root: ET.Element, source_file: str) -> tuple[TranscriptMetadata, str]:
    """Extract transcript metadata and body from a parsed XML root."""

    event_id = root.get("Id", "")

    story = root.find("EventStory")
    headline_el = story.find("Headline") if story is not None else None
    body_el = story.find("Body") if story is not None else None

    headline = (headline_el.text or "").strip() if headline_el is not None else ""
    body = (body_el.text or "").strip() if body_el is not None else ""

    company_name = _extract_company_name(headline)
    quarter = _extract_quarter(body)
    date = _extract_date(headline)

    metadata = TranscriptMetadata(
        event_id=event_id,
        headline=headline,
        company_name=company_name,
        quarter=quarter,
        date=date,
        source_file=source_file,
    )
    return metadata, body


def _extract_company_name(headline: str) -> str:
    """Extract company name from headline like 'Edited Transcript of COMPANY earnings ...'"""
    match = re.search(r"Edited Transcript of (.+?) earnings", headline, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(
        r"Transcript of (.+?) (?:earnings|conference)", headline, re.IGNORECASE
    )
    if match:
        return match.group(1).strip()
    return headline


def _extract_quarter(body: str) -> str:
    """Extract quarter like 'Q4 2004' or 'Half Year 2024' from the first line of the body."""
    first_line = body.split("\n")[0].strip() if body else ""
    match = re.search(r"(Q[1-4]\s+\d{4})", first_line, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(
        r"((?:Full Year|Half Year|FY)\s+\d{4})", first_line, re.IGNORECASE
    )
    if match:
        return match.group(1)
    return first_line[:60] if first_line else ""


def _extract_date(headline: str) -> str:
    """Extract date from headline like '... 17-Feb-05 9:30pm GMT'"""
    match = re.search(r"(\d{1,2}-\w{3}-\d{2,4})", headline)
    if match:
        return match.group(1)
    return ""
