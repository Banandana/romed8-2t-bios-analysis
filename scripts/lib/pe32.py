"""PE32 utilities: hashing, string extraction, basic byte-pattern search.

For full disassembly, drive radare2 directly via subprocess; this module
provides the cheap operations that don't need r2."""
import hashlib
import re
import subprocess
from pathlib import Path
from typing import List, Iterable


def sha256_short(path: Path, n: int = 12) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 16):
            h.update(chunk)
    return h.hexdigest()[:n]


def sha256_full(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 16):
            h.update(chunk)
    return h.hexdigest()


def extract_strings(path: Path, min_len: int = 6) -> List[str]:
    """Return all printable ASCII strings of length >= min_len."""
    out = subprocess.run(
        ["strings", "-n", str(min_len), str(path)],
        capture_output=True, text=True, check=False
    )
    return out.stdout.splitlines()


def grep_strings(path: Path, pattern: str, min_len: int = 6, case_insensitive: bool = True) -> List[str]:
    """Return strings matching a regex pattern."""
    flags = re.IGNORECASE if case_insensitive else 0
    rgx = re.compile(pattern, flags)
    return [s for s in extract_strings(path, min_len) if rgx.search(s)]


def find_byte_pattern(path: Path, pattern: bytes) -> List[int]:
    """Return all offsets where the byte pattern occurs in the file."""
    data = open(path, "rb").read()
    out = []
    start = 0
    while True:
        i = data.find(pattern, start)
        if i < 0:
            break
        out.append(i)
        start = i + 1
    return out


def r2_run(path: Path, commands: Iterable[str], analyze: bool = True, timeout: int = 120) -> str:
    """Drive r2 in batch mode, return concatenated output."""
    args = ["r2", "-q"]
    if analyze:
        args.append("-A")
    args.append(str(path))
    cmd_str = "; ".join(commands)
    result = subprocess.run(
        args + ["-c", cmd_str],
        capture_output=True, text=True, timeout=timeout, check=False
    )
    return result.stdout
