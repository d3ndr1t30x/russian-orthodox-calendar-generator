from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from orthodox_calendar.models import ServiceRank
from orthodox_calendar.service_ranks import highest_rank, normalize_holy_trinity_code


ENGLISH_ENDPOINT = "https://www.holytrinityorthodox.com/htc/ocalendar/v2calendar.php"
RUSSIAN_ENDPOINT = "https://www.holytrinityorthodox.com/htc/ocalendar/ru/v2calendar.php"
SOURCE_HOME = "https://www.holytrinityorthodox.com/htc/orthodox_calendar/"

FEAST_TERMS = (
    "nativity", "theophany", "meeting of", "annunciation", "entry of", "transfiguration",
    "dormition", "exaltation", "pascha", "resurrection of christ", "ascension", "pentecost",
    "рождество", "богоявление", "сретение", "благовещение", "вход господень", "преображение",
    "успение", "воздвижение", "пасха", "вознесение", "пятидесятница",
)


@dataclass(slots=True)
class HolyTrinityEntry:
    name: str
    rank: int
    language: str
    is_feast: bool = False
    source_rank_text: str = ""
    service_rank: ServiceRank = ServiceRank.NO_DATA


@dataclass(slots=True)
class HolyTrinityDay:
    civil_date: date
    language: str
    julian_label: str = ""
    liturgical_week: str = ""
    tone: int | None = None
    fasting_text: str = ""
    entries: list[HolyTrinityEntry] = field(default_factory=list)
    source_url: str = ""

    @property
    def service_rank_info(self):
        return highest_rank([normalize_holy_trinity_code(entry.source_rank_text, self.source_url) for entry in self.entries])


@dataclass(slots=True)
class HolyTrinitySyncResult:
    year: int
    days: list[HolyTrinityDay]
    downloaded: int
    cache_hits: int
    legacy_cache_hits: int
    failures: list[str]

    @property
    def complete(self) -> bool:
        return not self.failures and len(self.days) in {365 * 2, 366 * 2}


def build_url(day: date, language: str) -> str:
    endpoint = RUSSIAN_ENDPOINT if language == "ru" else ENGLISH_ENDPOINT
    query = urlencode({
        "dt": 1, "header": 1, "lives": 1, "trp": 0, "scripture": 0,
        "year": day.year, "month": day.month, "today": day.day, "sid": "em",
    })
    return f"{endpoint}?{query}"


def _tone(text: str) -> int | None:
    match = re.search(r"\bTone\s+(one|two|three|four|five|six|seven|eight)\b", text, re.I)
    if not match:
        match = re.search(r"Глас\s+(\d+)", text, re.I)
        return int(match.group(1)) if match else None
    return {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}[match.group(1).lower()]


def parse_day(html: str, expected_date: date, language: str, source_url: str = "") -> HolyTrinityDay:
    soup = BeautifulSoup(html, "lxml")
    data_header = soup.select_one("span.dataheader")
    header = soup.select_one("span.headerheader")
    normal = soup.select_one("span.normaltext")
    if not data_header or not header or not normal:
        raise ValueError("Holy Trinity response is missing expected calendar sections")
    date_text = data_header.get_text(" ", strip=True)
    julian_label = date_text.split("/", 1)[1].strip() if "/" in date_text else ""
    header_text = header.get_text(" ", strip=True)
    fast_node = header.select_one(".headerfast, .headernofast")
    fasting_text = fast_node.get_text(" ", strip=True) if fast_node else ""
    week = header_text.replace(fasting_text, "").strip(" .")
    week = re.sub(r"(\d)\s+(st|nd|rd|th)\b", r"\1\2", week, flags=re.I)
    entries: list[HolyTrinityEntry] = []
    inner = normal.decode_contents()
    for fragment_html in re.split(r"<br\s*/?>", inner, flags=re.I):
        fragment = BeautifulSoup(fragment_html, "lxml")
        rank_node = fragment.select_one('[class*="typicon-"]')
        if not rank_node:
            continue
        rank_text = rank_node.get_text(strip=True).lower()
        rank = int(rank_text) + 1 if rank_text.isdigit() else 0
        rank_node.decompose()
        name = " ".join(fragment.get_text(" ", strip=True).split())
        name = re.sub(r"\s+([.,;:])", r"\1", name)
        if not name:
            continue
        lowered = name.casefold()
        is_fast_note = any(term in lowered for term in ("fast-free period", "abstinence", "поста нет", "постный период"))
        if is_fast_note:
            continue
        is_feast = rank >= 6 or any(term in lowered for term in FEAST_TERMS)
        rank_info = normalize_holy_trinity_code(rank_text, source_url)
        entries.append(HolyTrinityEntry(name, rank, language, is_feast, rank_text, rank_info.normalized_rank))
    return HolyTrinityDay(expected_date, language, julian_label, week, _tone(header_text), fasting_text, entries, source_url)


