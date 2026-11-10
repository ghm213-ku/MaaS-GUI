# PyInstaller spec: builds a single-file, windowed MaaS-GUI.exe.
# Build with:  python -m PyInstaller --noconfirm --clean maas_gui.spec
# (or just run build.bat). Output: dist/MaaS-GUI.exe

block_cipher = None

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
)
