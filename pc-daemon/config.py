"""Pydantic Settings for the daemon (.env loader) and Windows DPI-awareness init."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from app_dirs import local_dir, remap_legacy, roaming_dir

ENV_PREFIX = "ARMREST_"
# Settings from before the rename (0.5.0). Always read, so no config.env ever has to be rewritten;
# where both are set, ARMREST_ wins.
LEGACY_ENV_PREFIX = "CJ_"

_EDGE_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


def _local_app_dir() -> Path:
    return local_dir()


def _roaming_app_dir() -> Path:
    return roaming_dir()


def env_value(name: str) -> str | None:
    """An environment variable by its short name (``ROOM_FILE``), under either prefix."""
    return os.environ.get(ENV_PREFIX + name) or os.environ.get(LEGACY_ENV_PREFIX + name)


def _default_edge_path() -> Path:
    for candidate in _EDGE_CANDIDATES:
        if Path(candidate).exists():
            return Path(candidate)
    return Path(_EDGE_CANDIDATES[0])


def resource_root() -> Path:
    """Where bundled resources live: the repo root, or PyInstaller's unpack directory."""
    frozen = getattr(sys, "_MEIPASS", None)
    return Path(frozen) if frozen else Path(__file__).resolve().parent.parent


def user_config_file() -> Path:
    """Per-user settings written by the installer / first run (edit this to change settings)."""
    return _roaming_app_dir() / "config.env"


def _env_files() -> tuple[Path, Path]:
    # Later files win: a .env in the working directory (development) overrides the user config.
    return user_config_file(), Path(".env")


class Settings(BaseSettings):
    # The files are named in get_settings, not here: the data folder may move (app_dirs) between
    # importing this module and reading the settings.
    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        files = (
            dotenv_settings.env_file if isinstance(dotenv_settings, DotEnvSettingsSource) else None
        )
        return (
            init_settings,
            env_settings,
            EnvSettingsSource(settings_cls, env_prefix=LEGACY_ENV_PREFIX),
            dotenv_settings,
            DotEnvSettingsSource(settings_cls, env_file=files, env_prefix=LEGACY_ENV_PREFIX),
            file_secret_settings,
        )

    @model_validator(mode="after")
    def _follow_moved_folders(self) -> Settings:
        """A config.env that names a file in the old CouchJarvis folder means the moved one."""
        for name, info in type(self).model_fields.items():
            value = getattr(self, name)
            if info.annotation in (Path, Path | None) and isinstance(value, Path):
                object.__setattr__(self, name, remap_legacy(value))
        return self

    # Cloud relay / PWA
    relay_ws_url: str | None = None
    pwa_base_url: str = "http://localhost:5173"

    # LAN server
    lan_host: str = "0.0.0.0"
    lan_port: int = 8765
    lan_tls_cert: Path | None = None
    lan_tls_key: Path | None = None

    # Edge / CDP
    edge_path: Path = _default_edge_path()
    edge_profile_dir: Path = Field(default_factory=lambda: _local_app_dir() / "edge-profile")
    cdp_port: int = 9222

    # STT
    stt_model: str = "auto"  # auto: large-v3-turbo on an NVIDIA GPU, small on a plain CPU
    stt_device: Literal["cuda", "cpu", "auto"] = "auto"
    groq_api_key: SecretStr | None = None

    # Router / VLM
    # auto: Gemini when a key is set (fast, free tier), else local Ollama; the other is the fallback
    router_provider: Literal["auto", "ollama", "gemini"] = "auto"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_text_model: str = "auto"  # auto: qwen2.5:7b with an NVIDIA GPU, phi4-mini without
    ollama_vlm_model: str = "qwen2.5vl:7b"
    gemini_api_key: SecretStr | None = None

    # Language "turn on subtitles" picks when you do not name one (ISO 639-1 code: en, es, fr...).
    subtitle_lang: str = "en"

    # Let paired phones drive the cursor/keyboard (touchpad). Pair only people you would trust
    # at your keyboard; set false to keep phones to media/browser commands.
    remote_input: bool = True
    update_check: bool = True  # once a day, ask GitHub if a newer release exists (notice only)
    # Opt-in: send a scrubbed error report when the app crashes (see crash_reports.py for what is
    # sent). crash_dsn overrides the address baked into the build (testing only).
    crash_reports: bool = False
    crash_dsn: str | None = None
    # Direct download: paste the licence key you bought here (the Control Center will do it).
    license_key: SecretStr | None = None
    license_file: Path = Field(default_factory=lambda: _roaming_app_dir() / "license.json")

    # Spoken replies ("Now playing X on YouTube Music"). Preferences are changed from the phone and
    # saved per TV. ElevenLabs is optional (its free plan is ~10k credits a month); without a key
    # the free Microsoft Edge neural voices speak, and Windows' own voices work offline.
    elevenlabs_api_key: SecretStr | None = None
    elevenlabs_monthly_chars: int = 9000  # stop before the free allowance runs out
    voice_file: Path = Field(default_factory=lambda: _roaming_app_dir() / "voice.json")
    bookmarks_file: Path = Field(default_factory=lambda: _roaming_app_dir() / "bookmarks.json")
    browser_file: Path = Field(default_factory=lambda: _roaming_app_dir() / "browser.json")
    memory_file: Path = Field(
        default_factory=lambda: _roaming_app_dir() / "memory.json"
    )  # the last few commands, PC only
    voice_cache_dir: Path = Field(default_factory=lambda: _local_app_dir() / "voice-cache")

    # Storage / misc
    telemetry_dir: Path = Field(default_factory=lambda: _local_app_dir() / "telemetry")
    room_file: Path = Field(default_factory=lambda: _roaming_app_dir() / "room.json")
    hud_screen_index: int = 0
    hud_badge_hide_s: float = 10.0  # the TV status pill fades after this much quiet; 0 = always on
    log_level: str = "INFO"

    @property
    def lan_tls_enabled(self) -> bool:
        return self.lan_tls_cert is not None and self.lan_tls_key is not None

    @property
    def cdp_url(self) -> str:
        return f"http://127.0.0.1:{self.cdp_port}"


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=_env_files())  # type: ignore[call-arg]


def init_dpi_awareness() -> bool:
    """Make the process per-monitor-v2 DPI aware so screen coordinates are physical pixels.

    Returns True when the call succeeded; False on non-Windows or failure. Must run before any
    GUI, screenshot or mouse code.
    """
    if sys.platform != "win32":
        return False
    import ctypes

    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == -4
        return bool(ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)))
    except (AttributeError, OSError):
        try:
            return bool(ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0)
        except (AttributeError, OSError):
            return False
