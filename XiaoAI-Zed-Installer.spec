# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# Ensure Tcl/Tk paths are explicitly set for Python 3.14 on Windows
base_prefix = sys.base_prefix
tcl_dir = os.path.join(base_prefix, 'tcl', 'tcl8.6')
tk_dir = os.path.join(base_prefix, 'tcl', 'tk8.6')

if os.path.exists(tcl_dir):
    os.environ['TCL_LIBRARY'] = tcl_dir
if os.path.exists(tk_dir):
    os.environ['TK_LIBRARY'] = tk_dir

# Collect Tcl/Tk data and DLLs explicitly
datas = []
if os.path.exists(tcl_dir):
    datas.append((tcl_dir, '_tcl_data'))
if os.path.exists(tk_dir):
    datas.append((tk_dir, '_tk_data'))

binaries = []
dlls_dir = os.path.join(base_prefix, 'DLLs')
for dll in ['_tkinter.pyd', 'tcl86t.dll', 'tk86t.dll']:
    p = os.path.join(dlls_dir, dll)
    if os.path.exists(p):
        binaries.append((p, '.'))

a = Analysis(
    ['gui_installer.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        '_tkinter',
        'keyring',
        'keyring.backends',
        'keyring.backends.Windows'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='XiaoAI-Zed-Installer',
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
)
