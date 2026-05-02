"""Path conventions for BIOS versions on disk.

A BIOS "version" is a string like "3.70", "3.80", "L3.11" matching the
filename suffix of `images/ROMD82T<version>`.

Layout (relative to PROJECT_ROOT):
    images/ROMD82T<version>                   raw BIOS image
    extracted/all/P<version>/img.bin.dump/    UEFIExtract dump tree
    ifr/P<version>/_all/                      flat dir of IFR text files
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ALL_VERSIONS = ["3.11", "3.70", "3.80", "3.90", "4.10"]


def image_path(version: str) -> Path:
    return PROJECT_ROOT / "images" / f"ROMD82T{version}"


def dump_root(version: str) -> Path:
    return PROJECT_ROOT / "extracted" / "all" / f"P{version}" / "img.bin.dump"


def ifr_dir(version: str) -> Path:
    """Per-version IFR text directory (flat, deduped)."""
    return PROJECT_ROOT / "ifr" / f"P{version}" / "_all"


def docs_dir() -> Path:
    return PROJECT_ROOT / "docs"


def label(version: str) -> str:
    """Human-readable version label, e.g. P3.70 / L3.11."""
    return f"L{version}" if version.startswith("L") else f"P{version}"
