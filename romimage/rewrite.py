"""Changing what a cartridge says about itself, and keeping it consistent.

Removing a coprocessor from a cartridge is mostly a question of code. The last
step is not: the header still declares the chip, and a machine that reads a
declaration the board cannot honour does not behave like one reading the truth.
So the header has to be rewritten, and rewriting it is where the mistakes are,
because three things have to stay consistent at once.

**The header is mirrored.** A cartridge image usually holds several byte-for-byte
copies of its header, because the same bank appears at several addresses. Tools
tend to read the first one they find, and they do not all agree about which that
is. Updating one copy produces an image that works in the tool it was tested in
and not on the machine it was built for.

**The checksum covers the fields that hold it.** The sixteen-bit sum is taken over
the whole image, including the four bytes storing the checksum and its complement,
which cannot be known before the sum. The convention resolves the circularity:
those four bytes count as `FF FF 00 00` whatever they actually hold, which is
`0x01FE` per header. Zero them, add `0x01FE` once per mirror, and the result is
the value to write.

**The size byte is an exponent, not a size.** It is the base-two logarithm of the
image in kilobytes, rounded up. An image that grew past a power of two and kept
its old byte declares itself smaller than it is, and a machine that trusts the
declaration never reads the rest.

Everything here returns a new image. Nothing is written in place, because a
half-rewritten header is worse than an unrewritten one, and a failure partway
through should leave nothing behind.

Finding the header is not this module's job, and an earlier version of it tried
anyway. It kept its own list of plausible mapping bytes, and a real library
disagreed with that list on six hundred cartridges: Contra III declares `53`,
HAL's Hole in One Golf declares `46`, and neither is in any table anyone has
written down. `mapper` decides by scoring four independent signals against that
same library, so the anchor comes from there and the disagreement cannot exist.

What is left here is the definition of a mirror, and it is simpler than the rule
it replaces. A mirror exists because the same bank is visible at two addresses,
so the bytes are literally the same bytes: every copy of the header is
byte-identical to the first. Searching for all thirty two of them rather than for
the title needs no allowlist of mapping bytes, and cannot match a title that
happens to appear in the middle of something else.
"""

import mapper
from mapper.header import HEADER_BYTES, TITLE_BYTES, NoHeader

MAP_MODE = 0x15
CHIPSET = 0x16
ROM_SIZE = 0x17
SRAM_SIZE = 0x18
CHECKSUM_COMPLEMENT = 0x1C
CHECKSUM = 0x1E

CHIPSET_ROM_ONLY = 0x00
CHECKSUM_FIELD_SUM = 0x01FE
CHECKSUM_FIELD_BYTES = 4

KILOBYTE = 1024

PADDING = frozenset({0x20, 0x00, 0xFF})

COPROCESSORS = {
    0x03: "DSP",
    0x05: "DSP",
    0x13: "SuperFX",
    0x14: "SuperFX",
    0x15: "SuperFX",
    0x1A: "SuperFX",
    0x25: "OBC1",
    0x32: "SA-1",
    0x34: "SA-1",
    0x35: "SA-1",
    0x43: "S-DD1",
    0x45: "S-DD1",
    0x55: "S-RTC",
    0xE3: "Super Game Boy",
    0xF3: "CX4",
    0xF5: "SPC7110",
    0xF6: "ST010",
    0xF9: "SPC7110",
}


