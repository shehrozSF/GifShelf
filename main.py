import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app import __version__, workers
from app.db import init_db
from app.main_window import MainWindow
from app.storage import APP_ID

# Must match AppMutex in installer/GifShelf.iss. While it exists, the installer
# and uninstaller ask the user to close GifShelf instead of running over it.
APP_MUTEX = "GifShelf-80CB7E02"


def resource_path(relative: str) -> Path:
    """Bundled file path, both from source and inside a PyInstaller build."""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base) / relative


def main() -> None:
    if sys.platform == "win32":
        # Own taskbar group + icon, instead of being grouped under python.exe.
        # Kept version-free so taskbar pins survive updates.
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)

        # Released automatically when the process exits. The Global\ copy covers
        # an uninstall started from another user session.
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        for name in (APP_MUTEX, "Global\\" + APP_MUTEX):
            kernel32.CreateMutexW(None, False, name)

    init_db()
    app = QApplication(sys.argv)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(resource_path("assets/icon.ico"))))
    app.aboutToQuit.connect(workers.shutdown)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
