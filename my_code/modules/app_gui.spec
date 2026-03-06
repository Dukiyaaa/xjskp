# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\MAIN\\xjskp\\my_code\\modules\\app_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\MAIN\\xjskp\\my_code\\modules\\images\\template', '.\\images\\/template'), ('D:\\MAIN\\xjskp\\my_code\\modules\\images\\test', '.\\images\\/test')],
    hiddenimports=[],
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
    name='app_gui',
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
    version='D:\\MAIN\\xjskp\\my_code\\modules\\app_gui_version_info.txt',
)
