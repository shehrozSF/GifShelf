from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject
from PySide6.QtGui import QImage, QMovie, QPixmap


def pil_to_qpixmap(img: Image.Image) -> QPixmap:
    rgba = img.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimage = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


def movie_from_bytes(data: bytes, parent: QObject) -> QMovie:
    """Play from memory so no file handle stays open (Windows can't delete open files)."""
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    movie = QMovie(buffer, QByteArray(), parent)
    buffer.setParent(movie)
    return movie
