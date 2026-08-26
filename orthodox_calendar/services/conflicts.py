from __future__ import annotations

import json
from datetime import date

from orthodox_calendar.database.database import Database


class ConflictService:
    def __init__(self, database: Database):
        self.database = database

    def detect(self, civil_date: date, entity_type: str, primary: list[dict], secondary: list[dict]) -> bool:
        if primary == secondary:
            return False
        with self.database.connect() as db:
            db.execute(
                "INSERT INTO conflicts(civil_date,entity_type,primary_json,secondary_json) VALUES(?,?,?,?)",
                (civil_date.isoformat(), entity_type, json.dumps(primary, ensure_ascii=False), json.dumps(secondary, ensure_ascii=False)),
            )
        return True

