import os
import threading
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMenu,
    QMessageBox,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
)

from preprocess import normalize_extension, normalize_keyword
from process import ScanSignals, scan_folder


def format_elapsed_time(seconds: float) -> str:
    if seconds < 0.001:
        return "under 1 ms"
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{seconds:.2f} sec"

    total_seconds = round(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, whole_seconds = divmod(remainder, 60)
    if hours:
        return f"{hours} hr {minutes} min {whole_seconds} sec"
    return f"{minutes} min {whole_seconds} sec"


class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        value = self.data(Qt.ItemDataRole.UserRole)
        other_value = other.data(Qt.ItemDataRole.UserRole)
        if value is not None and other_value is not None:
            return value < other_value
        return super().__lt__(other)


def format_file_size(size: int) -> str:
    if size < 1024:
        return f"{size:,} B"

    value = float(size)
    for unit in ("KB", "MB", "GB", "TB", "PB", "EB"):
        value /= 1024
        if value < 1024 or unit == "EB":
            return f"{value:.2f} {unit}"
    return f"{value:.2f} EB"


class ScannerController:
    def __init__(self, window):
        self.window = window
        self.cancel_event = None
        self.last_extension = window.extension_input.text().strip()
        self.discovered_count = 0
        self.scanned_count = 0
        self.match_count = 0
        self.signals = ScanSignals(window)
        self.signals.progress.connect(self.on_progress)
        self.signals.match.connect(self.add_match)
        self.signals.finished.connect(self.on_finished)
        self.signals.discovered.connect(self.on_discovered)
        self.signals.skipped.connect(self.add_skipped)

        window.browse_button.clicked.connect(self.choose_folder)
        window.scan_button.clicked.connect(self.start_scan)
        window.cancel_button.clicked.connect(self.cancel_scan)
        window.clear_button.clicked.connect(self.clear_results)
        window.retry_skipped_button.clicked.connect(self.retry_skipped)
        window.faq_button.clicked.connect(self.show_faq)
        window.all_extensions_input.toggled.connect(self.on_all_extensions_toggled)
        window.results_table.cellDoubleClicked.connect(self.open_result)
        window.results_table.customContextMenuRequested.connect(self.show_result_context_menu)
        self.on_all_extensions_toggled(window.all_extensions_input.isChecked())

    def show_faq(self):
        dialog = QDialog(self.window)
        dialog.setWindowTitle("FAQs & Quick Guide")
        dialog.resize(620, 520)

        layout = QVBoxLayout(dialog)
        guide = QTextBrowser()
        guide.setOpenExternalLinks(True)
        guide.setHtml(
            """
            <h2>Quick start</h2>
            <ol>
              <li>Choose a folder with <b>Browse Folder</b>.</li>
              <li>Enter an extension such as <code>.txt</code> or <code>.png</code>. Check <b>Include all file types</b> to search every extension.</li>
              <li>Enter a keyword, then choose case sensitivity and whole-word matching.</li>
              <li>Set the worker count and select <b>Scan</b>. Use <b>Cancel</b> to stop.</li>
            </ol>
            <h2>What gets matched?</h2>
            <p>The keyword is searched inside every readable text file in the selected scope, even when the keyword is not in the filename. It is also checked against the filename without its extension. The <b>Matched in</b> column tells you which one matched; <b>Match preview</b> shows a short excerpt from the first matching content line. Case-sensitive matching requires the same capitalization; whole-word matching avoids matches inside longer words.</p>
            <p>Text content is read as UTF-8. Binary files such as PNGs and MP4s are skipped unless their filename matches the keyword. This app does not perform OCR or extract text from media.</p>
            <h2>Results and skipped files</h2>
            <p>Double-click a result to open it. Right-click it and choose <b>Open in File Explorer</b> to reveal the file in its folder. The <b>Skipped</b> tab lists files that could not be searched and why. Use <b>Retry Skipped</b> after resolving access problems.</p>
            <p><b>Clear Results</b> removes both results and skipped entries. A blank keyword returns every file in the selected scope that can be read as text, plus any filename matches.</p>
            """
        )
        layout.addWidget(guide)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self.window, "Select folder")
        if folder:
            self.window.folder_input.setText(folder)

    def start_scan(self):
        self._start_scan()

    def retry_skipped(self):
        paths = [
            self.window.skipped_table.item(row, 0).text()
            for row in range(self.window.skipped_table.rowCount())
            if self.window.skipped_table.item(row, 0)
        ]
        if paths:
            self._start_scan(paths)

    def _start_scan(self, file_paths: list[str] | None = None):
        window = self.window
        folder = window.folder_input.text().strip()
        if file_paths is None and (not folder or not os.path.isdir(folder)):
            QMessageBox.warning(window, "Folder required", "Choose an existing folder before scanning.")
            return

        extension_text = window.extension_input.text().strip()
        include_all_types = window.all_extensions_input.isChecked()
        if file_paths is None and not include_all_types and not extension_text:
            QMessageBox.warning(
                window,
                "Extension required",
                "Enter a file extension or select Include all file types.",
            )
            return

        extension = "" if file_paths is not None or include_all_types else normalize_extension(extension_text)
        case_sensitive = window.case_sensitive_input.isChecked()
        whole_word = window.whole_word_input.isChecked()
        keyword = normalize_keyword(window.keyword_input.text(), case_sensitive)
        worker_count = window.worker_input.value()
        window.results_table.setSortingEnabled(False)
        self.clear_results()
        self.discovered_count = 0
        self.scanned_count = 0
        self.match_count = 0
        self.cancel_event = threading.Event()
        self.set_scanning(True)
        window.progress_bar.setRange(0, 0)
        window.status_label.setText("Discovering matching files...")

        thread = threading.Thread(
            target=scan_folder,
            args=(
                folder,
                extension,
                keyword,
                case_sensitive,
                worker_count,
                self.cancel_event,
                self.signals,
                file_paths,
                whole_word,
            ),
            daemon=True,
        )
        thread.start()

    def on_discovered(self, discovered: int):
        self.discovered_count = discovered
        self.window.progress_bar.setRange(0, max(1, discovered))
        self.window.progress_bar.setValue(0)
        self.update_status()

    def on_progress(self, scanned: int, matches: int):
        self.scanned_count = scanned
        self.match_count = matches
        self.window.progress_bar.setValue(scanned)
        self.update_status()

    def update_status(self):
        self.window.status_label.setText(
            f"Discovered {self.discovered_count:,}  |  "
            f"Scanned {self.scanned_count:,}  |  "
            f"Matches {self.match_count:,}"
        )

    def add_match(self, path: str, matches: int, size: int, match_source: str, preview: str):
        table = self.window.results_table
        row = table.rowCount()
        table.insertRow(row)
        name_item = QTableWidgetItem(Path(path).name)
        name_item.setToolTip(path)
        path_item = QTableWidgetItem(path)
        path_item.setToolTip(path)
        match_item = NumericTableWidgetItem(str(matches))
        match_item.setData(Qt.ItemDataRole.UserRole, matches)
        source_item = QTableWidgetItem(match_source)
        preview_item = QTableWidgetItem(preview or ("No content match" if match_source == "File name" else ""))
        preview_item.setToolTip(preview)
        size_item = NumericTableWidgetItem(format_file_size(size))
        size_item.setData(Qt.ItemDataRole.UserRole, size)
        table.setItem(row, 0, name_item)
        table.setItem(row, 1, path_item)
        table.setItem(row, 2, match_item)
        table.setItem(row, 3, source_item)
        table.setItem(row, 4, preview_item)
        table.setItem(row, 5, size_item)

    def add_skipped(self, path: str, reason: str):
        table = self.window.skipped_table
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(path))
        table.setItem(row, 1, QTableWidgetItem(reason))
        table.item(row, 0).setToolTip(path)
        table.item(row, 1).setToolTip(reason)
        self.window.results_tabs.setTabText(1, f"Skipped ({row + 1})")

    def clear_results(self):
        self.window.results_table.setRowCount(0)
        self.window.skipped_table.setRowCount(0)
        self.window.results_tabs.setTabText(1, "Skipped (0)")
        self.window.clear_button.setEnabled(False)
        self.window.retry_skipped_button.setEnabled(False)

    def cancel_scan(self):
        if self.cancel_event is not None:
            self.cancel_event.set()
            self.window.status_label.setText("Stopping scan...")
            self.window.cancel_button.setEnabled(False)

    def on_finished(self, scanned: int, matches: int, duration: float, cancelled: bool):
        window = self.window
        window.results_table.setSortingEnabled(True)
        self.set_scanning(False)
        window.progress_bar.setRange(0, 1)
        window.progress_bar.setValue(1)
        self.scanned_count = scanned
        self.match_count = matches
        skipped = window.skipped_table.rowCount()
        prefix = "Cancelled" if cancelled else "Finished"
        window.status_label.setText(
            f"{prefix} | Discovered {self.discovered_count:,}  |  "
            f"Scanned {scanned:,}  |  Matches {matches:,}  |  "
            f"Skipped {skipped:,}  |  Elapsed {format_elapsed_time(duration)}"
        )
        self.cancel_event = None

    def set_scanning(self, scanning: bool):
        window = self.window
        window.scan_button.setEnabled(not scanning)
        window.browse_button.setEnabled(not scanning)
        window.extension_input.setEnabled(not scanning and not window.all_extensions_input.isChecked())
        window.all_extensions_input.setEnabled(not scanning)
        window.keyword_input.setEnabled(not scanning)
        window.case_sensitive_input.setEnabled(not scanning)
        window.worker_input.setEnabled(not scanning)
        window.cancel_button.setEnabled(scanning)
        window.clear_button.setEnabled(not scanning and window.results_table.rowCount() > 0)
        window.retry_skipped_button.setEnabled(not scanning and window.skipped_table.rowCount() > 0)

    def on_all_extensions_toggled(self, checked: bool):
        extension_input = self.window.extension_input
        if checked:
            if extension_input.text().strip():
                self.last_extension = extension_input.text().strip()
            extension_input.clear()
            extension_input.setPlaceholderText("All extensions included")
        else:
            extension_input.setPlaceholderText(".txt, .log, .py")
            if not extension_input.text().strip() and self.last_extension:
                extension_input.setText(self.last_extension)
        extension_input.setEnabled(not checked and self.cancel_event is None)

    def open_result(self, row: int, _column: int):
        path_item = self.window.results_table.item(row, 1)
        if path_item:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path_item.text()))

    def show_result_context_menu(self, position):
        table = self.window.results_table
        index = table.indexAt(position)
        if not index.isValid():
            return

        table.selectRow(index.row())
        path_item = table.item(index.row(), 1)
        if not path_item:
            return

        menu = QMenu(table)
        open_location = menu.addAction("Open in File Explorer")
        if menu.exec(table.viewport().mapToGlobal(position)) == open_location:
            self.reveal_in_file_explorer(path_item.text())

    @staticmethod
    def reveal_in_file_explorer(path: str):
        if os.name == "nt":
            windows_path = os.path.abspath(os.path.normpath(path))
            QProcess.startDetached("explorer.exe", ["/select,", windows_path])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))