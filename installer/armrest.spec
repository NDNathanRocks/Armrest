# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Armrest.exe (onedir). Build with installer\build.ps1.
#
# Playwright's Node driver is bundled (collect_all) but NOT its browsers: the app drives the
# Microsoft Edge that is already on the PC over CDP.

import json
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
BUILD_INFO = os.path.join(SPECPATH, "build_info.json")  # written by build.ps1 (-Channel)
with open(BUILD_INFO, encoding="utf-8") as f:
    CHANNEL = json.load(f)["channel"]

datas, binaries, hiddenimports = [], [], ["main"]
for package in ("faster_whisper", "ctranslate2", "playwright", "segno", "mss", "pyautogui"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += collect_submodules("langgraph") + collect_submodules("uvicorn")
hiddenimports += ["websockets.asyncio.server", "pycaw.pycaw", "comtypes.client", "qasync"]
# sentry_sdk imports its default integrations by name at init (opt-in crash reports), and tries the
# "auto-enabling" ones for libraries that are present. Only those are listed: collecting every
# integration module made PyInstaller follow their imports and bundle whatever happened to sit in
# the build venv (litellm, transformers, boto3, openai, tiktoken: +60 MB in an early 0.7.0 build).
hiddenimports += [
    f"sentry_sdk.integrations.{name}"
    for name in (
        "argv", "atexit", "dedupe", "excepthook", "logging", "modules", "stdlib", "threading",
        "asyncio", "httpx", "fastapi", "starlette",
    )
]  # fmt: skip
# the Store licence check is imported lazily (licensing.query_store)
hiddenimports += collect_submodules("winrt.windows.services.store") + [
    "winrt.runtime",
    "winrt.windows.foundation",
    "winrt.windows.foundation.collections",
]
# other media apps (media_sessions.py, imported lazily); their properties reference streams
hiddenimports += collect_submodules("winrt.windows.media.control") + collect_submodules(
    "winrt.windows.storage.streams"
)

web_dist = os.path.join(ROOT, "web-remote", "dist")
if os.path.isdir(web_dist):
    datas.append((web_dist, os.path.join("web-remote", "dist")))
defaults = os.path.join(SPECPATH, "defaults.env")
if os.path.isfile(defaults):
    datas.append((defaults, "installer"))
datas.append((BUILD_INFO, "installer"))

# The TV overlay only needs QtWidgets/QtGui/QtCore: leave the big optional Qt modules out.
excludes = [
    "tkinter", "matplotlib", "IPython", "pytest",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.QtQuickWidgets", "PySide6.QtQuick3D", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtSql", "PySide6.QtTest",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtWebSockets", "PySide6.QtWebChannel",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtLocation", "PySide6.QtRemoteObjects",
    "PySide6.QtScxml", "PySide6.QtSpatialAudio", "PySide6.QtStateMachine",
    "PySide6.QtTextToSpeech", "PySide6.QtVirtualKeyboard",
    # edge-tts's terms do not cover a product we sell: never ship it (build_info.allows_hobby_services)
    "edge_tts",
    # GPLv3 helpers pyautogui imports optionally (message boxes, a mouse-position app). It works
    # without them and we use neither; a closed product must not ship GPL code (scripts/licenses.py).
    "pymsgbox", "mouseinfo",
    # Not used by the app. They reach the build only through the build venv's tooling (and the
    # sentry integrations that import them); the size gate in build.ps1 fails if they come back.
    "litellm", "transformers", "boto3", "botocore", "s3transfer", "openai", "anthropic", "tiktoken",
    "magika", "headroom", "langchain", "torch", "tensorflow", "jax",
]  # fmt: skip

a = Analysis(
    [os.path.join(ROOT, "pc-daemon", "app_entry.py")],
    pathex=[os.path.join(ROOT, "pc-daemon")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Armrest",
    console=False,  # no console window: logs go to %LOCALAPPDATA%\Armrest\logs
    disable_windowed_traceback=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Armrest")
