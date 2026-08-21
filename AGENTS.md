# Working in this repository

This file is for a coding agent. A person reading it will not be harmed, but
[README.md](README.md) is the document written for them.

## What this project is, in one paragraph

A package that reads a Super NES cartridge image and rewrites its header, so that
a cartridge whose coprocessor has been removed stops declaring one. The header is
mirrored, the checksum covers the bytes that store it, and the size byte is an
exponent, so all three have to stay consistent at once. What the header means
comes from Nintendo's own submission specification; what real cartridges actually
contain comes from a library of several thousand, and the two are not the same
thing.

## The authority ladder

This one is not shaped like the sibling projects, and the difference is
deliberate.

1. **`conformance/hardware.json`**, which is Nintendo's SNES Development Manual
   pinned fact by fact with the sentence each figure came from. It decides which
   byte holds what, what each value means, and how the checksum is calculated.
2. **A retail cartridge.** The specification is an instruction issued to
   licensees, not a description of silicon, so a genuine cartridge can disagree
   with it and still be genuine. Where one does, the cartridge is the fact and
   the specification is the intent.
3. **Nothing else.**

`conformance/divergences.json` records every place they part company.

## The submission checksum is not the header checksum

The manual carries two things called a check sum and only one of them is the one
in the header. Page 1-2-9 describes a plain sum for the submission sheet and says
outright: "This method of calculation is different from the check sum on the ROM
Registration Specification." Page 1-2-20 describes the real one, which neutralises
four bytes and counts a short image up to a power of two.

Reading the wrong page is how this package came to sum every byte once, which was
wrong on 630 of the 633 non-power-of-two retail cartridges it had been run over.

**If you are about to change anything about the checksum, read page 1-2-20 and
not page 1-2-9.**

## Every gate, in the order to run them

```bash
export PYTHONPATH=.:snes-mapper-python
ruff format --check .                                  # formatting
ruff check .                                           # lint, zero warnings
mypy                                                   # types, strict
pnpm run format:check                                  # every JSON file
for f in romimage/*.test.py conformance/*.test.py; do python3 "$f"; done
python3 -m coverage report                             # fails below 100%
python3 conformance/census.py <library> conformance/corpus.json
```

`PYTHONPATH` matters. `mapper` is a submodule on the path, not an installed
package, and nothing here works without it. CI sets the same value.

Coverage is collected by running each test file under `coverage run -a`, not by a
test runner. All of it is 100% of statements and branches, enforced.

## The census measures two different kinds of thing

Four **properties** must hold on every image, whatever it is, and a failure is a
defect: the value and its complement are complements, recomputing over the output
returns what was written, nothing outside a header moved, a second rewrite
changes nothing.

One **observation** is measured and reported without gating the verdict: whether
the checksum this package computes is the one the cartridge already carries.

The split is not bookkeeping. All four properties are internal, and a checksum
rule that was wrong the same way every time passed every one of them for as long
as it existed. The observation is the only check that asks the artefact instead
of asking the code whether it agrees with itself, and it is the one that caught
it.

It is an observation rather than a property because a hack that changed content
without recomputing its checksum is not a defect here, and a library of several
thousand contains a great many of those. Over the whole library it holds on about
sixty three percent; over the licensed retail regions alone it holds on 2,768 of
2,780. **Those are two different populations and reporting one number for both
would be misleading.**

## Things that will bite you

**A quarter of the retail library is not a power of two.** Any change to
`mirrored_sum` has to be checked against a real library, not against a synthetic
image, because a synthetic one is whatever length you made it.

**The four checksum bytes are written, not added afterwards.** Setting them to
`FF FF 00 00` and summing is not the same as zeroing them and adding `0x01FE` per
header, because on a short image the tail is counted more than once and a
constant added once is wrong. That equivalence is why the old code looked correct.

**Every mirror gets the neutral bytes, not just the first.** A cartridge carries
up to thirty two copies of its header and all of them are inside the region being
summed.

**The checksum is computed over the mirrors already found**, not over the mirrors
of the half-written image. A header with its coprocessor byte cleared and its size
byte corrected is momentarily less recognisable as a header than it was, and
re-deriving the mirrors from that intermediate finds none of them.

**Finding the header is not this package's job.** `mapper` decides, by scoring
four independent signals against the same library. An earlier version of this
package kept its own list of plausible mapping bytes and disagreed with reality on
six hundred cartridges.

## What is deliberately not here

- **No ROM, no fragment of one, no digest fine enough to reconstruct one.** The
  library is somebody's disk and stays there. The corpus records counts and
  declared bytes, never content.
- **No fetch at runtime.** Any file this package reads is one already on the
  machine because somebody put it there.

## Conventions

| Thing | Rule |
|:------|:-----|
| Language | Python only |
| Comments | None in source. Docstrings carry the reasoning, and say why rather than what |
| Test layout | `<module>.test.py` beside the module it covers |
| Test structure | Arrange, blank line, one act, blank line, assert. No section labels |
| Package manager for tooling | pnpm, never npm |
| Commits | Conventional Commits |
| Only retail dumps | A hack is somebody's edit. It is fine as a census subject and it is not evidence about what a cartridge is |