class HolyTrinitySource:
    name = "Holy Trinity Orthodox Calendar"

    def __init__(self, cache_root: Path, request_delay: float = 0.10, timeout: float = 15.0):
        self.cache_root = Path(cache_root)
        self.request_delay = request_delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "RussianOrthodoxCalendar/1.3 (+offline cache; contact user initiated)"})

    def _cache_path(self, day: date, language: str) -> Path:
        return self.cache_root / str(day.year) / language / f"{day.isoformat()}.html"

    @staticmethod
    def _read_html(path: Path) -> str:
        raw = path.read_bytes()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("windows-1251", errors="replace")

    @staticmethod
    def _legacy_cache(day: date, language: str) -> Path | None:
        import os
        appdata = Path(os.environ.get("APPDATA", ""))
        projects = appdata / "OrthodoxCalenderGenerator" / "Projects"
        if not projects.exists():
            return None
        matches = list(projects.glob(f"*/RawFiles/Church/{day.isoformat()}.{language}.html"))
        return matches[0] if matches else None

    def fetch_year(
        self,
        year: int,
        languages: tuple[str, ...] = ("en", "ru"),
        force: bool = False,
        cache_only: bool = False,
        progress: Callable[[int, int, str], bool | None] | None = None,
    ) -> HolyTrinitySyncResult:
        start = date(year, 1, 1)
        count = 366 if date(year, 12, 31).timetuple().tm_yday == 366 else 365
        total = count * len(languages)
        result = HolyTrinitySyncResult(year, [], 0, 0, 0, [])
        position = 0
        for offset in range(count):
            day = start + timedelta(days=offset)
            for language in languages:
                position += 1
                if progress and progress(position, total, f"{day.isoformat()} ({language})") is False:
                    result.failures.append("Synchronization cancelled")
                    return result
                cache_path = self._cache_path(day, language)
                url = build_url(day, language)
                html = ""
                if cache_path.exists() and not force:
                    html = self._read_html(cache_path)
                    result.cache_hits += 1
                elif not force and (legacy := self._legacy_cache(day, language)):
                    html = self._read_html(legacy)
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(html, encoding="utf-8")
                    result.legacy_cache_hits += 1
                elif not cache_only:
                    try:
                        response = self.session.get(url, timeout=self.timeout)
                        response.raise_for_status()
                        response.encoding = response.apparent_encoding or "windows-1251"
                        html = response.text
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        cache_path.write_text(html, encoding="utf-8")
                        result.downloaded += 1
                        if self.request_delay:
                            time.sleep(self.request_delay)
                    except requests.RequestException as exc:
                        result.failures.append(f"{day.isoformat()} {language}: {exc}")
                        continue
                else:
                    result.failures.append(f"{day.isoformat()} {language}: not cached")
                    continue
                try:
                    result.days.append(parse_day(html, day, language, url))
                except ValueError as exc:
                    result.failures.append(f"{day.isoformat()} {language}: {exc}")
        return result
