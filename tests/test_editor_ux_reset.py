import copy
from datetime import date
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox, QScrollArea

from orthodox_calendar.calendar_engine.orthodox_calendar import OrthodoxCalendarEngine
from orthodox_calendar.config import Settings, SettingsStore
from orthodox_calendar.database.database import Database
from orthodox_calendar.models import CalendarDay, Saint, ServiceRank, ServiceRankInfo
from orthodox_calendar.projects import CalendarProject, ProjectSettings, ProjectStore
from orthodox_calendar.rendering.pdf_renderer import PdfRenderer
from orthodox_calendar.service_ranks import RANK_ICON_NAMES, icon_name_for
from orthodox_calendar.ui.calendar_editor import CalendarEditor
from orthodox_calendar.ui.main_window import DayCell, InteractiveMonthCard, MainWindow


def make_project() -> CalendarProject:
    days = OrthodoxCalendarEngine().generate_year(2027, "Queensland")
    for index, civil_date in enumerate((date(2027, 1, 7), date(2027, 1, 15), date(2027, 2, 3), date(2027, 7, 4))):
        day = next(item for item in days if item.civil_date == civil_date)
        day.saints = [Saint(8000 + index, f"Source {index}", f"Source Saint {index}", civil_date)]
        day.service_rank = ServiceRankInfo(ServiceRank.POLYELEOS, "Polyeleos", "Полиелейная служба")
    project = CalendarProject.create("UX Test", ProjectSettings(2027, "Queensland"), days, "2027.test")
    for civil_date in (date(2027, 1, 7), date(2027, 1, 15), date(2027, 2, 3), date(2027, 7, 4)):
        day = next(item for item in project.resolve_days() if item.civil_date == civil_date)
        day.notes = [f"Edited {civil_date.isoformat()}"]; project.update_day(day)
    return project


def test_day_cell_hover_preserves_semantic_background_and_double_click(qtbot):
    day = CalendarDay(date(2027, 1, 7), date(2026, 12, 25), service_rank=ServiceRankInfo(ServiceRank.GREAT_FEAST, "Great Feast", ""))
    cell = DayCell(day); qtbot.addWidget(cell); opened = []
    cell.editRequested.connect(opened.append); initial = cell.styleSheet()
    assert "#F8CACA" in initial and cell.rank_text == "Great Feast" and not cell.icon().isNull()
    QApplication.sendEvent(cell, QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
    assert cell.hovered and "#F8CACA" in cell.styleSheet() and "#2474B5" in cell.styleSheet()
    qtbot.mouseDClick(cell, Qt.LeftButton)
    assert opened == [date(2027, 1, 7)]


def test_month_card_has_only_real_date_cells_and_exact_last_day(qtbot):
    days = OrthodoxCalendarEngine().generate_year(2027, "Queensland")
    card = InteractiveMonthCard(2); qtbot.addWidget(card); card.populate(2027, days); opened = []
    card.editRequested.connect(opened.append)
    assert len(card.day_cells) == 28 and max(card.day_cells) == date(2027, 2, 28)
    qtbot.mouseDClick(card.day_cells[date(2027, 2, 28)], Qt.LeftButton)
    assert opened == [date(2027, 2, 28)]


def test_editor_is_resizable_scrollable_collapsible_and_shows_rank_icon_text(qtbot):
    project = make_project(); resolved = project.resolve_days(); target = date(2027, 1, 7)
    editor = CalendarEditor(resolved, initial_date=target, source_day_provider=project.source_day); qtbot.addWidget(editor)
    assert editor.current.civil_date == target and target.strftime("%B %d, %Y") in editor.windowTitle()
    assert editor.windowFlags() & Qt.WindowMinMaxButtonsHint
    assert editor.findChildren(QScrollArea) and editor.save_button.text() == "Save Edits" and editor.cancel_button.text() == "Cancel"
    assert editor.rank_text.text() == "Polyeleos" and editor.rank_icon.pixmap() and not editor.rank_icon.pixmap().isNull()
    editor.resize(700, 500); assert editor.size().width() >= 700 and editor.size().height() >= 500
    editor.set_all_sections(False); assert all(not section.content.isVisible() for section in editor.sections)
    editor.set_all_sections(True); assert all(section.header.isChecked() for section in editor.sections)
    assert "QComboBox QAbstractItemView" in editor.styleSheet() and "color: #111111" in editor.styleSheet()


def test_editor_cancel_discards_transaction_and_reset_commits_only_on_save(qtbot, monkeypatch):
    project = make_project(); target = date(2027, 1, 7); original = copy.deepcopy(project.overrides[target.isoformat()]); edits = []
    editor = CalendarEditor(project.resolve_days(), on_project_edit=lambda day, primary: edits.append(day), initial_date=target, source_day_provider=project.source_day, on_project_reset=project.reset_day)
    qtbot.addWidget(editor); editor.custom_note.setPlainText("Unsaved editor note")
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Discard)
    editor.reject()
    assert edits == [] and project.overrides[target.isoformat()] == original

    editor = CalendarEditor(project.resolve_days(), on_project_edit=lambda day, primary: project.update_day(day, primary), initial_date=target, source_day_provider=project.source_day, on_project_reset=project.reset_day)
    qtbot.addWidget(editor); monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Reset)
    editor.reset_day()
    assert target.isoformat() in project.overrides and editor.custom_note.toPlainText() == ""
    editor.save_overrides()
    assert target.isoformat() not in project.overrides


