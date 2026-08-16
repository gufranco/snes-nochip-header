import hashlib
import zlib
from pathlib import Path

COPIER_HEADER = 512
BANK = 0x8000


def has_copier_header(data):
    if len(data) <= COPIER_HEADER:
        return False
    return len(data) % BANK == COPIER_HEADER


def strip_header(data):
    return data[COPIER_HEADER:] if has_copier_header(data) else data


def join_parts(parts):
    if not parts:
        return b""
    return b"".join([strip_header(parts[0]), *parts[1:]])


def load(path):
    return strip_header(Path(path).read_bytes())


def identity(data):
    return {
        "size": len(data),
        "crc32": f"{zlib.crc32(data):08X}",
        "sha256": hashlib.sha256(data).hexdigest(),
    }
