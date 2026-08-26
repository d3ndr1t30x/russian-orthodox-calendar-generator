from __future__ import annotations

import copy
import base64
import binascii
import hashlib
import mimetypes
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from orthodox_calendar import __version__
from orthodox_calendar.models import (
    CalendarDay, Feast, FeastRank, FastLevel, Fasting, PublicHoliday, Saint,
    ServiceRank, ServiceRankInfo, Source,
)


PROJECT_SCHEMA_VERSION = 1
SUPPORTED_LANGUAGES = {"English", "Russian"}
SUPPORTED_TEMPLATES = {"Traditional", "Minimal", "Parish"}
SUPPORTED_ORIENTATIONS = {"Landscape", "Portrait"}
SUPPORTED_JURISDICTIONS = {
    "Australian Capital Territory", "New South Wales", "Northern Territory",
    "Queensland", "South Australia", "Tasmania", "Victoria", "Western Australia",
}
MAX_EMBEDDED_ASSET_BYTES = 5 * 1024 * 1024


class ProjectValidationError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_to_dict(source: Source | None) -> dict[str, Any] | None:
    if source is None:
        return None
    return {
        "name": source.name, "url": source.url,
        "retrieved_at": source.retrieved_at.isoformat() if source.retrieved_at else None,
        "source_year": source.source_year, "version": source.version,
    }


def _source_from_dict(data: dict[str, Any] | None) -> Source | None:
    if not data:
        return None
    retrieved = datetime.fromisoformat(data["retrieved_at"]) if data.get("retrieved_at") else None
    return Source(str(data.get("name", "Unknown")), str(data.get("url", "")), retrieved, data.get("source_year"), str(data.get("version", "")))


def saint_key(saint: Saint) -> str:
    if saint.id is not None:
        return f"id:{saint.id}"
    raw = f"{saint.canonical_name}|{saint.language}|{saint.source.name if saint.source else ''}"
    return "fingerprint:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def feast_key(feast: Feast, civil_date: date) -> str:
    raw = f"{civil_date.isoformat()}|{feast.name}|{feast.source.name if feast.source else ''}|{feast.source.url if feast.source else ''}"
    return "fingerprint:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _saint_to_dict(saint: Saint) -> dict[str, Any]:
    return {
        "stable_id": saint_key(saint), "saint_id": saint.id,
        "canonical_name": saint.canonical_name, "display_name": saint.display_name,
        "commemoration_date": saint.commemoration_date.isoformat(), "category": saint.category,
        "rank": saint.rank, "description": saint.description, "language": saint.language,
        "source": _source_to_dict(saint.source), "selected": saint.selected,
        "display_order": saint.display_order, "service_rank": saint.service_rank.value,
        "source_rank_text": saint.source_rank_text,
    }


def _saint_from_dict(data: dict[str, Any], fallback_date: date) -> Saint:
    return Saint(
        data.get("saint_id"), str(data.get("canonical_name", data.get("display_name", "Unknown saint"))),
        str(data.get("display_name", data.get("canonical_name", "Unknown saint"))),
        date.fromisoformat(data.get("commemoration_date", fallback_date.isoformat())),
        str(data.get("category", "Saint")), str(data.get("rank", "")), str(data.get("description", "")),
        str(data.get("language", "en")), _source_from_dict(data.get("source")), bool(data.get("selected", True)),
        int(data.get("display_order", 0)), ServiceRank(data.get("service_rank", ServiceRank.NONE.value)),
        str(data.get("source_rank_text", "")),
    )


def _feast_to_dict(feast: Feast, civil_date: date) -> dict[str, Any]:
    return {
        "stable_id": feast_key(feast, civil_date), "name": feast.name, "rank": feast.rank.value,
        "description": feast.description, "source": _source_to_dict(feast.source), "calculated": feast.calculated,
        "liturgical_status": feast.liturgical_status, "service_rank": feast.service_rank.value,
        "source_rank_text": feast.source_rank_text,
    }


