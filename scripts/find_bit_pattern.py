#!/usr/bin/env python3
"""find_bit_pattern.py — scan every PE32 in given BIOS version(s) for byte
patterns that encode `OR/TEST/BTS/AND byte [reg+disp], imm` and similar
load-modify-store sequences targeting a specific (disp, imm) pair.

Default mode 'bit-set' with disp=0x2e imm=0x40 finds anything touching the
Gen4 enable bit (bit 6 of byte +0x2E) in any per-port DXIO descriptor —
which is the cap-deciding flag identified by subagent #5.

The producer of that bit is the open question this script targets. The
known consumer in `AmdNbioPcieDxe` (file offset 0x4b1e in P3.70 ImageBase
0x10000 → r2 addr 0x14b1e) is a sanity-check hit.

Patterns scanned (Intel SDM encoding, REX prefix matched as optional 4? byte):

  TEST byte [reg+disp8], imm8   F6 /0 ib    encoding form: F6 [mod=01,reg=000,rm] disp8 ib
                                            -> F6 4r dd ii  (mod=01, reg=0, rm=r) for low regs
  TEST byte [reg+disp32], imm8  F6 /0       -> F6 8r dd dd dd dd ii (mod=10, reg=0)
  OR   byte [reg+disp8], imm8   80 /1 ib    -> 80 4r dd ii (mod=01, reg=1; modrm.reg=1 -> nibble 4-7 unused, but reg-field-of-modrm=001 selects OR -> top three bits 010 = mod=01, then reg=001, then rm in low 3.  modrm = (mod<<6)|(reg<<3)|rm = 0x40|0x08|rm = 0x48..0x4F)
                                            so OR is 80 4? where ? in {8..F}; we treat the pattern
                                            as `80 4?` and accept any rm 8-F via wildcard nibble.
  OR   byte [reg+disp32], imm8  80 /1       -> 80 8? dd dd dd dd ii (modrm.reg=1: 0x88..0x8F)
  AND  byte [reg+disp8], imm8   80 /4 ib    -> 80 6? dd ii (modrm = 0x60..0x6F where reg-field=4 -> 0x60|rm; for mod=01, modrm = 0x40|0x20|rm = 0x60..0x67)
                                            we use 80 6? (allowing 0x60-0x6F covers SIB/no-SIB)
  BTS  byte [reg+disp8], imm8   0F BA /5 ib -> 0F BA 6r dd ib  (modrm = 0x68..0x6F)
  BTR  byte [reg+disp8], imm8   0F BA /6 ib -> 0F BA 7r dd ib

For load-modify-store (`mov al, [reg+disp]; or al, imm; mov [reg+disp], al`),
we use a sliding-window search: scan for any
  `8a 4? <disp> ... 88 4? <disp>` window (reg in {0..F} relaxed) with the
target disp byte, where between them there's a `0c <imm>` (or al, imm) or
`24 <imm>` (and al, imm). Window length capped at 32 bytes.

CLI:
  python3 scripts/find_bit_pattern.py [--versions 3.70 3.80] [--mode bit-set]
                                       [--disp 0x2e] [--imm 0x40]
                                       [--min-size 4096]
                                       [--include-known]   # don't filter the
                                                           # AmdNbioPcieDxe consumer

Output: stdout, one line per hit, plus surrounding 32 bytes context.
Designed to be re-run; cheap (pure Python, no r2)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

# Make scripts/lib importable when run from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.ffs import iter_pe32_bodies  # noqa: E402
from lib.versions import ALL_VERSIONS, label  # noqa: E402


# ---- pattern engine ----

class WildPat:
    """A byte pattern with single-nibble wildcards.

    Pattern syntax: each token is either two hex digits, or one of two
    hex digits where '?' means any nibble. Whitespace is ignored.
    Examples:
        '80 4? 2e 40'      4 bytes; second byte high nibble must be 4
        '0f ba 6? 2e 06'   5 bytes; third byte high nibble must be 6
    """

    __slots__ = ("raw", "vals", "masks", "length")

    def __init__(self, spec: str):
        self.raw = spec
        toks = spec.replace(" ", "").lower()
        if len(toks) % 2 != 0:
            raise ValueError(f"odd-length pattern: {spec!r}")
        vals = bytearray()
        masks = bytearray()
        for i in range(0, len(toks), 2):
            ch_hi, ch_lo = toks[i], toks[i + 1]
            mask = 0
            val = 0
            if ch_hi == '?':
                mask |= 0x0F  # high nibble unconstrained -> mask covers low only
            else:
                val |= int(ch_hi, 16) << 4
                mask |= 0xF0
            if ch_lo == '?':
                pass  # low nibble unconstrained -> mask doesn't cover it
            else:
                val |= int(ch_lo, 16)
                mask |= 0x0F
            vals.append(val)
            masks.append(mask)
        self.vals = bytes(vals)
        self.masks = bytes(masks)
        self.length = len(vals)

    def find_all(self, data: bytes) -> List[int]:
        """Return all start offsets where pattern matches."""
        out: List[int] = []
        n = len(data)
        L = self.length
        vals = self.vals
        masks = self.masks
        # Naive scan; binaries are <= ~100 KB so this is fine.
        for i in range(n - L + 1):
            ok = True
            for j in range(L):
                if (data[i + j] & masks[j]) != vals[j]:
                    ok = False
                    break
            if ok:
                out.append(i)
        return out

    def __repr__(self) -> str:
        return f"WildPat({self.raw!r})"


def fmt_imm(imm: int) -> str:
    return f"{imm:02x}"


def build_patterns_bit_set(disp: int, imm: int) -> List[Tuple[str, WildPat, str]]:
    """Build the set of byte patterns for 'bit-set / bit-test' modes,
    parametrised by disp (8-bit byte displacement) and imm (8-bit immediate).

    Returns list of (label, pattern, instr_template).
    """
    d = fmt_imm(disp)
    i = fmt_imm(imm)
    pats: List[Tuple[str, WildPat, str]] = []

    # OR  byte [reg+disp8], imm8           -> 80 4? dd ii
    pats.append((
        f"or  byte [reg+0x{d}], 0x{i} (disp8)",
        WildPat(f"80 4? {d} {i}"),
        f"or byte [reg+0x{d}], 0x{i}",
    ))
    # OR  byte [reg+disp32], imm8          -> 80 8? dd dd dd dd ii
    pats.append((
        f"or  byte [reg+0x{d}], 0x{i} (disp32)",
        WildPat(f"80 8? {d} 00 00 00 {i}"),
        f"or byte [reg+0x{d}], 0x{i}",
    ))
    # OR  with SIB: 80 4c sib dd ii  (rm=4 -> SIB present)
    pats.append((
        f"or  byte [reg+SIB+0x{d}], 0x{i}",
        WildPat(f"80 4c ?? {d} {i}"),
        f"or byte [base+idx+0x{d}], 0x{i}",
    ))
    # TEST byte [reg+disp8], imm8          -> F6 4? dd ii
    pats.append((
        f"test byte [reg+0x{d}], 0x{i} (disp8)",
        WildPat(f"f6 4? {d} {i}"),
        f"test byte [reg+0x{d}], 0x{i}",
    ))
    # TEST byte [reg+disp32], imm8         -> F6 8? dd dd dd dd ii
    pats.append((
        f"test byte [reg+0x{d}], 0x{i} (disp32)",
        WildPat(f"f6 8? {d} 00 00 00 {i}"),
        f"test byte [reg+0x{d}], 0x{i}",
    ))
    # BTS byte [reg+disp8], 6              -> 0F BA 6? dd 06   (only meaningful when imm bit is set)
    # We only emit BTS if imm == 0x40 (bit 6) — translate imm bit position automatically.
    bit_pos = imm.bit_length() - 1 if imm and (imm & (imm - 1)) == 0 else None
    if bit_pos is not None:
        bp = fmt_imm(bit_pos)
        pats.append((
            f"bts byte [reg+0x{d}], {bit_pos}",
            WildPat(f"0f ba 6? {d} {bp}"),
            f"bts byte [reg+0x{d}], {bit_pos}",
        ))
        pats.append((
            f"btr byte [reg+0x{d}], {bit_pos}",
            WildPat(f"0f ba 7? {d} {bp}"),
            f"btr byte [reg+0x{d}], {bit_pos}",
        ))

    # AND byte [reg+disp8], ~imm           -> 80 6? dd <~imm>
    notimm = (~imm) & 0xFF
    ni = fmt_imm(notimm)
    pats.append((
        f"and byte [reg+0x{d}], 0x{ni}  (clear bit{f' {bit_pos}' if bit_pos is not None else 's'})",
        WildPat(f"80 6? {d} {ni}"),
        f"and byte [reg+0x{d}], 0x{ni}",
    ))
    # AND with SIB
    pats.append((
        f"and byte [reg+SIB+0x{d}], 0x{ni}",
        WildPat(f"80 6c ?? {d} {ni}"),
        f"and byte [base+idx+0x{d}], 0x{ni}",
    ))

    return pats


# ---- load-modify-store sliding-window detector ----

def find_load_modify_store(data: bytes, disp: int, imm: int, window: int = 32
                            ) -> List[Tuple[int, int, int, str]]:
    """Find sequences of:
        MOV ?l, byte [reg+disp]   -- 8a 4? dd  (load to AL/CL/DL/BL low byte)
        ... up to <window> bytes ...
        OR/AND ?l, imm            -- 0c ii (or al, ii) / 24 ii (and al, ii)
                                     80 c? ii / 80 e? ii (or/and r/m8, ii)
        ... up to <window> bytes ...
        MOV byte [reg+disp], ?l   -- 88 4? dd

    Returns (load_offset, modify_offset, store_offset, summary).
    Heuristic; may have false positives but very useful for finding code
    that touches +0x2e via register.
    """
    d = disp & 0xFF
    out: List[Tuple[int, int, int, str]] = []
    n = len(data)
    i = 0
    while i < n - 3:
        # MOV r8, byte [reg+disp8]  -> 8a (modrm) disp8
        # modrm = mod=01, reg=any (3 bits = dst reg), rm=any (3 bits)
        # modrm byte: 0x40..0x7F (mod=01 with rm != 4 is fine; rm=4 means SIB)
        if data[i] == 0x8A:
            modrm = data[i + 1]
            if (modrm & 0xC0) == 0x40:  # mod=01
                disp_byte = data[i + 2]
                if disp_byte == d:
                    # candidate load. Now look forward for a modify within window.
                    end_search = min(n, i + 3 + window)
                    found = _scan_modify_then_store(data, i + 3, end_search, modrm, d, imm, window)
                    if found:
                        mod_off, store_off, summary = found
                        out.append((i, mod_off, store_off, summary))
        i += 1
    return out


def _scan_modify_then_store(data: bytes, start: int, end: int, load_modrm: int,
                             disp: int, imm: int, window: int):
    """Inside window after the load, find a modify (OR/AND with imm), then a
    matching store within another window. Return (modify_off, store_off, summary)
    or None."""
    # Modify candidates: OR al,imm = 0C ii ;  AND al,imm = 24 ii ;
    #                    OR/AND r/m8,imm = 80 (modrm) ii  -- but only if modrm == 0xC0|reg or 0xE0|reg
    # Store candidate:  MOV byte [reg+disp8], r8  -> 88 (modrm) disp8
    # The reg field of the load and store should match (typically same dst register).
    load_reg = (load_modrm >> 3) & 0x07  # dst reg of load
    n = end
    j = start
    found_modify = None
    while j < n:
        b = data[j]
        if b == 0x0C and j + 1 < n and data[j + 1] == imm and load_reg == 0:
            # OR al, imm — only matches if load_reg == AL (000)
            found_modify = (j, "or al, 0x%02x" % imm)
            j_after = j + 2
            break
        if b == 0x24 and j + 1 < n and data[j + 1] == ((~imm) & 0xFF) and load_reg == 0:
            found_modify = (j, "and al, 0x%02x" % ((~imm) & 0xFF))
            j_after = j + 2
            break
        if b == 0x80 and j + 2 < n:
            modrm2 = data[j + 1]
            # OR r/m8, imm: modrm reg field = 1 (mod=11 -> 0xC8..0xCF)
            if (modrm2 & 0xC0) == 0xC0 and ((modrm2 >> 3) & 0x07) == 1 and (modrm2 & 0x07) == load_reg and data[j + 2] == imm:
                found_modify = (j, "or r%d, 0x%02x" % (load_reg, imm))
                j_after = j + 3
                break
            # AND r/m8, imm: modrm reg field = 4
            if (modrm2 & 0xC0) == 0xC0 and ((modrm2 >> 3) & 0x07) == 4 and (modrm2 & 0x07) == load_reg and data[j + 2] == ((~imm) & 0xFF):
                found_modify = (j, "and r%d, 0x%02x" % (load_reg, (~imm) & 0xFF))
                j_after = j + 3
                break
        j += 1
    if not found_modify:
        return None
    # Find store within `window` bytes after modify
    store_end = min(len(data), j_after + window)
    k = j_after
    while k < store_end - 2:
        if data[k] == 0x88:
            modrm3 = data[k + 1]
            if (modrm3 & 0xC0) == 0x40:  # mod=01
                if data[k + 2] == disp:
                    # Same-source-reg sanity check (the stored reg should match load_reg)
                    src_reg = (modrm3 >> 3) & 0x07
                    if src_reg == load_reg:
                        return (found_modify[0], k,
                                f"load r{load_reg}, [reg+0x{disp:02x}] / {found_modify[1]} / store [reg+0x{disp:02x}], r{src_reg}")
        k += 1
    return None


# ---- runner ----

KNOWN_CONSUMER = "AmdNbioPcieDxe"
# The opcode byte (after the REX.B prefix 0x41) lands at file offset 0x4b1f in
# P3.70 and P3.80 entry-37, and 0x4a35 in P3.11 entry-36. P3.90 / P4.10 do not
# contain the consumer instruction at all (the descriptor layout changed).
KNOWN_CONSUMER_OFFSETS = {
    ("3.11", 68832): 0x4a34,
    ("3.70", 72640): 0x4b1f,
    ("3.80", 72640): 0x4b1f,
}


def hex_context(data: bytes, off: int, width: int = 32) -> str:
    """Render +/- width/2 bytes around `off` as hex, separated by `|` at off."""
    half = width // 2
    s = max(0, off - half)
    e = min(len(data), off + half)
    pre = data[s:off].hex()
    post = data[off:e].hex()
    return f"{pre}|{post}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--versions", nargs="+", default=["3.70", "3.80"],
                    help="BIOS versions to scan (default: 3.70 3.80). Use 'all' to scan ALL_VERSIONS.")
    ap.add_argument("--mode", default="bit-set",
                    choices=["bit-set", "raw"],
                    help="bit-set = standard set of OR/TEST/BTS/AND patterns. raw = use --pattern.")
    ap.add_argument("--disp", default="0x2e",
                    help="Byte displacement (default: 0x2e — Gen4-enable byte).")
    ap.add_argument("--imm", default="0x40",
                    help="Immediate (default: 0x40 — bit 6 mask).")
    ap.add_argument("--pattern", default=None,
                    help="In raw mode: one byte pattern with optional ? wildcards.")
    ap.add_argument("--min-size", type=int, default=4096,
                    help="Min PE32 size to consider (default: 4096).")
    ap.add_argument("--include-known", action="store_true",
                    help="Include the known consumer hit in AmdNbioPcieDxe at 0x4b1e (P3.70).")
    ap.add_argument("--include-te", action="store_true",
                    help="Also scan TE (Terse Executable) sections — i.e. PEI modules.")
    ap.add_argument("--lms-window", type=int, default=32,
                    help="Window size for load-modify-store sliding scan (default: 32).")
    ap.add_argument("--no-lms", action="store_true",
                    help="Skip the load-modify-store sliding-window scan.")
    args = ap.parse_args()

    versions = ALL_VERSIONS if args.versions == ["all"] else args.versions
    disp = int(args.disp, 0)
    imm = int(args.imm, 0)

    if args.mode == "raw":
        if not args.pattern:
            ap.error("--mode raw requires --pattern")
        patterns: List[Tuple[str, WildPat, str]] = [("user pattern", WildPat(args.pattern), args.pattern)]
    else:
        patterns = build_patterns_bit_set(disp, imm)

    print(f"# find_bit_pattern.py")
    print(f"# versions: {versions}")
    print(f"# mode    : {args.mode}  disp=0x{disp:02x}  imm=0x{imm:02x}")
    print(f"# patterns:")
    for name, pat, instr in patterns:
        print(f"#   {name:55s} -> bytes: {pat.raw}  ({instr})")
    if not args.no_lms:
        print(f"#   load-modify-store sliding window     -> 8A/0C|24/88 within {args.lms_window} B")
    print()

    total_hits = 0
    per_version: dict = {}

    for ver in versions:
        ver_label = label(ver)
        print(f"\n## {ver_label}\n")
        seen_modules = set()
        for module_name, body_path in iter_pe32_bodies(ver, min_size=args.min_size,
                                                        include_te=args.include_te):
            # Avoid duplicate (active-volume + recovery) hits: keep first per (name,sha)
            try:
                data = body_path.read_bytes()
            except OSError:
                continue
            key = (module_name, len(data))
            if key in seen_modules:
                continue
            seen_modules.add(key)

            module_hits = []
            for name, pat, instr in patterns:
                hits = pat.find_all(data)
                for off in hits:
                    # Filter known-consumer noise unless --include-known
                    if (not args.include_known
                            and module_name == KNOWN_CONSUMER
                            and KNOWN_CONSUMER_OFFSETS.get((ver, len(data))) == off):
                        continue
                    module_hits.append((off, name, instr, pat.length))

            lms_hits = []
            if not args.no_lms:
                for load_off, mod_off, store_off, summary in find_load_modify_store(data, disp, imm, args.lms_window):
                    lms_hits.append((load_off, mod_off, store_off, summary))

            if not module_hits and not lms_hits:
                continue

            print(f"### {module_name}  ({len(data)} bytes)")
            print(f"    path: {body_path}")
            for off, name, instr, plen in sorted(module_hits):
                ctx = hex_context(data, off)
                raw = data[off:off + plen].hex()
                print(f"    [+0x{off:06x}] {instr:40s}  raw={raw:20s}  ctx={ctx}")
                total_hits += 1
            for load_off, mod_off, store_off, summary in lms_hits:
                ctx = hex_context(data, load_off, 48)
                print(f"    [+0x{load_off:06x}] LMS: {summary}")
                print(f"                          (modify@+0x{mod_off:06x}, store@+0x{store_off:06x})  ctx={ctx}")
                total_hits += 1
            per_version.setdefault(ver_label, 0)
            per_version[ver_label] += len(module_hits) + len(lms_hits)
            print()

    print()
    print("## Summary")
    for v, n in per_version.items():
        print(f"   {v}: {n} hits")
    print(f"   total: {total_hits}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
