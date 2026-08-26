from datetime import date

from PySide6.QtCore import Qt

from orthodox_calendar.database.database import Database
from orthodox_calendar.models import CalendarDay, Saint, ServiceRank, ServiceRankInfo
from orthodox_calendar.ui.calendar_editor import CalendarEditor


def test_editor_is_light_and_saint_checkbox_states_are_obvious(qtbot, tmp_path):
    db = Database(tmp_path / "calendar.sqlite3"); db.initialize()
    day = CalendarDay(
        date(2027, 1, 1), date(2026, 12, 19),
        saints=[
            Saint(1, "Primary", "Primary saint", date(2027, 1, 1), selected=True),
            Saint(2, "Optional", "Optional saint", date(2027, 1, 1), selected=False),
        ], service_rank=ServiceRankInfo(ServiceRank.POLYELEOS, "Polyeleos", "Полиелейная служба", "Test Source", "https://example/rank", "4", "source_mapped"),
    )
    editor = CalendarEditor([day], db); qtbot.addWidget(editor)
    assert "background: #FAFAFA" in editor.styleSheet()
    assert "color: #111111" in editor.styleSheet()
    assert editor.saints.item(0).checkState() == Qt.Checked
    assert editor.saints.item(0).font().bold()
    assert editor.saints.item(1).checkState() == Qt.Unchecked
    assert editor.saints.item(1).foreground().color().name() == "#777777"

    editor.saints.item(1).setCheckState(Qt.Checked)
    assert editor.saints.item(1).foreground().color().name() == "#185c37"
    editor.saints.item(0).setCheckState(Qt.Unchecked)
    assert editor.saints.item(1).font().bold()

    editor.selection_filter.setCurrentText("Unselected")
    assert not editor.saints.item(0).isHidden()
    assert editor.saints.item(1).isHidden()
    assert "Source rank: 4" in editor.rank_provenance.text()
    assert "Полиелейная служба" in editor.rank_provenance.text()
    editor.service_rank.setCurrentIndex(editor.service_rank.findData(ServiceRank.DOXOLOGY.value))
    editor.save_overrides()
    override = db.connect()
    with override as connection:
        row = connection.execute("SELECT value_json FROM user_overrides WHERE entity_type='service_rank'").fetchone()
    assert "DOXOLOGY" in row[0]
