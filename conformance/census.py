"""Take a census of a cartridge library you own, and check the rewrite on all of it.

A cartridge header is thirty two bytes in which the cartridge describes how it is
built: which layout it declares, which coprocessor is fitted, how much ROM and
save memory it carries. Those are facts about a physical object. They are not
authored, they carry none of the game, and a count of how many cartridges share a
combination is a measurement rather than a copy.

So this reads those bytes from every cartridge in a library and writes down the
distinct combinations it found. It records no title, because a title is the one
header field that is a name rather than a measurement, and the corpus it produces
contains nothing from which any part of any cartridge could be reconstructed.

It also asks the header reader the same question and counts the disagreements.
Two packages that both decide whether a file carries a header, and disagree about
it, are two answers where there should be one, and the count is the only way to
know before a user finds out.

While it is there, it does the harder thing too. For every cartridge it runs the
whole rewrite and checks four properties that must hold on every real image:

- the value written and its complement are complements of each other
- recomputing the checksum over the result gives back the value that was written
- nothing outside a header changed
- rewriting an already rewritten image changes nothing

Those checks need the cartridges, so they run here rather than in the test suite,
and their result is a count in the corpus rather than a claim the suite can
verify on its own. What the suite verifies is the part that replays from the
corpus alone: given a size and the four declared bytes, the size exponent and the
rewrite verdict.

A cartridge whose header cannot be found is counted as refused rather than
guessed at. Prototypes and unfinished dumps often carry a blank one, and
inventing a header for them would put fiction into a corpus of facts.
"""

import collections
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mapper

from romimage import dump, rewrite

SUFFIXES = (".sfc", ".smc", ".fig", ".swc")

PROPERTIES = ("complement", "recompute", "confined", "settled")


def images(source, limit=None):
    """Every cartridge in a library, whether it is a folder or one archive.

    An eight gigabyte archive is read member by member rather than unpacked,
    because a census does not need a second copy of the library on disk.
    """
    source = Path(source)
    if source.is_dir():
        found = sorted(
            path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in SUFFIXES
        )
        for path in found[:limit] if limit else found:
            yield path.name, path.read_bytes()
        return

    with zipfile.ZipFile(source) as archive:
        names = sorted(name for name in archive.namelist() if Path(name).suffix.lower() in SUFFIXES)
        for name in names[:limit] if limit else names:
            with archive.open(name) as member:
                yield Path(name).name, member.read()


def properties_of(image, places):
    """The four things that must be true of every rewrite, on this cartridge."""
    written = rewrite.declare_rom_only(image)
    at = places[0]

    value = written[at + rewrite.CHECKSUM] | (written[at + rewrite.CHECKSUM + 1] << 8)
    complement = written[at + rewrite.CHECKSUM_COMPLEMENT] | (
        written[at + rewrite.CHECKSUM_COMPLEMENT + 1] << 8
    )

    inside = {
        offset
        for place in places
        for offset in range(place, min(place + rewrite.HEADER_BYTES, len(image)))
    }

    return {
        "complement": value ^ complement == 0xFFFF,
        "recompute": value == rewrite.checksum(written),
        "confined": all(offset in inside for offset in rewrite.changes(image, written)),
        "settled": rewrite.declare_rom_only(written) == written,
    }


def failed(name, properties):
    """The properties that did not hold on one cartridge, named with it."""
    return [
        {"file": name, "property": property_name}
        for property_name, ok in properties.items()
        if not ok
    ]


def survey(library, limit=None):
    """What the library is made of, and how the rewrite behaved on all of it."""
    cases = collections.Counter()
    mapping = collections.Counter()
    chipset = collections.Counter()
    coprocessor = collections.Counter()
    mirrors = collections.Counter()
    held = collections.Counter()
    forms = collections.Counter()
    failures = []
    read = refused = wanted = disagreed = 0

    for name, blob in images(library, limit):
        forms["copier stub" if dump.has_copier_stub(blob) else "bare"] += 1
        image = dump.strip_copier_stub(blob)

        places = rewrite.mirrors(image)
        try:
            mapper.read(image)
        except mapper.NoHeader:
            disagreed += bool(places)
        else:
            disagreed += not places

        if not places:
            refused += 1
            continue

        read += 1
        first = image[places[0] : places[0] + rewrite.HEADER_BYTES]
        declared = {
            "size": len(image),
            "map": first[rewrite.MAP_MODE],
            "chipset": first[rewrite.CHIPSET],
            "rom_size": first[rewrite.ROM_SIZE],
            "sram_size": first[rewrite.SRAM_SIZE],
        }

        mapping[declared["map"]] += 1
        chipset[declared["chipset"]] += 1
        coprocessor[rewrite.COPROCESSORS.get(declared["chipset"]) or "none"] += 1
        mirrors[len(places)] += 1

        needs = rewrite.needs_rewrite(image)
        wanted += needs
        cases[json.dumps({**declared, "needs_rewrite": needs}, sort_keys=True)] += 1

        properties = properties_of(image, places)
        for property_name, ok in properties.items():
            held[property_name] += ok
        failures.extend(failed(name, properties))

    return {
        "read": read,
        "refused": refused,
        "disagreed_with_the_map": disagreed,
        "needs_rewrite": wanted,
        "forms": dict(forms),
        "mapping": {f"{value:#04x}": count for value, count in sorted(mapping.items())},
        "chipset": {f"{value:#04x}": count for value, count in sorted(chipset.items())},
        "coprocessor": dict(coprocessor.most_common()),
        "mirrors": {str(count): total for count, total in sorted(mirrors.items())},
        "properties": {name: held[name] for name in PROPERTIES},
        "failures": failures,
        "cases": cases,
    }


def corpus(found):
    """The replayable part: every distinct case, with what it must produce."""
    cases = []
    for encoded, count in sorted(found["cases"].items()):
        declared = json.loads(encoded)
        cases.append(
            {
                **declared,
                "size_byte": rewrite.size_byte(declared["size"]),
                "cartridges": count,
            }
        )
    return {
        "measured_across": found["read"],
        "refused": found["refused"],
        "disagreed_with_the_map": found["disagreed_with_the_map"],
        "properties_held": found["properties"],
        "cases": cases,
    }


def report(found):
    """What the census saw, said in the order a reader needs it."""
    print(f"  {found['read']} cartridges read, {found['refused']} refused")
    print(f"  {found['disagreed_with_the_map']} disagreed with the map about having a header")
    print(f"  {len(found['cases'])} distinct declarations")
    print(f"  {found['needs_rewrite']} still declare a coprocessor or the wrong size")
    for name in PROPERTIES:
        print(f"  {name:<12} held on {found['properties'][name]} of {found['read']}")
    for failure in found["failures"][:10]:
        print(f"  FAILED {failure['property']}: {failure['file']}")


def verdict(found):
    """Zero when every property held on every cartridge, one when any did not."""
    return 1 if found["failures"] else 0


def main(argv):
    if len(argv) not in (3, 4):
        print("usage: census.py <library> <out.json> [limit]", file=sys.stderr)
        return 2

    limit = int(argv[3]) if len(argv) == 4 else None
    found = survey(argv[1], limit)
    report(found)

    Path(argv[2]).write_text(json.dumps(corpus(found), indent=2) + "\n")
    print(f"  written to {argv[2]}")
    return verdict(found)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
