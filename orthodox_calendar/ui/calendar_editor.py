from __future__ import annotations

import copy
from datetime import date

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QCalendarWidget, QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout,
    QDialogButtonBox, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from orthodox_calendar.database.database import Database
from orthodox_calendar.models import CalendarDay, FastLevel, Fasting, Saint, ServiceRank, ServiceRankInfo, Source
from orthodox_calendar.paths import asset_path
from orthodox_calendar.projects.model import feast_key, saint_key
from orthodox_calendar.service_ranks import icon_path_for, labels_for


EDITOR_STYLESHEET = """
QDialog, QWidget { background: #FAFAFA; color: #111111; }
QFrame#sectionFrame { background: #FFFFFF; border: 1px solid #B8B8B8; border-radius: 4px; }
QToolButton#sectionHeader { background: #F3EEE9; color: #5F1724; border: 1px solid #B8B8B8; border-radius: 4px; padding: 7px; font-weight: 700; text-align: left; }
QToolButton#sectionHeader:hover { background: #E8DED7; }
QListWidget, QTextEdit, QLineEdit, QComboBox, QCalendarWidget { background: #FFFFFF; color: #111111; border: 1px solid #8D8D8D; selection-background-color: #D9EAF7; selection-color: #111111; }
QListWidget::indicator, QCheckBox::indicator { width: 17px; height: 17px; border: 2px solid #4F5963; border-radius: 3px; background: #FFFFFF; }
QListWidget::indicator:hover, QCheckBox::indicator:hover { border-color: #185C37; background: #EDF7F1; }
QListWidget::indicator:checked, QCheckBox::indicator:checked { border-color: #12462B; background: #185C37; image: url("@CHECK_ICON@"); }
QListWidget#saintCheckboxList { padding: 4px; }
QComboBox { padding: 5px; min-height: 20px; }
QComboBox QAbstractItemView { background: #FFFFFF; color: #111111; border: 1px solid #777777; selection-background-color: #D9EAF7; selection-color: #111111; outline: 0; }
QPushButton { background: #F2F2F2; color: #111111; border: 1px solid #777777; border-radius: 3px; padding: 7px 13px; }
QPushButton:hover { background: #E5E5E5; }
QPushButton#saveEdits { background: #782535; color: #FFFFFF; border-color: #5F1724; font-weight: 700; }
QPushButton#saveEdits:hover { background: #963447; }
QPushButton#resetDay { color: #8B1E2D; }
QScrollArea { border: none; background: #FAFAFA; }
"""


class FullTextEditDialog(QDialog):
    """Wide, wrapped list-item editor with an unmistakable editing state."""

    def __init__(self, title: str, text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("fullTextEditDialog")
        self.setWindowTitle(title)
        self.setMinimumWidth(720); self.resize(820, 230)
        self.setStyleSheet("""
            QDialog#fullTextEditDialog { background: #EEF7FF; border: 3px solid #2474B5; }
            QLabel#editModeLabel { color: #155A8A; font-weight: 800; font-size: 11pt; }
            QTextEdit#fullTextEditor { background: #FFFFFF; border: 3px solid #2474B5; border-radius: 4px; padding: 8px; selection-background-color: #B9DCF5; }
        """)
        label = QLabel("EDIT MODE — the complete text is shown below")
        label.setObjectName("editModeLabel")
        self.editor = QTextEdit(); self.editor.setObjectName("fullTextEditor")
        self.editor.setAcceptRichText(False); self.editor.setLineWrapMode(QTextEdit.WidgetWidth)
        self.editor.setPlainText(text); self.editor.selectAll()
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self); layout.addWidget(label); layout.addWidget(self.editor, 1); layout.addWidget(buttons)
        self.editor.setFocus()

    @classmethod
    def get_text(cls, parent, title: str, text: str) -> tuple[str, bool]:
        dialog = cls(title, text, parent)
        accepted = dialog.exec() == QDialog.Accepted
        return dialog.editor.toPlainText(), accepted


