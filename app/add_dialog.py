import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QMovie, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
)

from app import db, thumbnail
from app.qtutil import movie_from_bytes, pil_to_qpixmap
from app.storage import remove_thumb, thumb_dir, thumb_file
from app.workers import FetchWorker, PreviewWorker, ThumbnailWorker

PREVIEW_SIZE = 200
FRAME_DEBOUNCE_MS = 80


class AddEditDialog(QDialog):
    def __init__(self, all_tags: list[str], entry: db.Entry | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit GIF" if entry else "Add GIF")
        self.setMinimumWidth(440)

        self.entry = entry
        self.raw_data: bytes | None = None
        self.loaded_source: str | None = None
        self.pil_image = None
        self.fetch_worker: FetchWorker | None = None
        self.preview_worker: PreviewWorker | None = None
        self.thumb_worker: ThumbnailWorker | None = None
        self._pending_save: tuple[Path, str, str, str, list[str]] | None = None
        self._preview_movie: QMovie | None = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.url_edit = QLineEdit(entry.url if entry else "")
        self.url_edit.setPlaceholderText("https://... or local file path")
        self.load_btn = QPushButton("Load preview")
        self.load_btn.clicked.connect(self._on_load_clicked)

        url_row = QHBoxLayout()
        url_row.addWidget(self.url_edit)
        url_row.addWidget(self.load_btn)
        form.addRow("URL / path:", url_row)

        self.title_edit = QLineEdit(entry.title if entry else "")
        self.title_edit.setPlaceholderText("optional label")
        form.addRow("Title:", self.title_edit)

        layout.addLayout(form)

        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        preview_row = QHBoxLayout()
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px solid; border-color: palette(mid);")
        preview_row.addWidget(self.preview_label)

        mode_col = QVBoxLayout()
        self.mode_gif = QRadioButton("Whole GIF (animated)")
        self.mode_frame = QRadioButton("Selected frame (static)")
        self.mode_gif.setChecked(True)
        self.mode_gif.toggled.connect(self._on_mode_changed)
        mode_col.addWidget(self.mode_gif)
        mode_col.addWidget(self.mode_frame)

        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setEnabled(False)
        self.frame_slider.valueChanged.connect(self._on_frame_changed)
        mode_col.addWidget(self.frame_slider)
        # Seeking a GIF backwards re-decodes from the start, so don't do it per slider tick.
        self._frame_timer = QTimer(self)
        self._frame_timer.setSingleShot(True)
        self._frame_timer.setInterval(FRAME_DEBOUNCE_MS)
        self._frame_timer.timeout.connect(self._refresh_preview)
        self.frame_label = QLabel("")
        self.frame_label.setObjectName("muted")
        mode_col.addWidget(self.frame_label)
        mode_col.addStretch()

        preview_row.addLayout(mode_col)
        layout.addLayout(preview_row)

        layout.addWidget(QLabel("Existing tags (click to toggle):"))
        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.tag_list.setMaximumHeight(110)
        for name in all_tags:
            item = QListWidgetItem(name)
            self.tag_list.addItem(item)
            if entry and name in entry.tags:
                item.setSelected(True)
        layout.addWidget(self.tag_list)

        self.new_tags_edit = QLineEdit()
        self.new_tags_edit.setPlaceholderText("new tags, comma separated")
        layout.addWidget(self.new_tags_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.save_btn.setEnabled(entry is not None)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        if entry:
            self.mode_frame.setChecked(entry.thumb_mode == "frame")
            self._show_existing_thumb(entry)

    def _show_existing_thumb(self, entry: db.Entry) -> None:
        path = thumb_file(entry.thumb_path)
        if path and path.exists():
            if entry.thumb_mode == "gif":
                self._set_preview_movie(path.read_bytes())
            else:
                pix = QPixmap(str(path))
                self.preview_label.setPixmap(
                    pix.scaled(PREVIEW_SIZE, PREVIEW_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )

    def _set_preview_movie(self, data: bytes | None) -> None:
        if self._preview_movie is not None:
            self._preview_movie.stop()
            self._preview_movie.deleteLater()
            self._preview_movie = None
        self.preview_label.setMovie(None)
        if data is not None:
            self._preview_movie = movie_from_bytes(data, self.preview_label)
            self.preview_label.setMovie(self._preview_movie)
            self._preview_movie.start()

    def _on_load_clicked(self) -> None:
        source = self.url_edit.text().strip()
        if not source:
            QMessageBox.warning(self, "Missing source", "Enter a URL or local file path first.")
            return
        self.load_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.status_label.setText("Loading...")

        self.fetch_worker = FetchWorker(source)
        self.fetch_worker.succeeded.connect(self._on_fetch_succeeded)
        self.fetch_worker.failed.connect(self._on_fetch_failed)
        self.fetch_worker.start()

    def _on_fetch_succeeded(self, data: bytes) -> None:
        # Only commit once the image parses, so a bad reload keeps the previous one.
        try:
            image = thumbnail.open_image(data)
            n_frames = thumbnail.get_frame_count(image)
        except Exception as exc:
            self._on_fetch_failed(str(exc))
            return
        self.raw_data = data
        self.pil_image = image
        self.loaded_source = self.fetch_worker.source

        self.load_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.status_label.setText(f"Loaded ({n_frames} frame{'s' if n_frames != 1 else ''}).")

        self.frame_slider.blockSignals(True)
        self.frame_slider.setMaximum(max(0, n_frames - 1))
        self.frame_slider.setValue(0)
        self.frame_slider.blockSignals(False)
        self.frame_slider.setEnabled(self.mode_frame.isChecked() and n_frames > 1)
        self.frame_label.setText("Frame 0")

        self._refresh_preview()

    def _on_fetch_failed(self, message: str) -> None:
        self.load_btn.setEnabled(True)
        # Saving is still valid with previously loaded data, or unchanged when editing.
        self.save_btn.setEnabled(self.raw_data is not None or self.entry is not None)
        self.status_label.setText(f"Failed to load: {message}")

    def _on_mode_changed(self) -> None:
        self.frame_slider.setEnabled(self.mode_frame.isChecked() and self.frame_slider.maximum() > 0)
        self._refresh_preview()

    def _on_frame_changed(self, value: int) -> None:
        self.frame_label.setText(f"Frame {value}")
        if self.mode_frame.isChecked():
            self._frame_timer.start()

    def _refresh_preview(self) -> None:
        if self.pil_image is None:
            return

        self._detach_preview_worker()
        if self.mode_gif.isChecked():
            self.preview_worker = PreviewWorker(self.raw_data, PREVIEW_SIZE)
            self.preview_worker.succeeded.connect(self._set_preview_movie)
            self.preview_worker.failed.connect(self._on_preview_failed)
            self.preview_worker.start()
        else:
            frame = thumbnail.get_frame(self.pil_image, self.frame_slider.value())
            frame.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE))
            self._set_preview_movie(None)
            self.preview_label.setPixmap(pil_to_qpixmap(frame))

    def _on_preview_failed(self, message: str) -> None:
        self.status_label.setText(f"Preview error: {message}")

    def _detach_preview_worker(self) -> None:
        # A superseded preview must not overwrite the current one when it finishes.
        if self.preview_worker and self.preview_worker.isRunning():
            self.preview_worker.detach()
        self.preview_worker = None

    def _collect_tags(self) -> list[str]:
        selected = [item.text() for item in self.tag_list.selectedItems()]
        new_raw = self.new_tags_edit.text().split(",")
        new_tags = [t.strip() for t in new_raw if t.strip()]
        combined = {t for t in selected + new_tags}
        return sorted(combined, key=str.lower)

    def _on_save_clicked(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Enter a URL or local file path.")
            return

        tags = self._collect_tags()
        title = self.title_edit.text().strip()

        mode = "frame" if self.mode_frame.isChecked() else "gif"

        if self.raw_data is None:
            if self.entry is None:
                QMessageBox.warning(self, "Not loaded", "Click 'Load preview' before saving.")
                return
            if mode != self.entry.thumb_mode:
                QMessageBox.warning(self, "Not loaded", "Click 'Load preview' to regenerate the thumbnail in the new mode.")
                return
            self._finish_save(self.entry.thumb_path, self.entry.thumb_mode, url, title, tags)
            return

        if url != self.loaded_source:
            QMessageBox.warning(
                self, "URL changed",
                "The URL changed after the preview was loaded. Click 'Load preview' again so the thumbnail matches.",
            )
            return

        ext = "png" if mode == "frame" else "gif"
        out_path = thumb_dir() / f"{uuid.uuid4().hex}.{ext}"

        # Cancel is locked until the worker reports back, so a finished
        # thumbnail can't commit after the user backed out.
        self.save_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Generating thumbnail...")

        self._pending_save = (out_path, mode, url, title, tags)
        self.thumb_worker = ThumbnailWorker(self.raw_data, mode, self.frame_slider.value(), out_path)
        self.thumb_worker.succeeded.connect(self._on_thumb_succeeded)
        self.thumb_worker.failed.connect(self._on_thumb_failed)
        self.thumb_worker.start()

    def _on_thumb_succeeded(self) -> None:
        out_path, mode, url, title, tags = self._pending_save
        self._pending_save = None
        self._finish_save(out_path.name, mode, url, title, tags)

    def _on_thumb_failed(self, message: str) -> None:
        if self._pending_save:
            remove_thumb(self._pending_save[0].name)
            self._pending_save = None
        self.save_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText(f"Thumbnail failed: {message}")

    def _finish_save(self, thumb_path: str, mode: str, url: str, title: str, tags: list[str]) -> None:
        if self.entry:
            db.update_entry(self.entry.id, url, title, thumb_path, mode, tags)
            if thumb_path != self.entry.thumb_path:
                remove_thumb(self.entry.thumb_path)
        else:
            db.add_entry(url, title, thumb_path, mode, tags)
        self.accept()

    def reject(self) -> None:
        # Also covers Esc and the window close button.
        if self._pending_save is not None:
            return
        super().reject()

    def done(self, result: int) -> None:
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.detach()
        self._detach_preview_worker()
        self._frame_timer.stop()
        self._set_preview_movie(None)
        super().done(result)
