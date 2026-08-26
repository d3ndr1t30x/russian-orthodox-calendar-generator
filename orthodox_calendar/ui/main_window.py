from __future__ import annotations

import calendar
import logging
from dataclasses import asdict
from datetime import date
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QProgressDialog, QPushButton, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
)

from orthodox_calendar.calendar_engine.australian_holidays import JURISDICTIONS
from orthodox_calendar.calendar_engine.orthodox_calendar import OrthodoxCalendarEngine
from orthodox_calendar.config import Settings, SettingsStore
from orthodox_calendar.data_sources.importer import CalendarImporter
from orthodox_calendar.database.database import Database
from orthodox_calendar.models import CalendarDay, FastLevel
from orthodox_calendar.paths import ensure_user_dirs
from orthodox_calendar.projects import CalendarProject, ProjectSettings, ProjectStore, ProjectValidationError
from orthodox_calendar.rendering.pdf_renderer import PdfOptions, PdfRenderer
from orthodox_calendar.services.synchronization import SynchronizationService
from .calendar_editor import CalendarEditor
from .preview import PreviewDialog
from .project_dialogs import NewProjectDialog
from .settings import SettingsDialog
from .source_dialog import SourceDialog


LOG = logging.getLogger(__name__)


class MonthCard(QGroupBox):
    def __init__(self, month: int):
        super().__init__(calendar.month_name[month]); self.month = month
        self.label = QLabel(); self.label.setTextFormat(Qt.RichText); self.label.setAlignment(Qt.AlignTop | Qt.AlignHCenter); self.label.setStyleSheet("font-family: Consolas, monospace; font-size: 8pt; line-height: 120%;")
        layout = QVBoxLayout(self); layout.addWidget(self.label)

    def populate(self, year: int, days: list[CalendarDay]) -> None:
        by_number = {day.civil_date.day: day for day in days if day.civil_date.month == self.month}
        rows = ["<table cellspacing='2' width='100%'><tr>" + "".join(f"<th>{x}</th>" for x in "S M T W T F S".split()) + "</tr>"]
        for week in calendar.Calendar(firstweekday=6).monthdayscalendar(year, self.month):
            cells = []
            for number in week:
                if not number or number not in by_number: cells.append("<td>&nbsp;</td>"); continue
                day = by_number[number]; marks = ("†" if day.feasts else "") + ("◆" if day.public_holidays else "") + ("·" if day.fasting and day.fasting.level != FastLevel.FREE else "")
                color = "#8b1e2d" if day.civil_date.weekday() == 6 or any(f.rank.value == "Great Feast" for f in day.feasts) else "#2c2723"
                cells.append(f"<td align='center'><span style='color:{color};font-weight:600'>{number}</span><sup>{marks}</sup></td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        rows.append("</table>"); self.label.setText("".join(rows))


class MainWindow(QMainWindow):
    def __init__(self, database: Database, settings: Settings, store: SettingsStore, initial_project: Path | None = None, check_data_updates: bool = True):
        super().__init__()
        self.database, self.settings, self.store = database, settings, store
        self.check_data_updates = check_data_updates
        self.engine, self.renderer = OrthodoxCalendarEngine(database), PdfRenderer()
        paths = ensure_user_dirs(); self.project_store = ProjectStore(paths["cache"] / "recovery")
        self.project: CalendarProject | None = None; self.days: list[CalendarDay] = []; self._loading_ui = False
        self.resize(1250, 860); self.setMinimumSize(960, 680)
        self._build_actions(); self._build_menu(); self._build_toolbar(); self._build_ui(); self._connect_controls()
        self.autosave_timer = QTimer(self); self.autosave_timer.setInterval(30_000); self.autosave_timer.timeout.connect(self.autosave_project); self.autosave_timer.start()
        if initial_project:
            QTimer.singleShot(0, lambda: self.open_project_path(initial_project))
        else:
            QTimer.singleShot(0, self._recover_untitled_or_load)
        self._update_project_ui()

    def _recover_untitled_or_load(self) -> None:
        directory = self.project_store.recovery_directory
        candidates = sorted(directory.glob("untitled-*.rocproject.recovery"), key=lambda item: item.stat().st_mtime, reverse=True) if directory and directory.exists() else []
        if not candidates:
            self.load_calendar(); return
        latest = candidates[0]
        answer = QMessageBox.question(self, "Recover unsaved project", "An unsaved project recovery was found. Recover it?", QMessageBox.Yes | QMessageBox.No)
        if answer == QMessageBox.Yes:
            try:
                self.project = self.project_store.load(latest); self.project.file_path = ""; self.project.modified = True
                self.days = self.project.resolve_days(); self._set_controls_from_project(); self._populate_months(); self._update_project_ui("Recovered unsaved project")
                LOG.info("Project recovered: %s", self.project.project_id); return
            except Exception as exc:
                QMessageBox.warning(self, "Recovery failed", str(exc))
        latest.unlink(missing_ok=True); self.load_calendar()

    def _build_actions(self) -> None:
        self.new_action = QAction("New Project", self, shortcut="Ctrl+N", triggered=self.new_project)
        self.open_action = QAction("Open Project...", self, shortcut="Ctrl+O", triggered=self.open_project)
        self.save_action = QAction("Save Project", self, shortcut="Ctrl+S", triggered=self.save_project)
        self.save_as_action = QAction("Save Project As...", self, shortcut="Ctrl+Shift+S", triggered=self.save_project_as)
        self.close_project_action = QAction("Close Project", self, shortcut="Ctrl+W", triggered=self.close_project)
        self.project_info_action = QAction("Project Information", self, triggered=self.show_project_information)
        self.export_action = QAction("Export PDF...", self, triggered=self.generate_pdf)
        self.exit_action = QAction("Exit", self, triggered=self.close)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        for action in (self.new_action, self.open_action, self.save_action, self.save_as_action, self.close_project_action): file_menu.addAction(action)
        self.recent_menu = file_menu.addMenu("Recent Projects"); file_menu.addAction(self.project_info_action); file_menu.addSeparator(); file_menu.addAction(self.export_action); file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        self._rebuild_recent_menu()

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Main"); toolbar.setMovable(False)
        for action in (self.new_action, self.open_action, self.save_action, self.export_action): toolbar.addAction(action)
        toolbar.addSeparator()
        for title, slot in (("Preview", self.preview_pdf), ("Edit Calendar", self.edit_calendar), ("Import Data", self.import_data), ("Update Data", self.update_data), ("Sources", self.show_sources), ("Settings", self.show_settings), ("About", self.about)):
            action = QAction(title, self); action.triggered.connect(slot); toolbar.addAction(action)

    def _build_ui(self) -> None:
        central = QWidget(); root = QVBoxLayout(central); root.setContentsMargins(18, 16, 18, 16)
        heading = QLabel("RUSSIAN ORTHODOX CALENDAR"); heading.setStyleSheet("font-size: 22pt; font-weight: 700; color: #782535; letter-spacing: 1px")
        self.project_status = QLabel(); self.project_status.setStyleSheet("background:#ffffff;border:1px solid #c7c0b8;padding:7px;color:#322b27")
        root.addWidget(heading); root.addWidget(self.project_status)
        controls = QGroupBox("Calendar publication"); form = QGridLayout(controls)
        self.year = QSpinBox(); self.year.setRange(1583, 4099); self.year.setValue(self.settings.effective_year)
        previous, current, next_button = QPushButton("Previous"), QPushButton("Current"), QPushButton("Next")
        previous.clicked.connect(lambda: self.year.setValue(self.year.value() - 1)); current.clicked.connect(lambda: self.year.setValue(date.today().year)); next_button.clicked.connect(lambda: self.year.setValue(self.year.value() + 1))
        year_row = QHBoxLayout(); year_row.addWidget(self.year); year_row.addWidget(previous); year_row.addWidget(current); year_row.addWidget(next_button)
        self.state = QComboBox(); self.state.addItems(JURISDICTIONS.keys()); self.state.setCurrentText(self.settings.jurisdiction)
        self.language = QComboBox(); self.language.addItems(["English", "Russian"]); self.language.setCurrentText(self.settings.language)
        self.template = QComboBox(); self.template.addItems(["Traditional", "Minimal", "Parish"]); self.template.setCurrentText(self.settings.template)
        self.orientation = QComboBox(); self.orientation.addItems(["Landscape", "Portrait"]); self.orientation.setCurrentText(self.settings.orientation)
        refresh = QPushButton("Load Calendar"); refresh.clicked.connect(self.load_calendar)
        form.addWidget(QLabel("Modern Gregorian year"), 0, 0); form.addLayout(year_row, 1, 0); form.addWidget(QLabel("Australian state / territory"), 0, 1); form.addWidget(self.state, 1, 1); form.addWidget(QLabel("Calendar language"), 0, 2); form.addWidget(self.language, 1, 2); form.addWidget(QLabel("Template"), 0, 3); form.addWidget(self.template, 1, 3); form.addWidget(QLabel("A4 orientation"), 0, 4); form.addWidget(self.orientation, 1, 4); form.addWidget(refresh, 1, 5)
        root.addWidget(controls)
        self.notice = QLabel(); self.notice.setWordWrap(True); self.notice.setStyleSheet("background:#fff4cf;border:1px solid #ddbd58;border-radius:5px;padding:8px;color:#594910"); root.addWidget(self.notice)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); content = QWidget(); content.setObjectName("annualContent"); content.setStyleSheet("#annualContent { background-color: #f4f1eb; }"); self.month_grid = QGridLayout(content); self.month_cards = []
        for month in range(1, 13):
            card = MonthCard(month); self.month_cards.append(card); self.month_grid.addWidget(card, (month - 1) // 4, (month - 1) % 4)
        scroll.setWidget(content); root.addWidget(scroll, 1); self.setCentralWidget(central); self.statusBar().showMessage("Ready")

    def _connect_controls(self) -> None:
        self.year.valueChanged.connect(self._controls_changed)
        for widget in (self.state, self.language, self.template, self.orientation): widget.currentTextChanged.connect(self._controls_changed)

    def _controls_changed(self, *_args) -> None:
        if self._loading_ui or not self.project: return
        self.project.mark_modified(); self._update_project_ui("Configuration changed; use Load Calendar before saving/exporting.")

    def _settings_from_controls(self) -> ProjectSettings:
        base = self.project.settings if self.project else None
        return ProjectSettings(
            self.year.value(), self.state.currentText(), self.language.currentText(), "A4", self.orientation.currentText(), self.template.currentText(),
            include_julian=base.include_julian if base else self.settings.include_julian, include_holidays=base.include_holidays if base else self.settings.include_holidays,
            include_sources=base.include_sources if base else self.settings.include_sources, include_fasting_icons=base.include_fasting_icons if base else self.settings.include_fasting_icons,
            include_fasting_legend=base.include_fasting_legend if base else self.settings.include_fasting_legend, include_service_rank_icons=base.include_service_rank_icons if base else self.settings.include_service_rank_icons,
            include_service_rank_legend=base.include_service_rank_legend if base else self.settings.include_service_rank_legend, rank_labels_en=dict(base.rank_labels_en if base else self.settings.rank_labels_en),
            rank_labels_ru=dict(base.rank_labels_ru if base else self.settings.rank_labels_ru), parish_name=base.parish_name if base else self.settings.parish_name, parish_logo=base.parish_logo if base else self.settings.parish_logo,
            address=base.address if base else self.settings.address, website=base.website if base else self.settings.website, phone=base.phone if base else self.settings.phone,
            custom_header=base.custom_header if base else self.settings.custom_header, custom_footer=base.custom_footer if base else self.settings.custom_footer,
        )

    def _apply_controls_to_project(self, show_warnings: bool = True) -> None:
        if not self.project: return
        new = self._settings_from_controls(); old = self.project.settings
        settings_changed = new != old
        source_changed = (new.year, new.jurisdiction, new.language) != (old.year, old.jurisdiction, old.language)
        self.project.settings = new
        if source_changed:
            current = self.engine.generate_year(new.year, new.jurisdiction, new.language)
            version, sync = self.database.calendar_version(new.year); self.days = self.project.update_source_data(current, version); self.project.last_synchronization_at = sync
            if show_warnings and self.project.missing_references:
                QMessageBox.warning(self, "Project data warning", "Some saved records could not be matched to the new source data and were retained for review:\n\n" + "\n".join(self.project.missing_references[:20]))
        else:
            self.days = self.project.resolve_days()
        if settings_changed and not source_changed:
            self.project.mark_modified()
        self._populate_months()

    def create_project(self, project_settings: ProjectSettings, name: str, require_authoritative: bool = False) -> CalendarProject:
        project_settings.validate()
        if require_authoritative and not self.database.has_authoritative_year(project_settings.year):
            raise ProjectValidationError(f"Calendar data for {project_settings.year} is not currently available")
        days = self.engine.generate_year(project_settings.year, project_settings.jurisdiction, project_settings.language)
        version, sync = self.database.calendar_version(project_settings.year)
        self.project = CalendarProject.create(name, project_settings, days, version, sync); self.days = self.project.resolve_days(); self._set_controls_from_project(); self._populate_months(); self._update_project_ui(); LOG.info("Project created: %s", self.project.project_id)
        return self.project

    def new_project(self) -> None:
        if not self._confirm_project_transition(): return
        dialog = NewProjectDialog(self.settings, self)
        if dialog.exec() != QDialog.Accepted: return
        project_settings = dialog.project_settings(self.settings)
        if not self._ensure_calendar_data(project_settings.year): return
        self.create_project(project_settings, dialog.name.text(), require_authoritative=True)

    def _ensure_calendar_data(self, year: int) -> bool:
        if self.database.has_authoritative_year(year): return True
        box = QMessageBox(self); box.setWindowTitle("Calendar data unavailable"); box.setText(f"Calendar data for {year} is not currently available.")
        sync = box.addButton("Sync Calendar Data", QMessageBox.AcceptRole); imp = box.addButton("Import Data", QMessageBox.ActionRole); box.addButton(QMessageBox.Cancel); box.exec()
        if box.clickedButton() == sync: self._sync_data(year)
        elif box.clickedButton() == imp: self.import_data(year)
        return self.database.has_authoritative_year(year)

    def load_calendar(self) -> None:
        self.statusBar().showMessage("Building calendar...")
        try:
            if self.project:
                self._apply_controls_to_project()
            else:
                self.days = self.engine.generate_year(self.year.value(), self.state.currentText(), self.language.currentText())
            self._populate_months(); loaded = self.database.has_authoritative_year(self.year.value()); self.notice.setVisible(not loaded)
            self.notice.setText("CALENDAR DATA NOT AVAILABLE: authoritative annual saint commemorations have not been imported. Calculated feasts, fasting rules, and Australian civil holidays are visible for review, but New Project requires imported/synchronized data.")
            self.statusBar().showMessage(f"Loaded {len(self.days)} civil days")
        except Exception as exc:
            LOG.exception("Calendar generation failed"); QMessageBox.critical(self, "Unable to load calendar", str(exc))

    def _populate_months(self) -> None:
        year = self.project.settings.year if self.project else self.year.value()
        for card in self.month_cards: card.populate(year, self.days)

    def _set_controls_from_project(self) -> None:
        if not self.project: return
        self._loading_ui = True; p = self.project.settings
        self.year.setValue(p.year); self.state.setCurrentText(p.jurisdiction); self.language.setCurrentText(p.language); self.template.setCurrentText(p.template); self.orientation.setCurrentText(p.orientation)
        self._loading_ui = False

    def _update_project_ui(self, message: str = "") -> None:
        if self.project:
            marker = " *" if self.project.modified else ""; self.setWindowTitle(f"Russian Orthodox Calendar — {self.project.project_name}{marker}")
            status = "Unsaved Changes" if self.project.modified else "Saved"; location = self.project.file_path or "Not yet saved"
            self.project_status.setText(f"Project: {self.project.project_name}    Status: {status}    Data: {self.project.calendar_data_version}    File: {location}" + (f"\n{message}" if message else ""))
        else:
            self.setWindowTitle("Russian Orthodox Calendar Generator"); self.project_status.setText("No project open — legacy browse/export mode")
        enabled = self.project is not None; self.save_action.setEnabled(enabled); self.save_as_action.setEnabled(enabled); self.close_project_action.setEnabled(enabled); self.project_info_action.setEnabled(enabled)

    def save_project(self) -> bool:
        if not self.project: return False
        self._apply_controls_to_project()
        if not self.project.file_path: return self.save_project_as()
        try:
            self.project_store.save(self.project, Path(self.project.file_path)); self._remember_project(Path(self.project.file_path)); self._update_project_ui(); return True
        except Exception as exc:
            QMessageBox.critical(self, "Project save failed", str(exc)); return False

    def save_project_as(self) -> bool:
        if not self.project: return False
        self._apply_controls_to_project(); default = self.project.file_path or str(Path.home() / f"Russian_Orthodox_Calendar_{self.project.settings.year}_{self.project.settings.jurisdiction.replace(' ', '_')}.rocproject")
        filename, _ = QFileDialog.getSaveFileName(self, "Save calendar project", default, "Russian Orthodox Calendar Project (*.rocproject)")
        if not filename: return False
        try:
            path = self.project_store.save(self.project, Path(filename)); self._remember_project(path); self._update_project_ui(); return True
        except Exception as exc:
            QMessageBox.critical(self, "Project save failed", str(exc)); return False

    def open_project(self) -> None:
        if not self._confirm_project_transition(): return
        filename, _ = QFileDialog.getOpenFileName(self, "Open calendar project", "", "Russian Orthodox Calendar Project (*.rocproject)")
        if filename: self.open_project_path(Path(filename), transition_checked=True)

    def open_project_path(self, path: Path, transition_checked: bool = False) -> bool:
        if not transition_checked and not self._confirm_project_transition(): return False
        try:
            if self.project_store.has_newer_recovery(path):
                answer = QMessageBox.question(self, "Recover unsaved project", "An unsaved recovery version of this project was found. Recover it?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
                if answer == QMessageBox.Cancel: return False
                if answer == QMessageBox.Yes: project = self.project_store.load_recovery(path)
                else: self.project_store.discard_recovery(path); project = self.project_store.load(path)
            else: project = self.project_store.load(path)
            self.project = project; self.days = project.resolve_days(); self._set_controls_from_project(); self._populate_months(); self._remember_project(path); self._update_project_ui()
            available, _ = self.database.calendar_version(project.settings.year)
            if self.check_data_updates and available != project.calendar_data_version:
                box = QMessageBox(self); box.setWindowTitle("Updated calendar data available"); box.setText(f"Current project data: {project.calendar_data_version}\nAvailable: {available}")
                keep = box.addButton("Keep Existing Data", QMessageBox.AcceptRole); update = box.addButton("Update Project", QMessageBox.ActionRole); compare = box.addButton("Compare", QMessageBox.HelpRole); box.exec()
                if box.clickedButton() == update:
                    current = self.engine.generate_year(project.settings.year, project.settings.jurisdiction, project.settings.language); self.days = project.update_source_data(current, available); self._populate_months(); self._update_project_ui()
                elif box.clickedButton() == compare:
                    current = self.engine.generate_year(project.settings.year, project.settings.jurisdiction, project.settings.language)
                    summary = project.compare_source_data(current)
                    QMessageBox.information(self, "Calendar data comparison", f"The saved snapshot remains active.\n\nChanged dates: {summary['changed_dates']}\nAdded records: {summary['added_records']}\nRemoved records: {summary['removed_records']}\n\nNo project data was changed.")
                else: _ = keep
            if project.missing_references:
                QMessageBox.warning(self, "Project data warning", "Saved references requiring review:\n" + "\n".join(project.missing_references[:20]))
            return True
        except Exception as exc:
            backup = Path(str(path) + ".bak")
            message = "Unable to open this project because the file appears to be corrupted or invalid."
            if backup.exists() and QMessageBox.question(self, "Unable to open project", message + "\n\nRestore the backup copy?") == QMessageBox.Yes:
                try:
                    project = self.project_store.load(backup); project.file_path = str(path); project.modified = True
                    self.project = project; self.days = project.resolve_days(); self._set_controls_from_project(); self._populate_months(); self._update_project_ui("Backup recovered; save to restore the main project file")
                    return True
                except Exception as backup_exc:
                    QMessageBox.critical(self, "Backup recovery failed", str(backup_exc)); return False
            QMessageBox.critical(self, "Unable to open project", message + f"\n\n{exc}"); return False

    def close_project(self) -> bool:
        if not self._confirm_project_transition(): return False
        if self.project: LOG.info("Project closed: %s", self.project.project_id)
        self.project = None; self.load_calendar(); self._update_project_ui(); return True

    def _confirm_project_transition(self) -> bool:
        if not self.project or not self.project.modified: return True
        answer = QMessageBox.question(self, "Unsaved project", "Save changes to this project?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if answer == QMessageBox.Cancel: return False
        if answer == QMessageBox.Save: return self.save_project()
        self.project_store.discard_project_recovery(self.project)
        return True

    def autosave_project(self) -> None:
        if self.project and self.project.modified:
            try:
                self._apply_controls_to_project(show_warnings=False)
                self.project_store.write_recovery(self.project)
            except Exception: LOG.exception("Project autosave failed")

    def _remember_project(self, path: Path) -> None:
        value = str(path.resolve()); existing = [item for item in self.settings.recent_projects if Path(item).exists() and item != value]
        self.settings.recent_projects = [value] + existing[:9]; self.store.save(self.settings); self._rebuild_recent_menu()

    def _rebuild_recent_menu(self) -> None:
        if not hasattr(self, "recent_menu"): return
        self.recent_menu.clear(); valid = []
        for path in self.settings.recent_projects[:10]:
            if Path(path).exists():
                valid.append(path); action = self.recent_menu.addAction(Path(path).stem); action.setToolTip(path); action.triggered.connect(lambda checked=False, item=path: self.open_project_path(Path(item)))
        if not valid: self.recent_menu.addAction("No recent projects").setEnabled(False)
        if valid != self.settings.recent_projects:
            self.settings.recent_projects = valid; self.store.save(self.settings)

    def show_project_information(self) -> None:
        if not self.project: return
        p = self.project; QMessageBox.information(self, "Project Information", f"Project Name: {p.project_name}\nYear: {p.settings.year}\nState/Territory: {p.settings.jurisdiction}\nLanguage: {p.settings.language}\nCalendar Data Version: {p.calendar_data_version}\nCreated: {p.created_at}\nLast Modified: {p.modified_at}\nApplication Version: {p.application_version}\nFile Location: {p.file_path or 'Not yet saved'}")

    def _options(self) -> PdfOptions:
        p = self.project.settings if self.project else self._settings_from_controls()
        logo = self.project.materialize_parish_logo(ensure_user_dirs()["cache"] / "project-assets" / self.project.project_id) if self.project else p.parish_logo
        return PdfOptions(p.year, p.jurisdiction, p.template, p.orientation, p.language, p.include_julian, p.include_holidays, p.include_sources, p.include_fasting_icons, p.include_fasting_legend, p.include_service_rank_icons, p.include_service_rank_legend, p.rank_labels_en, p.rank_labels_ru, list(range(1, 13)), p.parish_name, logo, p.custom_header, p.custom_footer)

    def _default_output(self) -> Path:
        p = self.project.settings if self.project else self._settings_from_controls(); paths = ensure_user_dirs(); folder = Path(self.settings.output_directory) if self.settings.output_directory else paths["output"]
        return folder / f"Russian_Orthodox_Calendar_{p.year}_{p.jurisdiction.replace(' ', '_')}_{p.language}.pdf"

    def generate_pdf(self) -> None:
        if self.project: self._apply_controls_to_project()
        suggested = self._default_output(); suggested.parent.mkdir(parents=True, exist_ok=True)
        filename, _ = QFileDialog.getSaveFileName(self, "Export project as print-ready PDF", str(suggested), "PDF documents (*.pdf)")
        if not filename: return
        output = Path(filename)
        try:
            self.renderer.render(output, self.days, self._options()); self.statusBar().showMessage(f"Generated {output}"); QMessageBox.information(self, "Calendar exported", f"Created PDF from the current project state.\n\n{output}\n\nProject changes were not automatically saved.")
        except Exception as exc: LOG.exception("PDF generation failed"); QMessageBox.critical(self, "PDF generation failed", str(exc))

    def preview_pdf(self) -> None:
        if self.project: self._apply_controls_to_project()
        p = self.project.settings if self.project else self._settings_from_controls(); temp = ensure_user_dirs()["cache"] / f"preview_{p.year}_{JURISDICTIONS.get(p.jurisdiction) or 'INT'}.pdf"
        self.renderer.render(temp, self.days, self._options()); PreviewDialog(temp, self).exec()

    def edit_calendar(self) -> None:
        if not self.project:
            self.create_project(self._settings_from_controls(), f"Untitled {self.year.value()} {self.state.currentText()}")
        CalendarEditor(self.days, None, self, self._project_day_edited).exec(); self._populate_months(); self._update_project_ui()

    def _project_day_edited(self, day: CalendarDay, primary_id: str | None) -> None:
        if self.project:
            self.project.update_day(day, primary_id); self.autosave_project(); self._populate_months(); self._update_project_ui()

    def import_data(self, year: int | None = None) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Import authoritative calendar data", "", "Calendar data (*.json *.csv *.xml *.html *.htm *.pdf)")
        if not filename: return
        try:
            result = CalendarImporter(self.database).import_file(Path(filename), year or self.year.value(), "Manual authoritative import"); QMessageBox.information(self, "Import complete", f"Imported {result.count} saint commemorations for {result.year}."); self.load_calendar()
        except Exception as exc: QMessageBox.critical(self, "Import failed", str(exc))

    def _sync_data(self, year: int) -> None:
        progress = QProgressDialog("Preparing synchronization...", "Cancel", 0, 732, self); progress.setWindowModality(Qt.WindowModal); progress.setMinimumDuration(0)
        def report(position, total, label): progress.setMaximum(total); progress.setValue(position); progress.setLabelText(label); QApplication.processEvents(); return not progress.wasCanceled()
        try:
            result, counts = SynchronizationService(self.database).sync_holy_trinity(year, progress=report); progress.close(); QMessageBox.information(self, "Synchronization complete", f"Imported {counts['saints']} commemorations and {counts['feasts']} feasts. Failures: {len(result.failures)}")
        except Exception as exc: progress.close(); QMessageBox.warning(self, "Unable to update calendar data", str(exc))

    def update_data(self) -> None:
        if QMessageBox.question(self, "Synchronize calendar source", f"Load {self.year.value()} from Holy Trinity English/Russian endpoints?") == QMessageBox.Yes:
            self._sync_data(self.year.value()); self.load_calendar()

    def show_sources(self) -> None: SourceDialog(self.database, self).exec()

    def show_settings(self) -> None:
        if self.project:
            data = asdict(self.settings); data.update({key: value for key, value in asdict(self.project.settings).items() if key in Settings.__dataclass_fields__}); temp = Settings(**{key: value for key, value in data.items() if key in Settings.__dataclass_fields__})
            dialog = SettingsDialog(temp, self)
            if dialog.exec():
                dialog.apply()
                for key in ProjectSettings.__dataclass_fields__: setattr(self.project.settings, key, getattr(temp, key))
                self.project.mark_modified(); self._set_controls_from_project(); self._update_project_ui()
        else:
            dialog = SettingsDialog(self.settings, self)
            if dialog.exec(): dialog.apply(); self.store.save(self.settings); self.language.setCurrentText(self.settings.language); self.orientation.setCurrentText(self.settings.orientation)

    def about(self) -> None:
        QMessageBox.about(self, "About", "<h2>Russian Orthodox Calendar Generator</h2><p>Version 1.5.0</p><p>Editable .rocproject documents preserve source snapshots, selections, ordering, overrides, notes and publication settings separately from the authoritative database.</p>")

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_project_transition(): event.ignore(); return
        self.settings.default_year = self.year.value(); self.settings.jurisdiction = self.state.currentText(); self.settings.language = self.language.currentText(); self.settings.template = self.template.currentText(); self.settings.orientation = self.orientation.currentText(); self.store.save(self.settings); event.accept()
