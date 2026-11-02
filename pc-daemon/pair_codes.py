"""Short pairing codes for phones that cannot scan the QR (plan 15G).

An iPhone home-screen app has its own storage, so a pairing done in Safari never reaches it, and
some phones have no working camera. Under the QR the TV shows a short code such as ``K7QM-4XPA``
that can be typed into the app instead.

- 8 characters from 31 that cannot be confused (no 0/O, 1/I/L): about 39 bits.
- A code lives 10 minutes and works once. It changes as soon as a phone pairs, and whenever the
  QR comes back after it expired.
- The relay only ever sees its SHA-256 (``pair.code``), never the code, and limits code tries
  per IP. The TV shows a code only once the relay has confirmed it (``pair.code.ok``); an older
  relay that does not know codes answers ``forbidden_type`` and the TV shows just the QR. On the
  local network (no relay) the PC checks the code itself.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LEN = 8
CODE_TTL_S = 600
REFRESH_BEFORE_S = 90  # a code about to expire is replaced before anyone starts typing it


def normalize(code: str) -> str:
    """What the person typed, as the code: upper case, no spaces or dashes."""
    return "".join(ch for ch in code.upper() if ch.isalnum())


def valid(code: str) -> bool:
    return len(code) == CODE_LEN and all(ch in ALPHABET for ch in code)


def code_hash(code: str) -> str:
    return hashlib.sha256(normalize(code).encode("ascii")).hexdigest()


def display(code: str) -> str:
    return f"{code[:4]}-{code[4:]}"


@dataclass(frozen=True)
class _Code:
    code: str
    expires_at: float
    confirmed: bool = False  # the relay knows it (cloud); not needed on the local network


class PairCodes:
    def __init__(
        self,
        clock: Callable[[], float] = time.time,
        new_code: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock
        self._new_code = new_code or (
            lambda: "".join(secrets.choice(ALPHABET) for _ in range(CODE_LEN))
        )
        self._current: _Code | None = None
        # Set by the relay client: register this hash for this many seconds.
        self.on_new: Callable[[str, int], None] = lambda _hash, _ttl: None

    def fresh(self) -> str:
        """The current code, replaced first if it is missing or about to expire."""
        now = self._clock()
        if self._current is None or self._current.expires_at - now < REFRESH_BEFORE_S:
            self.rotate()
        assert self._current is not None
        return self._current.code

    def rotate(self) -> None:
        """A new code (a phone just paired, or the old one ran out); the old one stops working."""
        self._current = _Code(self._new_code(), self._clock() + CODE_TTL_S)
        self.on_new(code_hash(self._current.code), CODE_TTL_S)

    def announce(self) -> None:
        """Tell the relay the current code again (after a reconnect)."""
        current = self._current
        if current is not None and current.expires_at > self._clock():
            self.on_new(code_hash(current.code), int(current.expires_at - self._clock()))

    def confirm(self, hashed: str) -> None:
        """The relay stored this hash: the TV may now show the code."""
        current = self._current
        if current is not None and hmac.compare_digest(code_hash(current.code), hashed):
            self._current = _Code(current.code, current.expires_at, confirmed=True)

    def shown(self, *, need_relay: bool) -> str | None:
        """The code for the TV (``K7QM-4XPA``), or None when it would not work."""
        code = self.fresh()
        assert self._current is not None
        if need_relay and not self._current.confirmed:
            return None
        return display(code)

    def check(self, typed: str) -> bool:
        """Local network pairing: is this the live code? A right code is used up."""
        current = self._current
        code = normalize(typed)
        if current is None or current.expires_at <= self._clock() or not valid(code):
            return False
        if not hmac.compare_digest(code, current.code):
            return False
        self.rotate()
        return True
