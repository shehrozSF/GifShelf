"""Writes build/version_info.txt for PyInstaller's --version-file, from app/__init__.py.

That puts product name, version and copyright into GifLibrary.exe's file
properties (required for signed releases).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import __copyright__, __version__  # noqa: E402
from app.storage import APP_ID, APP_NAME  # noqa: E402

# Windows wants four numbers; "1.2.3-beta" -> (1, 2, 3, 0).
nums = [int(n) for n in re.findall(r"\d+", __version__)[:4]]
vtuple = tuple(nums + [0] * (4 - len(nums)))

out = ROOT / "build" / "version_info.txt"
out.parent.mkdir(exist_ok=True)
out.write_text(
    f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={vtuple}, prodvers={vtuple}, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('ProductName', {APP_NAME!r}),
      StringStruct('FileDescription', {APP_NAME!r}),
      StringStruct('ProductVersion', {__version__!r}),
      StringStruct('FileVersion', {__version__!r}),
      StringStruct('InternalName', {APP_ID!r}),
      StringStruct('OriginalFilename', {APP_ID + ".exe"!r}),
      StringStruct('LegalCopyright', {__copyright__!r}),
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ]
)
""",
    encoding="utf-8",
)
print(out)