def _feast_from_dict(data: dict[str, Any]) -> Feast:
    return Feast(
        str(data.get("name", "")), FeastRank(data.get("rank", FeastRank.COMMEMORATION.value)),
        str(data.get("description", "")), _source_from_dict(data.get("source")), bool(data.get("calculated", False)),
        str(data.get("liturgical_status", "")), ServiceRank(data.get("service_rank", ServiceRank.NONE.value)),
        str(data.get("source_rank_text", "")),
    )


def _fasting_to_dict(fasting: Fasting | None) -> dict[str, Any] | None:
    if fasting is None:
        return None
    return {"level": fasting.level.value, "period": fasting.period, "detail": fasting.detail, "source": _source_to_dict(fasting.source)}


def _fasting_from_dict(data: dict[str, Any] | None) -> Fasting | None:
    if data is None:
        return None
    return Fasting(FastLevel(data["level"]), str(data.get("period", "")), str(data.get("detail", "")), _source_from_dict(data.get("source")))


def _rank_to_dict(rank: ServiceRankInfo) -> dict[str, Any]:
    return {
        "normalized_rank": rank.normalized_rank.value, "name_en": rank.name_en, "name_ru": rank.name_ru,
        "source_name": rank.source_name, "source_url": rank.source_url, "source_rank_text": rank.source_rank_text,
        "status": rank.status, "user_override": rank.user_override,
    }


def _rank_from_dict(data: dict[str, Any] | None) -> ServiceRankInfo:
    if not data:
        return ServiceRankInfo()
    return ServiceRankInfo(
        ServiceRank(data.get("normalized_rank", ServiceRank.NO_DATA.value)), str(data.get("name_en", "")),
        str(data.get("name_ru", "")), str(data.get("source_name", "")), str(data.get("source_url", "")),
        str(data.get("source_rank_text", "")), str(data.get("status", "no_data")), bool(data.get("user_override", False)),
    )


def day_to_dict(day: CalendarDay) -> dict[str, Any]:
    return {
        "civil_date": day.civil_date.isoformat(), "julian_date": day.julian_date.isoformat(),
        "saints": [_saint_to_dict(item) for item in day.saints],
        "feasts": [_feast_to_dict(item, day.civil_date) for item in day.feasts],
        "fasting": _fasting_to_dict(day.fasting),
        "public_holidays": [{"name": item.name, "jurisdiction": item.jurisdiction, "source": _source_to_dict(item.source)} for item in day.public_holidays],
        "readings": list(day.readings), "notes": list(day.notes), "liturgical_week": day.liturgical_week,
        "tone": day.tone, "paschal_offset": day.paschal_offset,
        "authoritative_data_available": day.authoritative_data_available, "service_rank": _rank_to_dict(day.service_rank),
    }


def day_from_dict(data: dict[str, Any]) -> CalendarDay:
    civil = date.fromisoformat(data["civil_date"])
    return CalendarDay(
        civil, date.fromisoformat(data["julian_date"]),
        [_saint_from_dict(item, civil) for item in data.get("saints", [])],
        [_feast_from_dict(item) for item in data.get("feasts", [])],
        _fasting_from_dict(data.get("fasting")),
        [PublicHoliday(str(item["name"]), str(item["jurisdiction"]), _source_from_dict(item.get("source")) or Source("Unknown")) for item in data.get("public_holidays", [])],
        list(data.get("readings", [])), list(data.get("notes", [])), str(data.get("liturgical_week", "")),
        data.get("tone"), data.get("paschal_offset"), bool(data.get("authoritative_data_available", False)),
        _rank_from_dict(data.get("service_rank")),
    )


