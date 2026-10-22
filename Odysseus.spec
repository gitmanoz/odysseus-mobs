# -*- mode: python ; coding: utf-8 -*-
import os
import tempfile
from pathlib import Path

import webview
from PyInstaller.utils.hooks import collect_all
from PyInstaller.config import CONF
from src.desktop_python_toolchain import prepare_bundle

# A frozen GUI executable is not a Python interpreter. Package the existing
# build interpreter for the TEB and compile its inventory pin into the archive.
_toolchain_work = Path(tempfile.mkdtemp(prefix="governed-python-", dir=CONF["workpath"]))
_toolchain = prepare_bundle(_toolchain_work)
_pin_module = _toolchain_work / "_desktop_python_toolchain_pin.py"
_pin_module.write_text(
    f'SHA256 = {_toolchain["sha256"]!r}\nVERSION = {_toolchain["version"]!r}\n', encoding="utf-8")

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
    (str(_toolchain["root"]), "python-toolchain"),
]
binaries = []
hiddenimports = ["webview.platforms.edgechromium", "_desktop_python_toolchain_pin"]
webview_datas, webview_binaries, webview_hidden = collect_all("webview")
datas += webview_datas
binaries += webview_binaries
hiddenimports += webview_hidden

# pywebview probes each WebView2Loader architecture while it initializes the
# Edge backend. PyInstaller's platform filtering otherwise omits the loaders
# that are not native to this build, making a valid x64 Desktop fail before
# the host can open its window.
_WEBVIEW2_LOADER_ARCHITECTURES = ("win-arm64", "win-x64", "win-x86")
_webview_runtimes = Path(webview.__file__).resolve().parent / "lib" / "runtimes"
for _architecture in _WEBVIEW2_LOADER_ARCHITECTURES:
    _runtime = _webview_runtimes / _architecture
    if not (_runtime / "native" / "WebView2Loader.dll").is_file():
        raise SystemExit(f"Missing pywebview WebView2Loader runtime: {_architecture}")
    datas.append((str(_runtime), f"webview/lib/runtimes/{_architecture}"))

a = Analysis(
    ["launcher.py"],
    pathex=[str(_toolchain_work)], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="MOBS Studio", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=True, console=False,
    disable_windowed_traceback=False, argv_emulation=False, target_arch=None,
    codesign_identity=None, entitlements_file=None, icon=["static/icon.ico"],
    version="desktop/version-info.txt",
)
coll = COLLECT(
    exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[], name="MOBS Studio",
)
