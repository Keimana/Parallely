from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from functions import ScannerController


def load_app_icon() -> QIcon:
    icon_path = Path(__file__).resolve().parent / "Assets" / "parallely.svg"
    renderer = QSvgRenderer(str(icon_path))
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


class ScannerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parallely")
        self.setWindowIcon(load_app_icon())
        self.resize(900, 620)

        self.faq_button = QPushButton("?")
        self.faq_button.setFixedSize(32, 32)
        self.faq_button.setAccessibleName("FAQs and quick guide")
        self.faq_button.setToolTip("FAQs and quick guide")

        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Choose a folder to scan")
        self.folder_input.setReadOnly(True)
        self.browse_button = QPushButton("Browse Folder")

        self.extension_input = QLineEdit(".txt")
        self.extension_input.setPlaceholderText("Any extension")
        self.all_extensions_input = QCheckBox("Include all file types")
        extension_controls = QWidget()
        extension_layout = QHBoxLayout(extension_controls)
        extension_layout.setContentsMargins(0, 0, 0, 0)
        extension_layout.addWidget(self.extension_input, 1)
        extension_layout.addWidget(self.all_extensions_input)
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("Text to find (leave blank to match all files)")
        self.case_sensitive_input = QCheckBox("Case-sensitive")
        self.whole_word_input = QCheckBox("Whole word")
        self.whole_word_input.setChecked(True)
        keyword_controls = QWidget()
        keyword_layout = QVBoxLayout(keyword_controls)
        keyword_layout.setContentsMargins(0, 0, 0, 0)
        keyword_layout.setSpacing(4)
        keyword_layout.addWidget(self.keyword_input)
        keyword_options = QHBoxLayout()
        keyword_options.addWidget(self.case_sensitive_input)
        keyword_options.addWidget(self.whole_word_input)
        keyword_options.addStretch(1)
        keyword_layout.addLayout(keyword_options)
        self.worker_input = QSpinBox()
        self.worker_input.setRange(1, 64)
        self.worker_input.setValue(4)

        self.scan_button = QPushButton("Scan")
        self.scan_button.setObjectName("primaryButton")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.clear_button = QPushButton("Clear Results")
        self.clear_button.setEnabled(False)
        self.retry_skipped_button = QPushButton("Retry Skipped")
        self.retry_skipped_button.setEnabled(False)

        self.status_label = QLabel("Choose a folder to get started.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)

        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(["File name", "Full path", "Keyword matches", "Matched in", "Match preview", "File size"])
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_table.setSortingEnabled(True)
        self.results_table.horizontalHeader().setStretchLastSection(False)
        self.results_table.horizontalHeader().setSectionResizeMode(0, self.results_table.horizontalHeader().ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, self.results_table.horizontalHeader().ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(2, self.results_table.horizontalHeader().ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, self.results_table.horizontalHeader().ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(4, self.results_table.horizontalHeader().ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(5, self.results_table.horizontalHeader().ResizeMode.ResizeToContents)

        self.skipped_table = QTableWidget(0, 2)
        self.skipped_table.setHorizontalHeaderLabels(["Full path", "Reason"])
        self.skipped_table.setAlternatingRowColors(True)
        self.skipped_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.skipped_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.skipped_table.horizontalHeader().setSectionResizeMode(0, self.skipped_table.horizontalHeader().ResizeMode.Stretch)
        self.skipped_table.horizontalHeader().setSectionResizeMode(1, self.skipped_table.horizontalHeader().ResizeMode.Stretch)
        self.results_tabs = QTabWidget()
        self.results_tabs.addTab(self.results_table, "Results")
        self.results_tabs.addTab(self.skipped_table, "Skipped (0)")

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Parallel File Scanner")
        title.setObjectName("title")
        subtitle = QLabel("Search file contents across a folder using concurrent workers.")
        subtitle.setObjectName("subtitle")
        title_row = QHBoxLayout()
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self.faq_button)
        layout.addLayout(title_row)
        layout.addWidget(subtitle)

        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(self.browse_button)
        layout.addLayout(folder_row)

        filters_row = QHBoxLayout()
        filters_row.addWidget(self.field_group("Extension", extension_controls), 1)
        filters_row.addWidget(self.field_group("Keyword", keyword_controls), 2)
        filters_row.addWidget(self.field_group("Threads", self.worker_input))
        layout.addLayout(filters_row)

        actions_row = QHBoxLayout()
        actions_row.addWidget(self.scan_button)
        actions_row.addWidget(self.cancel_button)
        actions_row.addWidget(self.clear_button)
        actions_row.addWidget(self.retry_skipped_button)
        actions_row.addStretch(1)
        actions_row.addWidget(self.status_label)
        layout.addLayout(actions_row)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.results_tabs, 1)

        self.setCentralWidget(root)
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f3f6fc; color: #0f1729; font-family: 'Segoe UI'; font-size: 10pt; }
            QLabel#title { font-size: 19pt; font-weight: 650; color: #0f1729; }
            QLabel#subtitle { color: #63718a; margin-bottom: 6px; }
            QLineEdit, QSpinBox { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 8px; }
            QLineEdit:focus, QSpinBox:focus { border: 1px solid #1257c8; }
            QCheckBox { spacing: 7px; color: #0f1729; }
            QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #aebbd0; border-radius: 3px; background: #ffffff; }
            QCheckBox::indicator:checked { background: #1257c8; border-color: #1257c8; }
            QPushButton { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 8px 14px; }
            QPushButton:hover { background: #e8eef9; }
            QPushButton:disabled { color: #98a4b7; }
            QPushButton#primaryButton { background: #1257c8; color: #ffffff; border-color: #1257c8; font-weight: 600; }
            QPushButton#primaryButton:hover { background: #0e49a8; }
            QTableWidget { background: #ffffff; alternate-background-color: #f6f8fc; border: 1px solid #d8e0ec; gridline-color: #e7ecf4; }
            QHeaderView::section { background: #e7edf7; color: #0f1729; border: 0; padding: 8px; font-weight: 600; }
            QProgressBar { background: #e0e7f1; border: 0; border-radius: 2px; max-height: 5px; }
            QProgressBar::chunk { background: #1257c8; }
            """
        )

        self.controller = ScannerController(self)

    @staticmethod
    def field_group(label: str, field: QWidget) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        caption = QLabel(label)
        caption.setStyleSheet("font-weight: 600; color: #405047;")
        layout.addWidget(caption)
        layout.addWidget(field)
        return container

