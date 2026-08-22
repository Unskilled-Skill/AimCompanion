from PyInstaller.utils.hooks import collect_data_files

datas = [
    ("style.qss", "."),
    ("data/benchmarks.json", "data"),
    ("data/scenarios.json", "data"),
    ("data/routines.json", "data"),
    ("data/recommended_scenarios.json", "data"),
    ("data/tiers.json", "data"),
    ("data/voltaic_guidance.json", "data"),
    ("data/voltaic_routines.json", "data"),
    ("data/aim_glossary.json", "data"),
    ("assets/AimCompanion.ico", "assets"),
]

a = Analysis(
    ["main.py"], pathex=[], binaries=[], datas=datas,
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name="AimCompanion",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    console=False, icon="assets/AimCompanion.ico", version="version_info.txt",
)
