import hashlib
import re
import zlib
from pathlib import Path

COPIER_HEADER = 512
BANK = 0x8000
PART_SUFFIX = re.compile(r"^\.\d{1,3}$")


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


def parts_in(folder):
    found = [
        path
        for path in Path(folder).rglob("*")
        if path.is_file() and PART_SUFFIX.match(path.suffix)
    ]
    return sorted(found, key=lambda path: path.name.upper())


def load(path):
    return strip_header(Path(path).read_bytes())


def source_form(path):
    path = Path(path)
    if path.is_dir():
        return f"{len(parts_in(path))} part set"
    return "copier header" if has_copier_header(path.read_bytes()) else "bare"


def read_source(path):
    path = Path(path)
    if path.is_dir():
        parts = parts_in(path)
        if not parts:
            raise ValueError(f"{path} holds no numbered parts to join")
        return join_parts([part.read_bytes() for part in parts])
    return load(path)


def identity(data):
    return {
        "size": len(data),
        "crc32": f"{zlib.crc32(data):08X}",
        "sha256": hashlib.sha256(data).hexdigest(),
    }