def size_byte(length):
    """The exponent a header uses to declare its own size in kilobytes."""
    kilobytes = max(1, (length + KILOBYTE - 1) // KILOBYTE)
    exponent = 0
    while (1 << exponent) < kilobytes:
        exponent += 1
    return exponent


def identifies(block):
    """Whether a run of bytes can be searched for, or is only padding.

    A header made entirely of spaces, zeroes or `FF` is rare and real, and
    searching an image for it matches every run of padding in the file, including
    every position inside one long run. Those overlap each other and are one
    blank region rather than many headers.
    """
    return bool(set(block) - PADDING)


def anchor_of(image):
    """Where the header is, decided by the package that decides that."""
    try:
        return mapper.read(image).at
    except NoHeader:
        return None


def mirrors(image):
    """Every place this image repeats its header, in the order they appear.

    A mirror exists because the same bank is visible at more than one address, so
    every copy is byte-identical to the first. That makes the search exact: look
    for the whole thirty two bytes rather than for the title, and a run of text
    that merely resembles a title cannot match.

    Two headers cannot overlap, so the search resumes a whole header past each
    match. Matches that overlap are one region seen many times, and rewriting all
    of them corrupts the bytes the later ones were found by.
    """
    anchor = anchor_of(image)
    if anchor is None:
        return []

    block = bytes(image[anchor : anchor + HEADER_BYTES])
    if not identifies(block):
        return [anchor]

    found = []
    at = image.find(block)
    while at != -1:
        found.append(at)
        at = image.find(block, at + HEADER_BYTES)
    return found


def describe(image):
    """What every mirror declares, in the words a report prints."""
    return [
        {
            "at": at,
            "title": bytes(image[at : at + TITLE_BYTES]).decode("ascii", "replace").strip(),
            "map": image[at + MAP_MODE],
            "chipset": image[at + CHIPSET],
            "coprocessor": COPROCESSORS.get(image[at + CHIPSET]),
            "size": image[at + ROM_SIZE],
            "sram": image[at + SRAM_SIZE],
            "checksum": image[at + CHECKSUM] | (image[at + CHECKSUM + 1] << 8),
        }
        for at in mirrors(image)
    ]


def checksum(image, places=None):
    """The sixteen-bit sum, with the fields that store it counted as convention.

    The mirrors can be supplied, and a rewrite in progress must supply them. A
    header with its coprocessor byte cleared and its size byte corrected is, for
    the moment before the checksum is written, less recognisable as a header than
    it was: two of the four signals the map scores are the checksum agreeing with
    its complement and a plausible declared size, and the rewrite disturbs both.
    Re-deriving the mirrors from that intermediate counts zero of them, and the
    sum comes out short by exactly one header's worth of the convention.
    """
    places = mirrors(image) if places is None else places
    neutral = bytearray(image)
    for at in places:
        start = at + CHECKSUM_COMPLEMENT
        neutral[start : start + CHECKSUM_FIELD_BYTES] = bytes(CHECKSUM_FIELD_BYTES)
    return (sum(neutral) + CHECKSUM_FIELD_SUM * len(places)) & 0xFFFF


def declare_rom_only(image):
    """A copy declaring no coprocessor, its real size, and a matching checksum.

    Every mirror is rewritten, and the checksum is computed after the other fields
    change, because it covers them. It is computed over the mirrors already found
    rather than over the mirrors of the half-written image, which are not always
    the same set.
    """
    places = mirrors(image)
    if not places:
        raise NoHeader("no cartridge header at any documented position")

    declared = bytearray(image)
    for at in places:
        declared[at + CHIPSET] = CHIPSET_ROM_ONLY
        declared[at + ROM_SIZE] = size_byte(len(image))

    value = checksum(declared, places)
    complement = value ^ 0xFFFF
    for at in places:
        declared[at + CHECKSUM_COMPLEMENT] = complement & 0xFF
        declared[at + CHECKSUM_COMPLEMENT + 1] = complement >> 8
        declared[at + CHECKSUM] = value & 0xFF
        declared[at + CHECKSUM + 1] = value >> 8

    return bytes(declared)


def needs_rewrite(image):
    """Whether any mirror still declares a coprocessor or the wrong size."""
    places = mirrors(image)
    if not places:
        raise NoHeader("no cartridge header at any documented position")

    wanted = size_byte(len(image))
    return any(
        image[at + CHIPSET] != CHIPSET_ROM_ONLY or image[at + ROM_SIZE] != wanted for at in places
    )


BLOCK_BYTES = 0x1000


def changes(before, after, block=BLOCK_BYTES):
    """Every position at which two images of the same length differ.

    A rewrite touches a few dozen bytes of a file that runs to millions, so the
    comparison is done a block at a time and only blocks that differ are walked
    byte by byte. Comparing whole slices happens below the interpreter; walking
    every byte of a four megabyte cartridge does not, and doing that across a
    library turns a survey into an overnight job.
    """
    found = []
    for start in range(0, len(before), block):
        stop = start + block
        if before[start:stop] == after[start:stop]:
            continue
        found.extend(at for at in range(start, min(stop, len(before))) if before[at] != after[at])
    return found
