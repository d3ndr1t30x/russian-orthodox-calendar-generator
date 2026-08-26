from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from orthodox_calendar.database.database import Database
from orthodox_calendar.data_sources.azbyka import AzbykaSource
from orthodox_calendar.data_sources.foma import FomaSource
from orthodox_calendar.data_sources.patriarchia import PatriarchiaSource
from orthodox_calendar.data_sources.holy_trinity import HolyTrinitySource, HolyTrinitySyncResult, SOURCE_HOME
from orthodox_calendar.models import Source
from orthodox_calendar.paths import ensure_user_dirs


@dataclass(slots=True)
class SyncResult:
    source: str
    available: bool
    message: str


class SynchronizationService:
    def __init__(self, database: Database, cache_root: Path | None = None):
        self.database = database
        self.cache_root = cache_root or ensure_user_dirs()["cache"] / "holy_trinity"
        self.sources = [PatriarchiaSource(), AzbykaSource(), FomaSource()]

    def sync_holy_trinity(self, year: int, cache_only: bool = False, force: bool = False, progress=None) -> tuple[HolyTrinitySyncResult, dict[str, int]]:
        adapter = HolyTrinitySource(self.cache_root)
        result = adapter.fetch_year(year, force=force, cache_only=cache_only, progress=progress)
        source = Source(adapter.name, SOURCE_HOME, datetime.now(timezone.utc), year, "legacy-compatible-v2calendar")
        counts = self.database.replace_holy_trinity_year(year, result.days, source, result.complete)
        message = (
            f"{counts['days']} language-days; {counts['saints']} commemorations; {counts['feasts']} feasts; "
            f"downloaded {result.downloaded}, cache {result.cache_hits}, legacy cache {result.legacy_cache_hits}; "
            f"failures {len(result.failures)}"
        )
        self.database.record_sync(adapter.name, result.complete, message)
        return result, counts

    def check_sources(self) -> list[SyncResult]:
        results = []
        for source in self.sources:
            availability = source.check_availability()
            self.database.record_sync(source.name, availability.available, availability.message)
            results.append(SyncResult(source.name, availability.available, availability.message))
        return results
