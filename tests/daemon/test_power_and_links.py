"""PC power (lock / sleep / shut down) and opening a link shared from the phone (plan 15B, 15D)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.fastpath import plan_button, plan_text
from agent.graph import USER_ONLY_OPS
from agent.policy import GUEST_REFUSAL, guest_refusal, shared_url_allowed
from command_queue import CommandRequest
from contracts import CmdButtonPayload
from roles import RoleStore
from support import AgentEnv


@pytest.mark.parametrize(
    ("said", "action"),
    [
        ("lock the pc", "lock"),
        ("lock my computer", "lock"),
        ("hey armrest, lock the screen", "lock"),
        ("put the pc to sleep", "sleep"),
        ("put my computer to sleep", "sleep"),
        ("sleep the laptop", "sleep"),
        ("shut down the pc", "shutdown"),
        ("shutdown the computer", "shutdown"),
        ("turn off the pc", "shutdown"),
        ("turn the computer off", "shutdown"),
        ("power off my pc", "shutdown"),
        ("cancel the shutdown", "cancel_shutdown"),
        ("stop shutdown", "cancel_shutdown"),
        ("don't shut down", "cancel_shutdown"),
        ("do not turn off the pc", "cancel_shutdown"),
    ],
)
def test_power_phrases(said: str, action: str) -> None:
    plan = plan_text(said)
    assert plan is not None and [(s.op, dict(s.args)) for s in plan.steps] == [
        ("power", {"action": action})
    ]


@pytest.mark.parametrize("said", ["turn off the tv", "turn off the screen", "sleep the display"])
def test_the_tv_and_screen_still_just_blank_the_display(said: str) -> None:
    plan = plan_text(said)
    assert plan is not None and [s.op for s in plan.steps] == ["sleep_display"]


@pytest.mark.parametrize("said", ["sleep timer 30 minutes", "turn off subtitles", "lock"])
def test_other_phrases_never_touch_power(said: str) -> None:
    plan = plan_text(said)
    assert plan is None or all(s.op != "power" for s in plan.steps)


def test_power_and_links_are_never_the_ais_idea() -> None:
    assert {"power", "open_url"} <= USER_ONLY_OPS


@pytest.mark.parametrize(
    ("button", "action"),
    [
        ("pc_lock", "lock"),
        ("pc_sleep", "sleep"),
        ("pc_shutdown", "shutdown"),
        ("pc_cancel_shutdown", "cancel_shutdown"),
    ],
)
def test_power_buttons(button: str, action: str) -> None:
    plan = plan_button(button)  # type: ignore[arg-type]
    assert [(s.op, dict(s.args)) for s in plan.steps] == [("power", {"action": action})]


async def test_shutdown_waits_and_can_be_cancelled(env: AgentEnv) -> None:
    result = await env.runner().run(
        CommandRequest(
            command_id="c1",
            idempotency_key="k1",
            device_id="d1",
            kind="text",
            text="shut down the pc",
        )
    )
    assert result.ok and "cancel the shutdown" in result.message and env.os.shutdown_pending
    cancelled = await env.runner().run(
        CommandRequest(
            command_id="c2", idempotency_key="k2", device_id="d1", kind="button",
            action="pc_cancel_shutdown",
        )
    )  # fmt: skip
    assert cancelled.ok and cancelled.message == "Shutdown cancelled"
    assert not env.os.shutdown_pending and env.os.power_log == ["shutdown", "cancel_shutdown"]


async def test_cancelling_with_nothing_to_cancel_says_so(env: AgentEnv) -> None:
    result = await env.runner().run(
        CommandRequest(
            command_id="c1", idempotency_key="k1", device_id="d1", kind="text",
            text="cancel the shutdown",
        )
    )  # fmt: skip
    assert not result.ok and "no shutdown" in result.message.lower()


async def test_a_guest_cannot_power_the_pc(env: AgentEnv, tmp_path: Path) -> None:
    roles = RoleStore(tmp_path / "roles.json")
    roles.set_role("g1", "guest")
    env.deps.is_guest = lambda d: roles.role(d) == "guest"
    for request in (
        {"kind": "text", "text": "lock the pc"},
        {"kind": "button", "action": "pc_sleep"},
        {"kind": "button", "action": "pc_shutdown"},
    ):
        result = await env.runner().run(
            CommandRequest(command_id="c", idempotency_key=str(request), device_id="g1", **request)  # type: ignore[arg-type]
        )
        assert not result.ok and result.message == GUEST_REFUSAL
    assert env.os.power_log == []


async def test_a_shared_link_opens_in_the_tv_tab(env: AgentEnv) -> None:
    url = "https://www.bbc.co.uk/news"
    result = await env.runner().run(
        CommandRequest(
            command_id="c1", idempotency_key="k1", device_id="d1", kind="button",
            action="open_url", args={"url": url},
        )
    )  # fmt: skip
    assert result.ok and result.message == "Opened your link on the TV"
    assert f"open_saved:{url}" in env.browser.calls


def test_guests_share_only_streaming_links() -> None:
    assert guest_refusal([("open_url", {"url": "https://www.youtube.com/watch?v=x"})]) is None
    refusal = guest_refusal([("open_url", {"url": "https://example.com/"})])
    assert refusal is not None and "streaming" in refusal


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("https://youtu.be/abc", True),
        ("http://192.168.1.20:8096/web/", True),  # a Jellyfin server at home
        ("javascript:alert(1)", False),
        ("file:///C:/Windows/win.ini", False),
        ("https://user:pw@example.com/", False),
        ("https://", False),
    ],
)
def test_which_shared_links_open(url: str, ok: bool) -> None:
    assert shared_url_allowed(url) is ok


def test_open_url_carries_only_a_web_address() -> None:
    ok = CmdButtonPayload(
        command_id="c", idempotency_key="k", action="open_url", args={"url": "https://youtu.be/x"}
    )
    assert ok.args == {"url": "https://youtu.be/x"}
    for args in (
        {},
        {"url": "javascript:alert(1)"},
        {"url": "https://youtu.be/x", "extra": 1},
        {"url": "https://a.b/" + "x" * 2000},
        {"url": 5},
    ):
        with pytest.raises(ValidationError):
            CmdButtonPayload(command_id="c", idempotency_key="k", action="open_url", args=args)


async def test_the_service_hands_the_link_to_the_agent(env: AgentEnv, tmp_path: Path) -> None:
    from contracts import CmdButton, envelope
    from event_bus import EventBus
    from service import CommandService
    from timers import TimerService

    service = CommandService(
        room_id="r1",
        bus=EventBus(),
        runner=env.runner(),
        browser=env.browser,
        os_ctl=env.os,
        telemetry=env.telemetry,
        timers=TimerService(lambda info: asyncio.sleep(0)),
        mode="lan",
    )
    await service.start()
    try:
        url = "https://www.youtube.com/watch?v=abc"
        msg = envelope(
            CmdButton,
            "r1",
            CmdButtonPayload(
                command_id="c1", idempotency_key="k1", action="open_url", args={"url": url}
            ),
        )
        await service.handle_envelope(msg, "d1")
        for _ in range(50):
            if f"open_saved:{url}" in env.browser.calls:
                break
            await asyncio.sleep(0.02)
        assert f"open_saved:{url}" in env.browser.calls
    finally:
        await service.stop()
