from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout

from orthodox_calendar.database.database import Database


class SourceDialog(QDialog):
    def __init__(self, database: Database, parent=None):
        super().__init__(parent); self.setWindowTitle("Calendar Data Sources"); self.resize(760, 440)
        stats = database.stats(); summary = QLabel("  ·  ".join(f"{key.replace('_',' ').title()}: {value}" for key, value in stats.items()))
        table = QTableWidget(0, 4); table.setHorizontalHeaderLabels(["Source", "Status", "Last successful", "Message"]); table.horizontalHeader().setStretchLastSection(True)
        rows = database.source_status(); table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for col, value in enumerate((row["source_name"], row["status"], row["last_success"] or "Never", row["message"])): table.setItem(r, col, QTableWidgetItem(str(value)))
        buttons = QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(self.reject)
        root = QVBoxLayout(self); root.addWidget(summary); root.addWidget(table); root.addWidget(buttons)

