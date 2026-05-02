#!/usr/bin/env python3
"""
Cross-version PE32 module sweep across all 5 ROMED8-2T BIOSes.

Unlike `diff_versions.py` (which checks a curated list of ~30 named modules),
this walks every `body.bin` under the FFS dump trees and reports every PE32
module found. Entries are keyed by (volume-index, FFS entry-index, module-name)
so that duplicates (e.g. AmdApcbDxeV3 entry 25 in volume 20 vs entry 43 in
volume 7) appear separately.

Usage:
    python3 scripts/module_sweep.py
        Emit a markdown table of every PE32 module across all 5 versions
        with hash + raw size to stdout.

    python3 scripts/module_sweep.py 3.70 3.80
        Diff mode: list only modules that differ between two versions, with
        size delta and a column flagging modules whose name matches one of
        the priority priors (Pcie/Nbio/Dxio/Cpm/Cbs/Apcb/Oem/Asrock/Board/
        Platform/Strap/Bmc/Setup/Smm/Rs1).

    python3 scripts/module_sweep.py --highlight
        Full table across all 5 versions with the priority-flag column.

    python3 scripts/module_sweep.py --report 3.70 3.80
        Diff and emit the deep-dive markdown report
        (`docs/MODULE_SWEEP_P3.70_vs_P3.80.md`).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Make `scripts.lib` importable
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from scripts.lib.versions import ALL_VERSIONS, dump_root, label, docs_dir  # noqa: E402
from scripts.lib.pe32 import sha256_full, extract_strings  # noqa: E402

PRIORITY_PATTERNS = [
    "Pcie", "Nbio", "Dxio", "Cpm", "Cbs", "Apcb", "Oem", "Asrock",
    "Board", "Platform", "Strap", "Bmc", "Setup", "Smm", "Rs1",
]
# Tier A: directly Gen4 / DXIO-relevant. These get a higher priority
# weight so generic SMM / Setup modules don't drown out the candidates
# that actually live near the link-init code path.
TIER_A_PATTERNS = [
    "Pcie", "Nbio", "Dxio", "Cpm", "Cbs", "Apcb", "Oem", "Asrock",
    "Board", "Platform", "Strap", "Rs1",
]
# Tier B: still on the prior list but very common (Bmc/Setup/Smm hit
# dozens of unrelated drivers).
TIER_B_PATTERNS = ["Bmc", "Setup", "Smm"]

_PRIORITY_RX = re.compile("|".join(PRIORITY_PATTERNS), re.IGNORECASE)
_TIER_A_RX = re.compile("|".join(TIER_A_PATTERNS), re.IGNORECASE)
_TIER_B_RX = re.compile("|".join(TIER_B_PATTERNS), re.IGNORECASE)


def is_priority_name(name: str) -> bool:
    return bool(_PRIORITY_RX.search(name))


def name_tier(name: str) -> int:
    """Return 2 if name matches a tier-A pattern, 1 if only tier-B, 0 otherwise."""
    if _TIER_A_RX.search(name):
        return 2
    if _TIER_B_RX.search(name):
        return 1
    return 0


def parse_entry_id(dirname: str) -> Tuple[int, str]:
    """Given a dir like '37 AmdNbioPcieDxe', return (37, 'AmdNbioPcieDxe').
    For 'NN GUID' style names, the name field is the GUID itself."""
    parts = dirname.split(" ", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return int(parts[0]), parts[1]
    return -1, dirname


def is_pe32_body(path: Path) -> bool:
    """Defensive check: the body.bin must start with 'MZ' to be a real PE32."""
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


def find_phase(path_parts: List[str]) -> str:
    """Determine PEI vs DXE phase by inspecting the parent FFS GUID.
    Top-level FV under img.bin.dump:
        '7 4F1C5...' / '20 4F1C5...'  -> primary DXE FVs
        '8 61C0F...' / '21 61C0F...'  -> PEI FVs (also contain Recovery)
    """
    for p in path_parts:
        if "61C0F511-A691-4F54-974F-B9A42172CE53" in p:
            return "PEI"
        if "4F1C52D3-D824-4D2A-A2F0-EC40C23C5916" in p:
            return "DXE"
    return "?"


# Key for a module instance:
#   (top_volume_idx, module_name, instance_rank)
# instance_rank breaks ties when the same module name appears multiple times
# inside the same volume (e.g. AmdLegacyInterrupt × 2 in volume 7). Rank is
# assigned by ascending FFS entry-index across versions to be stable.
# We *don't* key by FFS entry-index directly because inserting/removing a
# single FFS entry shifts every subsequent entry index by 1, which would
# flag every module after the insertion point as 'changed'.
ModuleKey = Tuple[int, str, int]


class ModuleEntry:
    __slots__ = ("vol_idx", "entry_idx", "name", "rank", "phase",
                 "size", "sha", "path")

    def __init__(self, vol_idx: int, entry_idx: int, name: str, rank: int,
                 phase: str, size: int, sha: str, path: Path):
        self.vol_idx = vol_idx
        self.entry_idx = entry_idx
        self.name = name
        self.rank = rank
        self.phase = phase
        self.size = size
        self.sha = sha
        self.path = path

    @property
    def key(self) -> ModuleKey:
        return (self.vol_idx, self.name, self.rank)


def collect_pe32(version: str) -> Dict[ModuleKey, ModuleEntry]:
    """Walk the dump tree for one BIOS version and collect all PE32 modules.
    Keyed by (top_volume_idx, module_name, instance_rank).

    Rank distinguishes multiple instances of the same module name within
    the same volume; assigned by ascending entry-index. This keying
    scheme is invariant under FFS-entry insertions elsewhere in the
    volume (which would shift entry-indices and create false-positive
    diffs)."""
    root = dump_root(version)
    if not root.exists():
        return {}

    # First pass: collect raw rows
    raw: List[ModuleEntry] = []
    for body in root.rglob("body.bin"):
        sp = str(body)
        if "PE32 image section" not in sp:
            continue
        if not is_pe32_body(body):
            continue
        rel = body.relative_to(root)
        parts = rel.parts
        top = parts[0]
        top_idx, _ = parse_entry_id(top)
        mod_dir = parts[-3]
        ffs_idx, mod_name = parse_entry_id(mod_dir)
        phase = find_phase(list(parts))
        try:
            size = body.stat().st_size
        except OSError:
            continue
        sha = sha256_full(body)
        raw.append(ModuleEntry(top_idx, ffs_idx, mod_name, 0, phase, size, sha, body))

    # Second pass: assign rank within (vol, name) by ascending entry_idx
    raw.sort(key=lambda e: (e.vol_idx, e.name, e.entry_idx))
    out: Dict[ModuleKey, ModuleEntry] = {}
    cur_key = None
    cur_rank = 0
    for e in raw:
        vn = (e.vol_idx, e.name)
        if vn == cur_key:
            cur_rank += 1
        else:
            cur_key = vn
            cur_rank = 0
        e.rank = cur_rank
        out[e.key] = e
    return out


# --------- Reporting ---------

def fmt_label(v: str) -> str:
    return label(v)


def all_keys(per_version: Dict[str, Dict[ModuleKey, ModuleEntry]]) -> List[ModuleKey]:
    keys = set()
    for vmap in per_version.values():
        keys.update(vmap.keys())
    # Sort by volume, then entry index, then name
    return sorted(keys)


def _name_with_rank(name: str, rank: int) -> str:
    return f"{name}#{rank}" if rank > 0 else name


def render_full_table(per_version: Dict[str, Dict[ModuleKey, ModuleEntry]],
                      versions: List[str], highlight: bool = False) -> str:
    lines: List[str] = []
    header = ["Vol", "Module", "Phase"]
    if highlight:
        header.append("Pri")
    for v in versions:
        header.append(f"{fmt_label(v)} sha")
        header.append(f"{fmt_label(v)} size")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    for k in all_keys(per_version):
        vol_idx, name, rank = k
        phase = "?"
        for v in versions:
            if k in per_version[v]:
                phase = per_version[v][k].phase
                break
        row = [str(vol_idx), f"`{_name_with_rank(name, rank)}`", phase]
        if highlight:
            row.append("*" if is_priority_name(name) else "")
        for v in versions:
            e = per_version[v].get(k)
            if e is None:
                row.append("(missing)")
                row.append("-")
            else:
                row.append(f"`{e.sha[:12]}`")
                row.append(str(e.size))
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def render_diff_table(per_version: Dict[str, Dict[ModuleKey, ModuleEntry]],
                      va: str, vb: str, highlight: bool = True) -> Tuple[str, List[ModuleKey]]:
    """Two-version diff. Returns (markdown_table, list_of_changed_keys)."""
    a = per_version[va]
    b = per_version[vb]
    keys = sorted(set(a) | set(b))
    changed: List[ModuleKey] = []

    lines: List[str] = []
    header = ["Vol", "Module", "Phase"]
    if highlight:
        header.append("Pri")
    header += [f"{fmt_label(va)} sha", f"{fmt_label(va)} size",
               f"{fmt_label(vb)} sha", f"{fmt_label(vb)} size",
               "Δ size"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    for k in keys:
        ea = a.get(k)
        eb = b.get(k)
        if ea is not None and eb is not None and ea.sha == eb.sha:
            continue  # identical - skip
        if ea is None and eb is None:
            continue
        changed.append(k)
        vol_idx, name, rank = k
        phase = (ea or eb).phase
        row = [str(vol_idx), f"`{_name_with_rank(name, rank)}`", phase]
        if highlight:
            row.append("*" if is_priority_name(name) else "")
        if ea is None:
            row.append("(missing)"); row.append("-")
        else:
            row.append(f"`{ea.sha[:12]}`"); row.append(str(ea.size))
        if eb is None:
            row.append("(missing)"); row.append("-")
        else:
            row.append(f"`{eb.sha[:12]}`"); row.append(str(eb.size))
        if ea is not None and eb is not None:
            delta = eb.size - ea.size
            row.append(f"{delta:+d}")
        else:
            row.append("-")
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines), changed


# --------- Strings deep-dive (for top candidates) ---------

DEEPDIVE_NEEDLES = [
    "Gen4", "ESM", "DXIO", "Strap", "Engine", "Port",
    "Descriptor", "Synth", "Init", "Rev", "Board", "1.02", "1.03",
]


def deepdive_strings(path: Path) -> List[str]:
    """All printable strings >=6 chars."""
    return extract_strings(path, min_len=6)


def deepdive_diff(path_a: Path, path_b: Path) -> dict:
    """For two PE32s, return:
       - strings unique to A
       - strings unique to B
       - keyword hits (count and example matches) per side
    """
    sa = set(deepdive_strings(path_a))
    sb = set(deepdive_strings(path_b))
    only_a = sa - sb
    only_b = sb - sa

    def kw_hits(strs):
        out = {}
        for needle in DEEPDIVE_NEEDLES:
            rx = re.compile(re.escape(needle), re.IGNORECASE)
            matches = [s for s in strs if rx.search(s)]
            if matches:
                out[needle] = matches
        return out

    return {
        "only_a": sorted(only_a),
        "only_b": sorted(only_b),
        "kw_a": kw_hits(sa),
        "kw_b": kw_hits(sb),
        "kw_only_b": kw_hits(only_b),
        "kw_only_a": kw_hits(only_a),
    }


def candidate_score(k: ModuleKey, ea, eb) -> Tuple[int, int]:
    """Score: (name_tier, abs_size_delta).
    Tier 2 = Gen4-relevant prior (Pcie/Nbio/Dxio/Cpm/Cbs/Apcb/Board/etc).
    Tier 1 = generic prior (Smm/Setup/Bmc).
    Tier 0 = none of the priors. Within a tier, larger |Δ size| wins."""
    name = k[1]
    tier = name_tier(name)
    if ea is not None and eb is not None:
        delta = abs(eb.size - ea.size)
    elif ea is None or eb is None:
        delta = (eb.size if eb else ea.size)
    else:
        delta = 0
    return (tier, delta)


def write_diff_report(per_version, va: str, vb: str, out_path: Path) -> None:
    a = per_version[va]
    b = per_version[vb]
    table, changed = render_diff_table(per_version, va, vb, highlight=True)

    total_keys = len(set(a) | set(b))

    # Rank changed candidates
    scored: List[Tuple[Tuple[int, int], ModuleKey]] = []
    for k in changed:
        ea = a.get(k); eb = b.get(k)
        scored.append((candidate_score(k, ea, eb), k))
    scored.sort(reverse=True)

    # Tier-A candidates first; fill remaining slots with Tier-B if any.
    tier_a_candidates = [(s, k) for s, k in scored if s[0] == 2]
    tier_b_candidates = [(s, k) for s, k in scored if s[0] == 1]
    priority_candidates = tier_a_candidates + tier_b_candidates
    top10 = priority_candidates[:10]
    top5 = priority_candidates[:5]

    # Phase split
    pei_changed = [k for k in changed if (a.get(k) or b.get(k)).phase == "PEI"]
    dxe_changed = [k for k in changed if (a.get(k) or b.get(k)).phase == "DXE"]
    other_changed = [k for k in changed if (a.get(k) or b.get(k)).phase not in ("PEI", "DXE")]

    out: List[str] = []
    out.append(f"# Module sweep — {fmt_label(va)} vs {fmt_label(vb)}")
    out.append("")
    out.append(f"_Generated by `scripts/module_sweep.py {va} {vb}`._")
    out.append("")
    out.append("## Summary")
    out.append("")
    out.append(
        f"- Total distinct PE32 module instances across both versions: **{total_keys}**"
    )
    out.append(f"- Modules in {fmt_label(va)}: {len(a)}")
    out.append(f"- Modules in {fmt_label(vb)}: {len(b)}")
    out.append(
        f"- Modules that differ (by sha256 / present-only-on-one-side): **{len(changed)}**"
    )
    out.append(
        f"  - DXE-phase changed: {len(dxe_changed)}  ·  "
        f"PEI-phase changed: {len(pei_changed)}  ·  other/unknown: {len(other_changed)}"
    )
    out.append("")
    out.append(
        "Module-name priority priors (`Pcie / Nbio / Dxio / Cpm / Cbs / Apcb / Oem / "
        "Asrock / Board / Platform / Strap / Bmc / Setup / Smm / Rs1`) flagged with `*`."
    )
    out.append("")

    out.append("## Top 10 candidates for Gen4 producer (by name × |Δ size|)")
    out.append("")
    if not top10:
        out.append("- (none — no priority-pattern modules differed)")
    else:
        out.append("| Rank | Vol | Module | Phase | Δ size | "
                   f"{fmt_label(va)} size | {fmt_label(vb)} size |")
        out.append("|---|---|---|---|---|---|---|")
        for i, (_, k) in enumerate(top10, 1):
            vol_idx, name, rank = k
            ea = a.get(k); eb = b.get(k)
            phase = (ea or eb).phase
            sa = str(ea.size) if ea else "(missing)"
            sb_ = str(eb.size) if eb else "(missing)"
            if ea and eb:
                delta = f"{eb.size - ea.size:+d}"
            else:
                delta = "n/a"
            out.append(f"| {i} | {vol_idx} | `{_name_with_rank(name, rank)}` | {phase} | {delta} | {sa} | {sb_} |")
    out.append("")

    # Phase-separated diff lists
    out.append("## Changed modules by phase")
    out.append("")
    out.append(f"### DXE-phase ({len(dxe_changed)} changed)")
    out.append("")
    out.append("| Vol | Module | Pri | Δ size |")
    out.append("|---|---|---|---|")
    for k in dxe_changed:
        vol_idx, name, rank = k
        ea = a.get(k); eb = b.get(k)
        delta = (f"{eb.size - ea.size:+d}" if (ea and eb)
                 else f"{eb.size if eb else -ea.size}*")
        pri = "*" if is_priority_name(name) else ""
        out.append(f"| {vol_idx} | `{_name_with_rank(name, rank)}` | {pri} | {delta} |")
    out.append("")
    out.append(f"### PEI-phase ({len(pei_changed)} changed)")
    out.append("")
    out.append("| Vol | Module | Pri | Δ size |")
    out.append("|---|---|---|---|")
    for k in pei_changed:
        vol_idx, name, rank = k
        ea = a.get(k); eb = b.get(k)
        delta = (f"{eb.size - ea.size:+d}" if (ea and eb)
                 else f"{eb.size if eb else -ea.size}*")
        pri = "*" if is_priority_name(name) else ""
        out.append(f"| {vol_idx} | `{_name_with_rank(name, rank)}` | {pri} | {delta} |")
    out.append("")
    if other_changed:
        out.append(f"### Other / unknown phase ({len(other_changed)} changed)")
        out.append("")
        for k in other_changed:
            vol_idx, name, rank = k
            out.append(f"- vol {vol_idx} `{_name_with_rank(name, rank)}`")
        out.append("")

    # Full diff table
    out.append("## Full diff table")
    out.append("")
    out.append(table)
    out.append("")

    # Strings deep-dive
    out.append("## Strings deep-dive on top 5 priority candidates")
    out.append("")
    out.append(
        "For each of the top 5 candidates (by priority-name × |Δ size|), we extract "
        "all printable ASCII strings ≥6 chars from both versions' PE32 bodies and "
        "report keyword hits ("
        + ", ".join(f"`{n}`" for n in DEEPDIVE_NEEDLES)
        + ") and any new-in-"
        + fmt_label(vb)
        + " strings that match those keywords. **Strongest signal:** a new-in-"
        + fmt_label(vb)
        + " string mentioning Gen4 / ESM / Strap / Rev / Board."
    )
    out.append("")

    for rnk, (_, k) in enumerate(top5, 1):
        vol_idx, name, inst_rank = k
        ea = a.get(k); eb = b.get(k)
        out.append(f"### {rnk}. `{_name_with_rank(name, inst_rank)}` (Vol {vol_idx})")
        out.append("")
        if ea is None or eb is None:
            out.append(f"_Module present in only one version — no string diff._")
            out.append("")
            continue
        out.append(f"- {fmt_label(va)} size: {ea.size}  ·  sha256: `{ea.sha[:16]}`")
        out.append(f"- {fmt_label(vb)} size: {eb.size}  ·  sha256: `{eb.sha[:16]}`  ·  Δ {eb.size - ea.size:+d}")
        out.append("")
        try:
            d = deepdive_diff(ea.path, eb.path)
        except Exception as ex:
            out.append(f"  (deep-dive failed: {ex})")
            out.append("")
            continue

        # New-in-B keyword hits
        if d["kw_only_b"]:
            out.append(f"**New-in-{fmt_label(vb)} strings matching priority keywords:**")
            out.append("")
            for kw, matches in sorted(d["kw_only_b"].items()):
                out.append(f"- `{kw}` ({len(matches)} match{'es' if len(matches)!=1 else ''}):")
                for m in matches[:8]:
                    safe = m.replace("|", "\\|").replace("`", "'")
                    out.append(f"    - `{safe[:160]}`")
                if len(matches) > 8:
                    out.append(f"    - …and {len(matches)-8} more")
            out.append("")
        else:
            out.append(f"_No new-in-{fmt_label(vb)} strings hit any of the priority keywords._")
            out.append("")

        # Removed-in-B keyword hits (occasionally interesting)
        if d["kw_only_a"]:
            out.append(f"**Strings removed in {fmt_label(vb)} (present in {fmt_label(va)} only):**")
            out.append("")
            for kw, matches in sorted(d["kw_only_a"].items()):
                out.append(f"- `{kw}` ({len(matches)}):")
                for m in matches[:6]:
                    safe = m.replace("|", "\\|").replace("`", "'")
                    out.append(f"    - `{safe[:160]}`")
                if len(matches) > 6:
                    out.append(f"    - …and {len(matches)-6} more")
            out.append("")

        # Total keyword hits (for context)
        out.append(f"**Total keyword presence ({fmt_label(va)} → {fmt_label(vb)}):**")
        out.append("")
        for kw in DEEPDIVE_NEEDLES:
            ca = len(d["kw_a"].get(kw, []))
            cb = len(d["kw_b"].get(kw, []))
            if ca or cb:
                out.append(f"- `{kw}`: {ca} → {cb}")
        out.append("")

    # Bonus: 5-version summary on suggestive-name modules
    out.append("## Bonus: 5-version size+hash summary on priority-name modules")
    out.append("")
    out.append(
        "Historical context — which priority-name modules were stable vs frequently "
        "modified across L3.11 → P3.70 → P3.80 → P3.90 → P4.10. A module unchanged "
        "across the P3.70 → P3.80 boundary is **not** a Gen4-producer candidate; "
        "one that changed there but was stable elsewhere is a stronger lead."
    )
    out.append("")
    versions = ALL_VERSIONS
    header_cells = ["Vol", "Module"] + [fmt_label(v) for v in versions]
    out.append("| " + " | ".join(header_cells) + " |")
    out.append("|" + "|".join(["---"] * len(header_cells)) + "|")

    pri_keys = [k for k in all_keys(per_version) if is_priority_name(k[1])]
    for k in pri_keys:
        vol_idx, name, rank = k
        cells = [str(vol_idx), f"`{_name_with_rank(name, rank)}`"]
        prev_sha = None
        for v in versions:
            e = per_version[v].get(k)
            if e is None:
                cells.append("(absent)")
                prev_sha = None
                continue
            if e.sha == prev_sha:
                cells.append(f"= ({e.size}B)")
            else:
                cells.append(f"`{e.sha[:8]}` ({e.size}B)")
                prev_sha = e.sha
        out.append("| " + " | ".join(cells) + " |")
    out.append("")

    out_path.write_text("\n".join(out))


# --------- main ---------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("versions", nargs="*",
                    help="Optional 2 versions for diff mode (e.g. 3.70 3.80).")
    ap.add_argument("--highlight", action="store_true",
                    help="In full-table mode, add priority-pattern flag column.")
    ap.add_argument("--report", action="store_true",
                    help="In diff mode, emit the markdown report doc to "
                         "docs/MODULE_SWEEP_P<va>_vs_P<vb>.md.")
    args = ap.parse_args()

    versions = ALL_VERSIONS

    # Collect once per version
    per_version: Dict[str, Dict[ModuleKey, ModuleEntry]] = {}
    for v in versions:
        per_version[v] = collect_pe32(v)

    if len(args.versions) == 2:
        va, vb = args.versions
        if va not in versions or vb not in versions:
            print(f"Unknown version(s); valid: {versions}", file=sys.stderr)
            sys.exit(1)
        if args.report:
            out_path = docs_dir() / f"MODULE_SWEEP_{fmt_label(va)}_vs_{fmt_label(vb)}.md"
            write_diff_report(per_version, va, vb, out_path)
            print(f"Wrote {out_path}")
        else:
            table, changed = render_diff_table(per_version, va, vb, highlight=True)
            print(f"# Diff: {fmt_label(va)} vs {fmt_label(vb)}")
            print()
            print(f"Modules differing: {len(changed)}")
            print()
            print(table)
        return

    if len(args.versions) not in (0,):
        print("Diff mode requires exactly 2 versions, or 0 for full-table mode.",
              file=sys.stderr)
        sys.exit(2)

    table = render_full_table(per_version, versions, highlight=args.highlight)
    print(table)


if __name__ == "__main__":
    main()
