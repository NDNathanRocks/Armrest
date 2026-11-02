"""Other media apps (Spotify, VLC...) through Windows media sessions (plan 15C)."""

from __future__ import annotations

import asyncio
import datetime as dt
import sys

import pytest

from command_queue import CommandRequest
from contracts import CmdButton, CmdButtonPayload, ErrorMsg, envelope
from event_bus import EventBus
from executors.fakes import FakeMediaApps
from media_sessions import AppMedia, SessionInfo, app_label, choose, estimate_position
from service import CommandService
from support import AgentEnv
from timers import TimerService

SONG = AppMedia(
    app_id="Spotify.exe",
    app="Spotify",
    title="Blinding Lights",
    artist="The Weeknd",
    is_playing=True,
    position_s=42.0,
    duration_s=200.0,
    can_seek=True,
)


@pytest.mark.parametrize(
    ("app_id", "label"),
    [
        ("Spotify.exe", "Spotify"),
        ("SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify", "Spotify"),
        (r"C:\Program Files\VideoLAN\VLC\vlc.exe", "VLC"),
        ("Microsoft.ZuneMusic_8wekyb3d8bbwe!Microsoft.ZuneMusic", "Media Player"),
        ("Contoso.Player_abc!App.Jukebox", "Jukebox"),
        ("winamp.exe", "Winamp"),
    ],
)
def test_app_names_the_phone_shows(app_id: str, label: str) -> None:
    assert app_label(app_id) == label


def test_the_tv_browser_is_never_chosen() -> None:
    edge = SessionInfo("MSEdge", is_playing=True, is_current=True)
    spotify = SessionInfo("Spotify.exe", is_playing=False, is_current=False)
    vlc = SessionInfo("vlc.exe", is_playing=True, is_current=False)
    assert choose([edge, spotify, vlc]) == 2  # the playing one
    assert choose([edge, spotify]) == 1  # nothing else plays: the open app
    assert choose([edge]) is None
    current = SessionInfo("vlc.exe", is_playing=False, is_current=True)
    assert choose([spotify, current]) == 1  # Windows' own pick beats list order


def test_position_runs_on_between_app_updates() -> None:
    then = dt.datetime(2026, 11, 1, 12, 0, 0, tzinfo=dt.UTC)
    now = then + dt.timedelta(seconds=7)
    assert estimate_position(40, 200, then, True, now) == 47
    assert estimate_position(40, 200, then, False, now) == 40  # paused: it stands still
    assert estimate_position(198, 200, then, True, now) == 200  # never past the end
    never = dt.datetime(1601, 1, 1, tzinfo=dt.UTC)  # Windows' "not set"
    assert estimate_position(40, 200, never, True, now) == 40


async def test_buttons_go_to_the_app_that_plays(env: AgentEnv) -> None:
    apps = FakeMediaApps(SONG)
    env.deps.media_apps = apps
    env.browser.snap = env.browser.snap.model_copy(update={"is_playing": None})  # empty tab
    result = await env.runner().run(
        CommandRequest(
            command_id="c1", idempotency_key="k1", device_id="d1", kind="button", action="next"
        )
    )
    assert result.ok and apps.commands == ["next"] and env.os.keys == []


async def test_a_paused_app_still_gets_the_button_when_the_tab_is_empty(env: AgentEnv) -> None:
    apps = FakeMediaApps(SONG.__class__(**{**SONG.__dict__, "is_playing": False}))
    env.deps.media_apps = apps
    env.browser.no_media = True
    result = await env.runner().run(
        CommandRequest(
            command_id="c1", idempotency_key="k1", device_id="d1", kind="text", text="resume"
        )
    )
    assert result.ok and apps.commands == ["play"] and env.os.keys == []


async def test_a_playing_video_keeps_the_buttons(env: AgentEnv) -> None:
    apps = FakeMediaApps(SONG)
    env.deps.media_apps = apps
    env.browser.snap = env.browser.snap.model_copy(update={"is_playing": True})
    result = await env.runner().run(
        CommandRequest(
            command_id="c1", idempotency_key="k1", device_id="d1", kind="text", text="pause"
        )
    )
    assert result.ok and apps.commands == []


async def test_no_app_falls_back_to_the_media_key(env: AgentEnv) -> None:
    env.deps.media_apps = FakeMediaApps(None)
    env.browser.snap = env.browser.snap.model_copy(update={"is_playing": None})
    env.browser.no_media = True
    result = await env.runner().run(
        CommandRequest(
            command_id="c1", idempotency_key="k1", device_id="d1", kind="button", action="next"
        )
    )
    assert result.ok and env.os.keys == ["next"]


def service_with(env: AgentEnv, apps: FakeMediaApps) -> CommandService:
    return CommandService(
        room_id="r1",
        bus=EventBus(),
        runner=env.runner(),
        browser=env.browser,
        os_ctl=env.os,
        telemetry=env.telemetry,
        timers=TimerService(lambda info: asyncio.sleep(0)),
        mode="lan",
        media_apps=apps,
    )


async def test_now_playing_shows_the_app_when_the_tab_has_nothing(env: AgentEnv) -> None:
    service = service_with(env, FakeMediaApps(SONG))
    env.browser.snap = env.browser.snap.model_copy(update={"is_playing": None})
    await service.refresh_state()
    shown = service.state.state.now_playing
    assert shown is not None and shown.app == "Spotify"
    assert shown.title == "Blinding Lights · The Weeknd" and shown.is_playing
    assert (shown.position_s, shown.duration_s) == (42, 200)
    assert env.os.awake  # music keeps the PC awake like a video does


async def test_a_paused_video_gives_way_to_playing_music(env: AgentEnv) -> None:
    service = service_with(env, FakeMediaApps(SONG))
    env.browser.snap = env.browser.snap.model_copy(update={"is_playing": False, "title": "Vid"})
    await service.refresh_state()
    assert service.state.state.now_playing and service.state.state.now_playing.app == "Spotify"
    env.browser.snap = env.browser.snap.model_copy(update={"is_playing": True})
    await service.refresh_state()
    shown = service.state.state.now_playing
    assert shown is not None and shown.app is None and shown.title == "Vid"


async def test_the_timeline_seeks_the_app(env: AgentEnv) -> None:
    apps = FakeMediaApps(SONG)
    service = service_with(env, apps)
    env.browser.snap = env.browser.snap.model_copy(update={"is_playing": None})
    await service.refresh_state()
    slide = envelope(
        CmdButton,
        "r1",
        CmdButtonPayload(
            command_id="c", idempotency_key="k", action="seek_to", args={"position_s": 90}
        ),
    )
    assert await service.handle_envelope(slide, "d1") == []
    assert apps.seeks == [90.0]
    apps.media = SONG.__class__(**{**SONG.__dict__, "can_seek": False})
    replies = await service.handle_envelope(slide, "d1")
    assert isinstance(replies[0], ErrorMsg) and "does not allow" in replies[0].payload.message


@pytest.mark.skipif(sys.platform != "win32", reason="Windows media sessions")
async def test_the_real_session_manager_answers_on_this_pc() -> None:
    from media_sessions import windows_media_sessions

    apps = windows_media_sessions()
    assert apps is not None
    media = await apps.current()  # whatever is (or is not) playing right now
    assert media is None or (media.app and not media.app_id.lower().startswith("msedge"))
