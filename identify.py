import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


romtools = _load("romtools")
header = _load("header")

MANIFEST = json.loads((ROOT / "artifacts.manifest.json").read_text())


def match_digest(digest):
    for artifact in MANIFEST["artifacts"]:
        for accepted in artifact["accepted"]:
            if accepted["sha256"] == digest:
                return {"state": "known", "artifact": artifact, "accepted": accepted}
        if artifact["repaired"]["sha256"] == digest:
            return {"state": "repaired", "artifact": artifact}
    return {"state": "unknown"}


def match_size(size):
    return [
        artifact
        for artifact in MANIFEST["artifacts"]
        for accepted in artifact["accepted"]
        if accepted["size"] == size
    ]


def diagnose(data):
    form = "copier header" if romtools.has_copier_header(data) else "bare"
    bare = romtools.strip_header(data)
    identity = romtools.identity(bare)
    found = match_digest(identity["sha256"])
    return {
        "form": form,
        "size": len(bare),
        "identity": identity,
        "state": found["state"],
        "artifact": found.get("artifact"),
        "same_size": [artifact["name"] for artifact in match_size(len(bare))],
        "headers": header.read(bare),
    }


def explain(found):
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
    if found["state"] == "known":
        lines.append(f"  known   {found['artifact']['name']}")
    elif found["state"] == "repaired":
        lines.append(f"  already repaired: {found['artifact']['name']}")
    elif found["same_size"]:
        lines.append(f"  size matches {', '.join(found['same_size'])}, contents do not")
        lines.append("  a different build, a different patch, or a damaged copy")
    else:
        lines.append("  not a file this manifest knows")
    return "\n".join(lines)


def main(argv):
    if len(argv) != 2:
        print("usage: identify.py <image>")
        return 2
    print(explain(diagnose(Path(argv[1]).read_bytes())))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))
