from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox, QVBoxLayout,
)

from orthodox_calendar.calendar_engine.australian_holidays import JURISDICTIONS
from orthodox_calendar.projects.model import ProjectSettings


class NewProjectDialog(QDialog):
    def __init__(self, defaults=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Orthodox Calendar Project")
        self.resize(520, 330)
        year = getattr(defaults, "effective_year", date.today().year)
        jurisdiction = getattr(defaults, "jurisdiction", "Queensland")
        language = getattr(defaults, "language", "English")
        template = getattr(defaults, "template", "Traditional")
        orientation = getattr(defaults, "orientation", "Landscape")
        self.name = QLineEdit()
        self.year = QSpinBox(); self.year.setRange(1583, 4099); self.year.setValue(year)
        self.state = QComboBox(); self.state.addItems(JURISDICTIONS.keys()); self.state.setCurrentText(jurisdiction)
        self.language = QComboBox(); self.language.addItems(["English", "Russian"]); self.language.setCurrentText(language)
        self.template = QComboBox(); self.template.addItems(["Traditional", "Minimal", "Parish"]); self.template.setCurrentText(template)
        self.paper = QComboBox(); self.paper.addItems(["A4"])
        self.orientation = QComboBox(); self.orientation.addItems(["Landscape", "Portrait"]); self.orientation.setCurrentText(orientation)
        self.year.valueChanged.connect(self._suggest_name); self.state.currentTextChanged.connect(self._suggest_name)
        self.name.textEdited.connect(lambda: self.name.setProperty("auto_name", False))
        form = QFormLayout(); form.addRow("Project name", self.name); form.addRow("Gregorian calendar year", self.year); form.addRow("Australian state / territory", self.state); form.addRow("Calendar language", self.language); form.addRow("Template", self.template); form.addRow("Paper", self.paper); form.addRow("Orientation", self.orientation)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.button(QDialogButtonBox.Ok).setText("Create Project"); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        root = QVBoxLayout(self); root.addLayout(form); root.addWidget(buttons); self._suggest_name()

    def _suggest_name(self, *_args) -> None:
        if not self.name.text().strip() or self.name.property("auto_name"):
            self.name.setText(f"Russian Orthodox Calendar {self.year.value()} — {self.state.currentText()}")
            self.name.setProperty("auto_name", True)

    def project_settings(self, defaults=None) -> ProjectSettings:
        return ProjectSettings(
            self.year.value(), self.state.currentText(), self.language.currentText(), self.paper.currentText(), self.orientation.currentText(), self.template.currentText(),
            include_julian=getattr(defaults, "include_julian", True), include_holidays=getattr(defaults, "include_holidays", True),
            include_sources=getattr(defaults, "include_sources", True), include_fasting_icons=getattr(defaults, "include_fasting_icons", True),
            include_fasting_legend=getattr(defaults, "include_fasting_legend", True), include_service_rank_icons=getattr(defaults, "include_service_rank_icons", True),
            include_service_rank_legend=getattr(defaults, "include_service_rank_legend", True), rank_labels_en=dict(getattr(defaults, "rank_labels_en", {})),
            rank_labels_ru=dict(getattr(defaults, "rank_labels_ru", {})), parish_name=getattr(defaults, "parish_name", ""), parish_logo=getattr(defaults, "parish_logo", ""),
            address=getattr(defaults, "address", ""), website=getattr(defaults, "website", ""), phone=getattr(defaults, "phone", ""),
            custom_header=getattr(defaults, "custom_header", ""), custom_footer=getattr(defaults, "custom_footer", ""),
        )
