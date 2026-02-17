import sys
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QCoreApplication

QGuiApplication.setDesktopFileName("io.github.quotezproject.quotez")

QCoreApplication.setApplicationName("QuoteZ")

def main(argv=None):
    # import GUI lazily
    from PySide6.QtWidgets import QApplication
    from app.ui_main import MainWindow

    if argv is None:
        argv = sys.argv

    app = QApplication(argv)
    win = MainWindow()
    win.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())