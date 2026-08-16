TITLE_LENGTH = 21
MAP_MODE = 0x15
CHIPSET = 0x16
ROM_SIZE = 0x17
SRAM_SIZE = 0x18
CHECKSUM_COMPLEMENT = 0x1C
CHECKSUM = 0x1E
HEADER_LENGTH = 0x20

CHIPSET_ROM_ONLY = 0x00
CHECKSUM_FIELD_SUM = 0x01FE

POSITIONS = (0x007FC0, 0x00FFC0)
PLAUSIBLE_MAP_MODES = frozenset({0x20, 0x21, 0x23, 0x25, 0x30, 0x31, 0x32, 0x35})

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
    kilobytes = max(1, (length + 1023) // 1024)
    exponent = 0
    while (1 << exponent) < kilobytes:
        exponent += 1
    return exponent


def looks_like_a_title(image, at):
    if at + HEADER_LENGTH > len(image):
        return False
    return all(0x20 <= byte < 0x7F for byte in image[at : at + TITLE_LENGTH])


def header_positions(image):
    seeds = [
        at
        for at in POSITIONS
        if looks_like_a_title(image, at) and image[at + MAP_MODE] in PLAUSIBLE_MAP_MODES
    ]
    if not seeds:
        return []

    title = bytes(image[seeds[0] : seeds[0] + TITLE_LENGTH])
    found = []
    at = image.find(title)
    while at != -1:
        if at + HEADER_LENGTH <= len(image) and image[at + MAP_MODE] in PLAUSIBLE_MAP_MODES:
            found.append(at)
        at = image.find(title, at + 1)
    return found


def checksum(image, at):
    positions = header_positions(image)
    zeroed = bytearray(image)
    for position in positions:
        start = position + CHECKSUM_COMPLEMENT
        zeroed[start : start + 4] = bytes(4)
    return (sum(zeroed) + CHECKSUM_FIELD_SUM * len(positions)) & 0xFFFF


def read(image):
    found = []
    for at in header_positions(image):
        found.append(
            {
                "at": at,
                "title": bytes(image[at : at + TITLE_LENGTH]).decode("ascii", "replace").strip(),
                "map": image[at + MAP_MODE],
                "chipset": image[at + CHIPSET],
                "coprocessor": COPROCESSORS.get(image[at + CHIPSET]),
                "size": image[at + ROM_SIZE],
                "sram": image[at + SRAM_SIZE],
                "checksum": image[at + CHECKSUM] | (image[at + CHECKSUM + 1] << 8),
            }
        )
    return found


def declare_no_coprocessor(image):
    declared = bytearray(image)
    positions = header_positions(image)
    if not positions:
        raise ValueError("no cartridge header found at either documented position")

    for at in positions:
        declared[at + CHIPSET] = CHIPSET_ROM_ONLY
        declared[at + ROM_SIZE] = size_byte(len(image))

    value = checksum(declared, positions[0])
    complement = value ^ 0xFFFF
    for at in positions:
        declared[at + CHECKSUM_COMPLEMENT] = complement & 0xFF
        declared[at + CHECKSUM_COMPLEMENT + 1] = complement >> 8
        declared[at + CHECKSUM] = value & 0xFF
        declared[at + CHECKSUM + 1] = value >> 8

    return bytes(declared)