@dataclass(slots=True)
class ProjectSettings:
    year: int
    jurisdiction: str
    language: str = "English"
    paper: str = "A4"
    orientation: str = "Landscape"
    template: str = "Traditional"
    include_julian: bool = True
    include_holidays: bool = True
    include_sources: bool = True
    include_fasting_icons: bool = True
    include_fasting_legend: bool = True
    include_service_rank_icons: bool = True
    include_service_rank_legend: bool = True
    rank_labels_en: dict[str, str] = field(default_factory=dict)
    rank_labels_ru: dict[str, str] = field(default_factory=dict)
    parish_name: str = ""
    parish_logo: str = ""
    address: str = ""
    website: str = ""
    phone: str = ""
    custom_header: str = ""
    custom_footer: str = ""

    def validate(self) -> None:
        if not 1583 <= int(self.year) <= 4099:
            raise ProjectValidationError("Calendar year must be between 1583 and 4099")
        if self.jurisdiction not in SUPPORTED_JURISDICTIONS:
            raise ProjectValidationError("Invalid Australian jurisdiction")
        if self.language not in SUPPORTED_LANGUAGES:
            raise ProjectValidationError("Language must be English or Russian")
        if self.paper != "A4":
            raise ProjectValidationError("Only A4 project paper is supported")
        if self.orientation not in SUPPORTED_ORIENTATIONS:
            raise ProjectValidationError("Invalid project orientation")
        if self.template not in SUPPORTED_TEMPLATES:
            raise ProjectValidationError("Invalid project template")


