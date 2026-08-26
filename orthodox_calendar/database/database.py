from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

from orthodox_calendar.models import Feast, FeastRank, FastLevel, Fasting, Saint, ServiceRank, ServiceRankInfo, Source
from orthodox_calendar.service_ranks import labels_for


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with self.connect() as db:
            db.executescript(schema)
            columns = {row[1] for row in db.execute("PRAGMA table_info(fasting_records)")}
            if "language" not in columns:
                db.execute("ALTER TABLE fasting_records ADD COLUMN language TEXT NOT NULL DEFAULT 'en'")
            migrations = {
                "saints": {"service_rank": "TEXT NOT NULL DEFAULT 'NONE'", "source_rank_text": "TEXT NOT NULL DEFAULT ''"},
                "feasts": {"service_rank": "TEXT NOT NULL DEFAULT 'NONE'", "source_rank_text": "TEXT NOT NULL DEFAULT ''"},
                "source_day_metadata": {
                    "service_rank": "TEXT NOT NULL DEFAULT 'NO_DATA'", "rank_name_en": "TEXT NOT NULL DEFAULT ''",
                    "rank_name_ru": "TEXT NOT NULL DEFAULT ''", "rank_source_text": "TEXT NOT NULL DEFAULT ''",
                    "rank_source_name": "TEXT NOT NULL DEFAULT ''", "rank_source_url": "TEXT NOT NULL DEFAULT ''",
                    "rank_status": "TEXT NOT NULL DEFAULT 'no_data'",
                },
            }
            for table, additions in migrations.items():
                existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
                for column, declaration in additions.items():
                    if column not in existing:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def _source_id(self, db: sqlite3.Connection, source: Source) -> int:
        db.execute(
            "INSERT OR IGNORE INTO sources(name,url,retrieved_at,source_year,source_version) VALUES(?,?,?,?,?)",
            (source.name, source.url, source.retrieved_at.isoformat() if source.retrieved_at else None, source.source_year, source.version),
        )
        row = db.execute(
            "SELECT id FROM sources WHERE name=? AND url=? AND source_year IS ? AND source_version=?",
            (source.name, source.url, source.source_year, source.version),
        ).fetchone()
        return int(row[0])

    def import_saints(self, year: int, saints: list[dict], source: Source, status: str = "authoritative") -> int:
        if status not in {"authoritative", "partial", "sample"}:
            raise ValueError("Invalid calendar status")
        with self.connect() as db:
            source_id = self._source_id(db, source)
            count = 0
            for record in saints:
                civil = date.fromisoformat(record["civil_date"])
                if civil.year != year:
                    raise ValueError(f"Date {civil} is outside import year {year}")
                cur = db.execute(
                    "INSERT INTO saints(canonical_name,display_name,alternate_names,category,rank,description,language,source_id) VALUES(?,?,?,?,?,?,?,?)",
                    (record["canonical_name"], record.get("display_name", record["canonical_name"]), json.dumps(record.get("alternate_names", [])), record.get("category", "Saint"), record.get("rank", ""), record.get("description", ""), record.get("language", "en"), source_id),
                )
                db.execute("INSERT INTO saint_commemorations(saint_id,civil_date) VALUES(?,?)", (cur.lastrowid, civil.isoformat()))
                count += 1
            db.execute(
                "INSERT INTO calendar_versions(year,status,source_id,imported_at) VALUES(?,?,?,?) ON CONFLICT(year) DO UPDATE SET status=excluded.status,source_id=excluded.source_id,imported_at=excluded.imported_at",
                (year, status, source_id, datetime.now(timezone.utc).isoformat()),
            )
            return count

    @staticmethod
    def _fast_level(text: str) -> FastLevel:
        lowered = text.casefold()
        if "fast-free" in lowered or "поста нет" in lowered:
            return FastLevel.FREE
        if "fish" in lowered or "рыб" in lowered:
            return FastLevel.FISH
        if "oil" in lowered or "еле" in lowered or "масл" in lowered:
            return FastLevel.WINE_OIL
        if "strict" in lowered or "строг" in lowered or "сухояд" in lowered or "воздержан" in lowered or "no food" in lowered:
            return FastLevel.STRICT
        return FastLevel.ORDINARY

    def replace_holy_trinity_year(self, year: int, days, source: Source, complete: bool) -> dict[str, int]:
        """Atomically replace one year's records from the legacy Holy Trinity source."""
        start, end = f"{year:04d}-01-01", f"{year + 1:04d}-01-01"
        with self.connect() as db:
            existing_ids = [row[0] for row in db.execute(
                "SELECT id FROM sources WHERE name=? AND source_year=?", (source.name, year)
            ).fetchall()]
            for source_id in existing_ids:
                saint_ids = [row[0] for row in db.execute(
                    """SELECT s.id FROM saints s JOIN saint_commemorations sc ON sc.saint_id=s.id
                       WHERE s.source_id=? AND sc.civil_date>=? AND sc.civil_date<?""", (source_id, start, end)
                ).fetchall()]
                if saint_ids:
                    db.executemany("DELETE FROM saints WHERE id=?", ((item,) for item in saint_ids))
                db.execute("DELETE FROM feasts WHERE source_id=? AND civil_date>=? AND civil_date<?", (source_id, start, end))
                db.execute("DELETE FROM fasting_records WHERE source_id=? AND civil_date>=? AND civil_date<?", (source_id, start, end))
                db.execute("DELETE FROM source_day_metadata WHERE source_id=? AND civil_date>=? AND civil_date<?", (source_id, start, end))
            source_id = self._source_id(db, source)
            counts = {"saints": 0, "feasts": 0, "fasting": 0, "days": 0}
            for day in days:
                civil = day.civil_date.isoformat()
                rank_info = day.service_rank_info
                db.execute(
                    """INSERT OR REPLACE INTO source_day_metadata(
                       civil_date,language,liturgical_week,tone,source_url,service_rank,rank_name_en,rank_name_ru,
                       rank_source_text,rank_source_name,rank_source_url,rank_status,source_id)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (civil, day.language, day.liturgical_week, day.tone, day.source_url, rank_info.normalized_rank.value,
                     rank_info.name_en, rank_info.name_ru, rank_info.source_rank_text, source.name,
                     day.source_url, rank_info.status, source_id),
                )
                counts["days"] += 1
                if day.fasting_text:
                    db.execute(
                        "INSERT INTO fasting_records(civil_date,level,period,detail,language,source_id) VALUES(?,?,?,?,?,?)",
                        (civil, self._fast_level(day.fasting_text).value, day.fasting_text, "Source-supplied daily fasting rule", day.language, source_id),
                    )
                    counts["fasting"] += 1
                for entry in day.entries:
                    if entry.is_feast:
                        rank = FeastRank.GREAT.value if entry.service_rank == ServiceRank.GREAT_FEAST else FeastRank.MAJOR.value if entry.service_rank in {ServiceRank.VIGIL, ServiceRank.POLYELEOS} else FeastRank.COMMEMORATION.value
                        db.execute(
                            """INSERT INTO feasts(civil_date,name,rank,description,liturgical_status,service_rank,
                               source_rank_text,language,source_id) VALUES(?,?,?,?,?,?,?,?,?)""",
                            (civil, entry.name, rank, "", f"Holy Trinity Typikon sign {entry.source_rank_text}",
                             entry.service_rank.value, entry.source_rank_text, entry.language, source_id),
                        )
                        counts["feasts"] += 1
                    else:
                        cur = db.execute(
                            """INSERT INTO saints(canonical_name,display_name,category,rank,service_rank,
                               source_rank_text,language,source_id) VALUES(?,?,?,?,?,?,?,?)""",
                            (entry.name, entry.name, "Commemoration", str(entry.rank), entry.service_rank.value,
                             entry.source_rank_text, entry.language, source_id),
                        )
                        db.execute("INSERT INTO saint_commemorations(saint_id,civil_date) VALUES(?,?)", (cur.lastrowid, civil))
                        counts["saints"] += 1
            db.execute(
                "INSERT INTO calendar_versions(year,status,source_id,imported_at) VALUES(?,?,?,?) ON CONFLICT(year) DO UPDATE SET status=excluded.status,source_id=excluded.source_id,imported_at=excluded.imported_at",
                (year, "authoritative" if complete else "partial", source_id, datetime.now(timezone.utc).isoformat()),
            )
            return counts

    def saints_for_year(self, year: int, language: str | None = None) -> dict[date, list[Saint]]:
        result: dict[date, list[Saint]] = {}
        with self.connect() as db:
            query = """SELECT s.*, sc.civil_date, src.name source_name, src.url source_url,
                          COALESCE(o.action,'show') override_action, COALESCE(o.value_json,'{}') override_value
                   FROM saints s JOIN saint_commemorations sc ON sc.saint_id=s.id
                   LEFT JOIN sources src ON src.id=s.source_id
                   LEFT JOIN user_overrides o ON o.entity_type='saint' AND o.entity_id=s.id AND o.civil_date=sc.civil_date
                   WHERE sc.civil_date>=? AND sc.civil_date<?"""
            params: list[object] = [f"{year:04d}-01-01", f"{year + 1:04d}-01-01"]
            if language:
                query += " AND s.language=?"
                params.append(language)
            query += " ORDER BY sc.civil_date,s.display_name"
            rows = db.execute(query, params).fetchall()
        for row in rows:
            override = json.loads(row["override_value"])
            saint = Saint(
                row["id"], row["canonical_name"], override.get("display_name", row["display_name"]),
                date.fromisoformat(row["civil_date"]), row["category"], row["rank"], row["description"], row["language"],
                Source(row["source_name"] or "Unknown", row["source_url"] or ""), row["override_action"] != "hide",
                int(override.get("display_order", 0)), ServiceRank(row["service_rank"]), row["source_rank_text"],
            )
            result.setdefault(saint.commemoration_date, []).append(saint)
        for entries in result.values():
            def rank_value(item):
                try: return int(item.rank)
                except (TypeError, ValueError): return 0
            entries.sort(key=lambda item: (item.display_order, -rank_value(item), item.display_name))
        return result

    def feasts_for_year(self, year: int, language: str = "en") -> dict[date, list[Feast]]:
        result: dict[date, list[Feast]] = {}
        with self.connect() as db:
            rows = db.execute(
                """SELECT f.*,s.name source_name,s.url source_url FROM feasts f
                   LEFT JOIN sources s ON s.id=f.source_id
                   WHERE f.civil_date>=? AND f.civil_date<? AND f.language=? ORDER BY f.civil_date,f.id""",
                (f"{year:04d}-01-01", f"{year + 1:04d}-01-01", language),
            ).fetchall()
        for row in rows:
            item = Feast(row["name"], FeastRank(row["rank"]), row["description"], Source(row["source_name"], row["source_url"]), False, row["liturgical_status"], ServiceRank(row["service_rank"]), row["source_rank_text"])
            result.setdefault(date.fromisoformat(row["civil_date"]), []).append(item)
        return result

    def fasting_for_year(self, year: int, language: str = "en") -> dict[date, Fasting]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT f.*,s.name source_name,s.url source_url FROM fasting_records f
                   LEFT JOIN sources s ON s.id=f.source_id WHERE f.civil_date>=? AND f.civil_date<? AND f.language=? ORDER BY f.id""",
                (f"{year:04d}-01-01", f"{year + 1:04d}-01-01", language),
            ).fetchall()
        return {date.fromisoformat(row["civil_date"]): Fasting(FastLevel(row["level"]), row["period"], row["detail"], Source(row["source_name"], row["source_url"])) for row in rows}

    def day_metadata_for_year(self, year: int, language: str = "en") -> dict[date, tuple[str, int | None, ServiceRankInfo]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT civil_date,liturgical_week,tone,service_rank,rank_name_en,rank_name_ru,
                   rank_source_text,rank_source_name,rank_source_url,rank_status
                   FROM source_day_metadata WHERE civil_date>=? AND civil_date<? AND language=?""",
                (f"{year:04d}-01-01", f"{year + 1:04d}-01-01", language),
            ).fetchall()
            override_rows = db.execute(
                "SELECT civil_date,value_json FROM user_overrides WHERE entity_type='service_rank' AND civil_date>=? AND civil_date<? ORDER BY id",
                (f"{year:04d}-01-01", f"{year + 1:04d}-01-01"),
            ).fetchall()
        overrides = {row["civil_date"]: json.loads(row["value_json"]) for row in override_rows}
        result = {}
        for row in rows:
            rank = ServiceRank(row["service_rank"]); name_en, name_ru = labels_for(rank)
            info = ServiceRankInfo(rank, row["rank_name_en"] or name_en, row["rank_name_ru"] or name_ru,
                                   row["rank_source_name"], row["rank_source_url"], row["rank_source_text"], row["rank_status"])
            if override := overrides.get(row["civil_date"]):
                override_rank = ServiceRank(override["normalized_rank"]); override_en, override_ru = labels_for(override_rank)
                info = ServiceRankInfo(override_rank, override_en, override_ru, info.source_name, info.source_url,
                                       info.source_rank_text, "user_override", True)
            result[date.fromisoformat(row["civil_date"])] = (row["liturgical_week"], row["tone"], info)
        return result

    def set_service_rank_override(self, civil_date: date, rank: ServiceRank | None) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM user_overrides WHERE civil_date=? AND entity_type='service_rank'", (civil_date.isoformat(),))
            if rank is not None:
                value = json.dumps({"normalized_rank": rank.value})
                db.execute(
                    "INSERT INTO user_overrides(civil_date,entity_type,action,value_json,created_at) VALUES(?,'service_rank','override',?,?)",
                    (civil_date.isoformat(), value, datetime.now(timezone.utc).isoformat()),
                )

    def set_saint_override(self, civil_date: date, saint_id: int, selected: bool, display_name: str, order: int) -> None:
        value = json.dumps({"display_name": display_name, "display_order": order}, ensure_ascii=False)
        with self.connect() as db:
            db.execute("DELETE FROM user_overrides WHERE civil_date=? AND entity_type='saint' AND entity_id=?", (civil_date.isoformat(), saint_id))
            db.execute(
                "INSERT INTO user_overrides(civil_date,entity_type,entity_id,action,value_json,created_at) VALUES(?,'saint',?,?,?,?)",
                (civil_date.isoformat(), saint_id, "show" if selected else "hide", value, datetime.now(timezone.utc).isoformat()),
            )

    def has_authoritative_year(self, year: int) -> bool:
        with self.connect() as db:
            row = db.execute("SELECT status FROM calendar_versions WHERE year=?", (year,)).fetchone()
        return bool(row and row[0] == "authoritative")

    def stats(self) -> dict[str, int]:
        tables = ("saints", "feasts", "fasting_records", "public_holidays", "conflicts")
        with self.connect() as db:
            result = {table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}
            result["calendar_days"] = int(db.execute("SELECT COUNT(DISTINCT civil_date) FROM saint_commemorations").fetchone()[0])
        return result

    def record_sync(self, name: str, success: bool, message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                """INSERT INTO sync_metadata(source_name,last_attempt,last_success,status,message) VALUES(?,?,?,?,?)
                   ON CONFLICT(source_name) DO UPDATE SET last_attempt=excluded.last_attempt,
                   last_success=CASE WHEN excluded.status='Available' THEN excluded.last_attempt ELSE sync_metadata.last_success END,
                   status=excluded.status,message=excluded.message""",
                (name, now, now if success else None, "Available" if success else "Offline / unavailable", message),
            )

    def source_status(self) -> list[sqlite3.Row]:
        with self.connect() as db:
            return db.execute("SELECT * FROM sync_metadata ORDER BY source_name").fetchall()
