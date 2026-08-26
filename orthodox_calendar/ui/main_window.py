from __future__ import annotations

import calendar
import logging
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QApplication, QMainWindow, QMessageBox, QProgressDialog, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from orthodox_calendar.calendar_engine.australian_holidays import JURISDICTIONS
from orthodox_calendar.calendar_engine.orthodox_calendar import OrthodoxCalendarEngine
from orthodox_calendar.config import Settings, SettingsStore
from orthodox_calendar.data_sources.importer import CalendarImporter
from orthodox_calendar.database.database import Database
from orthodox_calendar.models import CalendarDay, FastLevel
from orthodox_calendar.paths import ensure_user_dirs
from orthodox_calendar.rendering.pdf_renderer import PdfOptions, PdfRenderer
from orthodox_calendar.services.synchronization import SynchronizationService
from .calendar_editor import CalendarEditor
from .preview import PreviewDialog
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
        cal = calendar.Calendar(firstweekday=0)
        rows = ["<table cellspacing='2' width='100%'><tr>" + "".join(f"<th>{x}</th>" for x in "M T W T F S S".split()) + "</tr>"]
        for week in cal.monthdayscalendar(year, self.month):
            cells = []
            for number in week:
                if not number: cells.append("<td>&nbsp;</td>"); continue
                day = by_number[number]; marks = ""
                if day.feasts: marks += "†"
                if day.public_holidays: marks += "◆"
                if day.fasting and day.fasting.level != FastLevel.FREE: marks += "·"
                color = "#8b1e2d" if day.civil_date.weekday() == 6 or any(f.rank.value == "Great Feast" for f in day.feasts) else "#2c2723"
                cells.append(f"<td align='center'><span style='color:{color};font-weight:600'>{number}</span><sup>{marks}</sup></td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        rows.append("</table>")
        self.label.setText("".join(rows))


class MainWindow(QMainWindow):
    def __init__(self, database: Database, settings: Settings, store: SettingsStore):
        super().__init__(); self.database = database; self.settings = settings; self.store = store
        self.engine = OrthodoxCalendarEngine(database); self.renderer = PdfRenderer(); self.days: list[CalendarDay] = []
        self.setWindowTitle("Russian Orthodox Calendar Generator"); self.resize(1250, 860); self.setMinimumSize(960, 680)
        self._build_toolbar(); self._build_ui(); self.load_calendar()

    def _build_toolbar(self):
        toolbar = self.addToolBar("Main"); toolbar.setMovable(False)
        for title, slot in (("Generate PDF", self.generate_pdf), ("Preview", self.preview_pdf), ("Edit Calendar", self.edit_calendar), ("Import Data", self.import_data), ("Update Data", self.update_data), ("Sources", self.show_sources), ("Settings", self.show_settings), ("About", self.about)):
            action = QAction(title, self); action.triggered.connect(slot); toolbar.addAction(action)

    def _build_ui(self):
        central = QWidget(); root = QVBoxLayout(central); root.setContentsMargins(18, 16, 18, 16)
        heading = QLabel("RUSSIAN ORTHODOX CALENDAR"); heading.setStyleSheet("font-size: 22pt; font-weight: 700; color: #782535; letter-spacing: 1px")
        subtitle = QLabel("A print-ready Gregorian calendar with Julian church dates, Orthodox observances, and distinct Australian civil holidays")
        subtitle.setStyleSheet("color: #625850")
        root.addWidget(heading); root.addWidget(subtitle)
        controls = QGroupBox("Calendar publication")
        form = QGridLayout(controls)
        self.year = QSpinBox(); self.year.setRange(1583, 4099); self.year.setValue(self.settings.effective_year)
        previous = QPushButton("Previous"); current = QPushButton("Current"); next_button = QPushButton("Next")
        previous.clicked.connect(lambda: self.year.setValue(self.year.value() - 1)); current.clicked.connect(lambda: self.year.setValue(date.today().year)); next_button.clicked.connect(lambda: self.year.setValue(self.year.value() + 1))
        year_row = QHBoxLayout(); year_row.addWidget(self.year); year_row.addWidget(previous); year_row.addWidget(current); year_row.addWidget(next_button)
        self.state = QComboBox(); self.state.addItems(JURISDICTIONS.keys()); self.state.setCurrentText(self.settings.jurisdiction)
        self.language = QComboBox(); self.language.addItems(["English", "Russian"]); self.language.setCurrentText(self.settings.language)
        self.template = QComboBox(); self.template.addItems(["Traditional", "Minimal", "Parish"]); self.template.setCurrentText(self.settings.template)
        self.orientation = QComboBox(); self.orientation.addItems(["Landscape", "Portrait"]); self.orientation.setCurrentText(self.settings.orientation)
        refresh = QPushButton("Load Calendar"); refresh.clicked.connect(self.load_calendar)
        form.addWidget(QLabel("Modern Gregorian year"), 0, 0); form.addLayout(year_row, 1, 0)
        form.addWidget(QLabel("Australian state / territory"), 0, 1); form.addWidget(self.state, 1, 1)
        form.addWidget(QLabel("Calendar language"), 0, 2); form.addWidget(self.language, 1, 2)
        form.addWidget(QLabel("Template"), 0, 3); form.addWidget(self.template, 1, 3)
        form.addWidget(QLabel("A4 orientation"), 0, 4); form.addWidget(self.orientation, 1, 4); form.addWidget(refresh, 1, 5)
        root.addWidget(controls)
        self.notice = QLabel(); self.notice.setWordWrap(True); self.notice.setStyleSheet("background:#fff4cf;border:1px solid #ddbd58;border-radius:5px;padding:8px;color:#594910")
        root.addWidget(self.notice)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); content = QWidget(); content.setObjectName("annualContent"); content.setStyleSheet("#annualContent { background-color: #f4f1eb; }"); self.month_grid = QGridLayout(content); self.month_cards = []
        for month in range(1, 13):
            card = MonthCard(month); self.month_cards.append(card); self.month_grid.addWidget(card, (month - 1) // 4, (month - 1) % 4)
        scroll.setWidget(content); root.addWidget(scroll, 1)
        self.setCentralWidget(central); self.statusBar().showMessage("Ready")

    def load_calendar(self):
        self.statusBar().showMessage("Building calendar…")
        try:
            self.days = self.engine.generate_year(self.year.value(), self.state.currentText(), self.language.currentText())
            for card in self.month_cards: card.populate(self.year.value(), self.days)
            loaded = self.database.has_authoritative_year(self.year.value())
            self.notice.setVisible(not loaded)
            self.notice.setText("CALENDAR DATA NOT AVAILABLE: authoritative annual saint commemorations have not been imported. Calculated fixed/movable feasts, general fasting rules, and Australian civil holidays are shown and may be exported with a prominent warning. Use Import Data for verified source data.")
            self.statusBar().showMessage(f"Loaded {len(self.days)} civil days · † feast  · fasting  ◆ civil holiday")
        except Exception as exc:
            LOG.exception("Calendar generation failed"); QMessageBox.critical(self, "Unable to load calendar", str(exc))

    def _options(self) -> PdfOptions:
        return PdfOptions(
            year=self.year.value(), jurisdiction=self.state.currentText(), template=self.template.currentText(),
            orientation=self.orientation.currentText(), language=self.language.currentText(),
            include_julian=self.settings.include_julian, include_holidays=self.settings.include_holidays,
            include_sources=self.settings.include_sources, include_fasting_icons=self.settings.include_fasting_icons,
            include_fasting_legend=self.settings.include_fasting_legend,
            include_service_rank_icons=self.settings.include_service_rank_icons,
            include_service_rank_legend=self.settings.include_service_rank_legend,
            rank_labels_en=self.settings.rank_labels_en, rank_labels_ru=self.settings.rank_labels_ru,
            parish_name=self.settings.parish_name,
            parish_logo=self.settings.parish_logo, custom_header=self.settings.custom_header,
            custom_footer=self.settings.custom_footer,
        )

    def _default_output(self) -> Path:
        paths = ensure_user_dirs(); folder = Path(self.settings.output_directory) if self.settings.output_directory else paths["output"]
        state_name = self.state.currentText().replace(" ", "_").replace("/", "_")
        return folder / f"Russian_Orthodox_Calendar_{self.year.value()}_{state_name}_{self.language.currentText()}.pdf"

    def generate_pdf(self):
        suggested = self._default_output(); suggested.parent.mkdir(parents=True, exist_ok=True)
        filename, _ = QFileDialog.getSaveFileName(self, "Save print-ready calendar", str(suggested), "PDF documents (*.pdf)")
        if not filename: return
        output = Path(filename)
        if output.exists() and QMessageBox.question(self, "Replace file?", f"{output.name} already exists. Replace it?") != QMessageBox.Yes: return
        try:
            self.renderer.render(output, self.days, self._options()); self.statusBar().showMessage(f"Generated {output}")
            box = QMessageBox(self); box.setWindowTitle("Calendar generated"); box.setText(f"Created a {len(self._options().months)}-page A4 PDF."); box.setInformativeText(str(output)); open_button = box.addButton("Open PDF", QMessageBox.AcceptRole); box.addButton(QMessageBox.Close); box.exec()
            if box.clickedButton() == open_button: QDesktopServices.openUrl(output.as_uri())
        except Exception as exc:
            LOG.exception("PDF generation failed"); QMessageBox.critical(self, "PDF generation failed", str(exc))

    def preview_pdf(self):
        temp = ensure_user_dirs()["cache"] / f"preview_{self.year.value()}_{JURISDICTIONS.get(self.state.currentText()) or 'INT'}.pdf"
        self.renderer.render(temp, self.days, self._options()); PreviewDialog(temp, self).exec()

    def edit_calendar(self):
        CalendarEditor(self.days, self.database, self).exec(); self.load_calendar()

    def import_data(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Import authoritative calendar data", "", "Calendar data (*.json *.csv *.xml *.html *.htm *.pdf)")
        if not filename: return
        name = "Manual authoritative import"
        try:
            result = CalendarImporter(self.database).import_file(Path(filename), self.year.value(), name)
            QMessageBox.information(self, "Import complete", f"Imported {result.count} saint commemorations for {result.year}.\nSource provenance was retained."); self.load_calendar()
        except Exception as exc: QMessageBox.critical(self, "Import failed", str(exc))

    def update_data(self):
        answer = QMessageBox.question(
            self, "Synchronize legacy calendar source",
            f"Load {self.year.value()} from the same Holy Trinity English/Russian endpoints used by the legacy .NET application?\n\n"
            "Existing caches are reused. A first uncached year requires two requests per day and may take several minutes.",
        )
        if answer != QMessageBox.Yes: return
        progress = QProgressDialog("Preparing synchronization…", "Cancel", 0, 732, self)
        progress.setWindowTitle("Updating Orthodox calendar data"); progress.setWindowModality(Qt.WindowModal); progress.setMinimumDuration(0)
        def report(position, total, label):
            progress.setMaximum(total); progress.setValue(position); progress.setLabelText(f"Holy Trinity Orthodox Calendar\n{label}")
            QApplication.processEvents()
            return not progress.wasCanceled()
        try:
            result, counts = SynchronizationService(self.database).sync_holy_trinity(self.year.value(), progress=report)
            progress.close(); self.load_calendar()
            detail = f"Imported {counts['saints']} commemorations and {counts['feasts']} feast records.\nDownloaded: {result.downloaded}; cache hits: {result.cache_hits}; legacy cache hits: {result.legacy_cache_hits}."
            if result.failures:
                detail += f"\n\n{len(result.failures)} requests could not be completed. Available data was stored as partial; cached data remains usable offline."
                QMessageBox.warning(self, "Synchronization partially completed", detail)
            else:
                QMessageBox.information(self, "Synchronization complete", detail)
        except Exception as exc:
            progress.close(); LOG.exception("Holy Trinity synchronization failed")
            QMessageBox.warning(self, "Unable to update calendar data", f"{exc}\n\nThe application will continue using cached/local data.")
        self.statusBar().showMessage("Calendar data update complete")

    def show_sources(self): SourceDialog(self.database, self).exec()

    def show_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            dialog.apply(); self.store.save(self.settings)
            self.language.setCurrentText(self.settings.language); self.orientation.setCurrentText(self.settings.orientation)

    def about(self):
        QMessageBox.about(self, "About", "<h2>Russian Orthodox Calendar Generator</h2><p>Version 1.4.0</p><p>Supports cache-first synchronization with the same Holy Trinity English/Russian endpoints used by the legacy .NET application, including source-derived Typikon service ranks.</p><p>Calendar information is retrieved from external sources and should be verified against the current official liturgical calendar of the Russian Orthodox Church, particularly for parish or liturgical use.</p><p><b>Australian public holidays are civil-calendar information and are not part of the Orthodox liturgical calendar.</b></p><p>This application is not an ecclesiastical authority.</p>")

    def closeEvent(self, event: QCloseEvent):
        self.settings.default_year = self.year.value(); self.settings.jurisdiction = self.state.currentText(); self.settings.language = self.language.currentText(); self.settings.template = self.template.currentText(); self.settings.orientation = self.orientation.currentText(); self.store.save(self.settings); event.accept()