def test_project_reset_day_month_year_remove_only_overrides_and_keep_snapshot():
    project = make_project(); snapshot = copy.deepcopy(project.source_snapshot)
    assert project.reset_day(date(2027, 1, 7)) and date(2027, 1, 15).isoformat() in project.overrides
    removed = project.reset_month(2027, 1)
    assert removed == [date(2027, 1, 15).isoformat()]
    assert date(2027, 2, 3).isoformat() in project.overrides and date(2027, 7, 4).isoformat() in project.overrides
    removed = project.reset_year(2027)
    assert removed == [date(2027, 2, 3).isoformat(), date(2027, 7, 4).isoformat()]
    assert project.overrides == {} and project.source_snapshot == snapshot and project.modified


def test_reset_round_trip_persists_and_source_database_is_unchanged(tmp_path):
    project = make_project(); db = Database(tmp_path / "source.sqlite3"); db.initialize(); before = db.stats()
    project.reset_month(2027, 1); path = ProjectStore(tmp_path / "recovery").save(project, tmp_path / "reset.rocproject")
    reopened = ProjectStore().load(path)
    assert date(2027, 1, 7).isoformat() not in reopened.overrides and date(2027, 2, 3).isoformat() in reopened.overrides
    assert db.stats() == before


def test_central_rank_icon_mapping_is_shared_by_pdf_and_gui():
    for rank, expected in RANK_ICON_NAMES.items():
        info = ServiceRankInfo(rank, "", ""); day = CalendarDay(date(2027, 1, 1), date(2026, 12, 19), service_rank=info)
        assert icon_name_for(info) == expected and PdfRenderer.rank_icon_name(day) == expected


def test_every_supported_rank_has_icon_and_text_in_viewer_and_editor(qtbot):
    for index, rank in enumerate(RANK_ICON_NAMES, 1):
        info = ServiceRankInfo(rank, "", ""); day = CalendarDay(date(2027, 1, index), date(2026, 12, 18 + index), service_rank=info)
        cell = DayCell(day); qtbot.addWidget(cell)
        assert cell.rank_text and not cell.icon().isNull()
        editor = CalendarEditor([day], initial_date=day.civil_date); qtbot.addWidget(editor)
        assert editor.rank_text.text() and editor.rank_icon.pixmap() and not editor.rank_icon.pixmap().isNull()


def test_main_window_reset_cancel_and_save_confirmation(qtbot, tmp_path, monkeypatch):
    project = make_project(); path = ProjectStore(tmp_path / "recovery").save(project, tmp_path / "ux.rocproject")
    db = Database(tmp_path / "calendar.sqlite3"); db.initialize(); settings = Settings(default_year=2027)
    window = MainWindow(db, settings, SettingsStore(tmp_path / "settings.json"), path, check_data_updates=False); qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.project is not None, timeout=5000); window.autosave_timer.stop(); target = date(2027, 1, 7); window.select_day(target)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Cancel)
    assert not window.reset_day(target) and target.isoformat() in window.project.overrides
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Reset)
    assert window.reset_day(target) and target.isoformat() not in window.project.overrides and window.project.modified
    messages = []; monkeypatch.setattr(QMessageBox, "information", lambda _parent, title, text: messages.append((title, text)))
    assert window.save_project() and not window.project.modified
    assert messages and messages[-1][0] == "Project Saved" and "Saved successfully" in messages[-1][1]


def test_main_window_month_and_year_reset_scopes_and_typed_confirmation(qtbot, tmp_path, monkeypatch):
    project = make_project(); path = ProjectStore(tmp_path / "recovery").save(project, tmp_path / "scopes.rocproject")
    db = Database(tmp_path / "calendar.sqlite3"); db.initialize()
    window = MainWindow(db, Settings(default_year=2027), SettingsStore(tmp_path / "settings.json"), path, check_data_updates=False)
    qtbot.addWidget(window); qtbot.waitUntil(lambda: window.project is not None, timeout=5000); window.autosave_timer.stop()

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Reset)
    assert window.reset_month(1)
    assert date(2027, 1, 7).isoformat() not in window.project.overrides
    assert date(2027, 2, 3).isoformat() in window.project.overrides

    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("RESET 2026", True))
    assert not window.reset_current_year() and window.project.overrides
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("RESET 2027", True))
    assert window.reset_current_year() and window.project.overrides == {}
