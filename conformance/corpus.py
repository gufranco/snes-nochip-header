"""Replay every declaration a real cartridge library contains.

The corpus holds one entry per distinct combination of the five things a header
declares about how a cartridge is built, together with a count of how many
cartridges in the library share it. Facts about physical objects, and a
measurement. None of it is authored, and nothing in it could rebuild any part of
any cartridge.

Two claims are checked against every entry, and both are recomputable from the
entry alone, which is what makes the corpus worth shipping. The size exponent
must be the one the model derives from the size. And a cartridge that declares a
coprocessor, or declares a size that is not its own, must be one the model says
needs rewriting.

The second claim runs one way only, and deliberately. A cartridge whose first
header looks clean can still need a rewrite because a later mirror of that header
disagrees with it, and the corpus records the first mirror. So a claim of "needs
rewriting" is always allowed; a claim of "needs nothing" is checked.

The properties that do need the cartridges, that the checksum recomputes, that
nothing outside a header moved, that a second rewrite changes nothing, were
checked by the census across the whole library. Their counts travel with the
corpus as a record of what was measured, not as something this can re-derive.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from romimage import rewrite

CORPUS = Path(__file__).resolve().parent / "corpus.json"


def load(path=None):
    """The corpus, from where it ships or from a file a caller names."""
    return json.loads(Path(path or CORPUS).read_text())


def check(document):
    """Every case the model does not agree with, and why."""
    wrong = []
    for case in document["cases"]:
        wanted = rewrite.size_byte(case["size"])
        if case["size_byte"] != wanted:
            wrong.append({"case": case, "why": "size_byte", "wanted": wanted})
            continue

        dirty = case["chipset"] != rewrite.CHIPSET_ROM_ONLY or case["rom_size"] != wanted
        if dirty and not case["needs_rewrite"]:
            wrong.append({"case": case, "why": "needs_rewrite", "wanted": True})
    return wrong


def report(document, wrong):
    """What was replayed and what disagreed, in the order a reader needs it."""
    cases = document["cases"]
    print(f"  {len(cases)} declarations from {CORPUS.name}")
    print(f"  measured across {document['measured_across']} cartridges")
    print(f"  {len(cases) - len(wrong)} agreed, {len(wrong)} did not")
    for entry in wrong[:10]:
        case = entry["case"]
        print(
            f"  {entry['why']}: size {case['size']} chipset {case['chipset']:#04x} "
            f"rom_size {case['rom_size']:#04x} wanted {entry['wanted']}"
        )


def main(argv):
    if len(argv) > 2:
        print("usage: corpus.py [corpus.json]", file=sys.stderr)
        return 2

    document = load(argv[1] if len(argv) == 2 else None)
    wrong = check(document)
    report(document, wrong)
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