@dataclass(slots=True)
class CalendarProject:
    project_name: str
    settings: ProjectSettings
    calendar_data_version: str
    source_snapshot: list[dict[str, Any]]
    overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    project_schema_version: int = PROJECT_SCHEMA_VERSION
    project_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)
    modified_at: str = field(default_factory=utc_now)
    last_synchronization_at: str = ""
    application_version: str = __version__
    embedded_assets: dict[str, dict[str, str]] = field(default_factory=dict)
    file_path: str = field(default="", repr=False)
    modified: bool = field(default=True, repr=False)
    missing_references: list[str] = field(default_factory=list, repr=False)

    @classmethod
    def create(cls, name: str, settings: ProjectSettings, days: list[CalendarDay], data_version: str, last_sync: str = "") -> "CalendarProject":
        settings.validate()
        if not days or any(day.civil_date.year != settings.year for day in days):
            raise ProjectValidationError("Project calendar data does not match the selected year")
        return cls(name.strip() or f"Russian Orthodox Calendar {settings.year} — {settings.jurisdiction}", settings, data_version, [day_to_dict(day) for day in days], last_synchronization_at=last_sync)

    def validate(self) -> None:
        if self.project_schema_version != PROJECT_SCHEMA_VERSION:
            raise ProjectValidationError(f"Unsupported project schema version: {self.project_schema_version}")
        if not self.project_name or len(self.project_name) > 250:
            raise ProjectValidationError("Project name is missing or too long")
        self.settings.validate()
        if not self.calendar_data_version or len(self.calendar_data_version) > 500:
            raise ProjectValidationError("Calendar data version is missing or invalid")
        for label, value in (("creation", self.created_at), ("modification", self.modified_at)):
            try:
                datetime.fromisoformat(value)
            except (TypeError, ValueError) as exc:
                raise ProjectValidationError(f"Project {label} timestamp is invalid") from exc
        if not isinstance(self.source_snapshot, list) or len(self.source_snapshot) not in {365, 366}:
            raise ProjectValidationError("Project source snapshot is incomplete")
        try:
            parsed_days = [day_from_dict(item) for item in self.source_snapshot if isinstance(item, dict)]
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectValidationError("Project source snapshot contains invalid calendar data") from exc
        if len(parsed_days) != len(self.source_snapshot):
            raise ProjectValidationError("Project source snapshot entries must be objects")
        dates = [item.civil_date for item in parsed_days]
        if len(set(dates)) != len(dates):
            raise ProjectValidationError("Project contains duplicate calendar dates")
        expected_days = 366 if date(self.settings.year, 12, 31).toordinal() - date(self.settings.year, 1, 1).toordinal() + 1 == 366 else 365
        if len(dates) != expected_days or min(dates) != date(self.settings.year, 1, 1) or max(dates) != date(self.settings.year, 12, 31):
            raise ProjectValidationError("Project source snapshot does not cover the selected calendar year")
        if not isinstance(self.overrides, dict):
            raise ProjectValidationError("Project overrides must be an object")
        valid_dates = {item.isoformat() for item in dates}
        for key, override in self.overrides.items():
            if key not in valid_dates or not isinstance(override, dict):
                raise ProjectValidationError("Project contains an invalid dated override")
            try:
                override_date = date.fromisoformat(key)
                for saint in override.get("saints", []):
                    stable_id = saint.get("stable_id") if isinstance(saint, dict) else None
                    if not isinstance(stable_id, str) or not stable_id.startswith(("id:", "fingerprint:")) or len(stable_id) > 128:
                        raise ProjectValidationError("Project contains an invalid saint reference")
                    _saint_from_dict(saint, override_date)
                for feast in override.get("feasts", []):
                    if not isinstance(feast, dict) or not isinstance(feast.get("stable_id"), str):
                        raise ProjectValidationError("Project contains an invalid feast reference")
                    _feast_from_dict(feast)
                if "fasting" in override:
                    _fasting_from_dict(override["fasting"])
                if "service_rank" in override:
                    _rank_from_dict(override["service_rank"])
                notes = override.get("notes", [])
                if not isinstance(notes, list) or any(not isinstance(item, str) for item in notes):
                    raise ProjectValidationError("Project contains invalid notes")
                primary = override.get("primary_saint_id")
                if primary is not None and (not isinstance(primary, str) or len(primary) > 128):
                    raise ProjectValidationError("Project contains an invalid primary saint reference")
            except ProjectValidationError:
                raise
            except (KeyError, TypeError, ValueError) as exc:
                raise ProjectValidationError("Project contains invalid override data") from exc
        logo = self.settings.parish_logo
        if logo and logo != "embedded://parish_logo":
            if Path(logo).is_absolute() or ".." in Path(logo).parts:
                raise ProjectValidationError("Project assets must not contain absolute or parent-relative paths")
        if logo == "embedded://parish_logo" and "parish_logo" not in self.embedded_assets:
            raise ProjectValidationError("The embedded parish logo is missing")
        for key, asset in self.embedded_assets.items():
            if key != "parish_logo" or not isinstance(asset, dict):
                raise ProjectValidationError("Project contains an unsupported embedded asset")
            try:
                raw = base64.b64decode(asset.get("data_base64", ""), validate=True)
            except (binascii.Error, TypeError) as exc:
                raise ProjectValidationError("Project contains a corrupt embedded asset") from exc
            if not raw or len(raw) > MAX_EMBEDDED_ASSET_BYTES:
                raise ProjectValidationError("Embedded project asset is empty or exceeds 5 MB")

    def capture_parish_logo(self) -> None:
        """Embed a logo so a project remains portable and stores no absolute path."""
        value = self.settings.parish_logo
        if not value or value == "embedded://parish_logo":
            return
        source = Path(value)
        if not source.is_file():
            raise ProjectValidationError("The project parish logo could not be found")
        raw = source.read_bytes()
        if not raw or len(raw) > MAX_EMBEDDED_ASSET_BYTES:
            raise ProjectValidationError("The parish logo is empty or exceeds 5 MB")
        suffix = source.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg"}:
            raise ProjectValidationError("Parish logos must be PNG or JPEG images")
        self.embedded_assets["parish_logo"] = {
            "filename": "parish_logo" + suffix,
            "media_type": mimetypes.guess_type(source.name)[0] or "application/octet-stream",
            "data_base64": base64.b64encode(raw).decode("ascii"),
        }
        self.settings.parish_logo = "embedded://parish_logo"
        self.mark_modified()

    def materialize_parish_logo(self, directory: Path) -> str:
        """Return a safe runtime path for the embedded logo without changing the project."""
        if self.settings.parish_logo != "embedded://parish_logo":
            return self.settings.parish_logo
        asset = self.embedded_assets.get("parish_logo", {})
        filename = str(asset.get("filename", "parish_logo.png"))
        suffix = Path(filename).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg"}:
            raise ProjectValidationError("The embedded parish logo has an unsupported format")
        raw = base64.b64decode(asset.get("data_base64", ""), validate=True)
        if not raw or len(raw) > MAX_EMBEDDED_ASSET_BYTES:
            raise ProjectValidationError("The embedded parish logo is invalid")
        directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
        target = directory / ("parish_logo" + suffix)
        temp = directory / (".parish_logo" + suffix + ".tmp")
        with temp.open("wb") as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp, target)
        return str(target)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "project_schema_version": self.project_schema_version, "project_id": self.project_id,
            "project_name": self.project_name, "calendar_year": self.settings.year,
            "jurisdiction": self.settings.jurisdiction, "language": self.settings.language,
            "paper": self.settings.paper, "orientation": self.settings.orientation, "template": self.settings.template,
            "created_at": self.created_at, "last_modified_at": self.modified_at,
            "calendar_data_version": self.calendar_data_version,
            "last_synchronization_at": self.last_synchronization_at,
            "application_version": self.application_version,
            "settings": asdict(self.settings), "source_snapshot": self.source_snapshot,
            "overrides": self.overrides, "embedded_assets": self.embedded_assets,
            "notice": "Project document; source data plus user overrides. Not an ecclesiastical authority.",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalendarProject":
        migrated = migrate_project_dict(copy.deepcopy(data))
        settings_data = migrated.get("settings", {})
        if not settings_data:
            settings_data = {key: migrated.get(key) for key in ("calendar_year", "jurisdiction", "language", "paper", "orientation", "template")}
            settings_data["year"] = settings_data.pop("calendar_year")
        project = cls(
            str(migrated.get("project_name", "")), ProjectSettings(**{key: value for key, value in settings_data.items() if key in ProjectSettings.__dataclass_fields__}),
            str(migrated.get("calendar_data_version", "unknown")), list(migrated.get("source_snapshot", [])),
            dict(migrated.get("overrides", {})), int(migrated.get("project_schema_version", 0)),
            str(migrated.get("project_id", uuid4())), str(migrated.get("created_at", utc_now())),
            str(migrated.get("last_modified_at", utc_now())), str(migrated.get("last_synchronization_at", "")),
            str(migrated.get("application_version", "")), dict(migrated.get("embedded_assets", {})),
        )
        project.modified = False
        project.validate()
        return project

    def resolve_days(self, current_days: list[CalendarDay] | None = None, update_source: bool = False) -> list[CalendarDay]:
        self.missing_references.clear()
        base = copy.deepcopy(current_days) if update_source and current_days else [day_from_dict(item) for item in self.source_snapshot]
        by_date = {day.civil_date.isoformat(): day for day in base}
        for key, override in self.overrides.items():
            day = by_date.get(key)
            if not day:
                self.missing_references.append(f"Missing calendar date: {key}")
                continue
            states = override.get("saints", [])
            by_stable = {saint_key(item): item for item in day.saints}
            for state in states:
                stable = str(state.get("stable_id", ""))
                saint = by_stable.get(stable)
                if saint is None:
                    self.missing_references.append(f"{key}: {state.get('display_name') or state.get('canonical_name') or stable}")
                    saint = _saint_from_dict(state, day.civil_date)
                    saint.description = (saint.description + " [Saved project reference missing from current source data]").strip()
                    day.saints.append(saint); by_stable[stable] = saint
                saint.selected = bool(state.get("selected", saint.selected))
                saint.display_name = str(state.get("display_name", saint.display_name))
                saint.display_order = int(state.get("display_order", saint.display_order))
            primary = override.get("primary_saint_id")
            if primary and primary in by_stable:
                by_stable[primary].selected = True
            day.saints.sort(key=lambda item: (item.display_order, item.display_name))
            if "feasts" in override:
                day.feasts = [_feast_from_dict(item) for item in override["feasts"]]
            if "fasting" in override:
                day.fasting = _fasting_from_dict(override["fasting"])
            if "notes" in override:
                day.notes = [str(item) for item in override["notes"]]
            if "service_rank" in override:
                day.service_rank = _rank_from_dict(override["service_rank"])
        if update_source:
            self.source_snapshot = [day_to_dict(day) for day in current_days or base]
        return base

    def update_day(self, day: CalendarDay, primary_saint_id: str | None = None) -> None:
        states = [_saint_to_dict(item) for item in day.saints]
        self.overrides[day.civil_date.isoformat()] = {
            "saints": states,
            "primary_saint_id": primary_saint_id or next((saint_key(item) for item in sorted(day.saints, key=lambda item: item.display_order) if item.selected), None),
            "feasts": [_feast_to_dict(item, day.civil_date) for item in day.feasts],
            "fasting": _fasting_to_dict(day.fasting), "notes": list(day.notes),
            "service_rank": _rank_to_dict(day.service_rank),
        }
        self.mark_modified()

    def source_day(self, civil_date: date) -> CalendarDay | None:
        """Return this project's saved authoritative/default day, never live DB data."""
        key = civil_date.isoformat()
        item = next((value for value in self.source_snapshot if value.get("civil_date") == key), None)
        return day_from_dict(copy.deepcopy(item)) if item else None

    def reset_day(self, civil_date: date) -> bool:
        """Remove only this project's override for one date."""
        changed = self.overrides.pop(civil_date.isoformat(), None) is not None
        if changed:
            self.mark_modified()
        return changed

    def reset_month(self, year: int, month: int) -> list[str]:
        keys = [key for key in self.overrides if date.fromisoformat(key).year == year and date.fromisoformat(key).month == month]
        for key in keys:
            del self.overrides[key]
        if keys:
            self.mark_modified()
        return sorted(keys)

    def reset_year(self, year: int) -> list[str]:
        keys = [key for key in self.overrides if date.fromisoformat(key).year == year]
        for key in keys:
            del self.overrides[key]
        if keys:
            self.mark_modified()
        return sorted(keys)

    def override_dates(self, year: int | None = None, month: int | None = None) -> list[date]:
        result = [date.fromisoformat(key) for key in self.overrides]
        if year is not None:
            result = [value for value in result if value.year == year]
        if month is not None:
            result = [value for value in result if value.month == month]
        return sorted(result)

    def mark_modified(self) -> None:
        self.modified = True
        self.modified_at = utc_now()
        self.application_version = __version__

    def update_source_data(self, current_days: list[CalendarDay], new_version: str) -> list[CalendarDay]:
        resolved = self.resolve_days(current_days, update_source=True)
        self.calendar_data_version = new_version
        self.mark_modified()
        return resolved

    def compare_source_data(self, current_days: list[CalendarDay]) -> dict[str, int]:
        """Summarize source-record changes without mutating the project."""
        saved = {day.civil_date: day for day in (day_from_dict(item) for item in self.source_snapshot)}
        current = {day.civil_date: day for day in current_days}
        added = removed = changed_dates = 0
        for civil_date in set(saved) | set(current):
            old, new = saved.get(civil_date), current.get(civil_date)
            old_ids = {saint_key(item) for item in old.saints} if old else set()
            new_ids = {saint_key(item) for item in new.saints} if new else set()
            added += len(new_ids - old_ids); removed += len(old_ids - new_ids)
            old_feasts = {feast_key(item, civil_date) for item in old.feasts} if old else set()
            new_feasts = {feast_key(item, civil_date) for item in new.feasts} if new else set()
            added += len(new_feasts - old_feasts); removed += len(old_feasts - new_feasts)
            if old_ids != new_ids or old_feasts != new_feasts:
                changed_dates += 1
        return {"added_records": added, "removed_records": removed, "changed_dates": changed_dates}


def migrate_project_dict(data: dict[str, Any]) -> dict[str, Any]:
    version = data.get("project_schema_version")
    if not isinstance(version, int):
        raise ProjectValidationError("Project schema version is missing")
    if version > PROJECT_SCHEMA_VERSION:
        raise ProjectValidationError(f"This project requires a newer application (schema {version})")
    while version < PROJECT_SCHEMA_VERSION:
        migration = PROJECT_MIGRATIONS.get(version)
        if not migration:
            raise ProjectValidationError(f"No migration is available for project schema {version}")
        data = migration(data); version = data["project_schema_version"]
    return data


PROJECT_MIGRATIONS: dict[int, Any] = {}
