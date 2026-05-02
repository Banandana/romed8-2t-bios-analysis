# Disassembly of remaining DXE/SMM candidates — P3.70 vs P3.80

**Date:** 2026-04-27
**Scope:** Final round of candidate-DXE/SMM modules from `MODULE_SWEEP_REBASE_AWARE.md` after the PEI search space was exhausted negatively (`PEI_PRODUCER_SWEEP.md`). Targets per T's recommendation:

- `AmdRasSspDxe`
- `AmdRasSspSmm`
- `PciDxeInit`
- `PciBus`
- `PciRootBridge`

**Verdict (top-line):** **No producer found in any of these.** All P3.70 → P3.80 changes are **token-ID renumbering** (PCD / status-code / event-token IDs each incremented by exactly +1). No semantic change, no new bit-6/`+0x2E` manipulation, no new strings, no PE-section growth, no new BDF references. These five modules are **definitively eliminated** as candidates for the per-port DXIO descriptor producer.

---

## Inventory (PE32 bodies, P3.70 vs P3.80)

Multiple instances per name exist (Rome FV at index `7/`, Milan FV at index `20/`). The diff pattern below is identical across all instances; reported here are the Rome-side bodies.

| Module           | Size (B) | P3.70 md5    | P3.80 md5    | Identical? |
|------------------|---------:|--------------|--------------|:----------:|
| AmdRasSspDxe     |   24,864 | 62bee9e25ebe | ff692584f5bc | no         |
| AmdRasSspSmm     |   32,544 | b2b1b5044c45 | b2b1b5044c45 | **yes**    |
| PciDxeInit (Rome)|   27,904 | 8fd4d69071f3 | f20a7daa7d75 | no         |
| PciDxeInit (Milan)| 19,008 | 870ebce5d3ab | 870ebce5d3ab | **yes**    |
| PciBus (Rome)    |   94,304 | 5b22e2cd7c34 | 43f6bdc9c641 | no         |
| PciBus (Milan)   |   87,456 | 19038421887f | 19038421887f | **yes**    |
| PciRootBridge (Rome) | 51,328 | 0a90aeb059a7 | 737843e5bcff | no         |
| PciRootBridge (Milan)| 42,464 | 8090730fd6db | 8090730fd6db | **yes**    |

