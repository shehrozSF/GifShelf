import io
import math
import time
from pathlib import Path
from typing import BinaryIO, Callable

import requests
from PIL import Image, ImageSequence

MAX_THUMB_WIDTH = 160
MAX_FRAMES = 40
REQUEST_TIMEOUT = 15
TOTAL_TIMEOUT = 60
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
TRANSPARENT_INDEX = 255


def is_url(source: str) -> bool:
    return source.lower().startswith(("http://", "https://"))


def _too_large() -> ValueError:
    return ValueError(f"File is larger than {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB")


def fetch_bytes(source: str, should_stop: Callable[[], bool] = lambda: False) -> bytes:
    if not is_url(source):
        path = Path(source)
        if path.stat().st_size > MAX_DOWNLOAD_BYTES:
            raise _too_large()
        return path.read_bytes()

    deadline = time.monotonic() + TOTAL_TIMEOUT
    with requests.get(source, timeout=REQUEST_TIMEOUT, stream=True) as resp:
        resp.raise_for_status()
        declared = resp.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > MAX_DOWNLOAD_BYTES:
            raise _too_large()

        buf = bytearray()
        for chunk in resp.iter_content(CHUNK_SIZE):
            if should_stop():
                raise RuntimeError("Cancelled")
            if time.monotonic() > deadline:
                raise TimeoutError(f"Download took longer than {TOTAL_TIMEOUT}s")
            buf.extend(chunk)
            if len(buf) > MAX_DOWNLOAD_BYTES:
                raise _too_large()
        return bytes(buf)


def open_image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def get_frame_count(img: Image.Image) -> int:
    return getattr(img, "n_frames", 1)


def get_frame(img: Image.Image, index: int) -> Image.Image:
    img.seek(max(0, min(index, get_frame_count(img) - 1)))
    return img.convert("RGBA")


def _scaled_size(size: tuple[int, int], max_width: int) -> tuple[int, int]:
    w, h = size
    if w <= max_width:
        return w, h
    ratio = max_width / w
    return max_width, max(1, round(h * ratio))


def generate_frame_thumbnail(data: bytes, frame_index: int, out_path: Path, max_width: int = MAX_THUMB_WIDTH) -> None:
    img = open_image(data)
    frame = get_frame(img, frame_index)
    frame = frame.resize(_scaled_size(frame.size, max_width), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.save(out_path, format="PNG", optimize=True)


def _to_palette(rgba: Image.Image) -> Image.Image:
    # Converting RGBA straight to "P" drops alpha, so quantize the colours to
    # 255 entries and reserve the last palette slot for transparent pixels.
    p = rgba.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
    palette = p.getpalette()[: 255 * 3]
    palette += [0] * (256 * 3 - len(palette))
    p.putpalette(palette)
    mask = rgba.getchannel("A").point(lambda a: 255 if a < 128 else 0)
    p.paste(TRANSPARENT_INDEX, mask=mask)
    p.info["transparency"] = TRANSPARENT_INDEX
    return p


def generate_gif_thumbnail(data: bytes, out: Path | BinaryIO, max_width: int = MAX_THUMB_WIDTH) -> None:
    img = open_image(data)
    step = math.ceil(get_frame_count(img) / MAX_FRAMES)

    frames = []
    durations = []
    size = None
    for i, frame in enumerate(ImageSequence.Iterator(img)):
        # 0 ms means "as fast as possible"; browsers render it as ~100 ms.
        duration = frame.info.get("duration") or 100
        if i % step:
            durations[-1] += duration
            continue
        rgba = frame.convert("RGBA")
        if size is None:
            size = _scaled_size(rgba.size, max_width)
        frames.append(_to_palette(rgba.resize(size, Image.LANCZOS)))
        durations.append(duration)

    if not frames:
        return

    if isinstance(out, Path):
        out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        transparency=TRANSPARENT_INDEX,
        disposal=2,
    )
