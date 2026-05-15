# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('fonts', 'fonts'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyMuPDF', 'docx'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Prompt-Live',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='Prompt-Live',
)

app = BUNDLE(
    coll,
    name='Prompt-Live.app',
    icon='logo/prompt-live.icns',
    bundle_identifier='com.promptlive.app',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '1.0.0',
        'LSMinimumSystemVersion': '11.0',
    },
)
