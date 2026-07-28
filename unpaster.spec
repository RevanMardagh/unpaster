# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['run_unpaster.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pytest'],
)

pyz = PYZ(a.pure, a.zipped_data)

# UPX stays off deliberately: compressed executables raise antivirus
# heuristics, and this program already looks suspicious to scanners because it
# installs a keyboard hook and calls SendInput.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='unpaster',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon='assets/unpaster.ico',
    version='version_info.txt',
)
