from datetime import date

from orthodox_calendar.database.database import Database
from orthodox_calendar.services.conflicts import ConflictService


def test_conflicts_are_stored_not_silently_merged(tmp_path):
    db = Database(tmp_path / "db.sqlite3"); db.initialize(); service = ConflictService(db)
    assert service.detect(date(2027, 1, 1), "saint", [{"name": "A"}], [{"name": "B"}])
    assert db.stats()["conflicts"] == 1
    assert not service.detect(date(2027, 1, 2), "saint", [{"name": "A"}], [{"name": "A"}])

