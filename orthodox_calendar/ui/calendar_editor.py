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
from orthodox_calendar.models import CalendarDay, ServiceRank
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
    def __init__(self, days: list[CalendarDay], database: Database, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calendar Editor")
        self.resize(1050, 740)
        self.setStyleSheet(EDITOR_STYLESHEET)
        self.days = {day.civil_date: day for day in days}
        self.database = database
        self.current: CalendarDay | None = None
        self._updating = False

        self.calendar = QCalendarWidget()
        first, last = days[0].civil_date, days[-1].civil_date
        self.calendar.setMinimumDate(QDate(first.year, first.month, first.day))
        self.calendar.setMaximumDate(QDate(last.year, last.month, last.day))
        self.calendar.selectionChanged.connect(self.load_date)

        self.heading = QLabel(); self.heading.setStyleSheet("font-size: 18pt; font-weight: 700; color: #782535")
        self.gregorian, self.julian, self.liturgical = QLabel(), QLabel(), QLabel()
        self.service_rank = QComboBox()
        self.service_rank.addItem("Use source classification", "")
        for rank in (ServiceRank.GREAT_FEAST, ServiceRank.VIGIL, ServiceRank.POLYELEOS, ServiceRank.DOXOLOGY, ServiceRank.SIX_STICHERA, ServiceRank.NO_SIGN, ServiceRank.OTHER, ServiceRank.UNKNOWN, ServiceRank.NO_DATA):
            self.service_rank.addItem(labels_for(rank)[0], rank.value)
        self.rank_provenance = QLabel(); self.rank_provenance.setWordWrap(True); self.rank_provenance.setStyleSheet("color: #333333;")
        self.feasts = QListWidget()
        self.saints = QListWidget(); self.saints.setDragDropMode(QListWidget.InternalMove)
        self.saints.itemChanged.connect(self._saint_changed)
        self.saints.model().rowsMoved.connect(self._saints_reordered)
        self.search = QLineEdit(); self.search.setPlaceholderText("Search saints on this date..."); self.search.textChanged.connect(self._filter_saints)
        self.selection_filter = QComboBox(); self.selection_filter.addItems(["All", "Selected", "Unselected"]); self.selection_filter.currentTextChanged.connect(self._filter_saints)
        self.category_filter = QComboBox(); self.category_filter.currentTextChanged.connect(self._filter_saints)
        self.selection_help = QLabel("Checked saints are printed. The first checked saint is the primary commemoration. Drag entries to reorder them.")
        self.selection_help.setWordWrap(True); self.selection_help.setStyleSheet("color: #333333; font-size: 9pt;")
        self.fasting = QTextEdit(); self.fasting.setReadOnly(True); self.fasting.setMaximumHeight(90)
        self.holidays = QListWidget()
        self.sources = QTextEdit(); self.sources.setReadOnly(True); self.sources.setMaximumHeight(90)

        left = QWidget(); left_layout = QVBoxLayout(left); left_layout.addWidget(self.calendar); left_layout.addStretch()
        right = QWidget(); right_layout = QVBoxLayout(right); right_layout.addWidget(self.heading)
        form = QFormLayout(); form.addRow("Gregorian:", self.gregorian); form.addRow("Julian / Church:", self.julian); form.addRow("Liturgical week / tone:", self.liturgical)
        form.addRow("Service rank:", self.service_rank); form.addRow("Rank provenance:", self.rank_provenance)
        right_layout.addLayout(form)
        feast_box = QGroupBox("Feasts"); feast_layout = QVBoxLayout(feast_box); feast_layout.addWidget(self.feasts); right_layout.addWidget(feast_box, 1)
        saint_box = QGroupBox("Saints selected for PDF")
        saint_layout = QVBoxLayout(saint_box); filters = QHBoxLayout(); filters.addWidget(self.search, 1); filters.addWidget(self.selection_filter); filters.addWidget(self.category_filter)
        saint_layout.addLayout(filters); saint_layout.addWidget(self.selection_help); saint_layout.addWidget(self.saints)
        right_layout.addWidget(saint_box, 2)
        lower = QHBoxLayout()
        for title, widget in (("Fasting", self.fasting), ("Australian civil holidays", self.holidays), ("Sources", self.sources)):
            box = QGroupBox(title); box_layout = QVBoxLayout(box); box_layout.addWidget(widget); lower.addWidget(box)
        right_layout.addLayout(lower)

        splitter = QSplitter(); splitter.addWidget(left); splitter.addWidget(right); splitter.setSizes([320, 730])
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Save).clicked.connect(self.save_overrides); buttons.rejected.connect(self.reject)
        root = QVBoxLayout(self); root.addWidget(splitter); root.addWidget(buttons)
        self.load_date()

    def selected_date(self) -> date:
        qd = self.calendar.selectedDate(); return date(qd.year(), qd.month(), qd.day())

    def load_date(self) -> None:
        self.current = self.days.get(self.selected_date())
        if not self.current:
            return
        day = self.current
        self.heading.setText(day.civil_date.strftime("%A, %d %B %Y").upper())
        self.gregorian.setText(day.civil_date.strftime("%d %B %Y"))
        self.julian.setText(day.julian_date.strftime("%d %B %Y") + " O.S.")
        tone = f"Tone {day.tone}" if day.tone else ""
        self.liturgical.setText(" · ".join(part for part in (day.liturgical_week, tone) if part) or "Not supplied")
        rank = day.service_rank
        self.service_rank.setCurrentIndex(max(0, self.service_rank.findData(rank.normalized_rank.value) if rank.user_override else 0))
        status = "USER OVERRIDE" if rank.user_override else rank.status.replace("_", " ").upper()
        self.rank_provenance.setText(
            f"{status} | Source: {rank.source_name or 'Not supplied'}\n"
            f"Source rank: {rank.source_rank_text or 'Not supplied'} | Original Russian: {rank.name_ru}\n"
            f"Source URL: {rank.source_url or 'Not supplied'}"
        )
        self.feasts.clear()
        for feast in day.feasts:
            item = QListWidgetItem(f"{feast.name} — {feast.rank.value}"); item.setCheckState(Qt.Checked); self.feasts.addItem(item)

        self._updating = True; self.saints.clear()
        categories = sorted({saint.category or "Saint" for saint in day.saints})
        self.category_filter.blockSignals(True); self.category_filter.clear(); self.category_filter.addItem("All categories"); self.category_filter.addItems(categories); self.category_filter.blockSignals(False)
        for saint in sorted(day.saints, key=lambda value: value.display_order):
            item = QListWidgetItem(saint.display_name)
            item.setData(Qt.UserRole, saint.id); item.setData(Qt.UserRole + 1, saint.category or "Saint")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable | Qt.ItemIsDragEnabled)
            item.setCheckState(Qt.Checked if saint.selected else Qt.Unchecked); self.saints.addItem(item)
        if not day.saints:
            item = QListWidgetItem("Authoritative saint data has not been imported for this year."); item.setFlags(Qt.NoItemFlags); self.saints.addItem(item)
        self._updating = False; self._refresh_saint_visuals(); self._filter_saints()

        self.fasting.setPlainText(f"{day.fasting.level.value}\n{day.fasting.period}: {day.fasting.detail}" if day.fasting else "No record")
        self.holidays.clear()
        for holiday in day.public_holidays: self.holidays.addItem("CIVIL — " + holiday.name)
        if not day.public_holidays: self.holidays.addItem("None")
        source_names = {feast.source.name for feast in day.feasts if feast.source} | {saint.source.name for saint in day.saints if saint.source}
        self.sources.setPlainText("\n".join(sorted(source_names)) or "Calculated rules only")

    def _saint_changed(self, _item) -> None:
        if not self._updating:
            self._refresh_saint_visuals(); self._filter_saints()

    def _saints_reordered(self, *_args) -> None:
        self._refresh_saint_visuals()

    def _refresh_saint_visuals(self) -> None:
        self._updating = True
        primary_found = False
        for row in range(self.saints.count()):
            item = self.saints.item(row)
            if not item.data(Qt.UserRole):
                continue
            checked = item.checkState() == Qt.Checked
            primary = checked and not primary_found
            if primary:
                primary_found = True
            font = QFont(item.font()); font.setBold(primary); item.setFont(font)
            item.setForeground(QColor("#185C37") if checked else QColor("#777777"))
            item.setToolTip("Primary commemoration; printed first" if primary else ("Selected for PDF" if checked else "Not printed in PDF"))
        self._updating = False

    def _filter_saints(self, *_args) -> None:
        needle = self.search.text().casefold()
        state, category = self.selection_filter.currentText(), self.category_filter.currentText()
        for row in range(self.saints.count()):
            item = self.saints.item(row); checked = item.checkState() == Qt.Checked
            matches_state = state == "All" or (state == "Selected" and checked) or (state == "Unselected" and not checked)
            matches_category = category in ("", "All categories") or item.data(Qt.UserRole + 1) == category
            item.setHidden(needle not in item.text().casefold() or not matches_state or not matches_category)

    def save_overrides(self) -> None:
        if not self.current:
            return
        for row in range(self.saints.count()):
            item = self.saints.item(row); saint_id = item.data(Qt.UserRole)
            if saint_id:
                self.database.set_saint_override(self.current.civil_date, saint_id, item.checkState() == Qt.Checked, item.text(), row)
        selected_value = self.service_rank.currentData()
        self.database.set_service_rank_override(self.current.civil_date, ServiceRank(selected_value) if selected_value else None)
