"""The short pairing code under the TV's QR (plan 15G): PC side."""

from __future__ import annotations

from pathlib import Path

import jwt

from hud.viewmodel import HudViewModel
from lan_auth import LanAuth
from pair_codes import ALPHABET, CODE_LEN, CODE_TTL_S, PairCodes, code_hash, normalize, valid
from room import RoomStore


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def codes_with(clock: Clock, *sequence: str) -> PairCodes:
    pending = list(sequence)
    return PairCodes(clock=clock, new_code=lambda: pending.pop(0))


def test_codes_are_easy_to_read_and_type() -> None:
    assert len(ALPHABET) == 31 and not set("01OIL") & set(ALPHABET)
    code = PairCodes().fresh()
    assert len(code) == CODE_LEN and valid(code)
    assert normalize(" k7qm-4xpa ") == "K7QM4XPA"
    assert code_hash("k7qm-4xpa") == code_hash("K7QM4XPA")


def test_the_relay_must_confirm_before_the_tv_shows_a_cloud_code() -> None:
    clock = Clock()
    codes = codes_with(clock, "K7QM4XPA")
    announced: list[tuple[str, int]] = []
    codes.on_new = lambda h, ttl: announced.append((h, ttl))
    assert codes.shown(need_relay=True) is None
    assert announced == [(code_hash("K7QM4XPA"), CODE_TTL_S)]
    codes.confirm("0" * 64)  # someone else's hash changes nothing
    assert codes.shown(need_relay=True) is None
    codes.confirm(code_hash("K7QM4XPA"))
    assert codes.shown(need_relay=True) == "K7QM-4XPA"
    assert codes.shown(need_relay=False) == "K7QM-4XPA"


def test_a_code_is_replaced_before_it_runs_out() -> None:
    clock = Clock()
    codes = codes_with(clock, "AAAA2222", "BBBB3333")
    assert codes.fresh() == "AAAA2222"
    clock.now += CODE_TTL_S - 120
    assert codes.fresh() == "AAAA2222"
    clock.now += 60  # 60 s left: nobody should start typing it now
    assert codes.fresh() == "BBBB3333"


def test_lan_checks_use_a_code_up_and_refuse_old_or_wrong_ones() -> None:
    clock = Clock()
    codes = codes_with(clock, "AAAA2222", "BBBB3333", "CCCC4444")
    codes.fresh()
    assert not codes.check("AAAA2223")
    assert codes.check("aaaa-2222")
    assert not codes.check("AAAA2222")  # once
    assert codes.fresh() == "BBBB3333"
    clock.now += CODE_TTL_S + 1
    assert not codes.check("BBBB3333")  # expired


def test_announce_repeats_only_a_live_code() -> None:
    clock = Clock()
    codes = codes_with(clock, "AAAA2222")
    seen: list[int] = []
    codes.announce()  # nothing yet
    codes.fresh()
    codes.on_new = lambda _h, ttl: seen.append(ttl)
    clock.now += 100
    codes.announce()
    assert seen == [CODE_TTL_S - 100]
    clock.now += CODE_TTL_S
    codes.announce()
    assert seen == [CODE_TTL_S - 100]


def test_a_lan_phone_pairs_with_the_code(tmp_path: Path) -> None:
    store = RoomStore(tmp_path / "room.json")
    store.load_or_create()
    store.set_room_key("k" * 64)
    clock = Clock()
    codes = codes_with(clock, "AAAA2222", "BBBB3333")
    lan = LanAuth(store, codes, clock=clock)
    codes.fresh()
    assert lan.pair_with_code("ZZZZ9999", "iPhone") is None
    granted = lan.pair_with_code("aaaa-2222", "iPhone")
    assert granted is not None and granted.room_id == store.identity.room_id
    claims = jwt.decode(
        granted.device_token,
        "k" * 64,
        algorithms=["HS256"],
        issuer="couch-jarvis",
        options={"verify_exp": False, "verify_iat": False},  # the test clock is in 1970
    )
    assert claims["sub"] == granted.device_id
    assert lan.pair_with_code("AAAA2222", "iPad") is None  # used up
    assert lan.verify_token(granted.device_token) == granted.device_id


def test_wrong_codes_lock_lan_pairing_for_a_while(tmp_path: Path) -> None:
    store = RoomStore(tmp_path / "room.json")
    store.load_or_create()
    store.set_room_key("k" * 64)
    clock = Clock()
    codes = codes_with(clock, "AAAA2222", "BBBB3333")
    lan = LanAuth(store, codes, clock=clock)
    codes.fresh()
    for _ in range(10):
        assert lan.pair_with_code("ZZZZ9999", "x") is None
    assert lan.pair_with_code("AAAA2222", "x") is None  # locked out, even with the right code
    clock.now += 61
    assert lan.pair_with_code("AAAA2222", "x") is not None


def test_the_tv_card_carries_the_code_for_its_transport() -> None:
    asked: list[str] = []

    def pair_code(transport: str) -> str | None:
        asked.append(transport)
        return "K7QM-4XPA" if transport == "cloud" else None

    vm = HudViewModel(
        cloud_url=lambda: "https://armrest-app.pages.dev/?room=r&secret=s",
        lan_url=lambda: None,
        pair_code=pair_code,
    )
    card = vm.frame().qr
    assert card is not None and card.code == "K7QM-4XPA" and asked == ["cloud"]
    vm.hide_qr()
    asked.clear()
    assert vm.frame().qr is None and asked == []  # no code is made while nobody looks
