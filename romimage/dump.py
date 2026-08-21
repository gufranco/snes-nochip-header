"""What arrives on disk, before any of it is a cartridge.

A dump is not a cartridge image. It is a cartridge image plus whatever the device
that read it decided to add, minus whatever it decided to split off, and the
first job of anything reading one is to get back to the bytes the console would
have seen.

Two devices account for nearly all of it. A copier writes 512 bytes in front of
the image describing what it just read, which shifts every offset in the file by
an amount that appears nowhere in the file. A backup unit splits the image across
numbered files, of which only the first carries that stub. Neither is part of the
cartridge, and a tool that forgets either reads the right bytes from the wrong
place and reports something plausible.

The stub is detected by length rather than by content, because its content is not
standardised. That same test decides where a header reader looks, so it is
imported from the package that reads headers rather than restated here: two
implementations of one decision is one more than a decision can have and still be
relied on.

The rest of this module is measurement rather than format. Deflate ratio per
block finds the regions of a cartridge that are already compressed, since data a
general-purpose compressor cannot shrink further is usually data something else
already shrank. Chunk indexing answers how much of one image survived into
another, which is what tells you whether a rebuild changed what it meant to.
"""

import re
import zlib
from collections.abc import Sequence
from pathlib import Path

from mapper import COPIER_BYTES, has_copier_stub, stub_by_length

PART_SUFFIX = re.compile(r"^\.\d{1,3}$")

BARE = "bare"
COPIER = "copier header"

BLOCK_BYTES = 0x10000
DEFLATE_LEVEL = 6

CHUNK_BYTES = 1024
CHUNK_STRIDE = 512


class NoParts(Exception):
    pass


def strip_copier_stub(data: bytes) -> bytes:
    """The dump without the stub, or unchanged when it never had one."""
    return data[COPIER_BYTES:] if has_copier_stub(data) else data


def parts_in(folder: Path | str) -> list[Path]:
    """Every numbered part below a folder, in the order they join.

    The sort is case-insensitive because the device wrote the names in upper case
    and half the world has renamed them since. The search goes below the folder
    as well as into it, because a set that arrived in an archive usually keeps its
    own directory.
    """
    found = [
        path
        for path in Path(folder).rglob("*")
        if path.is_file() and PART_SUFFIX.match(path.suffix)
    ]
    return sorted(found, key=lambda path: path.name.upper())


def join(parts: Sequence[bytes]) -> bytes:
    """One image from a split set, with the stub taken off only the first part."""
    if not parts:
        return b""
    return b"".join([strip_copier_stub(parts[0]), *parts[1:]])


def form(path: Path | str) -> str:
    """How a source is stored, said in the words a report uses.

    The stub is decided from the file's length, so this reads no cartridge to
    answer a question about how one is packaged. On a library that runs to
    gigabytes the difference is the whole cost of the call.
    """
    path = Path(path)
    if path.is_dir():
        return f"{len(parts_in(path))} part set"
    return COPIER if stub_by_length(path.stat().st_size) else BARE


def read(path: Path | str) -> bytes:
    """A dump from disk or from a folder of parts, as the console would see it."""
    path = Path(path)
    if not path.is_dir():
        return strip_copier_stub(path.read_bytes())

    parts = parts_in(path)
    if not parts:
        raise NoParts(f"{path} holds no numbered parts to join")
    return join([part.read_bytes() for part in parts])


def deflate_ratio(block: bytes) -> float:
    """How much a general-purpose compressor can still take off a block."""
    if not block:
        return 0.0
    return len(zlib.compress(block, DEFLATE_LEVEL)) / len(block)


def block_ratios(data: bytes, block: int = BLOCK_BYTES) -> list[float]:
    """That ratio across the whole image, which is where its structure shows."""
    return [deflate_ratio(data[i : i + block]) for i in range(0, len(data) - block + 1, block)]


def chunk_index(
    data: bytes, chunk: int = CHUNK_BYTES, stride: int = CHUNK_STRIDE
) -> dict[bytes, int]:
    """Where each distinct chunk first appears, at a stride finer than the chunk.

    The stride is deliberately shorter than the chunk, so a run that moved by an
    amount that is not a whole chunk is still found.
    """
    index: dict[bytes, int] = {}
    for i in range(0, len(data) - chunk + 1, stride):
        index.setdefault(data[i : i + chunk], i)
    return index


def measure_reuse(
    source: bytes, target: bytes, chunk: int = CHUNK_BYTES, stride: int = CHUNK_STRIDE
) -> tuple[int, int]:
    """How many of one image's chunks appear anywhere in another."""
    index = chunk_index(target, chunk=chunk, stride=stride)
    found = total = 0
    for i in range(0, len(source) - chunk + 1, chunk):
        total += 1
        if source[i : i + chunk] in index:
            found += 1
    return found, total
