import sys

from PySide6.QtWidgets import QApplication

from app import workers
from app.db import init_db
from app.main_window import MainWindow
from app.storage import remove_stale_previews


def main() -> None:
    init_db()
    remove_stale_previews()
    app = QApplication(sys.argv)
    app.aboutToQuit.connect(workers.shutdown)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
