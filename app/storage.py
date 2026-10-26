import shutil
import sqlite3
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings, QStandardPaths

APP_NAME = "GifShelf"  # shown to users
APP_ID = "GifShelf"  # folder/settings name, so no spaces
DB_NAME = "library.sqlite3"
THUMB_DIR_NAME = "thumbnails"
_SETTINGS_KEY = "storage_dir"

# QStandardPaths builds per-user folders from the application name; no
# organisation name, so it's %LOCALAPPDATA%\GifShelf rather than <org>\GifShelf.
QCoreApplication.setApplicationName(APP_ID)


def _standard_dir(location: QStandardPaths.StandardLocation) -> Path:
    return Path(QStandardPaths.writableLocation(location))


def default_app_dir() -> Path:
    """Per-user data folder: %LOCALAPPDATA%\\GifShelf, ~/Library/Application Support/GifShelf,
    or ~/.local/share/GifShelf. Local (not roaming) since thumbnails can get large."""
    return _standard_dir(QStandardPaths.StandardLocation.AppLocalDataLocation)


def settings() -> QSettings:
    # An ini file instead of the Windows registry: same behaviour on every OS,
    # easy to find, and removing the app's folder removes everything.
    path = _standard_dir(QStandardPaths.StandardLocation.AppConfigLocation) / "settings.ini"
    return QSettings(str(path), QSettings.Format.IniFormat)


def app_dir() -> Path:
    value = settings().value(_SETTINGS_KEY, "")
    return Path(value) if value else default_app_dir()


def thumb_dir() -> Path:
    return app_dir() / THUMB_DIR_NAME


def db_path() -> Path:
    return app_dir() / DB_NAME


def ensure_dirs() -> None:
    thumb_dir().mkdir(parents=True, exist_ok=True)


def thumb_file(name: str | None) -> Path | None:
    """Resolve a stored thumbnail name to a path inside the current thumbnail dir.

    Only the file name is used, so the library survives being moved and a
    tampered DB value can't point anywhere else.
    """
    if not name:
        return None
    base = Path(name).name
    if base in ("", ".", ".."):
        return None
    return thumb_dir() / base


def remove_thumb(name: str | Path | None) -> None:
    path = thumb_file(str(name) if name else None)
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def has_library(directory: Path) -> bool:
    return (directory / DB_NAME).exists()


def _is_empty_dir(path: Path) -> bool:
    try:
        return path.is_dir() and not any(path.iterdir())
    except OSError:
        return False


def library_dir_for(chosen: Path) -> Path:
    """Where the library goes when the user picks `chosen` in a folder dialog.

    An existing library, or an empty/new folder, is used as-is; anything else
    (a drive root like D:\\, Documents, ...) gets a dedicated GifShelf
    subfolder, so our files never mix with the user's.
    """
    chosen = chosen.resolve()
    is_root = chosen == Path(chosen.anchor)
    if has_library(chosen) or not chosen.exists() or (_is_empty_dir(chosen) and not is_root):
        return chosen
    return chosen / APP_ID


def _referenced_thumbs(db_file: Path) -> list[str]:
    con = sqlite3.connect(db_file)
    try:
        rows = con.execute("SELECT DISTINCT thumb_path FROM entries WHERE thumb_path != ''").fetchall()
    finally:
        con.close()
    return [thumb_file(r[0]).name for r in rows if thumb_file(r[0]) is not None]


def _remove_empty_dirs(*dirs: Path) -> None:
    for d in dirs:
        try:
            d.rmdir()  # only succeeds if empty; never deletes anything else
        except OSError:
            pass


def move_library(new_dir: Path) -> None:
    """Copy the library to new_dir, switch to it, then delete the old copy.

    Only the database and the thumbnails it references are copied and later
    deleted, so unrelated files in either folder are never touched. The old
    files are only removed once the copy succeeded and the setting points at
    the new location, so a failure part-way leaves the old library usable.
    """
    old_dir = app_dir()
    new_dir = new_dir.resolve()
    if new_dir == old_dir.resolve():
        return
    if has_library(new_dir):
        raise FileExistsError(f"{new_dir} already contains a {APP_NAME} library.")
    if new_dir.is_relative_to(thumb_dir().resolve()):
        raise ValueError("The new location can't be inside the current thumbnails folder.")
    old_db, old_thumbs = db_path(), thumb_dir()
    new_db, new_thumbs = new_dir / DB_NAME, new_dir / THUMB_DIR_NAME
    names = _referenced_thumbs(old_db) if old_db.exists() else []
    clashes = [n for n in names if (new_thumbs / n).exists()]
    if clashes:
        raise FileExistsError(f"{new_thumbs} already has files with the same names. Pick another folder.")
    created_dirs = [d for d in (new_thumbs, new_dir) if not d.exists()]
    try:
        new_thumbs.mkdir(parents=True, exist_ok=True)
        if old_db.exists():
            # backup() gives a consistent copy even if the DB is mid-write.
            src = sqlite3.connect(old_db)
            dst = sqlite3.connect(new_db)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
        for name in names:
            if (old_thumbs / name).exists():
                shutil.copy2(old_thumbs / name, new_thumbs / name)
    except Exception:
        # Undo only what we created; a half-copied DB would block the next attempt.
        new_db.unlink(missing_ok=True)
        for name in names:
            (new_thumbs / name).unlink(missing_ok=True)
        _remove_empty_dirs(*created_dirs)
        raise

    use_library(new_dir)

    for f in [old_db, *(old_thumbs / name for name in names)]:
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass
    _remove_empty_dirs(old_thumbs, old_dir)


def use_library(directory: Path | None) -> None:
    """Point the app at directory (None = default) without copying anything."""
    s = settings()
    if directory is None or directory.resolve() == default_app_dir().resolve():
        s.remove(_SETTINGS_KEY)
    else:
        # Forward slashes: QSettings escapes backslashes in ini files, and the
        # uninstaller reads this value back as plain text.
        s.setValue(_SETTINGS_KEY, directory.resolve().as_posix())
    s.sync()
