# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import os
import sys

# Some Python installations omit Tcl scripts. Use a complete runtime, keeping
# its scripts and DLLs together, outside the output directory being replaced.
runtime_roots = [Path(os.environ.get('QUIZ_TK_RUNTIME', sys.base_prefix)),
                 Path('C:/laragon/bin/python/python-3.13')]
tk_root = next((root for root in runtime_roots
                if (root / 'tcl/tcl8.6/init.tcl').is_file()
                and (root / 'tcl/tk8.6/tk.tcl').is_file()
                and (root / 'DLLs/tcl86t.dll').is_file()
                and (root / 'DLLs/tk86t.dll').is_file()), None)
if tk_root is None:
    raise RuntimeError('Missing complete Tcl/Tk runtime. Set QUIZ_TK_RUNTIME to a Python installation containing tcl and DLLs.')
os.environ['TCL_LIBRARY'] = str(tk_root / 'tcl/tcl8.6')
os.environ['TK_LIBRARY'] = str(tk_root / 'tcl/tk8.6')

datas = [('examples', 'examples'), ('assets', 'assets'), ('docs', 'docs')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('imageio_ffmpeg')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('edge_tts')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['packaging_hooks'],
    hooksconfig={},
    runtime_hooks=['tk_runtime_hook.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Replace automatically discovered Tcl/Tk files with one complete runtime.
a.datas = [item for item in a.datas if not item[0].replace('\\', '/').startswith(('_tcl_data/', '_tk_data/', 'tcl8/'))]
for source, target in [('tcl8.6', '_tcl_data'), ('tk8.6', '_tk_data'), ('tcl8', 'tcl8')]:
    for path in (tk_root / 'tcl' / source).rglob('*'):
        if path.is_file():
            a.datas.append((str(Path(target) / path.relative_to(tk_root / 'tcl' / source)), str(path), 'DATA'))
a.binaries = [item for item in a.binaries if Path(item[0]).name.lower() not in ('tcl86t.dll', 'tk86t.dll', 'zlib1.dll')]
for name in ['tcl86t.dll', 'tk86t.dll', 'zlib1.dll']:
    path = tk_root / 'DLLs' / name
    if path.is_file():
        a.binaries.append((name, str(path), 'BINARY'))
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='QuizStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=bool(os.environ.get('QUIZ_DEBUG_CONSOLE')),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='QuizStudio',
)
