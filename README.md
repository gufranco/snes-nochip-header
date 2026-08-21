<div align="center">

<h1>SNES ROM Image</h1>

<strong>A cartridge image as a file: what the dumper added, what it says about itself, and how to change that.</strong>

<br>
<br>

[![CI](https://github.com/gufranco/snes-rom-image-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-rom-image-python/actions/workflows/ci.yml)
[![Corpus](https://img.shields.io/badge/corpus-489%20%2F%20489-brightgreen)](#the-corpus-and-why-it-can-ship)
[![Cartridges](https://img.shields.io/badge/measured%20across-7%2C317%20cartridges-blue)](#what-a-real-library-actually-contains)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20statement%20%2B%20branch-brightgreen)](#tests)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

<p align="center">
  <a href="#quick-start">Quick start</a> &nbsp;|&nbsp;
  <a href="#the-mistakes-this-exists-to-stop">The mistakes</a> &nbsp;|&nbsp;
  <a href="#the-corpus-and-why-it-can-ship">Why the corpus is legal</a> &nbsp;|&nbsp;
  <a href="#what-a-real-library-actually-contains">What a library contains</a> &nbsp;|&nbsp;
  <a href="https://github.com/gufranco/snes-rom-image-python/issues">Issues</a>
</p>

**489** declarations, **0** failures · **4** properties checked on every one of **7,330** cartridges · the computed checksum matches **2,768** of **2,780** retail cartridges · **219** tests · **100%** statement and branch coverage

```python
from romimage import dump, rewrite

image = dump.read("game.smc")

rewrite.declare_rom_only(image)
# every mirror of the header updated, checksum recomputed over the result
```

---

## The problem

A file on disk is not a cartridge image, and the difference is invisible.

A copier writes 512 bytes in front of the image describing what it just read, shifting every offset in the file by an amount that appears nowhere in the file. A backup unit splits the image across numbered files, of which only the first carries that stub. A cartridge repeats its header in several places, and tools disagree about which copy they read.

Each of those is silent. A patch written at a known address into a dump with a stub still attached lands 512 bytes early, in the middle of something else, and the build succeeds. A header rewritten in one mirror produces an image that works in the tool it was tested in and not on the machine it was built for.

## The solution

Answer the four questions in the order they have to be asked, and check the answers against a real library.

| Module | Question |
|:-------|:---------|
| [`dump`](romimage/dump.py) | What did the dumping device add or split off |
| [`identity`](romimage/identity.py) | What makes this file itself, and which value decides |
| [`rewrite`](romimage/rewrite.py) | What does the cartridge say, and how is that changed safely |
| [`manifest`](romimage/manifest.py) | When a reader supplies the wrong file, which wrong is it |

Finding a header is not this package's job. [`snes-mapper`](https://github.com/gufranco/snes-mapper-python) does that, measured against the same library, and this depends on it rather than carrying a second opinion. An earlier version did carry one, and the library disagreed with it on **0** cartridges before the two were made to share an answer.

<table>
<tr>
<td width="50%" valign="top">

### Every mirror, not the first

A header repeats across the image. Updating one copy is the bug that only appears on hardware.

</td>
<td width="50%" valign="top">

### The checksum covers itself

The four bytes holding it count as `FF FF 00 00` whatever they hold. Nothing else resolves the circularity.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### One value decides

SHA-256 accepts or rejects. CRC32, MD5 and SHA-1 are published to look up, never to decide.

</td>
<td width="50%" valign="top">

### A miss is a diagnosis

Stub attached, set not joined, known bad dump, right size and wrong content. Each has a different fix.

</td>
</tr>
</table>

## Quick start

### Prerequisites

| Tool | Version | Install |
|:-----|:--------|:--------|
| Python | >= 3.12 | [python.org](https://www.python.org/downloads/) |

### Setup

```bash
git clone --recurse-submodules https://github.com/gufranco/snes-rom-image-python.git
cd snes-rom-image-python
export PYTHONPATH=".:snes-mapper-python"
```

The header reader is a submodule rather than a copied file, which is the whole point: this package rewrites headers and that one finds them, and a second copy of those offsets is a second thing to keep true.

### Verify

```bash
python3 conformance/corpus.py
#   489 declarations from corpus.json
#   measured across 7330 cartridges
#   489 agreed, 0 did not
```

## The mistakes this exists to stop

### A copier stub shifts every offset in the file

```python
from romimage import dump

len(dump.read("game.smc")) - len(open("game.smc", "rb").read())
# -512, and a patch applied without this lands in the wrong place
```

Detected by length rather than content, because the stub's content is not standardised. The same test decides where a header reader looks, so it is imported from that package rather than restated.

### A split set is one cartridge in several files

```python
dump.read("game-parts/")
# the parts joined in name order, with the stub off only the first
```

The sort is case-insensitive, because the device wrote the names in upper case and half the world has renamed them since.

### The header is mirrored, and one copy is not enough

```python
from romimage import rewrite

rewrite.mirrors(image)
# [0x7FC0, 0x87FC0, 0x107FC0], and all of them have to change
```

A mirror exists because the same bank is visible at more than one address, so every copy is byte-identical to the first. That makes the search exact, and a run of text that merely resembles a title cannot match.

### The checksum covers the bytes that store it

```python
rewrite.checksum(rewrite.declare_rom_only(image)) == written_value
# True, because the four checksum bytes count as FF FF 00 00
```

The sum is taken over the whole image including the fields holding the result, which cannot be known before the sum. Nintendo's instruction resolves it by naming what those four bytes count as: "First, store 0FFH into the complement check area (FFDCH, FFDDH) and 00H into the check sum area (FFDEH, FFDFH). Then add each byte in the ROM data." Every mirror gets them, not only the first.

### A cartridge shorter than a power of two counts its tail more than once

```python
rewrite.mirrored_sum(twelve_megabit)
# the first eight megabit once, the last four twice
```

Nintendo: "If ROM size cannot be expressed evenly in 2nM bit, such as 10M or 20M bit, add the remainder until a total of 2nM bit is reached." A remainder that is not itself a power of two folds the same way before it repeats.

A quarter of the retail library is built this way, and summing every byte once is wrong on almost all of it. That is not a rounding difference: it is the wrong number, and it is why this rule is checked against the cartridges rather than against itself.

### A rewrite in progress is not a cartridge

```python
rewrite.checksum(half_written, places)
# the mirrors already found, not the mirrors of a half-written header
```

Clearing the coprocessor byte and correcting the size costs a header two of the four signals a reader scores it on, so for the moment before the new checksum is written it is less recognisable than it was. Re-deriving the mirrors from that intermediate finds none of them, and the sum comes out short by exactly one header's worth of the convention.

### The size byte is an exponent

```python
rewrite.size_byte(0x400000)
# 12, not 4096 and not 4
```

An image that grew past a power of two and kept its old byte declares itself smaller than it is, and a machine that trusts the declaration never reads the rest.

### One digest decides, and the others are for looking up

```python
from romimage import identity

identity.AUTHORITATIVE
# 'sha256'
```

CRC32 is a 32-bit error code. MD5 and SHA-1 are collision-broken. All three are published so a reader can find their copy in a database that still indexes by them, and none of them is allowed to accept a file.

## Where the facts come from

Two sources, in order, and they are not the same kind of thing.

**Nintendo's SNES Development Manual, Book 1** decides what each byte of the header means, what its values are, and how the checksum is calculated. [`conformance/hardware.json`](conformance/hardware.json) pins it fact by fact, each with the sentence it came from and the page it is on, and [`conformance/hardware.test.py`](conformance/hardware.test.py) holds this package's constants to it, so a citation here is a test that can fail rather than a claim in prose.

**A retail cartridge** decides everything the manual does not. The manual is an instruction issued to licensees rather than a description of silicon, so a genuine cartridge can disagree with it and still be genuine. Where one does, the cartridge is the fact.

Nothing else is evidence. No emulator, no wiki, no other implementation of this same job.

> [!WARNING]
> The manual describes two different things called a check sum, and only one of them is in the header. Page 1-2-9 gives a plain sum for the submission sheet, and says outright that it "is different from the check sum on the ROM Registration Specification". Page 1-2-20 gives the real one. Reading the first is how this package summed every byte once for as long as it did.

[`conformance/divergences.json`](conformance/divergences.json) records every place the two sources part company, what this package follows, and what evidence would settle it.

## What a real library actually contains

Measured across **7,330** cartridges, with 249 refused for carrying no readable header:

| Measurement | Value |
|:------------|------:|
| Distinct declarations | 489 |
| Distinct image sizes | 108 |
| Distinct chipset bytes | 36 |
| Cartridges that would need rewriting | 3,799 |
| Disagreements with the header reader | 0 |

Four properties were checked on every cartridge, not on a sample:

| Property | Held on |
|:---------|--------:|
| The written checksum and its complement are complements | 7,330 of 7,330 |
| Recomputing over the result returns the written value | 7,330 of 7,330 |
| Nothing outside a header changed | 7,330 of 7,330 |
| A second rewrite changes nothing | 7,330 of 7,330 |

Every one of those four failed on some cartridge at some point in getting here, and each failure was a defect rather than a strange cartridge. A bootleg with a blank title. A public-domain demo too small for the size band a reader scores against. Neither would have been found by reasoning about the code.

One more thing is measured and reported without deciding anything: whether the checksum this package computes is the one already written on the cartridge.

| Population | Agrees |
|:-----------|-------:|
| Licensed retail cartridges | 2,768 of 2,780 |
| Every image with a self-consistent header, hacks included | 4,502 of 7,167 |

Those are two different populations and one number for both would be misleading. A hack that changed content without recomputing is not a defect here, which is why this is reported rather than enforced.

It is also the only one of the five that asks the cartridge rather than asking the code whether it agrees with itself, and it is the one that caught a checksum rule wrong on 630 of the 633 short retail cartridges it had been run over. The other four had held on all 7,330 the whole time. [`conformance/divergences.json`](conformance/divergences.json) names the twelve retail cartridges that still disagree and what is known about each.

> [!NOTE]
> A file with no readable header is counted as refused rather than guessed at. Prototypes and unfinished dumps often carry a blank one, and inventing a header for them would put fiction into a corpus of facts.

## The corpus, and why it can ship

A header is thirty two bytes in which a cartridge describes how it is built.

| Field | What it is | Ships? |
|:------|:-----------|:-------|
| Size, mapping, chipset, ROM and RAM size | Facts about a physical object | Yes |
| Counts of how many cartridges share a combination | A measurement | Yes |
| The title | A name rather than a measurement | No |
| Anything outside the header | The game | Never read |

Facts and functional elements sit outside what copyright reaches, per [17 U.S.C. 102(b)](https://www.law.cornell.edu/uscode/text/17/102) and `Feist`. [`conformance/census.py`](conformance/census.py) records no title, and nothing in [`conformance/corpus.json`](conformance/corpus.json) could rebuild any part of any cartridge.

Two claims replay from the corpus alone, which is what makes it worth shipping. The size exponent must be the one the model derives from the size. And a cartridge declaring a coprocessor, or declaring a size that is not its own, must be one the model says needs rewriting.

That second claim runs one way only, deliberately. A cartridge whose first header looks clean can still need a rewrite because a later mirror disagrees with it, and the corpus records the first. So a claim of "needs rewriting" is always allowed; a claim of "needs nothing" is checked.

The four properties above need the cartridges, so they run in the census rather than in CI, and their counts travel with the corpus as a record of what was measured.

> [!IMPORTANT]
> This is how the repository is built, not legal advice. The rule it follows: publish behaviour and identity, never the work itself.

### Taking a census of your own library

```bash
python3 conformance/census.py "/path/to/roms" census.json
python3 conformance/census.py library.zip census.json
```

An archive is read member by member rather than unpacked, because a census does not need a second copy of the library on disk.

## Project structure

```
romimage/
  __init__.py     the package
  dump.py         copier stubs, split sets, and survey statistics
  identity.py     size and digests, and which one decides
  rewrite.py      declaring no coprocessor, and the checksum that follows
  manifest.py     matching a supplied file, and diagnosing a miss
  version.py      rewritten by the release job and by nothing else
conformance/
  census.py       walks a library you own and checks the rewrite on all of it
  corpus.py       replays every declaration the library contained
  corpus.json     489 declarations covering 7,330 cartridges
  hardware.json   Nintendo's specification, pinned fact by fact
  hardware.test.py  this package's constants against those facts
  divergences.json  every place a real cartridge and the specification part company
packages/
  snes-mapper     the header reader, pinned rather than copied
```

## Tests

```bash
export PYTHONPATH=".:snes-mapper-python"
for f in romimage/*.test.py conformance/*.test.py; do python3 "$f"; done
```

| Suite | File | Covers |
|:------|:-----|:-------|
| Dump | [`romimage/dump.test.py`](romimage/dump.test.py) | Copier stubs, split sets, forms, compression ratios, reuse |
| Identity | [`romimage/identity.test.py`](romimage/identity.test.py) | The five values, and that only one of them decides |
| Rewrite | [`romimage/rewrite.test.py`](romimage/rewrite.test.py) | Mirrors, checksum convention, size exponent, confinement, idempotence |
| Manifest | [`romimage/manifest.test.py`](romimage/manifest.test.py) | Every diagnosis, and what each one tells the reader to do |
| Census | [`conformance/census.test.py`](conformance/census.test.py) | Folders, archives, tallies, the four properties, and the observation |
| Corpus | [`conformance/corpus.test.py`](conformance/corpus.test.py) | The whole shipped set, replayed |
| Specification | [`conformance/hardware.test.py`](conformance/hardware.test.py) | Every field offset, value, and checksum rule against the figures Nintendo printed |

Coverage is enforced at 100% of statements and branches by [`pyproject.toml`](pyproject.toml).

## Development

| Command | Description |
|:--------|:------------|
| `ruff format .` | Format |
| `ruff check .` | Lint |
| `python3 -m coverage report` | Coverage, which fails below 100% |
| `python3 conformance/corpus.py` | Replay the shipped corpus |
| `python3 conformance/census.py <library> <out>` | Census a library you own |

## Versioning

This project follows [Semantic Versioning](https://semver.org/), and every release is tagged from `main` by semantic-release. See [releases](https://github.com/gufranco/snes-rom-image-python/releases).

## FAQ

<details>
<summary><strong>Why does this depend on another package just to find a header?</strong></summary>
<br>

Because finding one and rewriting one must never disagree about where to look. The offsets, the scoring and the copier-stub rule are one piece of knowledge, and a second copy of it is a second thing to keep true. When this package did carry its own copy, a real library disagreed with it on 0 cartridges, including Contra III, which declares a mapping byte that appears in no table anyone has written down.

</details>

<details>
<summary><strong>Why is CRC32 published if it cannot decide?</strong></summary>
<br>

Because the databases a reader will search still index by it. Publishing it saves them a step. Letting it accept a file would be an integrity claim from a 32-bit error code, which is a different thing entirely.

</details>

<details>
<summary><strong>Why does a mismatch print a diagnosis instead of just failing?</strong></summary>
<br>

Because "digest mismatch" tells the reader nothing they can act on, and most misses are entirely theirs to fix: a stub still attached, a set not joined, a different revision. Naming which one it is turns a dead end into an instruction.

</details>

<details>
<summary><strong>Does this ship or download any cartridge?</strong></summary>
<br>

No. It reads files a reader already owns, and it publishes measurements of them. It carries no cartridge content, links to no source, and nothing in the corpus could rebuild any part of any image.

</details>

## License

[MIT](LICENSE)