All differing pairs have **byte-identical PE section layouts** (every section's `.VirtualAddress`, `.VirtualSize`, `.PointerToRawData`, `.SizeOfRawData` is unchanged P3.70 → P3.80). No code or data growth.

---

## Diff windows (the actual changed bytes)

Coalesced contiguous diff regions, all in `.text`:

| Module          | # diff windows | total Δ bytes | Locations                                           |
|-----------------|---------------:|--------------:|-----------------------------------------------------|
| AmdRasSspDxe    | 2              | 25            | `0xfe4` (1 B), `0x10a1..0x10b8` (24 B; 2 hits in 1 grouped window) |
| PciDxeInit      | 2              | 2             | `0x1c1c`, `0x1e0f`                                  |
| PciBus          | 3              | 3             | `0x90df`, `0x912d`, `0xd7d2`                        |
| PciRootBridge   | 4              | 4             | `0x204d`, `0x2098`, `0x681a`, `0x7ffe`              |

**All differing bytes occupy the same position in a recurring 11-byte instruction pair:**

```
P3.70:  b9 XX 02 00 00      ff 50 NN     ; mov ecx, 0x2XX  ;  call [rax+NN]
P3.80:  b9 (XX+1) 02 00 00  ff 50 NN     ; mov ecx, 0x2(XX+1) ; call [rax+NN]
                ^^^
              this is the only byte that changed
```

Concrete examples (12 B each, P3.70 → P3.80):

| Module        | Offset   | P3.70 bytes (LO byte of token)              | P3.80 bytes                                  | Token Δ          |
|---------------|----------|----------------------------------------------|----------------------------------------------|------------------|
| AmdRasSspDxe  | `0xfe4`  | `b9` **`91`** `02 00 00 ff 50 08`            | `b9` **`92`** `02 00 00 ff 50 08`            | `0x291 → 0x292` |
| AmdRasSspDxe  | `0x10a1` | `b9` **`92`** `02 00 00 ff 50 30`            | `b9` **`93`** `02 00 00 ff 50 30`            | `0x292 → 0x293` |
| AmdRasSspDxe  | `0x10b8` | `b9` **`93`** `02 00 00 ff 50 10`            | `b9` **`94`** `02 00 00 ff 50 10`            | `0x293 → 0x294` |
| PciDxeInit    | `0x1c1c` | `b9` **`d5`** `02 00 00 ff 90 88 00 00 00`   | `b9` **`d6`** `02 00 00 ff 90 88 00 00 00`   | `0x2d5 → 0x2d6` |
| PciDxeInit    | `0x1e0f` | `b9` **`d5`** `02 00 00 ff 50 18`            | `b9` **`d6`** `02 00 00 ff 50 18`            | `0x2d5 → 0x2d6` |
| PciBus        | `0x90df` | `b9` **`d2`** `02 00 00 ff 90 a0 00 00 00`   | `b9` **`d3`** `02 00 00 ff 90 a0 00 00 00`   | `0x2d2 → 0x2d3` |
| PciBus        | `0x912d` | `b9` **`d2`** `02 00 00 ff 90 a0 00 00 00`   | `b9` **`d3`** `02 00 00 ff 90 a0 00 00 00`   | `0x2d2 → 0x2d3` |
| PciBus        | `0xd7d2` | `b9` **`d3`** `02 00 00 ff 50 28`            | `b9` **`d4`** `02 00 00 ff 50 28`            | `0x2d3 → 0x2d4` |
| PciRootBridge | `0x204d` | `b9` **`d2`** `02 00 00 ff 50 30`            | `b9` **`d3`** `02 00 00 ff 50 30`            | `0x2d2 → 0x2d3` |
| PciRootBridge | `0x2098` | `b9` **`d2`** `02 00 00 ff 50 30`            | `b9` **`d3`** `02 00 00 ff 50 30`            | `0x2d2 → 0x2d3` |
| PciRootBridge | `0x681a` | `b9` **`d2`** `02 00 00 ff 50 30`            | `b9` **`d3`** `02 00 00 ff 50 30`            | `0x2d2 → 0x2d3` |
| PciRootBridge | `0x7ffe` | `b9` **`d5`** `02 00 00 ff 50 18`            | `b9` **`d6`** `02 00 00 ff 50 18`            | `0x2d5 → 0x2d6` |

**Pattern interpretation:** every changed byte is the low byte of a 32-bit immediate loaded into `ECX` immediately before an indirect `call [rax+N]` (PE/EFI vtable dispatch). `ECX` carries the **first argument** under the Windows x64 ABI — so this is a token ID being passed to a service function. The **same token (e.g. `0x2D2`) shifts to the next ID (`0x2D3`) in lockstep across multiple unrelated modules** (PciBus, PciRootBridge, PciDxeInit all reference `0x2D2 → 0x2D3` at the same call signature `ff 50 30` / `ff 90 a0`).

Lockstep renumbering across multiple modules with no other change = a **shared global token table** (PCD database, gReportStatusCode codes, AMI proprietary status-code registry, or similar) had **one entry inserted between IDs 0x291 and 0x2D5**, pushing every consumer's references up by exactly +1. This is a **build-system byproduct**, not a Gen4-relevant code change.

---

## Bit-6 / `+0x2E` byte-pattern scan (full set)

Patterns from `APCB_DXEV3_DIFF.md` plus extended sliding-window encodings, applied to all PE32 bodies (both differing pairs and byte-identical Rome bodies):

| Pattern                                              | AmdRasSspDxe | AmdRasSspSmm | PciDxeInit | PciBus    | PciRootBridge |
|------------------------------------------------------|:------------:|:------------:|:----------:|:---------:|:-------------:|
| `or  byte [r+0x2e], 0x40` (8/32-disp, no SIB / SIB)  |    0 / 0     |    0 / 0     |   0 / 0    |  0 / 0    |    0 / 0      |
| `test byte [r+0x2e], 0x40` (8/32-disp)               |    0 / 0     |    0 / 0     |   0 / 0    |  0 / 0    |    0 / 0      |
| `and byte [r+0x2e], 0xbf` (clear bit 6)              |     0        |      0       |     0      |    0      |       0       |
| `mov al, [r+0x2e]`                                   |     0        |      0       |     0      |    0      |       1       |
| `mov [r+0x2e], 0x40`                                 |     0        |      0       |     0      |    0      |       0       |
| Generic `[op] byte [r+0x2e]` (any opcode)            |     0        |      0       |     0      |    0      |       1       |
| `byte [r+0x1d]`                                      |     0        |      0       |     0      |    3      |       0       |
| `byte [r+0x34]`                                      |     0        |      0       |     0      |    0      |       0       |

The sole hits — PciBus's three `byte [r+0x1d]` references at `0x45c5 / 0x852c / 0x10146`, and PciRootBridge's single `mov al, [r+0x2e]` at `0x6a68` — are **identical in P3.70 and P3.80** (same offsets in both versions), so even if they were touching the descriptor (they aren't — these are generic PCI config-space accesses, where `+0x2E` is the Subsystem ID register and `+0x1D` is the Secondary Bus / Capability pointer area), they pre-exist P3.80 and are not the rev-1.03 unlock.

**Conclusion: no bit-6/`+0x2E` manipulation appears in any of these binaries, in any version, in any encoding.**

---

## String diff (P3.80 minus P3.70)

For every differing pair, **the set of ASCII strings ≥ 6 chars and the set of UTF-16LE strings ≥ 6 chars are identical**:

| Module          | strings only-in-P3.80 | strings only-in-P3.70 |
|-----------------|----------------------:|----------------------:|
| AmdRasSspDxe    | 0                     | 0                     |
| PciDxeInit      | 0                     | 0                     |
| PciBus          | 0                     | 0                     |
| PciRootBridge   | 0                     | 0                     |

No new occurrences in any module of: `Gen4`, `GEN4`, `ESM`, `DXIO`, `Engine`, `Strap`, `Rev`, `Board`, `Synth`, `Descriptor`, `1.02`, `1.03`, `AttemptEsm`, `LinkSpeed`, `TargetLink`, `PcieGen`, `BoardId`, `BoardRev`, `PortDescriptor`. (Most of these strings are absent from these modules entirely — these are PCI-bus / RAS modules, not DXIO/AGESA-pcie modules.)

PciBus does carry the only Gen4-adjacent string in this set: `"AMI PCI Bus Driver"` and `"PCI_DEV_%X_PCI"` etc. — generic PCI enumeration strings, no Gen-related content. Verified via `mcp__radare2__list_strings`.

---

## BDF '40 01 03' (the lone Gen4-capable non-slot port)

| Module        | hits | versions | location | meaning |
|---------------|------|----------|----------|---------|
| PciBus        | 1    | both, identical offset | `.data` (string table) | part of `"PCI_DEV_%X..."` token — coincidental byte sequence, not a hardcoded BDF |
| (others)      | 0    | —        | —        | —       |

No module has a true hardcoded reference to BDF `40:01.3`.

---

## Per-module verdicts

### `AmdRasSspDxe`
Same-size, 25-byte diff in 1 region, all of which is **3 token-ID increments** in the recurring `mov ecx, imm32 ; call [rax+N]` pattern. No new strings, no new sections. **Not the producer.**

### `AmdRasSspSmm`
**Byte-identical** P3.70 = P3.80. Pattern scans for bit-6 / `+0x2E`: zero hits. **Not the producer.**

### `PciDxeInit`
Same-size, 2-byte diff (single token-ID `0x2d5 → 0x2d6` referenced twice). No new content. **Not the producer.** This module is also Generic-AMI PCI init, not AGESA — would not house DXIO synthesis a priori.

### `PciBus`
Same-size, 3-byte diff (token IDs `0x2d2/0x2d3 → 0x2d3/0x2d4`). String table has `"AMI PCI Bus Driver"` — pure UEFI PCI-bus enumeration code, not pre-AGESA Gen-cap logic. The 3 `[r+0x1d]` and zero `[r+0x2e]` semantic hits are PCI config-space accesses unrelated to DXIO descriptors. **Not the producer.**

### `PciRootBridge`
Same-size, 4-byte diff (token IDs `0x2d2 → 0x2d3` ×3, plus `0x2d5 → 0x2d6` ×1). Single `mov al,[r+0x2e]` is a generic byte-load against PCI config space (Subsystem ID register), present unchanged in both versions. **Not the producer.**

---

## Cross-module synthesis: token renumbering hypothesis

The **only** semantic change across all four differing modules is **+1 to selected global-table token IDs**. The shifted IDs cluster in two ranges:

- `0x291..0x294` (AmdRasSspDxe only)
- `0x2D2..0x2D6` (PciDxeInit, PciBus, PciRootBridge — all three reference this range)

The lockstep behavior across modules built and shipped together strongly indicates a **shared resource table** (PCD database, AMI status-code, or DXE protocol GUID enumeration) had **one or two entries inserted** between P3.70 and P3.80 build dates. This is a build-system artifact unrelated to AGESA / DXIO / Gen4. None of the changes touch:

- PCIe config space LnkCap2 fields
- Per-port DXIO descriptor structures
- Bit 6 of byte `+0x2E` of any structure
- ESM enable flags
- Board-rev MMIO straps

---

## Producer location: still unknown

All five candidate DXE/SMM modules from the rebase-aware shortlist are now eliminated. Combined with prior work, the cumulative elimination is:

| Layer        | Modules eliminated                                                        |
|--------------|---------------------------------------------------------------------------|
| PEI          | exhaustive (per `PEI_PRODUCER_SWEEP.md`)                                  |
| AGESA-DXE    | `AmdNbioPcieDxe` (consumer, not producer; per `RADARE2_NBIOPCIE.md`)      |
| AGESA-DXE    | `AmdApcbDxeV3` (per `APCB_DXEV3_DIFF.md`)                                 |
| AGESA-RAS    | `AmdRasSspDxe`, `AmdRasSspSmm` (this doc)                                 |
| OEM-shim     | `AmdPlatformRasSspDxe`, `AmdPlatformRasZpDxe` (per `OEM_SHIM_HUNT.md`)    |
| Generic UEFI | `PciDxeInit`, `PciBus`, `PciRootBridge` (this doc)                        |

**The producer of bit 6 of `+0x2E` is not in any unencrypted DXE/SMM module differing between P3.70 and P3.80.**

This is a strong negative result. The remaining possibilities, in order of plausibility:

1. **The producer pre-exists in P3.70 and is fed via a different data input in P3.80.** The producer is a byte-identical module across the two versions, but it reads a token / PCD / PCH-strap / fuse / SPD / ROM-data blob whose **value** changed. Because we found no per-port descriptor manipulation in any unencrypted module at all (in any version), this is the leading hypothesis. The candidate next-target shifts to **the data source** rather than code: APCB tokens (already shown identical body bytes — but the *shadow-copy commit logic changed in P3.80*, per `APCB_DXEV3_DIFF.md`, suggesting a runtime-mutated APCB token may carry the unlock); `AmdCpmOemInitDxe` PCD writes; ASRock OEM SPI scratch areas; AMD MicroBIOS / SMU firmware blob updates.

2. **The producer lives in a PSP-encrypted blob** (ABL-stage code that runs before any DXE module gets control). The unlock would be in the ABL or microBIOS firmware delivered with the AGESA package, not in the BIOS PE32 universe at all. This would explain the total absence of bit-6/`+0x2E` manipulation across every unencrypted module sweeped to date.

3. **The producer was missed by name pattern.** A handful of modules in the 85-differs list (e.g. `AmdNbioBaseSspDxe`, `AmdNbioBaseSspSmm`, `AmdCpmPcieInitDxe`, raw-GUID modules whose UI section was missing) have not yet been individually disassembled. Worth one final sweep before declaring (2) terminal.

**Recommended next move:** disassemble `AmdNbioBaseSspDxe` and `AmdCpmPcieInitDxe` if they exist in the 85-differs list. If those also lack `+0x2E`/bit-6 manipulation, the conclusion **"producer is in a PSP-encrypted blob — no static analysis path remains"** is justified, and the project terminates on the no-flash side.
