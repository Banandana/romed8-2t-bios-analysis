"""FFS dump tree navigation — find PE32 module body.bin files in UEFIExtract output."""
from pathlib import Path
from typing import Iterator, Optional, List, Tuple

from .versions import dump_root


def iter_pe32_bodies(version: str, min_size: int = 0,
                     include_te: bool = False) -> Iterator[Tuple[str, Path]]:
    """Yield (module_name, body_path) for every PE32 image section in the active
    volume of the given BIOS version.

    With ``include_te=True``, also yields TE (Terse Executable) sections — the
    PEI-phase analogue of PE32 used by AGESA PEIMs and other early-boot drivers.

    Module name is the directory name minus the leading FFS index, e.g.
    "37 AmdNbioPcieDxe" -> "AmdNbioPcieDxe".
    """
    root = dump_root(version)
    if not root.exists():
        return
    for body in root.rglob("body.bin"):
        s = str(body)
        is_pe = "PE32 image section" in s
        is_te = "TE image section" in s
        if not (is_pe or (include_te and is_te)):
            continue
        try:
            if body.stat().st_size < min_size:
                continue
        except OSError:
            continue
        # parent = "1 PE32 image section" (or "1 TE image section"),
        # grandparent = "<idx> <module name>"
        gp = body.parent.parent.name
        name = gp.split(" ", 1)[-1] if " " in gp else gp
        yield name, body


def find_module_body(version: str, module_name: str, min_size: int = 4096) -> Optional[Path]:
    """Find the PE32 body.bin for a named module. Returns the largest match
    (the active-volume copy, not header/recovery shards)."""
    candidates = []
    for name, body in iter_pe32_bodies(version, min_size=min_size):
        if name == module_name:
            try:
                candidates.append((body.stat().st_size, body))
            except OSError:
                pass
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def list_modules(version: str, min_size: int = 4096) -> List[Tuple[str, int]]:
    """Return [(module_name, size_bytes), ...] for all PE32 modules, sorted by name."""
    seen = {}
    for name, body in iter_pe32_bodies(version, min_size=min_size):
        try:
            size = body.stat().st_size
        except OSError:
            continue
        # Keep largest if duplicates (active volume vs recovery)
        if name not in seen or size > seen[name]:
            seen[name] = size
    return sorted(seen.items())
