"""The CouchJarvis -> Armrest data move (0.5.0): all of a folder or none, never half."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import app_dirs
from app_dirs import APP_DIR, LEGACY_DIR, MOVED_NOTE
from config import Settings


@pytest.fixture
def bases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    roaming, local = tmp_path / "Roaming", tmp_path / "Local"
    roaming.mkdir()
    local.mkdir()
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    for key in ("ARMREST_ROOM_FILE", "CJ_ROOM_FILE", "ARMREST_EDGE_PROFILE_DIR"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("CJ_EDGE_PROFILE_DIR", raising=False)
    return roaming, local


def _old_install(roaming: Path, local: Path) -> str:
    old = roaming / LEGACY_DIR
    old.mkdir()
    (old / "room.json").write_text('{"room_id": "room-1"}', encoding="utf-8")
    (old / "config.env").write_text("CJ_SUBTITLE_LANG=fr\n", encoding="utf-8")
    cookies = local / LEGACY_DIR / "edge-profile" / "Default" / "Network" / "Cookies"
    cookies.parent.mkdir(parents=True)
    cookies.write_bytes(b"signed in")
    return hashlib.sha256((old / "room.json").read_bytes()).hexdigest()


def test_a_fresh_pc_uses_the_armrest_folders(bases: tuple[Path, Path]) -> None:
    roaming, local = bases
    assert app_dirs.move_legacy_folders(packaged=False) == {
        "roaming": "nothing",
        "local": "nothing",
    }
    assert app_dirs.roaming_dir() == roaming / APP_DIR
    assert app_dirs.local_dir() == local / APP_DIR
    assert not (roaming / LEGACY_DIR).exists()


def test_an_old_install_moves_whole_and_leaves_a_note(bases: tuple[Path, Path]) -> None:
    roaming, local = bases
    room_hash = _old_install(roaming, local)
    assert app_dirs.roaming_dir() == roaming / LEGACY_DIR  # used where it is until it moves

    assert app_dirs.move_legacy_folders(packaged=False) == {"roaming": "moved", "local": "moved"}

    new_room = roaming / APP_DIR / "room.json"
    assert hashlib.sha256(new_room.read_bytes()).hexdigest() == room_hash
    assert (local / APP_DIR / "edge-profile" / "Default" / "Network" / "Cookies").read_bytes() == (
        b"signed in"
    )
    for base in (roaming, local):
        assert [p.name for p in (base / LEGACY_DIR).iterdir()] == [MOVED_NOTE]
    assert app_dirs.roaming_dir() == roaming / APP_DIR
    assert app_dirs.local_dir() == local / APP_DIR
    # a second start has nothing to do
    assert app_dirs.move_legacy_folders(packaged=False) == {
        "roaming": "nothing",
        "local": "nothing",
    }


def test_a_folder_in_use_stays_and_is_used_where_it_is(bases: tuple[Path, Path]) -> None:
    roaming, local = bases
    _old_install(roaming, local)
    profile_file = local / LEGACY_DIR / "edge-profile" / "Default" / "Network" / "Cookies"
    with profile_file.open("rb"):  # Edge still has the TV profile open
        outcome = app_dirs.move_legacy_folders(packaged=False)
    assert outcome == {"roaming": "moved", "local": "busy"}
    assert app_dirs.local_dir() == local / LEGACY_DIR
    assert not (local / APP_DIR).exists()
    assert Settings(_env_file=None).edge_profile_dir == local / LEGACY_DIR / "edge-profile"
    # next start, Edge is closed
    assert app_dirs.move_legacy_folder(local) == "moved"
    assert Settings(_env_file=None).edge_profile_dir == local / APP_DIR / "edge-profile"


def test_a_new_folder_made_too_early_is_kept_aside(bases: tuple[Path, Path]) -> None:
    roaming, local = bases
    _old_install(roaming, local)
    stray = roaming / APP_DIR
    stray.mkdir()
    (stray / "ui.json").write_text("{}", encoding="utf-8")
    assert app_dirs.move_legacy_folder(roaming, clock=lambda: 1234.0) == "moved"
    assert (roaming / APP_DIR / "room.json").is_file()  # the real data won
    assert (roaming / f"{APP_DIR}.before-move-1234" / "ui.json").is_file()


def test_the_store_app_never_moves_anything(bases: tuple[Path, Path]) -> None:
    roaming, local = bases
    _old_install(roaming, local)
    assert app_dirs.move_legacy_folders(packaged=True) == {}
    assert (roaming / LEGACY_DIR / "room.json").is_file()
    assert app_dirs.roaming_dir() == roaming / LEGACY_DIR


def test_settings_follow_the_move(bases: tuple[Path, Path]) -> None:
    roaming, local = bases
    _old_install(roaming, local)
    app_dirs.move_legacy_folders(packaged=False)
    s = Settings(_env_file=None)
    assert s.room_file == roaming / APP_DIR / "room.json"
    assert s.telemetry_dir == local / APP_DIR / "telemetry"
    # setup_edge_profile.ps1 told people to write the old profile path into config.env
    old_profile = local / LEGACY_DIR / "edge-profile"
    named = Settings(_env_file=None, edge_profile_dir=old_profile)
    assert named.edge_profile_dir == local / APP_DIR / "edge-profile"
    elsewhere = Path("D:/profiles/tv")
    assert Settings(_env_file=None, edge_profile_dir=elsewhere).edge_profile_dir == elsewhere
