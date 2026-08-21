"""What makes a file itself, and which of those values is allowed to decide.

A project that cannot ship a cartridge still has to tell the reader which one to
supply, and has to refuse the wrong one before reading a byte of it. That means
publishing enough identity for a person to confirm their copy, and checking it in
code before use. A digest printed in a readme that nothing checks is decoration.

Each value here has one job, and publishing a row of hexadecimal without saying
which one decides is cargo cult.

| Value  | Job                                                     | Decides |
|--------|---------------------------------------------------------|---------|
| size   | reject the wrong file for one stat, before hashing      | no      |
| crc32  | cross-reference against community databases             | no      |
| md5    | interoperate with database entries that still key on it | no      |
| sha1   | the same, for the databases that moved on once          | no      |
| sha256 | accept or reject                                        | yes     |

CRC32 is a 32-bit error code, not an integrity claim, and both MD5 and SHA-1 are
collision-broken. They are published so a reader can look their copy up somewhere
that still indexes by them, never so that code can decide by them.

A digest describes bytes, so it only means something alongside the exact form
those bytes are in: stub stripped or present, parts joined or separate. `dump`
answers that question, and every measurement here assumes it was asked first.
"""

import hashlib
import zlib
from collections.abc import Mapping
from typing import Any

AUTHORITATIVE = "sha256"

INTEROPERABLE = ("crc32", "md5", "sha1")


class NoAuthority(Exception):
    pass


def measure(data: bytes) -> dict[str, Any]:
    """Everything published about a file, with one value able to decide."""
    return {
        "size": len(data),
        "crc32": f"{zlib.crc32(data):08X}",
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        AUTHORITATIVE: hashlib.sha256(data).hexdigest(),
    }


def agrees(found: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    """Whether a measurement is the file that was expected, by one value only.

    A weaker value that happens to disagree does not overrule the deciding one,
    and an expectation that omits the deciding one is refused rather than settled
    by whatever else it carries.
    """
    if AUTHORITATIVE not in expected:
        raise NoAuthority(f"an expectation with no {AUTHORITATIVE} cannot accept or reject")
    agreed: bool = found.get(AUTHORITATIVE) == expected[AUTHORITATIVE]
    return agreed
