"""Render viewer/editor screenshots and exercise responsive controls for visual QA."""
from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from orthodox_calendar.config import Settings, SettingsStore
from orthodox_calendar.database.database import Database
from orthodox_calendar.ui.calendar_editor import CalendarEditor
from orthodox_calendar.ui.main_window import MainWindow
from orthodox_calendar.ui.styles import APP_STYLESHEET


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path("tests/fixtures/sample_calendar.rocproject"))
    parser.add_argument("--output", type=Path, default=Path("output/visual"))
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([]); app.setStyleSheet(APP_STYLESHEET)
    with tempfile.TemporaryDirectory(prefix="roc-gui-smoke-") as temporary:
        root = Path(temporary); database = Database(root / "calendar.sqlite3"); database.initialize()
        window = MainWindow(database, Settings(default_year=2027), SettingsStore(root / "settings.json"), args.project.resolve(), check_data_updates=False)
        window.show(); deadline = time.monotonic() + 8
        while window.project is None and time.monotonic() < deadline:
            app.processEvents(); time.sleep(.02)
        if window.project is None: raise RuntimeError("Project did not open")
        target = next(iter(window.project.override_dates()))
        window.select_day(target); cell = window.month_cards[target.month - 1].day_cells[target]; cell.hovered = True; cell._apply_style()
        window.resize(1250, 860); app.processEvents(); window.grab().save(str(args.output / "calendar-viewer.png"))
        editor = CalendarEditor(window.days, initial_date=target, source_day_provider=window.project.source_day)
        editor.show(); editor.resize(900, 650); app.processEvents(); editor.grab().save(str(args.output / "day-editor.png"))
        editor.service_rank.showPopup(); app.processEvents(); editor.service_rank.view().grab().save(str(args.output / "service-rank-dropdown.png")); editor.service_rank.hidePopup()
        editor.resize(700, 500); editor.set_all_sections(False); app.processEvents(); editor.grab().save(str(args.output / "day-editor-minimum-collapsed.png"))
        editor.close(); window.project.modified = False; window.close(); app.processEvents()
    print((args.output / "calendar-viewer.png").resolve()); print((args.output / "day-editor.png").resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
