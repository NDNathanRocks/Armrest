"""Other media apps on the PC (Spotify, VLC, Media Player...) through Windows' media sessions.

Windows keeps one "media session" per app that plays something (the same list the volume flyout
shows). Reading it tells the phone what is playing outside the TV browser, and controlling the
right session beats pressing a media key and hoping the right app hears it. The TV browser's own
session (Edge) is skipped: the CDP executor already controls that tab, precisely.

``choose`` / ``app_label`` / ``estimate_position`` are pure, so the logic is tested without
Windows; ``WindowsMediaSessions`` is the thin winrt layer around them.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from executors.base import ActionResult

log = logging.getLogger(__name__)

AppCommand = Literal["play", "pause", "play_pause", "next", "prev"]
# GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING
PLAYING = 4
TICKS_PER_S = 10_000_000  # Windows TimeSpan ticks (100 ns)

KNOWN_APPS = {
    "spotify": "Spotify",
    "vlc": "VLC",
    "zunemusic": "Media Player",
    "zunevideo": "Films & TV",
    "applemusic": "Apple Music",
    "appletv": "Apple TV",
    "itunes": "iTunes",
    "foobar2000": "foobar2000",
    "musicbee": "MusicBee",
    "aimp": "AIMP",
    "chrome": "Chrome",
    "firefox": "Firefox",
    "plex": "Plex",
    "netflix": "Netflix",
    "tidal": "TIDAL",
    "amazonmusic": "Amazon Music",
    "deezer": "Deezer",
    "mpv": "mpv",
    "potplayer": "PotPlayer",
    "mpc-hc": "MPC-HC",
}


@dataclass(frozen=True)
class AppMedia:
    app_id: str  # the session's AppUserModelId, e.g. "Spotify.exe"
    app: str  # what the phone shows: "Spotify"
    title: str
    artist: str
    is_playing: bool
    position_s: float
    duration_s: float
    can_seek: bool

    @property
    def display_title(self) -> str:
        return f"{self.title} · {self.artist}" if self.artist and self.title else self.title


class MediaApps(Protocol):
    async def current(self) -> AppMedia | None: ...
    async def command(self, cmd: AppCommand) -> ActionResult: ...
    async def seek_to(self, position_s: float) -> ActionResult: ...


def is_tv_browser(app_id: str) -> bool:
    return "msedge" in app_id.lower()


def app_label(app_id: str) -> str:
    """'SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify' / 'C:\\...\\vlc.exe' -> 'Spotify' / 'VLC'."""
    raw = app_id.lower()
    for key, label in KNOWN_APPS.items():
        if key in raw:
            return label
    name = re.split(r"[\\/]", app_id)[-1]
    name = name.split("!")[-1]  # a packaged app: "Publisher.App_hash!AppId"
    name = re.sub(r"\.exe$", "", name, flags=re.IGNORECASE)
    name = name.split(".")[-1] or name
    return name[:1].upper() + name[1:40] if name else "An app"


@dataclass(frozen=True)
class SessionInfo:
    """What `choose` needs to know about one session."""

    app_id: str
    is_playing: bool
    is_current: bool


def choose(sessions: Sequence[SessionInfo]) -> int | None:
    """Which session the phone controls: one that is playing, else Windows' current one, else
    the first; never the TV browser. Returns its index, or None when there is nothing."""
    candidates = [(i, s) for i, s in enumerate(sessions) if not is_tv_browser(s.app_id)]
    for rank in (lambda s: s.is_playing, lambda s: s.is_current, lambda s: True):
        found = next((i for i, s in candidates if rank(s)), None)
        if found is not None:
            return found
    return None


def estimate_position(
    position_s: float,
    duration_s: float,
    updated_at: dt.datetime | None,
    playing: bool,
    now: dt.datetime | None = None,
) -> float:
    """Apps update their timeline only now and then: add the time since, while it plays."""
    if playing and updated_at is not None and updated_at.year > 1601:  # 1601 = "never"
        now = now or dt.datetime.now(dt.UTC)
        position_s += max(0.0, (now - updated_at).total_seconds())
    return min(position_s, duration_s) if duration_s > 0 else max(0.0, position_s)


def _seconds(value: Any) -> float:
    """A winrt TimeSpan: timedelta in pywinrt 2+, ticks in older builds."""
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    try:
        return float(value) / TICKS_PER_S
    except (TypeError, ValueError):
        return 0.0


class WindowsMediaSessions:
    """The winrt side. Every call is cheap (local IPC); errors become 'nothing playing'."""

    def __init__(self) -> None:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as Manager,
        )

        self._manager_type = Manager
        self._manager: Any = None

    async def _session(self) -> Any:
        if self._manager is None:
            self._manager = await self._manager_type.request_async()
        sessions = list(self._manager.get_sessions())
        current = self._manager.get_current_session()
        current_id = current.source_app_user_model_id if current is not None else None
        infos = [
            SessionInfo(
                app_id=s.source_app_user_model_id,
                is_playing=int(s.get_playback_info().playback_status) == PLAYING,
                is_current=s.source_app_user_model_id == current_id,
            )
            for s in sessions
        ]
        index = choose(infos)
        return None if index is None else sessions[index]

    async def current(self) -> AppMedia | None:
        try:
            session = await self._session()
            if session is None:
                return None
            props = await session.try_get_media_properties_async()
            info = session.get_playback_info()
            timeline = session.get_timeline_properties()
        except Exception:  # an app closing mid-read, or the service restarting
            log.debug("media session read failed", exc_info=True)
            return None
        playing = int(info.playback_status) == PLAYING
        start = _seconds(timeline.start_time)
        duration = max(0.0, _seconds(timeline.end_time) - start)
        updated = getattr(timeline, "last_updated_time", None)
        position = estimate_position(
            _seconds(timeline.position) - start,
            duration,
            updated if isinstance(updated, dt.datetime) else None,
            playing,
        )
        title = (props.title or "").strip()
        if not title and not playing:
            return None  # an idle app with nothing loaded
        app_id = str(session.source_app_user_model_id)
        return AppMedia(
            app_id=app_id,
            app=app_label(app_id),
            title=title or "Something",
            artist=(props.artist or "").strip(),
            is_playing=playing,
            position_s=round(position, 1),
            duration_s=round(duration, 1),
            can_seek=bool(info.controls.is_playback_position_enabled) and duration > 0,
        )

    async def command(self, cmd: AppCommand) -> ActionResult:
        try:
            session = await self._session()
            if session is None:
                return ActionResult(False, "os", "No media app is open", "no_media_app")
            call = {
                "play": session.try_play_async,
                "pause": session.try_pause_async,
                "play_pause": session.try_toggle_play_pause_async,
                "next": session.try_skip_next_async,
                "prev": session.try_skip_previous_async,
            }[cmd]
            done = bool(await call())
        except Exception as exc:
            log.warning("media session command failed", exc_info=True)
            return ActionResult(False, "os", f"{type(exc).__name__}: {exc}", "no_media_app")
        if not done:
            return ActionResult(False, "os", "The app did not accept that", "unsupported")
        return ActionResult(
            True, "os", observed={"app": app_label(session.source_app_user_model_id)}
        )

    async def seek_to(self, position_s: float) -> ActionResult:
        try:
            session = await self._session()
            if session is None:
                return ActionResult(False, "os", "No media app is open", "no_media_app")
            start = _seconds(session.get_timeline_properties().start_time)
            ticks = int((start + max(0.0, position_s)) * TICKS_PER_S)
            done = bool(await session.try_change_playback_position_async(ticks))
        except Exception as exc:
            log.warning("media session seek failed", exc_info=True)
            return ActionResult(False, "os", f"{type(exc).__name__}: {exc}", "no_media_app")
        if not done:
            return ActionResult(False, "os", "This app does not allow seeking", "unsupported")
        return ActionResult(True, "os")


def windows_media_sessions() -> MediaApps | None:
    """The real thing on Windows with the winrt package; None elsewhere (tests, dry runs)."""
    try:
        return WindowsMediaSessions()
    except Exception:  # ImportError off Windows, or a build without the package
        log.info("media sessions unavailable: other media apps are controlled by media keys only")
        return None
