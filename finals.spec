# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = [
    ('docs', 'docs'),
    ('samples', 'samples'),
]
binaries = []
hiddenimports = []

for package in ['pyvista', 'pyvistaqt', 'vtkmodules', 'reportlab', 'matplotlib']:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        pass

a = Analysis(
    ['finals_gui.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='槽型深度宽度测量软件',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='槽型深度宽度测量软件',
)
