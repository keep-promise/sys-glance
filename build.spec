# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：python -m PyInstaller build.spec
a = Analysis(
    ['main.py'],
    pathex=['.'],
    datas=[('assets', 'assets')],
    hiddenimports=['wmi', 'win32com', 'pynvml', 'pyqtgraph'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='SysGlance',
    console=False,
    icon='assets/icons/sysglance.ico',
    upx=False,
)
