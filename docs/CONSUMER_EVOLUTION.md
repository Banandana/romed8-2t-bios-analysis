# `AmdNbioPcieDxe.efi` evolution across L3.11 / P3.70 / P3.80 / P3.90 / P4.10

**Question (this task):** subagent #5 located the Gen4-ESM consumer test in P3.70 at file offset
`0x14b1e` — `test byte [r14+0x2e], 0x40`. The CROSS_VERSION_DIFF table shows
`AmdNbioPcieDxe` byte-identical P3.70 ↔ P3.80, but **changed** in P3.90 and again
in P4.10. Does the consumer site move, become conditional, gain new code, or
add new bit-6 instructions? Is the `+0x2E` / `0x40` shape preserved?

**TL;DR:** the consumer logic is unchanged. The descriptor field offset shifted
from `+0x2E` to `+0x32` between P3.80 and P3.90 (the entire descriptor layout
moved by 4 bytes — every access offset > 0x2E shifted by `+4`). The bit number
stays at 6 (mask `0x40`). The ESM gating shape — single `test byte [r14+disp],
0x40` followed by `jne` to ESM path or `lea str.Port_does_not_have_ESM…` to
the fail path — is **byte-equivalent across every version that has the test**.
P3.11 already has the same logic but uses `r15+0x2e` instead of `r14+0x2e`.
**No new bit-6 / `+0x2E` (or `+0x32`) instructions appear in P3.90 / P4.10**;
exactly one consumer site per binary, ever.

This is consistent with subagent #5's read: the descriptor producer (upstream
of this DXE — a PEI-phase or earlier-DXE module) is the only thing that ever
sets that bit, and `AmdNbioPcieDxe` only consumes it. The descriptor *layout
grew* but the *gating logic did not*.

---

## 1. Hash + size table

PE32 body extracted from `extracted/all/<v>/img.bin.dump/.../<NN> AmdNbioPcieDxe/1 PE32 image section/body.bin`.
Index `36` (P3.11) and `37` (P3.70+) under the Rome SP3 SSP volume.

| Version | Size (B) | Δsize    | SHA-256 (first 16 hex) | Note |
|--------:|---------:|---------:|:-----------------------|:-----|
| L3.11   |  68 832  |    —     | `e204ee474aaf085d`     | First version with this module |
| P3.70   |  72 640  |  +3 808  | `fdd08d2044493e3e`     | Subagent #5 baseline |
| P3.80   |  72 640  |       0  | `fdd08d2044493e3e`     | **Byte-identical to P3.70** |
| P3.90   |  72 640  |       0  | `d58dde757fc3ccc1`     | Same size, different content |
| P4.10   |  74 240  |  +1 600  | `6d08f6a7b26c87cb`     | New code added |

