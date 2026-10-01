# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

runtime_root = os.environ.get("ODYSSEUS_WEBVIEW2_FIXED_ROOT")
if not runtime_root or not (Path(runtime_root) / "msedgewebview2.exe").is_file():
    raise SystemExit("ODYSSEUS_WEBVIEW2_FIXED_ROOT must point to an extracted Fixed Version runtime")

datas = [
    ("static", "static"),
    ("scripts", "scripts"),
    ("mcp_servers", "mcp_servers"),
    ("services/hwfit/data", "services/hwfit/data"),
    ("config", "config"),
    (".env.example", "."),
    (runtime_root, "webview2-runtime"),
]
binaries = []
hiddenimports = ["webview.platforms.edgechromium"]
webview_datas, webview_binaries, webview_hidden = collect_all("webview")
datas += webview_datas
binaries += webview_binaries
hiddenimports += webview_hidden

a = Analysis(
    ["launcher.py"],
    pathex=[], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="Odysseus", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=True, console=False,
    disable_windowed_traceback=False, argv_emulation=False, target_arch=None,
    codesign_identity=None, entitlements_file=None, icon=["static/icon.ico"],
)
coll = COLLECT(
    exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[], name="Odysseus",
)
