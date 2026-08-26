from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class FeastRank(StrEnum):
    GREAT = "Great Feast"
    MAJOR = "Major Feast"
    COMMEMORATION = "Commemoration"


class FastLevel(StrEnum):
    FREE = "Fast-free"
    ORDINARY = "Fast day"
    WINE_OIL = "Wine/oil permitted"
    FISH = "Fish permitted"
    STRICT = "Strict fast"


class ServiceRank(StrEnum):
    GREAT_FEAST = "GREAT_FEAST"
    VIGIL = "VIGIL"
    POLYELEOS = "POLYELEOS"
    DOXOLOGY = "DOXOLOGY"
    SIX_STICHERA = "SIX_STICHERA"
    NO_SIGN = "NO_SIGN"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"
    NO_DATA = "NO_DATA"
    NONE = "NONE"


@dataclass(slots=True)
class Source:
    name: str
    url: str = ""
    retrieved_at: datetime | None = None
    source_year: int | None = None
    version: str = ""


@dataclass(slots=True)
class Saint:
    id: int | None
    canonical_name: str
    display_name: str
    commemoration_date: date
    category: str = "Saint"
    rank: str = ""
    description: str = ""
    language: str = "en"
    source: Source | None = None
    selected: bool = True
    display_order: int = 0
    service_rank: ServiceRank = ServiceRank.NONE
    source_rank_text: str = ""


@dataclass(slots=True)
class Feast:
    name: str
    rank: FeastRank
    description: str = ""
    source: Source | None = None
    calculated: bool = False
    liturgical_status: str = ""
    service_rank: ServiceRank = ServiceRank.NONE
    source_rank_text: str = ""


@dataclass(slots=True)
class ServiceRankInfo:
    normalized_rank: ServiceRank = ServiceRank.NO_DATA
    name_en: str = "No rank data"
    name_ru: str = "Нет данных о ранге"
    source_name: str = ""
    source_url: str = ""
    source_rank_text: str = ""
    status: str = "no_data"
    user_override: bool = False


@dataclass(slots=True)
class Fasting:
    level: FastLevel
    period: str
    detail: str
    source: Source | None = None


@dataclass(slots=True)
class PublicHoliday:
    name: str
    jurisdiction: str
    source: Source


@dataclass(slots=True)
class CalendarDay:
    civil_date: date
    julian_date: date
    saints: list[Saint] = field(default_factory=list)
    feasts: list[Feast] = field(default_factory=list)
    fasting: Fasting | None = None
    public_holidays: list[PublicHoliday] = field(default_factory=list)
    readings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    liturgical_week: str = ""
    tone: int | None = None
    paschal_offset: int | None = None
    authoritative_data_available: bool = False
    service_rank: ServiceRankInfo = field(default_factory=ServiceRankInfo)
