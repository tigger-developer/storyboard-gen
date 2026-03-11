# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/tigger/code/tigoss/storyboard-gen/src/storyboard_gen/gui/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['storyboard_gen.providers.google', 'storyboard_gen.providers.fal', 'storyboard_gen.providers.replicate'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['QtWebEngine', 'Qt3D', 'QtBluetooth', 'QtNfc', 'QtRemoteObjects', 'QtSensors', 'QtSerialPort', 'QtTest', 'QtPositioning'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Storyboard Gen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
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
    name='Storyboard Gen',
)
app = BUNDLE(
    coll,
    name='Storyboard Gen.app',
    icon=None,
    bundle_identifier='com.tigger04.storyboard-gen',
)
