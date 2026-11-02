"""Pairing with the short code under the TV's QR (plan 15G): relay side."""

from __future__ import annotations

from typing import Any

from common import auth
from infra_support import ROOM, World, msg

CODE = "K7QM4XPA"
CODE_HASH = auth.sha256_hex(CODE)


def connect_code(world: World, cid: str, code: str, ip: str = "203.0.113.9", **query: str) -> int:
    import connect_handler

    event = world.event(
        cid,
        queryStringParameters={"code": code, "pair": "1", **query},
        headers={},
    )
    event["requestContext"]["identity"] = {"sourceIp": ip}
    return int(connect_handler.handler(event, None)["statusCode"])


def register(world: World, code_hash: str = CODE_HASH, expires_s: int = 600) -> list[Any]:
    assert world.connect_pc()["statusCode"] == 200
    world.send("pc-1", msg("pair.code", {"code_hash": code_hash, "expires_s": expires_s}, "c1"))
    return world.api.to("pc-1")


def test_the_pc_registers_a_code_and_hears_it_is_stored(world: World) -> None:
    replies = register(world)
    ok = [m for m in replies if m["type"] == "pair.code.ok"]
    assert ok and ok[0]["payload"] == {"code_hash": CODE_HASH} and ok[0]["reply_to"] == "c1"
    assert world.store.pair_code_room(CODE_HASH) == ROOM


def test_a_bad_registration_is_refused(world: World) -> None:
    for payload in (
        {"code_hash": "nothex", "expires_s": 600},
        {"code_hash": CODE_HASH, "expires_s": 5},
        {"code_hash": CODE_HASH, "expires_s": 99999},
        {"code_hash": CODE_HASH, "expires_s": True},
    ):
        world.api.sent.clear()
        if not world.store.get_room(ROOM):
            world.connect_pc()
        world.send("pc-1", msg("pair.code", payload))
        assert world.api.to("pc-1", "error")[0]["payload"]["code"] == "bad_message"
    assert world.store.pair_code_room(CODE_HASH) is None


def test_a_phone_pairs_with_the_code_and_learns_its_room(world: World) -> None:
    register(world)
    assert connect_code(world, "ph-1", "k7qm-4xpa") == 200  # typed in lower case with a dash
    world.send("ph-1", msg("pair.request", {"pair_code": "K7QM-4XPA", "device_name": "iPhone"}))
    granted = world.api.to("ph-1", "pair.granted")
    assert granted and granted[0]["payload"]["room_id"] == ROOM
    claims = auth.verify_device_token(
        world.room_key(), ROOM, granted[0]["payload"]["device_token"], world.clock[0]
    )
    assert claims is not None
    # the socket is now paired: commands reach the PC
    world.send("ph-1", msg("state.sync", {}, "s1"))
    assert world.api.to("pc-1", "state.sync")


def test_a_code_works_once(world: World) -> None:
    register(world)
    assert connect_code(world, "ph-1", CODE) == 200
    world.send("ph-1", msg("pair.request", {"pair_code": CODE, "device_name": "iPhone"}))
    assert world.api.to("ph-1", "pair.granted")
    assert connect_code(world, "ph-2", CODE) == 403  # used up


def test_wrong_and_expired_codes_are_refused(world: World) -> None:
    register(world)
    assert connect_code(world, "ph-1", "AAAA2222") == 403
    assert connect_code(world, "ph-2", "short") == 400
    assert connect_code(world, "ph-3", "K7QM4XP0") == 400  # 0 is not in the alphabet
    world.store._clock = lambda: world.clock[0] + 601  # type: ignore[method-assign]
    assert connect_code(world, "ph-4", CODE) == 403  # DynamoDB may not have deleted it yet


def test_the_code_on_the_request_must_match_the_one_connected_with(world: World) -> None:
    register(world)
    other = auth.sha256_hex("BBBB3333")
    world.send("pc-1", msg("pair.code", {"code_hash": other, "expires_s": 600}, "c2"))
    assert connect_code(world, "ph-1", CODE) == 200
    world.send("ph-1", msg("pair.request", {"pair_code": "BBBB3333", "device_name": "iPhone"}))
    assert world.api.to("ph-1", "pair.denied")[0]["payload"]["reason"] == "invalid_code"
    assert "ph-1" in world.api.closed  # one try per socket
    assert world.store.pair_code_room(other) == ROOM  # and the other code is still fine


def test_a_room_paired_phone_cannot_use_a_code_without_connecting_with_it(world: World) -> None:
    register(world)
    assert world.connect_phone("ph-1", pair="1")["statusCode"] == 200
    world.send("ph-1", msg("pair.request", {"pair_code": CODE, "device_name": "x"}))
    assert world.api.to("ph-1", "pair.denied") and not world.api.to("ph-1", "pair.granted")


def test_guessing_codes_is_rate_limited_per_ip(world: World) -> None:
    fixed = float(int(world.clock[0]) // 3600 * 3600 + 5)  # one 10-minute window for the run
    world.store._clock = lambda: fixed  # type: ignore[method-assign]
    register(world)
    results = [connect_code(world, f"g-{i}", "AAAA2222") for i in range(12)]
    assert results[:10] == [403] * 10 and results[10:] == [429, 429]
    assert connect_code(world, "g-right", CODE) == 429  # even the right code, until the window ends
    assert connect_code(world, "other-ip", CODE, ip="198.51.100.7") == 200


def test_a_code_is_only_for_pairing_a_phone(world: World) -> None:
    register(world)
    assert connect_code(world, "x-1", CODE, role="pc") == 400
    import connect_handler

    event = world.event("x-2", queryStringParameters={"code": CODE}, headers={})
    assert connect_handler.handler(event, None)["statusCode"] == 400  # no pair=1


def test_another_room_cannot_take_over_a_code(world: World) -> None:
    register(world)
    assert world.store.put_pair_code(CODE_HASH, "another-room-1", 600) is False
    assert world.store.pair_code_room(CODE_HASH) == ROOM
