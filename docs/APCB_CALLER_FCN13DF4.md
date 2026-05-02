# `fcn.00013df4` (P3.70) vs `fcn.00013e14` (P3.80) — single-function diff

**Date:** 2026-04-27
**Module:** `AmdApcbDxeV3.efi` entry-43 (the `+64 B` PE32 from `CROSS_VERSION_DIFF.md`).
**Trigger:** open question #3 in `docs/APCB_DXEV3_DIFF.md`: "what extra mutation did P3.80 add such that the entry checksum needs full recomputation?"
**Verdict (executive summary):** **No mutation was added in this function.** `fcn.00013df4` and `fcn.00013e14` are byte-for-byte functionally identical — same 440-byte length, same 24 basic blocks, same 113 instructions, same 6-string set, same call graph. Every byte difference is a relocation artifact (rel32 call displacements and RIP-relative disp32 LEA bytes) caused by `.text` and `.data` shifting. **This function is not the source of the new pre-write-back mutation, and it is unrelated to PCIe/Gen4.** It handles **DDR4 Post Package Repair** (memory RAS), not DXIO.

---

## Tool availability

- `radare2 6.1.4-1` — installed and used.
- `mcp__radare2__*` MCP tools — schemas loaded but found unnecessary; bash-driven `r2 -A -c '...'` was faster.
- Both PE32 bodies extracted to `/tmp/apcb_diff/p3{70,80}.bin` (50 848 B / 50 912 B) per the file-paths in `APCB_DXEV3_DIFF.md`.

---

## Function identification

Both binaries: `afl` reports a function at the start address with **identical size, identical basic-block count, identical instruction count**:

| Version | Address       | Size  | BBs | Instrs | `afi` `noreturn` | `afi` `recursive` |
|---------|---------------|-------|----:|-------:|------------------|-------------------|
| P3.70   | `0x00013df4`  | 440 B | 24  | 113    | false            | false             |
| P3.80   | `0x00013e14`  | 440 B | 24  | 113    | false            | false             |

Address shift is exactly `+0x20`, matching the global `.text` shift documented in `APCB_DXEV3_DIFF.md` (and consistent with the +33 B insertion inside `fcn.00012b9c` — the immediate-prior function — pushing everything that follows).

The function is identified **not** as a caller of `AmdPspWriteBackApcbShadowCopy` but as a **DDR4 Post Package Repair (PPR) entry handler**. Identification basis:

- Six embedded debug strings, all `"[APCB Lib V3] ..."` prefixed:
  - `APCB.RecoveryFlag Set, exit service`
  - `Recovery flag set, exit service`
  - `Failed to locate DDR4 Post Package Repair Entries`
  - `Failed to allocate buffer for a new DDR4 Post Package Repair Entry`
  - `Failed to find the type for Post Package Repair Entries`
  - `Failed to find the DDR4 Post Package Repair Entry`
- An `mov ecx, 0x1704` literal — APCB token-group ID for the **MEMG / DDR4-PPR-list** entry type, *not* DXIO/PCIe.

The brief in `APCB_DXEV3_DIFF.md` step #3 referred to this function as "the caller of `AmdPspWriteBackApcbShadowCopy`". On closer inspection that wording is approximate: the actual call to `fcn.00012b9c` (the `AmdPspWriteBackApcbShadowCopy` we tracked) is at file offset `0x1477a` (P3.70) / `0x1479a` (P3.80) — radare2's `axt` reports it as `(nofunc)` because that callsite lives in a region the auto-analyzer didn't promote into a discrete function. Radare's xref-graph associates that callsite with `fcn.00013df4` only via downstream xref-walking, not via lineal containment. The 440-byte function actually disassembled here is fully self-contained DDR4-PPR setup logic that does **not** itself call `fcn.00012b9c`.

(For follow-up: the *actual* immediate caller of `AmdPspWriteBackApcbShadowCopy` is the disconnected basic block at `0x14770`-ish, ending at `0x14794` with the call sequence `call AmdPspWriteBackApcbShadowCopy; call fcn.00012634; call qword [gApcbV3Protocol+0x48]; ret`. That pre-amble is what should be diffed if the goal is "find the new mutation". See "Implication" below.)

