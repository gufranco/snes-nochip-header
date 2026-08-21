"""Telling a reader which file to supply, and why the one they supplied is wrong.

A project that needs a cartridge it cannot ship has one obligation to the person
who owns one: publish enough identity for them to confirm their copy is the right
one, and verify it in code before reading a byte. Both halves matter. A digest
printed in a readme that nothing checks is decoration, and a check that reports
only "digest mismatch" tells the reader nothing they can act on.

So a mismatch is a diagnosis rather than a rejection. A file can miss for reasons
that are entirely the reader's to fix and entirely invisible from a digest: a
copier stub still attached, a split set not joined, a dump already known to be
damaged, a different regional revision, or the right size with altered content.
Each of those has a different next step, and naming which one it is turns a dead
end into an instruction.

The manifest carries facts about physical objects: sizes, digests, and the form
those digests describe. It carries no content, and nothing here reads a byte
outside the file it was handed. That is the line this module is built along:
publish behaviour and identity, never the work itself.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import dump, identity, rewrite

KNOWN = "known"
REWRITTEN = "rewritten"
BAD_DUMP = "bad dump"
SAME_SIZE = "same size"
UNKNOWN = "unknown"


class Malformed(Exception):
    pass


def _checked(document: Mapping[str, Any]) -> Mapping[str, Any]:
    artifacts = document.get("artifacts")
    if not artifacts:
        raise Malformed("a manifest with no artifacts cannot accept or reject anything")
    for artifact in artifacts:
        accepted = artifact.get("accepted")
        if not accepted:
            raise Malformed(f"{artifact.get('name', 'an artifact')} lists no accepted form")
        for form in accepted:
            if identity.AUTHORITATIVE not in form:
                raise Malformed(
                    f"{artifact.get('name', 'an artifact')} has an accepted form with no "
                    f"{identity.AUTHORITATIVE}, which is the only value that decides"
                )
    return document


class Manifest:
    """The artefacts a project expects, and what it can say about a miss."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        self.document = _checked(document)

    @classmethod
    def from_path(cls, path: Path | str) -> "Manifest":
        return cls(json.loads(Path(path).read_text()))

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        held: tuple[Mapping[str, Any], ...] = tuple(self.document["artifacts"])
        return held

    def by_digest(self, found: Mapping[str, Any]) -> Mapping[str, Any] | None:
        """Which artefact a measurement is, and in which of its forms."""
        for artifact in self.artifacts:
            for accepted in artifact["accepted"]:
                if identity.agrees(found, accepted):
                    return {"state": KNOWN, "artifact": artifact}
            written = artifact.get("rewritten")
            if written and identity.agrees(found, written):
                return {"state": REWRITTEN, "artifact": artifact}
            for bad in artifact.get("bad", ()):
                if identity.agrees(found, bad):
                    return {"state": BAD_DUMP, "artifact": artifact, "why": bad.get("why")}
        return None

    def by_size(self, size: int) -> tuple[Mapping[str, Any], ...]:
        """Every artefact that expects a file of exactly this length."""
        return tuple(
            artifact
            for artifact in self.artifacts
            for accepted in artifact["accepted"]
            if accepted.get("size") == size
        )

    def diagnose(self, data: bytes, form: str | None = None) -> Mapping[str, Any]:
        """What this file is, and when it is not what was wanted, what went wrong.

        The stub comes off first, because a dump that carries one is the right
        cartridge in the wrong form, which is a different problem from the wrong
        cartridge and has a different fix.
        """
        held = dump.strip_copier_stub(data)
        found = identity.measure(held)
        matched = self.by_digest(found)
        same_size = [artifact["name"] for artifact in self.by_size(len(held))]

        return {
            "form": form or (dump.COPIER if len(held) != len(data) else dump.BARE),
            "size": len(held),
            "identity": found,
            "state": matched["state"] if matched else (SAME_SIZE if same_size else UNKNOWN),
            "artifact": matched["artifact"] if matched else None,
            "why": matched.get("why") if matched else None,
            "same_size": same_size,
            "headers": rewrite.describe(held),
        }

    def explain(self, found: Mapping[str, Any]) -> str:
        """The diagnosis as a reader reads it, with what to do about it."""
        lines = [
            f"  size    {found['size']:,} bytes, read as {found['form']}",
            f"  crc32   {found['identity']['crc32']}",
            f"  sha256  {found['identity']['sha256']}",
        ]
        for entry in found["headers"]:
            declared = entry["coprocessor"] or "none"
            lines.append(
                f"  header at {entry['at']:#08x}  {entry['title']!r}  map {entry['map']:02X}  "
                f"chipset {entry['chipset']:02X} ({declared})  size {entry['size']:02X}"
            )

        if found["state"] == KNOWN:
            lines.append(f"  known   {found['artifact']['name']}")
        elif found["state"] == REWRITTEN:
            lines.append(f"  already rewritten: {found['artifact']['name']}")
        elif found["state"] == BAD_DUMP:
            lines.append(f"  a known bad dump of {found['artifact']['name']}: {found['why']}")
            lines.append("  find another copy; this one cannot be repaired from itself")
        elif found["state"] == SAME_SIZE:
            lines.append(f"  size matches {', '.join(found['same_size'])}, contents do not")
            lines.append("  a different build, a different revision, or a damaged copy")
        else:
            lines.append("  not a file this manifest knows")
        return "\n".join(lines)
