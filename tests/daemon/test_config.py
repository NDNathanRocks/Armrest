from __future__ import annotations

from pathlib import Path

import pytest

from config import Settings, init_dpi_awareness


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("CJ_CDP_PORT", "CJ_LAN_PORT", "CJ_STT_DEVICE"):
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.cdp_port == 9222
    assert s.lan_port == 8765
    assert s.stt_device == "auto"
    assert s.cdp_url == "http://127.0.0.1:9222"
    assert not s.lan_tls_enabled


def test_env_override_and_secret_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CJ_CDP_PORT", "9333")
    monkeypatch.setenv("CJ_GROQ_API_KEY", "gsk_secret")
    s = Settings(_env_file=None)
    assert s.cdp_port == 9333
    assert s.groq_api_key is not None
    assert "gsk_secret" not in repr(s)
    assert s.groq_api_key.get_secret_value() == "gsk_secret"


def test_old_cj_settings_still_work_and_armrest_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for key in ("CJ_CDP_PORT", "ARMREST_CDP_PORT", "CJ_LAN_PORT", "ARMREST_LAN_PORT"):
        monkeypatch.delenv(key, raising=False)
    old = tmp_path / "config.env"
    old.write_text("CJ_CDP_PORT=9333\nCJ_SUBTITLE_LANG=fr\nARMREST_SUBTITLE_LANG=de\n", "utf-8")
    s = Settings(_env_file=old)  # type: ignore[call-arg]
    assert s.cdp_port == 9333  # a config.env from before the rename
    assert s.subtitle_lang == "de"
    monkeypatch.setenv("CJ_LAN_PORT", "9001")
    assert Settings(_env_file=None).lan_port == 9001  # type: ignore[call-arg]
    monkeypatch.setenv("ARMREST_LAN_PORT", "9002")
    assert Settings(_env_file=None).lan_port == 9002  # type: ignore[call-arg]
    monkeypatch.setenv("ARMREST_CDP_PORT", "9444")
    assert Settings(_env_file=old).cdp_port == 9444  # type: ignore[call-arg]


def test_tls_requires_both_files(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CJ_LAN_TLS_CERT", "cert.pem")
    assert not Settings(_env_file=None).lan_tls_enabled
    monkeypatch.setenv("CJ_LAN_TLS_KEY", "key.pem")
    assert Settings(_env_file=None).lan_tls_enabled


def test_invalid_stt_device_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CJ_STT_DEVICE", "tpu")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_dpi_init_returns_bool() -> None:
    assert isinstance(init_dpi_awareness(), bool)


def test_qr_codes_never_point_at_the_retired_vercel_site() -> None:
    from brand import SITE_URL, qr_base_url

    assert SITE_URL == "https://armrest-app.pages.dev"
    assert qr_base_url("https://couch-jarvis-remote.vercel.app") == SITE_URL
    assert qr_base_url("https://couch-jarvis-remote.vercel.app/") == SITE_URL
    assert qr_base_url("https://couch-jarvis.vercel.app") == SITE_URL
    assert qr_base_url(SITE_URL) == SITE_URL
    assert qr_base_url("https://my.own.host") == "https://my.own.host"  # untouched
    assert qr_base_url("http://localhost:5173") == "http://localhost:5173"
