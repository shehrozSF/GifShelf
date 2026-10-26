import io
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app import thumbnail

# Workers are unparented so they can outlive the dialog that started them;
# this set keeps them alive until they finish.
_running: set[QThread] = set()


class _Worker(QThread):
    def start(self):
        _running.add(self)
        # Bound slot (not a lambda) so it's queued to the main thread.
        self.finished.connect(self._on_finished)
        super().start()

    def _on_finished(self) -> None:
        _running.discard(self)

    def detach(self) -> None:
        """Stop delivering results and ask the thread to stop early."""
        self.requestInterruption()
        for sig in (self.succeeded, self.failed):
            try:
                sig.disconnect()
            except (RuntimeError, TypeError):
                pass


def shutdown(timeout_ms: int = 3000) -> None:
    workers = list(_running)
    for worker in workers:
        worker.requestInterruption()
    for worker in workers:
        worker.wait(timeout_ms)


class FetchWorker(_Worker):
    succeeded = Signal(bytes)
    failed = Signal(str)

    def __init__(self, source: str):
        super().__init__()
        self.source = source

    def run(self):
        try:
            data = thumbnail.fetch_bytes(self.source, should_stop=self.isInterruptionRequested)
            self.succeeded.emit(data)
        except Exception as exc:
            self.failed.emit(str(exc))


class PreviewWorker(_Worker):
    succeeded = Signal(bytes)
    failed = Signal(str)

    def __init__(self, data: bytes, max_width: int):
        super().__init__()
        self.data = data
        self.max_width = max_width

    def run(self):
        try:
            buf = io.BytesIO()
            thumbnail.generate_gif_thumbnail(self.data, buf, max_width=self.max_width)
            self.succeeded.emit(buf.getvalue())
        except Exception as exc:
            self.failed.emit(str(exc))


class ThumbnailWorker(_Worker):
    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, data: bytes, mode: str, frame_index: int, out_path: Path):
        super().__init__()
        self.data = data
        self.mode = mode
        self.frame_index = frame_index
        self.out_path = out_path

    def run(self):
        try:
            if self.mode == "frame":
                thumbnail.generate_frame_thumbnail(self.data, self.frame_index, self.out_path)
            else:
                thumbnail.generate_gif_thumbnail(self.data, self.out_path)
            self.succeeded.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
