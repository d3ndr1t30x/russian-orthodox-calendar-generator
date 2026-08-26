from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout
from PySide6.QtCore import Qt


class PreviewDialog(QDialog):
    def __init__(self, pdf_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"PDF Preview — {pdf_path.name}")
        self.resize(1050, 800)
        self.document = QPdfDocument(self)
        self.document.load(str(pdf_path))
        self.view = QPdfView(); self.view.setDocument(self.document); self.view.setPageMode(QPdfView.PageMode.SinglePage); self.view.setZoomMode(QPdfView.ZoomMode.FitInView)
        previous = QPushButton("Previous"); next_button = QPushButton("Next"); fit = QPushButton("Fit page")
        self.page_label = QLabel()
        previous.clicked.connect(lambda: self.go(-1)); next_button.clicked.connect(lambda: self.go(1)); fit.clicked.connect(lambda: self.view.setZoomMode(QPdfView.ZoomMode.FitInView))
        zoom = QSlider(Qt.Horizontal); zoom.setRange(50, 220); zoom.setValue(100); zoom.setMaximumWidth(220); zoom.valueChanged.connect(self.set_zoom)
        bar = QHBoxLayout(); bar.addWidget(previous); bar.addWidget(next_button); bar.addWidget(self.page_label); bar.addStretch(); bar.addWidget(QLabel("Zoom")); bar.addWidget(zoom); bar.addWidget(fit)
        root = QVBoxLayout(self); root.addLayout(bar); root.addWidget(self.view)
        self.update_label()

    def go(self, delta: int) -> None:
        navigator = self.view.pageNavigator(); page = max(0, min(self.document.pageCount() - 1, navigator.currentPage() + delta)); navigator.jump(page, navigator.currentLocation(), navigator.currentZoom()); self.update_label()

    def set_zoom(self, value: int) -> None:
        self.view.setZoomMode(QPdfView.ZoomMode.Custom); self.view.setZoomFactor(value / 100)

    def update_label(self) -> None:
        self.page_label.setText(f"Page {self.view.pageNavigator().currentPage() + 1} of {self.document.pageCount()}")

