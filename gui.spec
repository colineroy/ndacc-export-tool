# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for raw_to_woudc GUI.

Build from the raw_to_woudc/ directory:
    cd raw_to_woudc
    pyinstaller gui.spec

Output: dist/raw_to_woudc.exe (one-file, no console window)
"""

import os
import sys
from pathlib import Path

_HERE = os.getcwd()
_SRC = os.path.join(_HERE, "src")

# Locate conda environment Library/bin for critical DLLs
_PYTHON_HOME = os.path.dirname(sys.executable)
_LIB_BIN = os.path.join(_PYTHON_HOME, "Library", "bin")
if not os.path.isdir(_LIB_BIN):
    _LIB_BIN = _PYTHON_BASE  # fallback

# Collect DLLs needed by stdlib modules (_ctypes, _ssl, _hashlib, etc.)
_CRITICAL_DLLS = [
    "ffi-8.dll",
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "tcl86t.dll",
    "tk86t.dll",
    "sqlite3.dll",
    "liblzma.dll",
    "libbz2.dll",
    "libexpat.dll",
]
_BINARIES = []
for dll in _CRITICAL_DLLS:
    src = os.path.join(_LIB_BIN, dll)
    if os.path.isfile(src):
        _BINARIES.append((src, "."))

a = Analysis(
    ['gui.py'],
    pathex=[_HERE, _SRC],
    binaries=_BINARIES,
    datas=[
        (os.path.join(_SRC, "gui", "*.py"), "src/gui"),
        (os.path.join(_SRC, "*.py"), "src"),
        (os.path.join(_HERE, "manual_params.csv"), "."),
    ],
    hiddenimports=[
        "tkinter.filedialog",
        "tkinter.scrolledtext",
        "ttkbootstrap",
        "pandas",
        "numpy",
        "openpyxl",
        "sharp_dqa",
        "nogdb_parser",
        "nogdb_mr_parser",
        "woudc_export",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "scipy",
        "tkinter.test",
        "unittest",
        "pdb",
        "doctest",
        "test",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='raw_to_woudc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(_HERE, 'ballon.ico'),
)
