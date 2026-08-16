<div align="center">

<strong>A SNES image with the coprocessor removed still says it needs one. This corrects the cartridge header, and proves which image it corrected.</strong>

<br>
<br>

[![ci](https://github.com/gufranco/snes-nochip-header/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-nochip-header/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/gufranco/snes-nochip-header?sort=semver)](https://github.com/gufranco/snes-nochip-header/releases)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

**4** modules · **70** tests · **18** coprocessor values recognised · **12** bytes changed on a 96 Mbit image · **zero** dependencies

---

```console
$ python3 fix.py star-ocean-jp-nochip-96mbit.sfc fixed.sfc
star-ocean-jp-nochip-96mbit.sfc
  size    12,582,912 bytes, read as bare
  crc32   4DBE75BE
  sha256  e5ba9bef71c8ea31ce9650b90a60245c3434ff679475f847903011bf69e6d338
  header at 0x007fc0  'Star Ocean'  map 32  chipset 45 (S-DD1)  size 0D
  header at 0xa07fc0  'Star Ocean'  map 32  chipset 45 (S-DD1)  size 0D
  known   Star Ocean, Japanese, S-DD1 removed, 96 Mbit

fixed.sfc
  size    12,582,912 bytes, read as bare
  crc32   4CDE067C
  sha256  37131fc112149dc7946c229ade1e226aebc4e2749edf7cf9470bff6952760924
  header at 0x007fc0  'Star Ocean'  map 32  chipset 00 (none)  size 0E
  header at 0xa07fc0  'Star Ocean'  map 32  chipset 00 (none)  size 0E
  already repaired: Star Ocean, Japanese, S-DD1 removed, 96 Mbit
  12 bytes changed, all inside the cartridge headers
```

## The problem

Several SNES games shipped with a coprocessor on the cartridge. Star Ocean carries an S-DD1, which decompresses graphics on the fly, and no flash cart or copier without that chip can run the game as it stands. The community answer is to decompress the graphics ahead of time and expand the image, which works: the chip is no longer needed.

What those expanded images do not do is say so. Byte `$16` of the cartridge header still declares `0x45`, the S-DD1, and byte `$17` still declares the size the image used to be. Emulators and flash carts read that header to decide what hardware to present. Being told to enable a chip that is not there, for an image that is a third larger than advertised, is a lie the loader has no way to detect.

## What it changes

Twelve bytes on a 96 Mbit image, all of them inside a cartridge header. Nothing else in the file is touched, and a test asserts exactly that.

| Field | Offset | Before | After | Why |
|:------|:-------|:-------|:------|:----|
| Chipset | `$16` | `0x45`, S-DD1 | `0x00`, ROM only | The chip was removed; the header should agree |
| ROM size | `$17` | `0x0D`, 8 MB | `0x0E`, 16 MB | The rounded-up power of two that covers 12 MB |
| Checksum | `$1E` | stale | recomputed | Every header copy carries the same new pair |
| Complement | `$1C` | stale | recomputed | `checksum ^ 0xFFFF`, verified by a test |

Both header copies get the change. Star Ocean's 96 Mbit build carries one at `$007FC0` and a mirror at `$A07FC0`, and repairing only the first leaves a loader free to read the other.

## Identity, not guesswork

A header repair is only safe on an image that is what you think it is, so the tool identifies before it writes. [`artifacts.manifest.json`](artifacts.manifest.json) records, for each known image, the exact size, CRC32 and SHA-256 before the repair and the SHA-256 it must reach after.

| Value | Job | Decides accept or reject |
|:------|:----|:------------------------:|
| Size | Rejects the wrong file for one `stat` | No |
| CRC32 | Cross-reference against community databases | No |
| SHA-256 | The accept or reject decision | Yes |

The manifest also names the canonical form the digests describe, which matters more than it sounds: the same bytes appear as a bare file, as a file with a 512 byte copier header, and as a twelve part Game Doctor set. All three are the same image and only one of them hashes to the recorded value. [`romtools.py`](romtools.py) strips and joins so the comparison happens on the canonical form.

When a digest is not recognised, the tool says which case it is rather than printing a mismatch and stopping: already repaired, right size and different contents, or nothing this manifest knows.

## Quick start

### Prerequisites

| Tool | Version | Install |
|:-----|:--------|:--------|
| Python | 3.12 or newer | [python.org](https://www.python.org/downloads/) |

Nothing else. No packages, no virtual environment.

### Inspect an image without changing it

```bash
python3 fix.py "Star Ocean (J) no S-DD1 96Mbit.sfc"
```

### Repair it

```bash
python3 fix.py "Star Ocean (J) no S-DD1 96Mbit.sfc" star-ocean-fixed.sfc
```

### Or point it at a split set

```bash
python3 fix.py "Star Ocean (English DeJap) [no S-DD1 96Mbit]" star-ocean-en-fixed.sfc
```

Give it a folder and it joins the numbered parts in name order, taking the copier header off the first
one only, then works on the result. A twelve floppy Game Doctor set and the single file it was split
from are the same image, and both reach the same digest.

### Verify what you got

```bash
python3 identify.py star-ocean-fixed.sfc
```

The last line reads `already repaired`, with the name of the image it matched. That is the whole verification: the output's digest is one the manifest predicted in advance, not one computed after the fact from whatever the tool happened to produce.

## Modules

| Module | Does |
|:-------|:-----|
| [`fix.py`](fix.py) | The command. Identifies, reports, repairs, and reports again |
| [`header.py`](header.py) | Finds every cartridge header, reads the fields, rewrites the chipset, size and checksum |
| [`identify.py`](identify.py) | Matches a digest against the manifest and explains what was found |
| [`romtools.py`](romtools.py) | Reads a file or a folder of parts, strips copier headers, and measures size, CRC32 and SHA-256 |

## What it will not do

This project ships no game data and will not help you obtain any. It reads an image you already have and writes a corrected copy beside it. The manifest carries whole-file digests, which identify an image and reconstruct nothing.

It also refuses work that would be a lie. A retail cartridge that still needs its chip has a correct header already; the manifest lists that case explicitly so the tool can say why it is leaving it alone.

## Running the tests

```bash
for module in *.test.py; do python3 "$module"; done
```

Seventy tests, no network, no fixtures larger than a synthetic 1 MB image built in memory.

Three of them are acceptance tests against a real image and skip unless you point them at one:

```bash
NOCHIP_IMAGE=/path/to/your/image.sfc python3 fix.test.py
```

Those assert what the unit tests cannot: that the manifest recognises a real file, that repairing it reaches the digest recorded in advance, and that every changed byte lands inside a header.

## Project conventions

| Convention | Source |
|:-----------|:-------|
| Commit format | [Conventional Commits](https://www.conventionalcommits.org/) |
| Releases | [semantic-release](https://semantic-release.gitbook.io/) on merge to `main`, configured in [`.releaserc.json`](.releaserc.json) |
| Lint and format | [ruff](https://docs.astral.sh/ruff/), configured in [`pyproject.toml`](pyproject.toml) |
| Tests | One `<module>.test.py` beside every module, run on Ubuntu and macOS by [`ci.yml`](.github/workflows/ci.yml) |

## Versioning

[Semantic Versioning](https://semver.org/), tagged on every release. The current version lives in [`version.py`](version.py) and is set by the release pipeline, never by hand. See [releases](https://github.com/gufranco/snes-nochip-header/releases).

## License

[MIT](LICENSE)
