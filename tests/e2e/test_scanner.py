"""The in-app QR scanner against a real camera feed: Edge's fake camera plays a Y4M clip of the TV's
pairing QR, and the phone must end up paired without ever opening the link in a camera app."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, sync_playwright

from e2e_support import Daemon
from hud.qr import qr_matrix

pytestmark = pytest.mark.e2e

WIDTH, HEIGHT = 640, 480


def qr_y4m(text: str, path: Path, frames: int = 10, quiet: bool = True) -> Path:
    """A short uncompressed video (YUV 4:2:0) of the QR, dark modules on a white card, as a
    phone camera would see the TV. ``quiet=False`` paints the QR edge to edge, without the
    white border a real card has."""
    matrix = qr_matrix(text, border=4 if quiet else 0)
    n = len(matrix)
    module = max(1, (min(WIDTH, HEIGHT) - 40) // n)
    size = module * n
    ox, oy = (WIDTH - size) // 2, (HEIGHT - size) // 2
    y_plane = bytearray(b"\x80" * (WIDTH * HEIGHT))  # mid grey around the card
    for r in range(oy - 12, oy + size + 12):
        for c in range(ox - 12, ox + size + 12):
            if 0 <= r < HEIGHT and 0 <= c < WIDTH:
                y_plane[r * WIDTH + c] = 0xEB  # white card (video range)
    for r, row in enumerate(matrix):
        for c, dark in enumerate(row):
            if not dark:
                continue
            for dy in range(module):
                base = (oy + r * module + dy) * WIDTH + ox + c * module
                y_plane[base : base + module] = b"\x10" * module
    chroma = b"\x80" * (WIDTH * HEIGHT // 4)
    with path.open("wb") as out:
        out.write(f"YUV4MPEG2 W{WIDTH} H{HEIGHT} F30:1 Ip A1:1 C420jpeg\n".encode())
        for _ in range(frames):
            out.write(b"FRAME\n")
            out.write(bytes(y_plane))
            out.write(chroma)
            out.write(chroma)
    return path


@pytest.fixture
def camera_browser(tmp_path: Path, daemon: Daemon) -> Iterator[Browser]:
    clip = qr_y4m(daemon.pair_url, tmp_path / "tv-qr.y4m")
    with sync_playwright() as p:
        b = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=[
                "--use-fake-device-for-media-stream",
                "--use-fake-ui-for-media-stream",
                f"--use-file-for-fake-video-capture={clip}",
            ],
        )
        yield b
        b.close()


def test_scanning_the_tv_qr_inside_the_app_pairs_the_phone(
    camera_browser: Browser, daemon: Daemon
) -> None:
    ctx = camera_browser.new_context(
        viewport={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
        permissions=["camera"],
    )
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(daemon.url)  # no QR link: the landing page offers to scan
    page.get_by_role("button", name="Scan the code on the TV").click()
    page.get_by_label("Camera").wait_for(timeout=10_000)
    # the scanner found the TV's QR and the phone paired over the LAN by itself
    page.get_by_role("button", name="Play / Pause").wait_for(timeout=20_000)
    page.wait_for_function(
        "() => [...document.querySelectorAll('button')].some(b => b.getAttribute('aria-label') === 'Play / Pause' && !b.disabled)",
        timeout=15_000,
    )
    assert "secret=" not in page.url
    assert page.evaluate("() => JSON.parse(localStorage.getItem('cj.pairing') || 'null')")[
        "deviceId"
    ].startswith("lan-")
    assert errors == []
    ctx.close()


def test_a_foreign_qr_is_named_as_such_and_scanning_goes_on(tmp_path: Path, daemon: Daemon) -> None:
    clip = qr_y4m("https://example.com/not-a-tv", tmp_path / "other.y4m")
    with sync_playwright() as p:
        b = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=[
                "--use-fake-device-for-media-stream",
                "--use-fake-ui-for-media-stream",
                f"--use-file-for-fake-video-capture={clip}",
            ],
        )
        page = b.new_context(
            viewport={"width": 390, "height": 844}, permissions=["camera"]
        ).new_page()
        page.goto(daemon.url)
        page.get_by_role("button", name="Scan the code on the TV").click()
        page.get_by_text("That isn't the TV's pairing code").wait_for(timeout=20_000)
        assert page.get_by_role("button", name="Play / Pause").count() == 0
        b.close()