---

## Basic-block / size deltas

| Metric                 | P3.70 | P3.80 | Delta |
|------------------------|------:|------:|------:|
| Size                   | 440 B | 440 B | **0** |
| Basic blocks           | 24    | 24    | 0     |
| Instructions           | 113   | 113   | 0     |
| Stack frame            | 144 B | 144 B | 0     |
| Cyclomatic complexity  | 13    | 13    | 0     |
| Edges                  | 35    | 35    | 0     |

**Zero structural change.**

---

## Side-by-side disasm — what the diff actually contains

Full disassembly of both functions (`pdf @ fcn.00013df4` and `pdf @ fcn.00013e14`) is 128 lines each. After normalizing absolute addresses (`s/0x[0-9a-f]+/X/g`) and `fcn.NNNNN` symbol names, the line-level diff has zero functional changes. Every single difference falls into one of three categories:

1. **rel32 call-displacement bytes** — e.g. P3.70 `e8c1390000  call fcn.000177e0` vs P3.80 `e8c1390000  call fcn.00017800`. The encoded byte-pattern `c1 39 00 00` is identical (same call distance from current address), only the symbolic resolution differs because the target moved by `+0x20` along with this function. Verified against full byte stream: every `e8 xx xx xx xx` rel32 in P3.70 is bit-identical at the same in-function offset in P3.80.

2. **RIP-relative LEA disp32 bytes for string loads** — e.g. P3.70 `488d156c5f0000` vs P3.80 `488d15cc5f0000`. The LEA opcode and ModR/M are identical (`48 8d 15`); only the 32-bit displacement differs by `+0x60`, matching the shift of the strings from P3.70's `0x19d98` to P3.80's `0x19e18`. Same string, different link-time offset.

3. **RIP-relative MOV disp32 for global-data reads** — e.g. P3.70 `381d227d0000  cmp byte [0x1bb35], bl` vs P3.80 `381d427d0000  cmp byte [0x1bb75], bl`. The encoded global moved by `+0x40` (consistent with `.data` shrinking by `-0x40` and `.text` growing by `+0x80` — the data sections re-rebased by the link). Same global variable, just at a new address.

**No category 4 (new instruction)** appears. The opcode/ModR/M streams are identical instruction-by-instruction. The `.xdata` (Win64 unwind) entry for this function would be likewise unchanged (the `.xdata` `+0x8` virt-size growth documented in `APCB_DXEV3_DIFF.md` belongs to the modified `fcn.00012b9c`, not this function).

---

## What mutation was added in this function — answer

**None.** P3.80's `fcn.00013e14` does no more, no less, and no different work than P3.70's `fcn.00013df4`. The instruction-level diff is empty after relocation normalization.

If the brief's hypothesis was "P3.80 added a new APCB-token edit at runtime in the caller of `AmdPspWriteBackApcbShadowCopy`, which is why `fcn.00012b9c` had to add the full-recompute checksum block" — that hypothesis is **falsified for `fcn.00013df4`**. The new mutation, if it exists, is in some *other* caller of `fcn.00012b9c`. The actual immediate-caller code at `0x14770`-ish was not analyzed in this single-function diff (it sits outside any radare-promoted function); see "Implication for next steps".

---

## Group / entry / offset interpretation

The `mov ecx, 0x1704` literal in this function targets APCB **MEMG group entry-type `0x5e` for DDR4 Post Package Repair lists** (visible in the `lea edx, [r8 + 0x5e]` immediately before the `0x1704` group-ID load). This is the same MEMG group `APCB_DECODE.md` documented (4496-byte memory-training group). The mutation, if any happened in P3.80, would be a memory-training table edit — the kind of fix typically driven by DDR4 errata workarounds, not by PCIe.

