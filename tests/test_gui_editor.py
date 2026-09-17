from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTextEdit

from orthodox_calendar.database.database import Database
from orthodox_calendar.models import CalendarDay, Saint, ServiceRank, ServiceRankInfo
from orthodox_calendar.ui.calendar_editor import CalendarEditor, FullTextEditDialog, SaintCheckboxList


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


def test_primary_and_additional_saints_use_matching_visible_checkbox_lists(qtbot, tmp_path):
    db = Database(tmp_path / "calendar.sqlite3"); db.initialize()
    day = CalendarDay(
        date(2027, 1, 1), date(2026, 12, 19),
        saints=[
            Saint(1, "Primary", "Primary saint", date(2027, 1, 1), selected=True),
            Saint(2, "Additional", "A long additional saint name", date(2027, 1, 1), selected=True),
        ],
        primary_saint_id="id:1", default_primary_saint_id="id:1",
    )
    editor = CalendarEditor([day], db); qtbot.addWidget(editor)
    assert isinstance(editor.primary_saint, SaintCheckboxList)
    assert isinstance(editor.saints, SaintCheckboxList)
    assert editor.primary_saint.objectName() == editor.saints.objectName() == "saintCheckboxList"
    assert editor.primary_saint.count() == editor.saints.count() == 2
    assert editor.primary_saint.item(0).checkState() == Qt.Checked
    assert editor.primary_saint.item(1).checkState() == Qt.Unchecked
    editor.primary_saint.item(1).setCheckState(Qt.Checked)
    assert editor.primary_saint.item(0).checkState() == Qt.Unchecked
    assert editor.primary_saint.item(1).checkState() == Qt.Checked
    assert editor.saints.item(1).checkState() == Qt.Checked
    assert "border: 2px solid #4F5963" in editor.styleSheet()
    assert "editor-check.svg" in editor.styleSheet()


def test_full_text_double_click_editor_is_wide_wrapped_and_visibly_highlighted(qtbot, tmp_path, monkeypatch):
    db = Database(tmp_path / "calendar.sqlite3"); db.initialize()
    original = "Saint with a name long enough to exceed the old inline editing width"
    replacement = original + " and this complete suffix must remain visible and untruncated"
    day = CalendarDay(date(2027, 1, 1), date(2026, 12, 19), saints=[Saint(1, "Saint", original, date(2027, 1, 1), selected=True)])
    editor = CalendarEditor([day], db); qtbot.addWidget(editor)
    dialog = FullTextEditDialog("Edit Saint", replacement, editor); qtbot.addWidget(dialog)
    assert dialog.minimumWidth() >= 720
    assert dialog.editor.lineWrapMode() == QTextEdit.WidgetWidth
    assert dialog.editor.toPlainText() == replacement
    assert "border: 3px solid #2474B5" in dialog.styleSheet()
    monkeypatch.setattr(FullTextEditDialog, "get_text", classmethod(lambda cls, parent, title, text: (replacement, True)))
    editor._edit_saint_item(editor.saints.item(0))
    assert editor.saints.item(0).text() == replacement
    assert editor.primary_saint.item(0).text() == replacement
    assert editor.saints.textElideMode() == Qt.ElideNone
