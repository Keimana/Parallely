import sys

from PySide6.QtWidgets import QApplication

from design import ScannerWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScannerWindow()
    app.setWindowIcon(window.windowIcon())
    window.show()
    raise SystemExit(app.exec())
