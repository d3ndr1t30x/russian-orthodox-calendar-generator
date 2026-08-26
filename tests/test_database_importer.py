import json
from datetime import date

from orthodox_calendar.data_sources.importer import CalendarImporter
from orthodox_calendar.database.database import Database


def test_import_retrieve_and_override(tmp_path):
    db = Database(tmp_path / "calendar.sqlite3"); db.initialize()
    payload = {"saints": [
        {"civil_date": "2027-01-07", "canonical_name": "Saint Test", "display_name": "Святой Тест", "language": "ru"},
        {"civil_date": "2027-01-07", "canonical_name": "Another Saint", "category": "Martyr"},
    ]}
    source_file = tmp_path / "source.json"; source_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    result = CalendarImporter(db).import_file(source_file, 2027, "Verified test source", "https://example.invalid")
    assert result.count == 2 and db.has_authoritative_year(2027)
    saints = db.saints_for_year(2027)[date(2027, 1, 7)]
    assert len(saints) == 2 and any(s.display_name == "Святой Тест" for s in saints)
    target = saints[0]; db.set_saint_override(target.commemoration_date, target.id, False, "Edited name", 4)
    updated = next(s for s in db.saints_for_year(2027)[date(2027, 1, 7)] if s.id == target.id)
    assert not updated.selected and updated.display_name == "Edited name" and updated.display_order == 4


def test_rejects_wrong_year(tmp_path):
    db = Database(tmp_path / "db.sqlite3"); db.initialize()
    source = tmp_path / "bad.json"; source.write_text('[{"civil_date":"2028-01-01","canonical_name":"X"}]')
    try:
        CalendarImporter(db).import_file(source, 2027, "test")
    except ValueError as exc:
        assert "outside import year" in str(exc)
    else:
        raise AssertionError("Wrong-year record was accepted")

