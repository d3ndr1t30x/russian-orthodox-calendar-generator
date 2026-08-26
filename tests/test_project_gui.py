from datetime import date

from PySide6.QtCore import Qt

from orthodox_calendar.calendar_engine.orthodox_calendar import OrthodoxCalendarEngine
from orthodox_calendar.models import Saint
from orthodox_calendar.projects import CalendarProject, ProjectSettings
from orthodox_calendar.ui.calendar_editor import CalendarEditor
from orthodox_calendar.ui.project_dialogs import NewProjectDialog


def test_new_project_dialog_defaults_to_current_gregorian_year(qtbot):
    dialog = NewProjectDialog(); qtbot.addWidget(dialog)
    assert dialog.year.value() == date.today().year
    dialog.year.setValue(2029); dialog.state.setCurrentText("Queensland"); dialog.language.setCurrentText("Russian")
    settings = dialog.project_settings()
    assert settings.year == 2029 and settings.jurisdiction == "Queensland" and settings.language == "Russian"


def test_editor_commits_to_project_without_database_writes(qtbot):
    days = OrthodoxCalendarEngine().generate_year(2027, "Queensland"); target = days[0]
    target.saints = [Saint(1, "A", "Saint A", target.civil_date), Saint(2, "B", "Saint B", target.civil_date)]
    project = CalendarProject.create("Test", ProjectSettings(2027, "Queensland"), days, "test")
    resolved = project.resolve_days(); edits = []
    editor = CalendarEditor(resolved, None, on_project_edit=lambda day, primary: (project.update_day(day, primary), edits.append(day.civil_date)))
    qtbot.addWidget(editor); editor.saints.item(0).setCheckState(Qt.Unchecked); editor.custom_note.setPlainText("Project-only note"); editor.save_overrides()
    restored = project.resolve_days()[0]
    assert edits == [date(2027, 1, 1)] and not restored.saints[0].selected and restored.notes == ["Project-only note"]
