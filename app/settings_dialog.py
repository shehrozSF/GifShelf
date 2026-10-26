from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app import db, storage


class SettingsDialog(QDialog):
    library_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Library location (database and thumbnails):"))

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        layout.addWidget(self.path_edit)

        hint = QLabel("Changing it moves your existing library to the new folder.")
        hint.setObjectName("muted")
        layout.addWidget(hint)

        row = QHBoxLayout()
        open_btn = QPushButton("Open folder")
        open_btn.clicked.connect(self._on_open)
        change_btn = QPushButton("Change...")
        change_btn.setObjectName("primary")
        change_btn.clicked.connect(self._on_change)
        self.default_btn = QPushButton("Use default")
        self.default_btn.clicked.connect(lambda: self._switch_to(storage.default_app_dir()))
        row.addWidget(open_btn)
        row.addWidget(change_btn)
        row.addWidget(self.default_btn)
        row.addStretch()
        layout.addLayout(row)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

        self._refresh()

    def _refresh(self) -> None:
        self.path_edit.setText(str(storage.app_dir()))
        self.default_btn.setEnabled(storage.app_dir().resolve() != storage.default_app_dir().resolve())

    def _on_open(self) -> None:
        storage.ensure_dirs()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(storage.app_dir())))

    def _on_change(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose library folder", str(storage.app_dir()))
        if chosen:
            self._switch_to(storage.library_dir_for(Path(chosen)))

    def _switch_to(self, target: Path) -> None:
        current = storage.app_dir()
        if target.resolve() == current.resolve():
            return

        if storage.has_library(target):
            answer = QMessageBox.question(
                self, "Library found",
                f"{target} already contains a {storage.APP_NAME} library.\n\n"
                f"Switch to it? Your current library stays in {current}.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            storage.use_library(target)
        else:
            answer = QMessageBox.question(
                self, "Move library",
                f"Move your library to:\n{target}\n\n"
                f"The database and thumbnails are copied there, then removed from:\n{current}",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                storage.move_library(target)
            except Exception as exc:
                QMessageBox.critical(self, "Move failed", f"Couldn't move the library:\n{exc}")
                return
            finally:
                QGuiApplication.restoreOverrideCursor()

        db.init_db()
        self._refresh()
        self.library_changed.emit()
