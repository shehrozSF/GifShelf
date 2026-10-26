import html
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImageReader, QMovie, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout

from app import db
from app.qtutil import movie_from_bytes
from app.storage import thumb_file

THUMB_W, THUMB_H = 120, 90


class _ElidedLabel(QLabel):
    """One-line label that elides to fit its width; the full text is in the tooltip.

    Long URLs have no break points, so word wrap can't shrink them and they
    would force the card wider than the window.
    """

    def __init__(self, text: str, mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight):
        super().__init__()
        self._full_text = text
        self._mode = mode
        # QLabel auto-detects rich text; user-entered titles/URLs must not render as HTML.
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setToolTip(f"<p>{html.escape(text)}</p>")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(self._full_text, self._mode, self.width()))


class CardWidget(QFrame):
    copy_requested = Signal(int)
    edit_requested = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, entry: db.Entry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._movie: QMovie | None = None

        layout = QHBoxLayout(self)

        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(THUMB_W, THUMB_H)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_thumbnail()
        layout.addWidget(self.thumb_label)

        info_col = QVBoxLayout()
        info_col.setSpacing(4)
        title_label = _ElidedLabel(entry.title or entry.url)
        font = title_label.font()
        font.setBold(True)
        title_label.setFont(font)
        info_col.addWidget(title_label)

        url_label = _ElidedLabel(entry.url, Qt.TextElideMode.ElideMiddle)
        url_label.setObjectName("muted")
        info_col.addWidget(url_label)

        tags_label = _ElidedLabel("Tags: " + (", ".join(entry.tags) if entry.tags else "(none)"))
        tags_label.setObjectName("muted")
        info_col.addWidget(tags_label)
        info_col.addStretch()

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy link")
        copy_btn.setObjectName("primary")
        copy_btn.clicked.connect(lambda: self.copy_requested.emit(self.entry.id))
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.entry.id))
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.entry.id))
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        info_col.addLayout(btn_row)

        layout.addLayout(info_col, stretch=1)

    def _load_thumbnail(self) -> None:
        path = thumb_file(self.entry.thumb_path)
        if not path or not path.exists():
            self.thumb_label.setText("No preview")
            return

        if self.entry.thumb_mode == "gif":
            self._movie = movie_from_bytes(path.read_bytes(), self)
            self._movie.setScaledSize(self._fit_size(path))
            self.thumb_label.setMovie(self._movie)
            self._movie.start()
        else:
            pix = QPixmap(str(path))
            self.thumb_label.setPixmap(
                pix.scaled(THUMB_W, THUMB_H, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )

    def _fit_size(self, path: Path) -> QSize:
        size = QImageReader(str(path)).size()
        if size.width() <= 0 or size.height() <= 0:
            return QSize(THUMB_W, THUMB_H)
        ratio = min(THUMB_W / size.width(), THUMB_H / size.height())
        return QSize(max(1, int(size.width() * ratio)), max(1, int(size.height() * ratio)))