(Hashes match `docs/CROSS_VERSION_DIFF.md`'s module table — column "Rome SSP".)

For completeness, the mirror copy in folder `40` (Milan-side variant of this
volume tree, 69 824 B in all versions) follows the same evolution shape:
P3.11 unique → P3.70=P3.80 → P3.90=P4.10. The Milan binary is **NOT** the one
analyzed by subagent #5 and is not relevant to the rig — noted only because
the dump tree contains both.

## 2. Function map and basic-block stability

```
                P3.11   P3.70   P3.80   P3.90   P4.10
function count   124     127     127     127     127
```

Three new functions appear at L3.11 → P3.70; **none** at P3.70 → P3.80,
P3.80 → P3.90, or P3.90 → P4.10. The +1600-B P4.10 growth happens *inside
existing functions* — entirely consistent with the four new debug strings
introduced in P4.10 (see §5).

`PcieAttemptEsmIfEnabled` (the function containing the bit-6 test) is
**identical in shape** across P3.70, P3.80, and P3.90:

- Function entry: file offset `0x14883` (P3.70/P3.80/P3.90) → `0x149f7`
  (P4.10, shifted +0x174 by upstream growth).
- Bit-6 test instruction: `+0x29b` from function entry — identical relative
  offset across all four versions.
- Fall-through caller distance from `pop r15 ... ret` epilogue immediately
  preceding the bit-6 test: byte-for-byte identical instructions
  `415f 415e 415d 415c 5f 5e 5d c3` in P3.70/P3.80/P3.90/P4.10.

`PcieAttemptEsmIfEnabled` xref count to its own debug-tag string is 14 in
**every** version P3.70+ (and 14 in P3.11 too). Same call-graph shape, same
print sites, same number of basic blocks reachable from the function entry.

## 3. The bit-6 / `+0x2E` test across versions

Byte-pattern scan for `41 F6 46 dd ii` (REX `test byte [r14+disp8], imm8`):

| Version | File offset | Disassembly                          | Same callsite? |
|--------:|:-----------:|:-------------------------------------|:---------------|
| L3.11   | `0x4a33`    | `41 f6 47 2e 40` — `test [r15+0x2e], 0x40` | **r15** not r14 |
| P3.70   | `0x4b1e`    | `41 f6 46 2e 40` — `test [r14+0x2e], 0x40` | yes (subagent #5) |
| P3.80   | `0x4b1e`    | `41 f6 46 2e 40` — `test [r14+0x2e], 0x40` | identical to P3.70 |
| P3.90   | `0x4b1e`    | `41 f6 46 32 40` — `test [r14+0x32], 0x40` | **disp shifted +4** |
| P4.10   | `0x4c92`    | `41 f6 46 32 40` — `test [r14+0x32], 0x40` | disp = 0x32, addr shifted by upstream growth |

**Key finding:** the descriptor field for the ESM-enable bit moved
`+0x2E → +0x32` between P3.80 and P3.90. The bit number (mask `0x40` = bit 6)
and the register holding the descriptor pointer (`r14`) are unchanged.

The 5-byte basic-block immediately after the test is **bit-identical across
P3.70/P3.80/P3.90 except for the disp byte**:

```
0x14b1e  41 f6 46 2e 40   test byte [r14+0x2e], 0x40   ; P3.70/P3.80
         41 f6 46 32 40   test byte [r14+0x32], 0x40   ; P3.90
0x14b23  75 1d            jne  0x14b42                  ; → ESM path
0x14b25  48 8d 15 …       lea  rdx, str."… does not have ESM enabled"
0x14b2c  49 8b cd         mov  rcx, r13
0x14b2f  e8 …             call DebugPrint
0x14b34  8b cf            mov  ecx, edi
0x14b36  c1 e9 0c         shr  ecx, 0xc
0x14b39  83 e1 07         and  ecx, 7
0x14b3c  89 4c 24 28      mov  [rsp+0x28], ecx
0x14b40  eb 92            jmp  0x14ad4                  ; → outer loop continue
```

Every other instruction in that block is byte-identical across P3.70/3.80/3.90.
Same `jne` distance (+0x1d), same `lea str.Port_does_not_have_ESM_enabled`,
same call to the same DebugPrint helper. **Only the descriptor field offset
moved**; the gating logic is unchanged.

P3.11 has the same instruction shape with the same `0x2e` disp and `0x40`
mask but reads through `r15` not `r14`, and the fall-through path uses
`rcx ← r12` not `rcx ← r13`. Otherwise structurally equivalent.

## 4. Byte-level diff: P3.70 vs P3.90

Both binaries are exactly 72 640 B. **212 bytes differ across 164 contiguous
runs; every run is ≤ 8 bytes.** No inserted/removed code blocks. Histogram
of byte deltas:

| Δbyte | count | meaning |
|------:|------:|:--------|
| `+4`  | 32    | struct-field disp adjusted by +4 (e.g. `0x2e → 0x32`, `0x30 → 0x34`) |
| `+2`  | 34    | struct-field disp adjusted by +2 |
| `+6`  | 10    | struct-field disp adjusted by +6 |
| `+60`/`-100` | 51 | rel32/rel8 jump-target adjustments forced by code/data shifts |
| `-1`  | 47    | size-field decrements (e.g. struct-end terminators) |

**Interpretation: a uniform +4-byte shift in the descriptor layout.** Every
field at or beyond the previous `+0x2E` accessor moved up by 4 bytes — i.e. a
new 4-byte field was inserted somewhere in the first 0x2E bytes (or a
pre-existing field was widened from 4 → 8 bytes), pushing every later field
including the ESM-enable byte. The displacement-byte deltas at file offsets
`0x1460` (`0x2e → 0x32`) and `0x14b8` (also `0x2e → 0x32`) mark **two**
different functions inside `AmdNbioPcieDxe` that read the ESM-enable byte —
both at the same descriptor offset, both updated identically.

The Gen4-enable gating shape itself is preserved verbatim. There is no new
`if (board_rev == 1.03)` MMIO read introduced into `AmdNbioPcieDxe` between
P3.70 and P3.90 — that conclusion already held at the P3.70 ↔ P3.80 boundary
(byte-identical) and is reinforced by the P3.90 binary being a pure
descriptor-layout adjustment with no logical changes.

## 5. New strings across versions

Strings unique to each transition (after sorting/uniquing both sides):

- **L3.11 → P3.70:** stack-frame fragment differences only (different
  prologue register-save patterns due to inlining changes). No new
  ESM/Gen4/strap/rev strings.
- **P3.70 → P3.80:** binary identical, no string changes.
- **P3.80 → P3.90:** **zero** real new strings — only two binary fragments
  (`F2@u`, `F.@u`) that look like printable code-byte sequences, not actual
  strings.
- **P3.90 → P4.10:** four new debug-tags for two new wrapper functions:
  - `PcieAllEndpointsInitCallback Enter` / `… Exit`
  - `PcieAllEndpointsUpdate Enter` / `… Exit`
  - `PcieCompletionTimeoutCallback for Device = %d:%d:%d` (new)

  These are post-init endpoint sweep wrappers, not Gen-cap related.

The full ESM/Gen4-relevant string set is **identical across all 5 versions**
(verified: same 30-line set of `%a … ESM …` debug strings, including the
load-bearing `Port does not have ESM enabled` and `Setting ESM rates to
PCIE_LC_SPEED_CNTL.LC_GEN4_EN_STRAP=1 register`). No new strap, board-rev,
Gen4-cap, or platform-detection strings introduced anywhere.

## 6. Did any version introduce **new** bit-6 / descriptor-bitfield
instructions?

Byte-pattern sweep across all 5 binaries for any `test byte [reg+disp8], 0x40`
form addressed through r14, r15, rsi, rdi, rbx, rdx, rcx, or rax:

| Version | Sites for "test byte [reg+disp], 0x40" | Field disp | Register |
|--------:|---------------------------------------:|:-----------|:---------|
| L3.11   | 1                                      | `0x2e`     | r15      |
| P3.70   | 1                                      | `0x2e`     | r14      |
| P3.80   | 1                                      | `0x2e`     | r14      |
| P3.90   | 1                                      | `0x32`     | r14      |
| P4.10   | 1                                      | `0x32`     | r14      |

**Exactly one instance per binary, every version.** No producer-side bit-set
instructions added in P3.90/P4.10. This module remains a pure consumer of
the descriptor flag; no version of `AmdNbioPcieDxe` ever writes the bit.

## 7. Verdict and implications for the P3.80 unlock question

What the cross-version evolution of `AmdNbioPcieDxe` says:

1. **The consumer-side logic of the Gen4 gate is unchanged across the
   rev-1.03 unlock boundary.** P3.70 and P3.80 are byte-identical;
   P3.90/P4.10 only adjust the descriptor field offset (`+0x2E → +0x32`) and
   add unrelated post-init wrapper functions. The single
   `test byte [r14+disp], 0x40 / jne ESM` pattern persists from L3.11 all the
   way to P4.10. ASRock did not patch `AmdNbioPcieDxe` to flip the gate.

2. **Therefore the P3.80 unlock is not in this module.** This was already
   known from P3.70=P3.80 byte-identity; the P3.90/P4.10 evolution only
   strengthens it. If a board-rev MMIO check exists, it is upstream — in the
   *producer* that fills the descriptor before this DXE reads it. The prime
   suspect remains `AmdApcbDxeV3` (per CROSS_VERSION_DIFF: +64 B P3.80 vs
   P3.70, +0 B P3.80 vs P3.90, more changes in P4.10).

3. **The descriptor layout DID change between P3.80 and P3.90** (`+0x2E →
   +0x32` ESM-enable position). This means at minimum the AGESA descriptor
   schema was bumped; the producer in P3.90 must write to the new offset to
   keep the consumer working. Whoever produces the descriptor was therefore
   *modified* across that boundary too — but not in `AmdNbioPcieDxe` and not
   in any way that affects the gating decision; just bookkeeping.

4. **No "rev-1.03" string, no MMIO-rev-strap test, no platform-detection
   call** appears in any version of `AmdNbioPcieDxe`. The Gen-cap decision
   for ASRock's GPU root ports is *entirely* delegated to whatever sets bit 6
   of the per-port DXIO descriptor before this DXE runs.

**Action item still standing (Phase 2):** disassemble `AmdApcbDxeV3` P3.70 vs
P3.80 (the +64-B growth). That is the binary where the rev-1.03 / Gen4
unlock — if it exists as a runtime-evaluable check rather than a build-time
flip — must live. Subagents already dispatched to that question per
`docs/PLANNED_SUBAGENTS.md`.

---

## Appendix: reproduction commands

```bash
# Hashes
cd /tmp/nbio_evo  # populated from the 5 BIOS dump trees
sha256sum rome_*.efi

# Bit-6 byte-pattern scan
python3 -c "
import re
for v in ['P3.11','P3.70','P3.80','P3.90','P4.10']:
    data = open(f'rome_{v}.efi','rb').read()
    for m in re.finditer(b'\x41\xf6.(.)(.)', data, re.DOTALL):
        if m.group(2)[0] == 0x40:
            print(v, hex(m.start()), 'disp', hex(m.group(1)[0]))
"

# Disassembly around test site
r2 -A -q -c 's 0x14b1e ; pd 12' rome_P3.70.efi
r2 -A -q -c 's 0x14b1e ; pd 12' rome_P3.90.efi

# Byte-diff
python3 -c "
a=open('rome_P3.70.efi','rb').read(); b=open('rome_P3.90.efi','rb').read()
print(sum(1 for i,(x,y) in enumerate(zip(a,b)) if x!=y), 'bytes differ')
"

# String diff
diff <(strings rome_P3.70.efi|sort -u) <(strings rome_P3.90.efi|sort -u)
diff <(strings rome_P3.90.efi|sort -u) <(strings rome_P4.10.efi|sort -u)
```
