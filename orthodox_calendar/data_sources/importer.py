from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from orthodox_calendar.database.database import Database
from orthodox_calendar.models import Source

REQUIRED_FIELDS = {"civil_date", "canonical_name"}


@dataclass(slots=True)
class ImportResult:
    count: int
    year: int
    source_name: str
    status: str


class CalendarImporter:
    """Validated CSV/JSON importer for source-supplied saint commemorations."""

    def __init__(self, database: Database):
        self.database = database

    def import_file(self, path: Path, year: int, source_name: str, source_url: str = "", authoritative: bool = True) -> ImportResult:
        suffix = path.suffix.lower()
        if suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            records = payload["saints"] if isinstance(payload, dict) else payload
        elif suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                records = list(csv.DictReader(handle))
        elif suffix == ".xml":
            root = ET.fromstring(path.read_text(encoding="utf-8-sig"))
            records = []
            for element in root.findall(".//saint"):
                record = dict(element.attrib)
                record.update({child.tag: (child.text or "").strip() for child in element})
                records.append(record)
        elif suffix in {".html", ".htm"}:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(path.read_text(encoding="utf-8-sig"), "lxml")
            table = soup.find("table")
            if not table:
                raise ValueError("HTML import requires a table")
            rows = table.find_all("tr")
            headers = [cell.get_text(" ", strip=True) for cell in rows[0].find_all(["th", "td"])]
            records = [dict(zip(headers, [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])])) for row in rows[1:] if row.find_all(["th", "td"])]
        elif suffix == ".pdf":
            from pypdf import PdfReader
            lines = []
            for page in PdfReader(path).pages:
                lines.extend((page.extract_text() or "").splitlines())
            parsed = list(csv.DictReader(lines, delimiter="|", skipinitialspace=True))
            records = [{str(k).strip(): str(v).strip() for k, v in row.items()} for row in parsed]
        else:
            raise ValueError("Supported import formats are CSV, JSON, XML, HTML, and pipe-delimited PDF")
        if not isinstance(records, list):
            raise ValueError("Import must contain a list of saint records")
        for index, record in enumerate(records, 1):
            missing = REQUIRED_FIELDS - set(record)
            if missing:
                raise ValueError(f"Record {index} is missing: {', '.join(sorted(missing))}")
        status = "authoritative" if authoritative else "partial"
        source = Source(source_name, source_url, datetime.now(timezone.utc), year, path.name)
        count = self.database.import_saints(year, records, source, status)
        return ImportResult(count, year, source_name, status)