The token group `0x1704` is **not** DXIO. DXIO groups in AGESA's APCB schema are typically `0x1705`/`0x1706` (per coreboot's apcb_v3 schema), and they are **absent from this BIOS's APCB entirely** (per subagent #1's APCB_DECODE.md finding).

So even if `fcn.00013df4` *had* changed, its target group would still be irrelevant to Gen4: it operates on memory-RAS tables, not link-speed straps.

---

## Gen4-relevance verdict

**No.** Both:

1. **Indirect (group-membership) test:** the function targets DDR4-PPR memory-RAS data (group `0x1704`, entry type `0x5e`) — not PCIe, not DXIO, not a link-speed token. Even a hypothetical mutation here could not propagate to bit 6 of `+0x2E` of any DXIO descriptor.
2. **Direct (instruction-level) test:** there is no mutation. P3.70 and P3.80 versions are byte-functionally identical.

Cross-checked against the explicit byte-pattern scans for "set bit 6 of `[reg + 0x2e]`" already performed in `APCB_DXEV3_DIFF.md`: zero hits in either version, anywhere in this binary. The producer of bit 6 is not in `AmdApcbDxeV3` and that conclusion is unchanged.

---

## Implication for next steps

The question raised in `APCB_DXEV3_DIFF.md` step #3 — "what extra mutation requires full checksum recompute in P3.80?" — is **not answered by this function**. Two follow-ups remain to close that question, both lower-priority:

1. **Diff the actual immediate-caller of `fcn.00012b9c`** — the radare-orphaned basic block at `0x14770`-`0x14794` (P3.70) / `0x14790`-`0x147b4` (P3.80) and however far back its predecessor block extends. This is the code that:
   - calls `AmdPspWriteBackApcbShadowCopy` (`fcn.00012b9c`),
   - then calls `fcn.00012634` (likely the SPI-flash commit),
   - then invokes `[gApcbV3Protocol+0x48]` (likely an ApcbModified-broadcast).
   The new mutation has to live in this sequence's predecessor (the code that decided "the entry was modified, please write back"). Force-promoting that block to a function in radare (`af @ 0x14770` / `af @ 0x14790`) and re-diffing would be ~15 minutes of work.

2. **Search for new write-callsites to byte `+0x10` of an APCB entry across the whole binary** in P3.80 — i.e. any `mov [reg+0x10], imm` or `mov [reg+0x10], reg` that didn't exist in P3.70. The new full-recompute exists *because* something writes to a byte other than the 4-byte instance counter at `+0x0c` and the 1-byte checksum at `+0x10`. Find that new write, find the mutation.

Neither follow-up changes the executive verdict: the mutation, wherever it is, is **not Gen4-relevant**, because it lives in `AmdApcbDxeV3` (which `APCB_DXEV3_DIFF.md` already established does not touch the Gen4-enable bit and contains no PCIe/DXIO/ESM strings or `+0x2E` bit-6 patterns).

The single highest-leverage offline question therefore remains the same as in `APCB_DXEV3_DIFF.md` step #1: **find which DXE actually synthesizes the per-port DXIO descriptors** (candidates: `AmdNbioBaseSspDxe`, `AmdCpmPcieInitDxe`, `AmdCpmOemInitDxe`, ASRock `Rs1*Dxe`, or a PEI-phase counterpart). This priority is **unchanged** by today's diff.

---

## Files

- `/tmp/apcb_diff/p370.bin` — P3.70 entry-43 PE32 body (50 848 B)
- `/tmp/apcb_diff/p380.bin` — P3.80 entry-43 PE32 body (50 912 B)
- `/tmp/apcb_diff/p370_13df4.txt` / `p380_13e14.txt` — raw `pdf` disassembly
- `/tmp/apcb_diff/p370_full.txt` / `p380_full.txt` — extended `pD 2464` disassembly
- `/tmp/apcb_diff/p370_mnem.txt` / `p380_mnem.txt` — address-stripped mnemonic-only streams
- `/tmp/apcb_diff/p3{70,80}_strs.txt` — string sets used by the function (identical 6-string sets)
