# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\FileDecoder\\File_decoder\\File_decoder\\QTVersion\\app.py'],
    pathex=['C:\\FileDecoder\\File_decoder\\File_decoder\\QTVersion', 'C:\\FileDecoder\\File_decoder\\File_decoder'],
    binaries=[('C:\\FileDecoder\\.conda\\Library\\bin\\liblzma.dll', '.'), ('C:\\FileDecoder\\.conda\\Library\\bin\\libbz2.dll', '.'), ('C:\\FileDecoder\\.conda\\Library\\bin\\libexpat.dll', '.'), ('C:\\FileDecoder\\.conda\\Library\\bin\\libcrypto-3-x64.dll', '.'), ('C:\\FileDecoder\\.conda\\Library\\bin\\libssl-3-x64.dll', '.'), ('C:\\FileDecoder\\.conda\\Library\\bin\\libmpdec-4.dll', '.'), ('C:\\FileDecoder\\.conda\\Library\\bin\\ffi.dll', '.'), ('C:\\FileDecoder\\.conda\\Library\\bin\\sqlite3.dll', '.')],
    datas=[],
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
    name='FileDecoder',
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
