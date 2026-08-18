"""A SNES cartridge image as a file, rather than as an address space.

    from romimage import dump, identity, rewrite

    image = dump.read("game.smc")
    identity.measure(image)["sha256"]
    rewrite.declare_rom_only(image)

Four questions, in the order they have to be asked. What did the dumping device
add or split off, and how do we get back to the bytes the console saw. What makes
this file itself, and which of those values is allowed to decide. What does the
cartridge say about itself, and how is that changed without breaking the checksum
that covers it. And when a reader supplies the wrong file, which of the several
reasons it could be wrong is it.

None of that is a memory map. Where an address lands is `mapper`, which this
package depends on for finding a header, because finding one and rewriting one
must never disagree about where to look.
"""

from . import dump, identity, manifest, rewrite
from .dump import NoParts
from .identity import AUTHORITATIVE, NoAuthority
from .manifest import Malformed, Manifest
from .rewrite import CHIPSET_ROM_ONLY, COPROCESSORS, declare_rom_only, needs_rewrite
from .version import VERSION

__version__ = VERSION

__all__ = [
    "AUTHORITATIVE",
    "CHIPSET_ROM_ONLY",
    "COPROCESSORS",
    "Malformed",
    "Manifest",
    "NoAuthority",
    "NoParts",
    "__version__",
    "declare_rom_only",
    "dump",
    "identity",
    "manifest",
    "needs_rewrite",
    "rewrite",
]
