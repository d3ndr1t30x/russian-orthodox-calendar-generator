APP_STYLESHEET = """
QMainWindow, QDialog { background: #f4f1eb; }
QWidget { color: #2c2723; font-family: "Segoe UI"; font-size: 10pt; }
QToolBar { background: #2d2220; border: none; spacing: 8px; padding: 6px; }
QToolBar QToolButton { color: white; padding: 7px 10px; border-radius: 4px; }
QToolBar QToolButton:hover { background: #684047; }
QGroupBox { background: #fffdf9; border: 1px solid #d5c9bc; border-radius: 7px; margin-top: 12px; padding: 12px 8px 8px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #782535; }
QPushButton { background: #782535; color: white; border: none; border-radius: 5px; padding: 8px 14px; font-weight: 600; }
QPushButton:hover { background: #963447; }
QPushButton:disabled { background: #aaa29b; }
QComboBox, QSpinBox, QLineEdit, QTextEdit { background: white; border: 1px solid #bdb2a7; border-radius: 4px; padding: 5px; }
QComboBox { color: #111111; min-height: 20px; }
QComboBox QAbstractItemView { background: #ffffff; color: #111111; border: 1px solid #777777; selection-background-color: #d9eaf7; selection-color: #111111; outline: 0; }
QMenu { background: #ffffff; color: #111111; border: 1px solid #999999; }
QMenu::item { background: transparent; color: #111111; padding: 6px 24px 6px 10px; }
QMenu::item:selected { background: #d9eaf7; color: #111111; }
QHeaderView::section { background: #eadfd4; padding: 5px; border: none; border-right: 1px solid #d5c9bc; font-weight: 600; }
QTableWidget { background: white; gridline-color: #ded6ce; border: 1px solid #d5c9bc; }
QStatusBar { background: #2d2220; color: white; }
QTabWidget::pane { border: 1px solid #d5c9bc; background: white; }
QTabBar::tab { background: #e5ddd4; padding: 8px 14px; }
QTabBar::tab:selected { background: #782535; color: white; }
"""
