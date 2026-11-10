# PyInstaller spec: builds a single-file, windowed MaaS-GUI.exe.
# Build with:  python -m PyInstaller --noconfirm --clean maas_gui.spec
# (or just run build.bat). Output: dist/MaaS-GUI.exe

import sys

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable,
    VarFileInfo, VarStruct, VSVersionInfo,
)

sys.path.insert(0, SPECPATH)
from version import __version__  # noqa: E402

block_cipher = None

# Version shown in the exe's Properties -> Details.
_ver = tuple(int(p) for p in __version__.split(".")) + (0,)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_ver, prodvers=_ver),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("ProductName", "MaaS GUI"),
            StringStruct("FileDescription", "MaaS GUI"),
            StringStruct("FileVersion", __version__),
            StringStruct("ProductVersion", __version__),
            StringStruct("OriginalFilename", "MaaS-GUI.exe"),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    # Imported lazily inside functions, so make sure they are bundled.
    hiddenimports=["ui.main_window", "requests", "websocket"],
    hookspath=[],
    runtime_hooks=[],
    # Dev/test-only or unused heavy packages that may sit in the environment.
    excludes=[
        "tkinter", "matplotlib", "IPython", "pytest", "pytestqt",
        "PyQt5", "PySide2", "PySide6", "scipy", "pandas",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MaaS-GUI",
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,  # GUI app: no console window
    version=version_info,
)