class SaintCheckboxList(QListWidget):
    """Shared visible-list presentation for primary and additional saints."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("saintCheckboxList")
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideNone)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setEditTriggers(QListWidget.NoEditTriggers)
        self.setSpacing(2)

    def currentData(self):
        """Compatibility helper returning the checked role value."""
        for row in range(self.count()):
            item = self.item(row)
            if item.checkState() == Qt.Checked: return item.data(Qt.UserRole)
        return None

    def setCurrentIndex(self, index: int) -> None:
        """Select a visible primary row using checkbox semantics."""
        if 0 <= index < self.count():
            self.setCurrentRow(index); self.item(index).setCheckState(Qt.Checked)


class CollapsibleSection(QWidget):
    def __init__(self, title: str, content: QWidget, expanded: bool = True):
        super().__init__()
        self.header = QToolButton(); self.header.setObjectName("sectionHeader")
        self.header.setText(title); self.header.setCheckable(True); self.header.setChecked(expanded)
        self.header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.header.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.content = QFrame(); self.content.setObjectName("sectionFrame")
        content_layout = QVBoxLayout(self.content); content_layout.setContentsMargins(10, 9, 10, 9); content_layout.addWidget(content)
        self.content.setVisible(expanded)
        self.header.toggled.connect(self.set_expanded)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(2)
        layout.addWidget(self.header); layout.addWidget(self.content)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.set_expanded(expanded)

    def set_expanded(self, expanded: bool) -> None:
        self.header.setChecked(expanded); self.header.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow); self.content.setVisible(expanded)
        self.setMaximumHeight(16777215 if expanded else self.header.sizeHint().height() + 4)


class CalendarEditor(QDialog):
    def __init__(
        self, days: list[CalendarDay], database: Database | None = None, parent=None,
        on_project_edit=None, initial_date: date | None = None,
        source_day_provider=None, on_project_reset=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Edit Calendar Day")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.setSizeGripEnabled(True); self.resize(1040, 760); self.setMinimumSize(700, 500)
        check_icon = asset_path("icons", "editor-check.svg").as_posix()
        self.setStyleSheet(EDITOR_STYLESHEET.replace("@CHECK_ICON@", check_icon))
        self.days = {day.civil_date: day for day in days}
        self.database = database; self.on_project_edit = on_project_edit
        self.source_day_provider = source_day_provider; self.on_project_reset = on_project_reset
        self.current: CalendarDay | None = None; self._updating = False
        self._baseline_state = None; self._reset_state = None; self._reset_requested = False

        self.calendar = QCalendarWidget(); self.calendar.setGridVisible(True)
        first, last = days[0].civil_date, days[-1].civil_date
        self.calendar.setMinimumDate(QDate(first.year, first.month, first.day)); self.calendar.setMaximumDate(QDate(last.year, last.month, last.day))
        selected = initial_date if initial_date in self.days else first
        self.calendar.setSelectedDate(QDate(selected.year, selected.month, selected.day))
        self.calendar.selectionChanged.connect(self.load_date)

        self.heading = QLabel(); self.heading.setWordWrap(True); self.heading.setStyleSheet("font-size: 17pt; font-weight: 700; color: #782535")
        self.edit_status = QLabel(); self.edit_status.setStyleSheet("font-weight:600;color:#555555;padding:2px 0")
        self.gregorian, self.julian, self.liturgical = QLabel(), QLabel(), QLabel()
        date_widget = QWidget(); date_form = QFormLayout(date_widget)
        date_form.addRow("Gregorian:", self.gregorian); date_form.addRow("Julian / Church:", self.julian); date_form.addRow("Liturgical week / tone:", self.liturgical)

        self.primary_saint = SaintCheckboxList(); self.primary_saint.setMinimumHeight(125)
        self.primary_saint.itemChanged.connect(self._primary_saint_changed)
        self.primary_saint.itemDoubleClicked.connect(self._edit_saint_item)
        self.saints = SaintCheckboxList(); self.saints.setMinimumHeight(170); self.saints.setDragDropMode(QListWidget.InternalMove)
        self.saints.itemChanged.connect(self._saint_changed); self.saints.model().rowsMoved.connect(self._saints_reordered)
        self.saints.itemDoubleClicked.connect(self._edit_saint_item)
        self.search = QLineEdit(); self.search.setPlaceholderText("Search saints on this date..."); self.search.textChanged.connect(self._filter_saints)
        self.selection_filter = QComboBox(); self.selection_filter.addItems(["All", "Selected", "Unselected"]); self.selection_filter.currentTextChanged.connect(self._filter_saints)
        self.category_filter = QComboBox(); self.category_filter.currentTextChanged.connect(self._filter_saints)
        self.selection_help = QLabel("Choose one primary saint, then check any additional saints to publish. Double-click a name to edit its complete text."); self.selection_help.setWordWrap(True)
        self.add_saint_button = QPushButton("Add Additional Saint..."); self.add_saint_button.clicked.connect(self.add_saint)
        saints_widget = QWidget(); saints_layout = QVBoxLayout(saints_widget); saints_layout.setContentsMargins(0, 0, 0, 0)
        filters = QHBoxLayout(); filters.addWidget(self.search, 1); filters.addWidget(self.selection_filter); filters.addWidget(self.category_filter)
        saint_actions = QHBoxLayout(); saint_actions.addWidget(self.add_saint_button); saint_actions.addStretch()
        primary_label = QLabel("Primary / featured saint — choose one"); primary_label.setStyleSheet("font-weight:700;color:#5F1724")
        additional_label = QLabel("Additional saints — check all to publish"); additional_label.setStyleSheet("font-weight:700;color:#5F1724")
        saints_layout.addLayout(filters); saints_layout.addWidget(self.selection_help)
        saints_layout.addWidget(primary_label); saints_layout.addWidget(self.primary_saint)
        saints_layout.addWidget(additional_label); saints_layout.addLayout(saint_actions); saints_layout.addWidget(self.saints)

        self.feasts = QListWidget(); self.feasts.setMinimumHeight(95)
        self.feasts.setWordWrap(True); self.feasts.setTextElideMode(Qt.ElideNone); self.feasts.setEditTriggers(QListWidget.NoEditTriggers)
        self.feasts.itemDoubleClicked.connect(self._edit_feast_item)
        feast_help = QLabel("Uncheck a feast to hide it; double-click its name to edit it."); feast_help.setWordWrap(True)
        feast_widget = QWidget(); feast_layout = QVBoxLayout(feast_widget); feast_layout.setContentsMargins(0, 0, 0, 0); feast_layout.addWidget(feast_help); feast_layout.addWidget(self.feasts)

        self.rank_icon = QLabel(); self.rank_icon.setFixedSize(34, 34); self.rank_icon.setAlignment(Qt.AlignCenter)
        self.rank_text = QLabel(); self.rank_text.setStyleSheet("font-size: 13pt; font-weight: 700; color: #5F1724")
        self.rank_banner = QFrame(); self.rank_banner.setStyleSheet("background:#FFF7F7;border:1px solid #C99AA3;border-radius:4px;padding:4px")
        rank_summary = QHBoxLayout(self.rank_banner); rank_summary.setContentsMargins(7, 4, 7, 4); rank_summary.addWidget(self.rank_icon); rank_summary.addWidget(QLabel("SERVICE RANK:")); rank_summary.addWidget(self.rank_text, 1)
        self.service_rank = QComboBox(); self.service_rank.setMinimumWidth(230); self.service_rank.addItem("Use source classification", "")
        for rank in (ServiceRank.GREAT_FEAST, ServiceRank.VIGIL, ServiceRank.POLYELEOS, ServiceRank.DOXOLOGY, ServiceRank.SIX_STICHERA, ServiceRank.NO_SIGN, ServiceRank.OTHER, ServiceRank.UNKNOWN, ServiceRank.NO_DATA):
            self.service_rank.addItem(labels_for(rank)[0], rank.value)
        self.service_rank.currentIndexChanged.connect(self._update_rank_display)
        self.rank_provenance = QLabel(); self.rank_provenance.setWordWrap(True); self.rank_provenance.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rank_widget = QWidget(); rank_layout = QVBoxLayout(rank_widget); rank_layout.setContentsMargins(0, 0, 0, 0)
        rank_form = QFormLayout(); rank_form.addRow("Service ranking:", self.service_rank); rank_layout.addLayout(rank_form); rank_layout.addWidget(self.rank_provenance)

        self.fasting_level = QComboBox()
        for level in FastLevel: self.fasting_level.addItem(level.value, level.value)
        self.fasting_period, self.fasting_detail = QLineEdit(), QLineEdit()
        fasting_widget = QWidget(); fasting_form = QFormLayout(fasting_widget); fasting_form.addRow("Level:", self.fasting_level); fasting_form.addRow("Period:", self.fasting_period); fasting_form.addRow("Details / permissions:", self.fasting_detail)

        self.custom_note = QTextEdit(); self.custom_note.setMinimumHeight(95); self.custom_note.setPlaceholderText("Project-specific notes")
        self.holidays = QListWidget(); self.holidays.setMinimumHeight(70)
        self.sources = QTextEdit(); self.sources.setReadOnly(True); self.sources.setMinimumHeight(80)
        advanced_widget = QWidget(); advanced_layout = QVBoxLayout(advanced_widget); advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.addWidget(QLabel("Australian civil holidays")); advanced_layout.addWidget(self.holidays); advanced_layout.addWidget(QLabel("Source provenance")); advanced_layout.addWidget(self.sources)

        self.sections = [
            CollapsibleSection("Date Information", date_widget), CollapsibleSection("Saints of the Day", saints_widget),
            CollapsibleSection("Feast Information", feast_widget), CollapsibleSection("Service Ranking", rank_widget),
            CollapsibleSection("Fasting", fasting_widget), CollapsibleSection("Notes", self.custom_note),
            CollapsibleSection("Advanced Information", advanced_widget, False),
        ]
        expand_all, collapse_all = QPushButton("Expand All"), QPushButton("Collapse All")
        expand_all.clicked.connect(lambda: self.set_all_sections(True)); collapse_all.clicked.connect(lambda: self.set_all_sections(False))
        section_controls = QHBoxLayout(); section_controls.addWidget(expand_all); section_controls.addWidget(collapse_all); section_controls.addStretch()
        right_content = QWidget(); right_layout = QVBoxLayout(right_content); right_layout.addWidget(self.heading); right_layout.addWidget(self.edit_status); right_layout.addWidget(self.rank_banner); right_layout.addLayout(section_controls)
        for section in self.sections: right_layout.addWidget(section)
        right_layout.addStretch()
        right_scroll = QScrollArea(); right_scroll.setWidgetResizable(True); right_scroll.setWidget(right_content)

        left = QWidget(); left_layout = QVBoxLayout(left); left_layout.addWidget(QLabel("Choose a date")); left_layout.addWidget(self.calendar); left_layout.addStretch()
        splitter = QSplitter(); splitter.addWidget(left); splitter.addWidget(right_scroll); splitter.setStretchFactor(1, 1); splitter.setSizes([300, 740])

        self.reset_button = QPushButton("Reset Day"); self.reset_button.setObjectName("resetDay"); self.reset_button.clicked.connect(self.reset_day)
        self.cancel_button = QPushButton("Cancel"); self.cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton("Save Edits"); self.save_button.setObjectName("saveEdits"); self.save_button.setDefault(True); self.save_button.clicked.connect(self.save_overrides)
        actions = QHBoxLayout(); actions.addWidget(self.reset_button); actions.addStretch(); actions.addWidget(self.cancel_button); actions.addWidget(self.save_button)
        action_bar = QFrame(); action_bar.setFrameShape(QFrame.StyledPanel); action_bar.setLayout(actions)
        root = QVBoxLayout(self); root.addWidget(splitter, 1); root.addWidget(action_bar)
        self._load_date(selected)

    def set_all_sections(self, expanded: bool) -> None:
        for section in self.sections: section.set_expanded(expanded)

    def selected_date(self) -> date:
        qd = self.calendar.selectedDate(); return date(qd.year(), qd.month(), qd.day())

    def load_date(self) -> None:
        target = self.selected_date()
        if self.current and target != self.current.civil_date and self.has_pending_changes():
            answer = QMessageBox.question(self, "Discard day edits?", f"Discard unsaved editor changes for {self.current.civil_date.strftime('%B %d, %Y')}?", QMessageBox.Discard | QMessageBox.Cancel)
            if answer != QMessageBox.Discard:
                self.calendar.blockSignals(True); old = self.current.civil_date; self.calendar.setSelectedDate(QDate(old.year, old.month, old.day)); self.calendar.blockSignals(False); return
        self._load_date(target)

    def _load_date(self, target: date, source_day: CalendarDay | None = None) -> None:
        day = source_day or self.days.get(target)
        if not day: return
        self.current = copy.deepcopy(day); self._reset_requested = source_day is not None
        self.setWindowTitle(f"Edit Calendar Day - {target.strftime('%B %d, %Y')}")
        self._populate_fields(); self._baseline_state = self.editor_state(); self._reset_state = self._baseline_state if self._reset_requested else None

    def _populate_fields(self) -> None:
        if not self.current: return
        day = self.current; self._updating = True
        self.heading.setText(day.civil_date.strftime("%A, %d %B %Y").upper())
        self.edit_status.setText("✎ Edited from default calendar data" if day.is_edited else "Default calendar data")
        self.edit_status.setStyleSheet(f"font-weight:600;color:{'#8B1E2D' if day.is_edited else '#555555'};padding:2px 0")
        self.gregorian.setText(day.civil_date.strftime("%d %B %Y")); self.julian.setText(day.julian_date.strftime("%d %B %Y") + " O.S.")
        tone = f"Tone {day.tone}" if day.tone else ""; self.liturgical.setText(" · ".join(part for part in (day.liturgical_week, tone) if part) or "Not supplied")
        rank = day.service_rank; index = self.service_rank.findData(rank.normalized_rank.value) if rank.user_override else 0; self.service_rank.setCurrentIndex(max(0, index))
        status = "USER OVERRIDE" if rank.user_override else rank.status.replace("_", " ").upper()
        self.rank_provenance.setText(f"{status} | Source: {rank.source_name or 'Not supplied'}\nSource rank: {rank.source_rank_text or 'Not supplied'} | Original Russian: {rank.name_ru}\nSource URL: {rank.source_url or 'Not supplied'}")
        self.feasts.clear()
        for feast in day.feasts:
            item = QListWidgetItem(feast.name); item.setData(Qt.UserRole, feast_key(feast, day.civil_date)); item.setData(Qt.UserRole + 1, feast.rank.value)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable); item.setCheckState(Qt.Checked); item.setToolTip(feast.name); self.feasts.addItem(item)
        self.primary_saint.clear(); self.saints.clear(); categories = sorted({saint.category or "Saint" for saint in day.saints})
        self.category_filter.blockSignals(True); self.category_filter.clear(); self.category_filter.addItem("All categories"); self.category_filter.addItems(categories); self.category_filter.blockSignals(False)
        for saint in sorted(day.saints, key=lambda value: value.display_order):
            item = QListWidgetItem(saint.display_name); item.setData(Qt.UserRole, saint_key(saint)); item.setData(Qt.UserRole + 1, saint.category or "Saint")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled); item.setCheckState(Qt.Checked if saint.selected else Qt.Unchecked); item.setToolTip(saint.display_name); self.saints.addItem(item)
            primary_item = QListWidgetItem(saint.display_name); primary_item.setData(Qt.UserRole, saint_key(saint)); primary_item.setData(Qt.UserRole + 1, saint.category or "Saint")
            primary_item.setFlags(primary_item.flags() | Qt.ItemIsUserCheckable); primary_item.setCheckState(Qt.Unchecked); primary_item.setToolTip(saint.display_name); self.primary_saint.addItem(primary_item)
        if not day.saints:
            item = QListWidgetItem("Authoritative saint data has not been imported for this year."); item.setFlags(Qt.NoItemFlags); self.saints.addItem(item)
            primary_item = QListWidgetItem(item.text()); primary_item.setFlags(Qt.NoItemFlags); self.primary_saint.addItem(primary_item)
        self._refresh_primary_options(day.primary_saint_id or day.default_primary_saint_id)
        self.fasting_level.setCurrentIndex(self.fasting_level.findData(day.fasting.level.value) if day.fasting else self.fasting_level.findData(FastLevel.FREE.value))
        self.fasting_period.setText(day.fasting.period if day.fasting else ""); self.fasting_detail.setText(day.fasting.detail if day.fasting else "")
        self.custom_note.setPlainText("\n".join(day.notes)); self.holidays.clear()
        for holiday in day.public_holidays: self.holidays.addItem("CIVIL - " + holiday.name)
        if not day.public_holidays: self.holidays.addItem("None")
        source_names = {feast.source.name for feast in day.feasts if feast.source} | {saint.source.name for saint in day.saints if saint.source}
        self.sources.setPlainText("\n".join(sorted(source_names)) or "Calculated rules only")
        self._updating = False; self._refresh_saint_visuals(); self._filter_saints(); self._update_rank_display()

    def _effective_rank(self) -> ServiceRankInfo:
        if not self.current: return ServiceRankInfo()
        value = self.service_rank.currentData()
        if value:
            rank = ServiceRank(value); en, ru = labels_for(rank); return ServiceRankInfo(rank, en, ru)
        return self.current.service_rank

    def _update_rank_display(self, *_args) -> None:
        info = self._effective_rank(); self.rank_text.setText(labels_for(info.normalized_rank)[0])
        path = icon_path_for(info); pixmap = QPixmap(str(path)) if path and path.exists() else QPixmap()
        self.rank_icon.setPixmap(pixmap.scaled(QSize(28, 28), Qt.KeepAspectRatio, Qt.SmoothTransformation) if not pixmap.isNull() else pixmap); self.rank_icon.setToolTip(self.rank_text.text())

    def _saint_changed(self, _item) -> None:
        if not self._updating: self._refresh_primary_options(); self._refresh_saint_visuals(); self._filter_saints()

    def _saints_reordered(self, *_args) -> None: self._refresh_primary_options(); self._refresh_saint_visuals()

    def _primary_saint_id(self) -> str | None:
        for row in range(self.primary_saint.count()):
            item = self.primary_saint.item(row)
            if item.data(Qt.UserRole) and item.checkState() == Qt.Checked:
                return item.data(Qt.UserRole)
        return None

    def _primary_saint_changed(self, changed: QListWidgetItem) -> None:
        if self._updating or not changed.data(Qt.UserRole): return
        self._updating = True
        if changed.checkState() == Qt.Checked:
            for row in range(self.primary_saint.count()):
                item = self.primary_saint.item(row)
                if item is not changed and item.checkState() == Qt.Checked: item.setCheckState(Qt.Unchecked)
            for row in range(self.saints.count()):
                item = self.saints.item(row)
                if item.data(Qt.UserRole) == changed.data(Qt.UserRole): item.setCheckState(Qt.Checked); break
        self._updating = False
        self._refresh_primary_options(); self._refresh_saint_visuals(); self._filter_saints()

    def _edit_saint_item(self, item: QListWidgetItem) -> None:
        if not item.data(Qt.UserRole): return
        text, accepted = FullTextEditDialog.get_text(self, "Edit Saint or Commemoration", item.text())
        text = text.strip()
        if not accepted or not text: return
        stable_id = item.data(Qt.UserRole); self._updating = True
        for widget in (self.primary_saint, self.saints):
            for row in range(widget.count()):
                candidate = widget.item(row)
                if candidate.data(Qt.UserRole) == stable_id:
                    candidate.setText(text); candidate.setToolTip(text)
        self._updating = False; self._filter_saints()

    def _edit_feast_item(self, item: QListWidgetItem) -> None:
        text, accepted = FullTextEditDialog.get_text(self, "Edit Feast or Commemoration", item.text())
        text = text.strip()
        if accepted and text: item.setText(text); item.setToolTip(text)

    def add_saint(self) -> None:
        if not self.current: return
        name, accepted = QInputDialog.getText(self, "Add Additional Saint", "Saint or commemoration name:")
        name = name.strip()
        if not accepted or not name: return
        if any(item.display_name.casefold() == name.casefold() for item in self.current.saints):
            QMessageBox.information(self, "Saint already listed", "That saint or commemoration is already available on this day."); return
        saint = Saint(None, name, name, self.current.civil_date, source=Source("User project"), selected=True,
                      display_order=self.saints.count(), source_order=10_000 + self.saints.count())
        self.current.saints.append(saint)
        item = QListWidgetItem(name); item.setData(Qt.UserRole, saint_key(saint)); item.setData(Qt.UserRole + 1, "Saint")
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled); item.setCheckState(Qt.Checked); item.setToolTip(name)
        self.saints.addItem(item)
        primary_item = QListWidgetItem(name); primary_item.setData(Qt.UserRole, saint_key(saint)); primary_item.setData(Qt.UserRole + 1, "Saint")
        primary_item.setFlags(primary_item.flags() | Qt.ItemIsUserCheckable); primary_item.setCheckState(Qt.Unchecked); primary_item.setToolTip(name)
        self.primary_saint.addItem(primary_item); self._refresh_primary_options(); self._refresh_saint_visuals(); self._filter_saints()

    def _refresh_primary_options(self, preferred: str | None = None) -> None:
        if self._updating and preferred is None: return
        current = preferred or self._primary_saint_id()
        selected_ids: list[str] = []
        for row in range(self.saints.count()):
            item = self.saints.item(row); stable_id = item.data(Qt.UserRole)
            if stable_id and item.checkState() == Qt.Checked: selected_ids.append(stable_id)
        chosen = current if current in selected_ids else (selected_ids[0] if selected_ids else None)
        self._updating = True
        for row in range(self.primary_saint.count()):
            item = self.primary_saint.item(row); stable_id = item.data(Qt.UserRole)
            item.setCheckState(Qt.Checked if stable_id and stable_id == chosen else Qt.Unchecked)
        self._updating = False

    def _refresh_saint_visuals(self) -> None:
        self._updating = True; primary_id = self._primary_saint_id()
        for row in range(self.saints.count()):
            item = self.saints.item(row)
            if not item.data(Qt.UserRole): continue
            checked = item.checkState() == Qt.Checked; primary = checked and item.data(Qt.UserRole) == primary_id
            font = QFont(item.font()); font.setBold(primary); item.setFont(font); item.setForeground(QColor("#185C37") if checked else QColor("#777777"))
            item.setToolTip("Primary / featured saint; published first" if primary else ("Selected for PDF and Word" if checked else "Explicitly hidden in this project"))
        for row in range(self.primary_saint.count()):
            item = self.primary_saint.item(row)
            if not item.data(Qt.UserRole): continue
            primary = item.checkState() == Qt.Checked
            font = QFont(item.font()); font.setBold(primary); item.setFont(font)
            item.setForeground(QColor("#185C37") if primary else QColor("#555555"))
            item.setToolTip("Selected as primary / featured saint" if primary else item.text())
        self._updating = False

    def _filter_saints(self, *_args) -> None:
        needle = self.search.text().casefold(); state, category = self.selection_filter.currentText(), self.category_filter.currentText()
        for row in range(self.saints.count()):
            item = self.saints.item(row); checked = item.checkState() == Qt.Checked
            matches_state = state == "All" or (state == "Selected" and checked) or (state == "Unselected" and not checked)
            matches_category = category in ("", "All categories") or item.data(Qt.UserRole + 1) == category
            item.setHidden(needle not in item.text().casefold() or not matches_state or not matches_category)

    def editor_state(self):
        return (
            tuple((self.saints.item(row).data(Qt.UserRole), self.saints.item(row).text(), self.saints.item(row).checkState() == Qt.Checked) for row in range(self.saints.count()) if self.saints.item(row).data(Qt.UserRole)),
            self._primary_saint_id(),
            tuple((self.feasts.item(row).data(Qt.UserRole), self.feasts.item(row).text(), self.feasts.item(row).checkState() == Qt.Checked) for row in range(self.feasts.count())),
            self.service_rank.currentData(), self.fasting_level.currentData(), self.fasting_period.text(), self.fasting_detail.text(), self.custom_note.toPlainText(),
        )

    def has_pending_changes(self) -> bool:
        return self._baseline_state is not None and self.editor_state() != self._baseline_state

    def reset_day(self) -> None:
        if not self.current or not self.source_day_provider: return
        label = self.current.civil_date.strftime("%B %d, %Y")
        answer = QMessageBox.question(self, "Reset day?", f"Reset {label}?\n\nThis will remove all custom edits for this day and restore the project's saved default calendar data after you click Save Edits.", QMessageBox.Reset | QMessageBox.Cancel)
        if answer != QMessageBox.Reset: return
        source = self.source_day_provider(self.current.civil_date)
        if source:
            original_baseline = self._baseline_state; self._load_date(self.current.civil_date, source); self._baseline_state = original_baseline; self._reset_state = self.editor_state(); self._reset_requested = True

    def _apply_widgets_to_current(self) -> str | None:
        if not self.current: return None
        by_key = {saint_key(item): item for item in self.current.saints}; primary_id = self._primary_saint_id()
        for row in range(self.saints.count()):
            item = self.saints.item(row); stable_id = item.data(Qt.UserRole); saint = by_key.get(stable_id)
            if not saint: continue
            saint.selected = item.checkState() == Qt.Checked; saint.display_name = item.text().strip() or saint.display_name; saint.display_order = row
            if self.on_project_edit is None and self.database is not None and saint.id is not None: self.database.set_saint_override(self.current.civil_date, saint.id, saint.selected, saint.display_name, row)
        self.current.primary_saint_id = primary_id or ""
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
            rank = ServiceRank(selected_value); old = self.current.service_rank; en, ru = labels_for(rank); self.current.service_rank = ServiceRankInfo(rank, en, ru, old.source_name, old.source_url, old.source_rank_text, "user_override", True)
        elif self.source_day_provider:
            source = self.source_day_provider(self.current.civil_date)
            if source: self.current.service_rank = source.service_rank
        return primary_id

    def save_overrides(self) -> None:
        if not self.current: return
        reset_unchanged = self._reset_requested and self._reset_state == self.editor_state(); primary_id = self._apply_widgets_to_current()
        if reset_unchanged and self.on_project_reset is not None: self.on_project_reset(self.current.civil_date)
        elif self.on_project_edit is not None: self.on_project_edit(self.current, primary_id)
        elif self.database is not None:
            selected_value = self.service_rank.currentData(); self.database.set_service_rank_override(self.current.civil_date, ServiceRank(selected_value) if selected_value else None)
        self._baseline_state = self.editor_state(); self.accept()

    def reject(self) -> None:
        if self.has_pending_changes():
            answer = QMessageBox.question(self, "Discard changes?", "Discard changes made in the day editor?", QMessageBox.Discard | QMessageBox.Cancel)
            if answer != QMessageBox.Discard: return
        super().reject()
