import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


romtools = _load("romtools")
header = _load("header")
identify = _load("identify")


def repair(image):
    return header.declare_no_coprocessor(image)


def needs_repair(image):
    positions = header.header_positions(image)
    if not positions:
        raise ValueError("no cartridge header found at either documented position")
    wanted = header.size_byte(len(image))
    return any(
        image[at + header.CHIPSET] != header.CHIPSET_ROM_ONLY
        or image[at + header.ROM_SIZE] != wanted
        for at in positions
    )


def changes(before, after):
    return [index for index in range(len(before)) if before[index] != after[index]]


def main(argv):
    if len(argv) not in (2, 3):
        print("usage: fix.py <image> [output]", file=sys.stderr)
        return 2

    source = Path(argv[1])
    try:
        image = romtools.read_source(source)
    except (ValueError, OSError) as error:
        print(f"  refused: {error}", file=sys.stderr)
        return 1

    print(f"{source.name}")
    print(identify.explain(identify.diagnose(image, romtools.source_form(source))))

    try:
        wanted = needs_repair(image)
    except ValueError as error:
        print(f"  refused: {error}", file=sys.stderr)
        return 1

    if not wanted:
        print("  nothing to repair, the header already declares no coprocessor")
        return 0

    if len(argv) == 2:
        print("  run again with an output path to write the repaired image")
        return 0

    repaired = repair(image)
    Path(argv[2]).write_bytes(repaired)
    print(f"\n{Path(argv[2]).name}")
    print(identify.explain(identify.diagnose(repaired)))
    print(f"  {len(changes(image, repaired))} bytes changed, all inside the cartridge headers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
