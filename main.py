import ctypes
import sys

from PySide6.QtWidgets import QApplication

from design import ScannerWindow, load_app_icon


if __name__ == "__main__":
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Keimana.Parallely")

    app = QApplication(sys.argv)
    app.setWindowIcon(load_app_icon())
    window = ScannerWindow()
    window.show()
    raise SystemExit(app.exec())
