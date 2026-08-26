from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCalendarWidget, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QSplitter,
    QTextEdit, QVBoxLayout, QWidget,
)

from orthodox_calendar.database.database import Database
from orthodox_calendar.models import CalendarDay, FastLevel, Fasting, ServiceRank, ServiceRankInfo
from orthodox_calendar.projects.model import feast_key, saint_key
from orthodox_calendar.service_ranks import labels_for


EDITOR_STYLESHEET = """
QDialog, QWidget { background: #FAFAFA; color: #111111; }
QGroupBox { background: #FFFFFF; border: 1px solid #B8B8B8; border-radius: 4px; margin-top: 9px; padding-top: 8px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #5F1724; }
QListWidget, QTextEdit, QLineEdit, QComboBox, QCalendarWidget { background: #FFFFFF; color: #111111; border: 1px solid #8D8D8D; selection-background-color: #D9EAF7; selection-color: #111111; }
QPushButton { background: #F2F2F2; color: #111111; border: 1px solid #777777; border-radius: 3px; padding: 5px 12px; }
QPushButton:hover { background: #E5E5E5; }
QCheckBox { color: #111111; }
"""


class CalendarEditor(QDialog):
    def __init__(self, days: list[CalendarDay], database: Database | None = None, parent=None, on_project_edit=None):
        super().__init__(parent)
        self.setWindowTitle("Calendar Editor")
        self.resize(1080, 790)
        self.setStyleSheet(EDITOR_STYLESHEET)
        self.days = {day.civil_date: day for day in days}
        self.database = database
        self.on_project_edit = on_project_edit
        self.current: CalendarDay | None = None
        self._updating = False

        self.calendar = QCalendarWidget()
        first, last = days[0].civil_date, days[-1].civil_date
        self.calendar.setMinimumDate(QDate(first.year, first.month, first.day)); self.calendar.setMaximumDate(QDate(last.year, last.month, last.day))
        self.calendar.selectionChanged.connect(self.load_date)
        self.heading = QLabel(); self.heading.setStyleSheet("font-size: 18pt; font-weight: 700; color: #782535")
        self.gregorian, self.julian, self.liturgical = QLabel(), QLabel(), QLabel()
        self.service_rank = QComboBox(); self.service_rank.addItem("Use source classification", "")
        for rank in (ServiceRank.GREAT_FEAST, ServiceRank.VIGIL, ServiceRank.POLYELEOS, ServiceRank.DOXOLOGY, ServiceRank.SIX_STICHERA, ServiceRank.NO_SIGN, ServiceRank.OTHER, ServiceRank.UNKNOWN, ServiceRank.NO_DATA):
            self.service_rank.addItem(labels_for(rank)[0], rank.value)
        self.rank_provenance = QLabel(); self.rank_provenance.setWordWrap(True)
        self.feasts = QListWidget()
        self.saints = QListWidget(); self.saints.setDragDropMode(QListWidget.InternalMove)
        self.saints.itemChanged.connect(self._saint_changed); self.saints.model().rowsMoved.connect(self._saints_reordered)
        self.search = QLineEdit(); self.search.setPlaceholderText("Search saints on this date..."); self.search.textChanged.connect(self._filter_saints)
        self.selection_filter = QComboBox(); self.selection_filter.addItems(["All", "Selected", "Unselected"]); self.selection_filter.currentTextChanged.connect(self._filter_saints)
        self.category_filter = QComboBox(); self.category_filter.currentTextChanged.connect(self._filter_saints)
        self.selection_help = QLabel("Checked saints are printed. The first checked saint is primary. Drag to reorder; double-click a name to edit it.")
        self.selection_help.setWordWrap(True)
        self.fasting_level = QComboBox()
        for level in FastLevel:
            self.fasting_level.addItem(level.value, level.value)
        self.fasting_period, self.fasting_detail = QLineEdit(), QLineEdit()
        self.custom_note = QTextEdit(); self.custom_note.setMaximumHeight(65); self.custom_note.setPlaceholderText("Project-specific note")
        self.holidays = QListWidget()
        self.sources = QTextEdit(); self.sources.setReadOnly(True); self.sources.setMaximumHeight(90)

        left = QWidget(); left_layout = QVBoxLayout(left); left_layout.addWidget(self.calendar); left_layout.addStretch()
        right = QWidget(); right_layout = QVBoxLayout(right); right_layout.addWidget(self.heading)
        form = QFormLayout(); form.addRow("Gregorian:", self.gregorian); form.addRow("Julian / Church:", self.julian); form.addRow("Liturgical week / tone:", self.liturgical); form.addRow("Service rank:", self.service_rank); form.addRow("Rank provenance:", self.rank_provenance)
        right_layout.addLayout(form)
        feast_box = QGroupBox("Feasts (uncheck to hide; double-click to edit)"); feast_layout = QVBoxLayout(feast_box); feast_layout.addWidget(self.feasts); right_layout.addWidget(feast_box, 1)
        saint_box = QGroupBox("Saints selected for PDF"); saint_layout = QVBoxLayout(saint_box)
        filters = QHBoxLayout(); filters.addWidget(self.search, 1); filters.addWidget(self.selection_filter); filters.addWidget(self.category_filter)
        saint_layout.addLayout(filters); saint_layout.addWidget(self.selection_help); saint_layout.addWidget(self.saints); right_layout.addWidget(saint_box, 2)
        lower = QHBoxLayout()
        fasting_widget = QWidget(); fasting_form = QFormLayout(fasting_widget); fasting_form.addRow("Level", self.fasting_level); fasting_form.addRow("Period", self.fasting_period); fasting_form.addRow("Detail", self.fasting_detail)
        for title, widget in (("Fasting override", fasting_widget), ("Australian civil holidays", self.holidays), ("Sources", self.sources)):
            box = QGroupBox(title); box_layout = QVBoxLayout(box); box_layout.addWidget(widget); lower.addWidget(box)
        right_layout.addLayout(lower)
        note_box = QGroupBox("Project note"); note_layout = QVBoxLayout(note_box); note_layout.addWidget(self.custom_note); right_layout.addWidget(note_box)
        splitter = QSplitter(); splitter.addWidget(left); splitter.addWidget(right); splitter.setSizes([310, 770])
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Save).clicked.connect(self.save_overrides); buttons.rejected.connect(self.reject)
        root = QVBoxLayout(self); root.addWidget(splitter); root.addWidget(buttons)
        self.load_date()

    def selected_date(self) -> date:
        qd = self.calendar.selectedDate(); return date(qd.year(), qd.month(), qd.day())

    def load_date(self) -> None:
        self.current = self.days.get(self.selected_date())
        if not self.current: return
        day = self.current
        self.heading.setText(day.civil_date.strftime("%A, %d %B %Y").upper())
        self.gregorian.setText(day.civil_date.strftime("%d %B %Y")); self.julian.setText(day.julian_date.strftime("%d %B %Y") + " O.S.")
        tone = f"Tone {day.tone}" if day.tone else ""; self.liturgical.setText(" · ".join(part for part in (day.liturgical_week, tone) if part) or "Not supplied")
        rank = day.service_rank; self.service_rank.setCurrentIndex(max(0, self.service_rank.findData(rank.normalized_rank.value) if rank.user_override else 0))
        status = "USER OVERRIDE" if rank.user_override else rank.status.replace("_", " ").upper()
        self.rank_provenance.setText(f"{status} | Source: {rank.source_name or 'Not supplied'}\nSource rank: {rank.source_rank_text or 'Not supplied'} | Original Russian: {rank.name_ru}\nSource URL: {rank.source_url or 'Not supplied'}")
        self.feasts.clear()
        for feast in day.feasts:
            item = QListWidgetItem(feast.name); item.setData(Qt.UserRole, feast_key(feast, day.civil_date)); item.setData(Qt.UserRole + 1, feast.rank.value)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable); item.setCheckState(Qt.Checked); item.setToolTip(feast.rank.value); self.feasts.addItem(item)
        self._updating = True; self.saints.clear()
        categories = sorted({saint.category or "Saint" for saint in day.saints})
        self.category_filter.blockSignals(True); self.category_filter.clear(); self.category_filter.addItem("All categories"); self.category_filter.addItems(categories); self.category_filter.blockSignals(False)
        for saint in sorted(day.saints, key=lambda value: value.display_order):
            item = QListWidgetItem(saint.display_name); item.setData(Qt.UserRole, saint_key(saint)); item.setData(Qt.UserRole + 1, saint.category or "Saint")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable | Qt.ItemIsDragEnabled); item.setCheckState(Qt.Checked if saint.selected else Qt.Unchecked); self.saints.addItem(item)
        if not day.saints:
            item = QListWidgetItem("Authoritative saint data has not been imported for this year."); item.setFlags(Qt.NoItemFlags); self.saints.addItem(item)
        self._updating = False; self._refresh_saint_visuals(); self._filter_saints()
        self.fasting_level.setCurrentIndex(self.fasting_level.findData(day.fasting.level.value) if day.fasting else self.fasting_level.findData(FastLevel.FREE.value))
        self.fasting_period.setText(day.fasting.period if day.fasting else ""); self.fasting_detail.setText(day.fasting.detail if day.fasting else "")
        self.custom_note.setPlainText("\n".join(day.notes))
        self.holidays.clear()
        for holiday in day.public_holidays: self.holidays.addItem("CIVIL — " + holiday.name)
        if not day.public_holidays: self.holidays.addItem("None")
        source_names = {feast.source.name for feast in day.feasts if feast.source} | {saint.source.name for saint in day.saints if saint.source}
        self.sources.setPlainText("\n".join(sorted(source_names)) or "Calculated rules only")

    def _saint_changed(self, _item) -> None:
        if not self._updating: self._refresh_saint_visuals(); self._filter_saints()

    def _saints_reordered(self, *_args) -> None: self._refresh_saint_visuals()

    def _refresh_saint_visuals(self) -> None:
        self._updating = True; primary_found = False
        for row in range(self.saints.count()):
            item = self.saints.item(row)
            if not item.data(Qt.UserRole): continue
            checked = item.checkState() == Qt.Checked; primary = checked and not primary_found; primary_found = primary_found or primary
            font = QFont(item.font()); font.setBold(primary); item.setFont(font); item.setForeground(QColor("#185C37") if checked else QColor("#777777"))
            item.setToolTip("Primary commemoration; printed first" if primary else ("Selected for PDF" if checked else "Explicitly hidden in this project"))
        self._updating = False

    def _filter_saints(self, *_args) -> None:
        needle = self.search.text().casefold(); state, category = self.selection_filter.currentText(), self.category_filter.currentText()
        for row in range(self.saints.count()):
            item = self.saints.item(row); checked = item.checkState() == Qt.Checked
            matches_state = state == "All" or (state == "Selected" and checked) or (state == "Unselected" and not checked)
            matches_category = category in ("", "All categories") or item.data(Qt.UserRole + 1) == category
            item.setHidden(needle not in item.text().casefold() or not matches_state or not matches_category)

    def save_overrides(self) -> None:
        if not self.current: return
        by_key = {saint_key(item): item for item in self.current.saints}; primary_id = None
        for row in range(self.saints.count()):
            item = self.saints.item(row); stable_id = item.data(Qt.UserRole); saint = by_key.get(stable_id)
            if not saint: continue
            saint.selected = item.checkState() == Qt.Checked; saint.display_name = item.text().strip() or saint.display_name; saint.display_order = row
            if saint.selected and primary_id is None: primary_id = stable_id
            if self.on_project_edit is None and self.database is not None and saint.id is not None:
                self.database.set_saint_override(self.current.civil_date, saint.id, saint.selected, saint.display_name, row)
        feast_by_key = {feast_key(item, self.current.civil_date): item for item in self.current.feasts}; updated_feasts = []
        for row in range(self.feasts.count()):
            item = self.feasts.item(row)
            if item.checkState() != Qt.Checked: continue
            feast = feast_by_key.get(item.data(Qt.UserRole))
            if feast: feast.name = item.text().strip() or feast.name; updated_feasts.append(feast)
        self.current.feasts = updated_feasts
        self.current.fasting = Fasting(FastLevel(self.fasting_level.currentData()), self.fasting_period.text().strip(), self.fasting_detail.text().strip())
        self.current.notes = [line.strip() for line in self.custom_note.toPlainText().splitlines() if line.strip()]
        selected_value = self.service_rank.currentData()
        if selected_value:
            rank = ServiceRank(selected_value); old = self.current.service_rank
            en, ru = labels_for(rank); self.current.service_rank = ServiceRankInfo(rank, en, ru, old.source_name, old.source_url, old.source_rank_text, "user_override", True)
        if self.on_project_edit is not None:
            self.on_project_edit(self.current, primary_id)
        elif self.database is not None:
            self.database.set_service_rank_override(self.current.civil_date, ServiceRank(selected_value) if selected_value else None)
