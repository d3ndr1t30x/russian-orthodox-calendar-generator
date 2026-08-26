from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLineEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from orthodox_calendar.config import Settings
from orthodox_calendar.models import ServiceRank
from orthodox_calendar.service_ranks import labels_for


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(620, 480)
        self.settings = settings

        tabs = QTabWidget()
        general, pdf, ranks, parish = QWidget(), QWidget(), QWidget(), QWidget()
        general_layout = QFormLayout(general)
        self.output = QLineEdit(settings.output_directory)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self.browse_output)
        output_row = QHBoxLayout(); output_row.addWidget(self.output); output_row.addWidget(browse)
        general_layout.addRow("Default output folder", output_row)
        self.language = QComboBox(); self.language.addItems(["English", "Russian"]); self.language.setCurrentText(settings.language)
        self.paper = QComboBox(); self.paper.addItems(["A4"]); self.paper.setCurrentText(settings.paper)
        self.orientation = QComboBox(); self.orientation.addItems(["Landscape", "Portrait"]); self.orientation.setCurrentText(settings.orientation)
        general_layout.addRow("Calendar language", self.language)
        general_layout.addRow("Paper size", self.paper)
        general_layout.addRow("Default orientation", self.orientation)

        pdf_layout = QFormLayout(pdf)
        self.julian = self._checkbox(settings.include_julian)
        self.holidays = self._checkbox(settings.include_holidays)
        self.icons = self._checkbox(settings.include_fasting_icons)
        self.legend = self._checkbox(settings.include_fasting_legend)
        self.rank_icons = self._checkbox(settings.include_service_rank_icons)
        self.rank_legend = self._checkbox(settings.include_service_rank_legend)
        self.sources = self._checkbox(settings.include_sources)
        pdf_layout.addRow("Include Julian dates", self.julian)
        pdf_layout.addRow("Include civil holidays", self.holidays)
        pdf_layout.addRow("Show fasting permission icons", self.icons)
        pdf_layout.addRow("Show compact fasting legend", self.legend)
        pdf_layout.addRow("Show liturgical service-rank icons", self.rank_icons)
        pdf_layout.addRow("Show liturgical service-rank legend", self.rank_legend)
        pdf_layout.addRow("Include source footer", self.sources)

        rank_layout = QFormLayout(ranks)
        self.rank_label_fields: dict[tuple[str, str], QLineEdit] = {}
        for rank in (ServiceRank.GREAT_FEAST, ServiceRank.VIGIL, ServiceRank.POLYELEOS, ServiceRank.DOXOLOGY, ServiceRank.SIX_STICHERA, ServiceRank.NO_SIGN):
            default_en, default_ru = labels_for(rank)
            english = QLineEdit(settings.rank_labels_en.get(rank.value, default_en))
            russian = QLineEdit(settings.rank_labels_ru.get(rank.value, default_ru))
            self.rank_label_fields[(rank.value, "en")] = english; self.rank_label_fields[(rank.value, "ru")] = russian
            rank_layout.addRow(f"{rank.value.replace('_', ' ').title()} - English", english)
            rank_layout.addRow(f"{rank.value.replace('_', ' ').title()} - Russian", russian)

        parish_layout = QFormLayout(parish)
        self.fields = {}
        for attr, label in (("parish_name", "Parish name"), ("address", "Address"), ("website", "Website"), ("phone", "Phone"), ("custom_header", "Custom header"), ("custom_footer", "Custom footer")):
            edit = QLineEdit(getattr(settings, attr)); self.fields[attr] = edit; parish_layout.addRow(label, edit)

        tabs.addTab(general, "General"); tabs.addTab(pdf, "PDF"); tabs.addTab(ranks, "Rank terminology"); tabs.addTab(parish, "Parish")
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        root = QVBoxLayout(self); root.addWidget(tabs); root.addWidget(buttons)

    @staticmethod
    def _checkbox(checked: bool) -> QCheckBox:
        widget = QCheckBox(); widget.setChecked(checked); return widget

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select output folder", self.output.text())
        if folder:
            self.output.setText(folder)

    def apply(self):
        self.settings.output_directory = self.output.text()
        self.settings.language = self.language.currentText()
        self.settings.paper = self.paper.currentText()
        self.settings.orientation = self.orientation.currentText()
        self.settings.include_julian = self.julian.isChecked()
        self.settings.include_holidays = self.holidays.isChecked()
        self.settings.include_fasting_icons = self.icons.isChecked()
        self.settings.include_fasting_legend = self.legend.isChecked()
        self.settings.include_service_rank_icons = self.rank_icons.isChecked()
        self.settings.include_service_rank_legend = self.rank_legend.isChecked()
        self.settings.rank_labels_en = {rank: field.text().strip() for (rank, language), field in self.rank_label_fields.items() if language == "en" and field.text().strip()}
        self.settings.rank_labels_ru = {rank: field.text().strip() for (rank, language), field in self.rank_label_fields.items() if language == "ru" and field.text().strip()}
        self.settings.include_sources = self.sources.isChecked()
        for attr, edit in self.fields.items():
            setattr(self.settings, attr, edit.text())
