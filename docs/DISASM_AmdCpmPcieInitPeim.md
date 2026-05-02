# AmdCpmPcieInitPeim P3.70 vs P3.80 — disassembly diff

**Date:** 2026-04-27
**Goal:** determine whether `AmdCpmPcieInitPeim.efi` produces or mutates the per-port DXIO descriptor's `+0x2E` bit 6 (the Gen4/ESM enable flag identified by Subagent #5), and whether anything changed between BIOS P3.70 and P3.80.
**Verdict (executive summary):** **NEGATIVE on every axis.** This PEIM is a tiny stub (1 032 byte TE image, ~700 bytes of `.text`) that only registers PPIs and walks an FFS directory. It contains **no Gen4/ESM/DXIO/descriptor logic**, **no MMIO reads to a board-rev strap**, **no APCB token getter calls**, and **no bit-6 / `+0x2E` byte manipulation**. The P3.70 ↔ P3.80 diff is **purely a relocation shift** (`ImageBase` changed by exactly −0x20); zero semantic code changes. The companion `AmdCpmPcieInitDxe.efi` is **byte-identical** between the two versions. This module is not the descriptor producer and is not where the rev-1.03 unlock lives.

---

## Tool availability

- `radare2 6.1.4` — installed and working.
- `python3` — used for TE-header parsing and reloc-aware byte diffing.
- No `pefile` needed (TE format, not PE).
- Module bodies copied to `/tmp/peim_p370.bin` and `/tmp/peim_p380.bin`.

---

## Files examined

`AmdCpmPcieInitPeim` appears **twice** per BIOS image (Rome volume + Milan volume), both as TE images (PEIMs are emitted in TE format to save space), plus a companion DXE driver:

| Module                    | Volume / index                                  | Size (P3.70) | Size (P3.80) | sha256 P3.70 ↔ P3.80 |
|---------------------------|-------------------------------------------------|--------------|--------------|----------------------|
| `AmdCpmPcieInitPeim` (Rome) | `61C0F511-…/8 / 53`                              | 1 032 B      | 1 032 B      | **differ** (15 bytes) |
| `AmdCpmPcieInitPeim` (Milan)| `61C0F511-…/21 / 49`                             | 1 184 B      | 1 184 B      | **identical**         |
| `AmdCpmPcieInitDxe` (Rome)  | `4F1C52D3-…/7 / .../68`                          | 2 080 B      | 2 080 B      | **identical**         |
| `AmdCpmPcieInitDxe` (Milan) | `4F1C52D3-…/20 / .../60`                         | 2 112 B      | 2 112 B      | **identical**         |

Only the Rome-side PEIM differs. All other instances are byte-for-byte unchanged across the rev-1.03 boundary. Sizes are tiny (~1 KB PEIM, ~2 KB DXE), implying these are stubs that bind PPI/Protocol GUIDs and dispatch to the real init code in `AmdNbioBaseSspDxe` / `AmdApcbDxeV3` / `AmdNbioPcieDxe`.

---

## Byte diff of the Rome PEIM (1 032 B → 1 032 B)

15 bytes differ. All exhibit a uniform delta of **−32** (=−0x20), or are part of a 16-bit immediate that wraps with the same delta:

```
off=0x0010  0x44 -> 0x24  (delta=-32)   ← TE header ImageBase low byte
off=0x00bd  0x74 -> 0x54  (delta=-32)
off=0x00e5  0x98 -> 0x78  (delta=-32)
off=0x00ec  0x84 -> 0x64  (delta=-32)
off=0x011f  0x44 -> 0x24  (delta=-32)
off=0x016d  0x44 -> 0x24  (delta=-32)
off=0x019f  0x98 -> 0x78  (delta=-32)
off=0x0200  0x98 -> 0x78  (delta=-32)
off=0x020b  0x1c -> 0xfc  ┐  16-bit value 0x031c -> 0x02fc (delta=-32)
off=0x020c  0x03 -> 0x02  ┘
off=0x02ec  0x64 -> 0x44  (delta=-32)
off=0x02f6  0x90 -> 0x70  (delta=-32)
off=0x03ac  0x54 -> 0x34  (delta=-32)
off=0x03b0  0x33 -> 0x13  (delta=-32)
off=0x03b8  0xd8 -> 0xb8  (delta=-32)
```

TE header confirms the cause:

| field          | P3.70          | P3.80          | delta |
|----------------|----------------|----------------|-------|
| sig            | 0x5A56 (`VZ`)  | 0x5A56         | —     |
| machine        | 0x14C (i386)   | 0x14C          | —     |
| nsec           | 3              | 3              | —     |
| StrippedSize   | 0x1C0          | 0x1C0          | —     |
| AddrOfEntry    | 0x240          | 0x240          | —     |
| BaseOfCode     | 0x240          | 0x240          | —     |
| **ImageBase**  | **0xFFE40044** | **0xFFE40024** | **−0x20** |
| Reloc dir RVA  | 0x560          | 0x560          | —     |
| Reloc dir size | 0x24           | 0x24           | —     |

Section table (.text=0x2c0 raw, .data=0x60, .reloc=0x40) is identical between versions.

After masking ±3 bytes around each diff site (i.e. zeroing the immediate/operand carrying an absolute address), the residual diff is **0 bytes**. Every difference is a relocation fixup pointing at an address that shifted by exactly the ImageBase delta. No instruction added, removed, or modified.

This means PI dispatcher chose to load the PEIM at a slightly different fixed address in P3.80 (likely because some upstream PEIM grew). The PEIM's compiled code is unchanged.

---

## Pattern search — Gen4/ESM/descriptor signals (both versions)

Run against both binaries. Every value below is **0** unless noted. Searching for the descriptor-mutation patterns identified by Subagent #5:

| Pattern                                          | P3.70 | P3.80 |
|--------------------------------------------------|------:|------:|
| `or  byte [reg+0x2e], 0x40` (`83 .. 2e 40`)      |     0 |     0 |
| `or  byte [reg+0x2e], 0x40` (`80 .. 2e 40`)      |     0 |     0 |
| `and byte [reg+0x2e], 0xBF` (`83 .. 2e bf`)      |     0 |     0 |
| `test byte [reg+0x2e], 0x40` (`f6 .. 2e 40`)     |     0 |     0 |
| 32-bit immediate `0x0000002E`                    |     0 |     0 |
| MMIO load from `0xFEDxxxxx` region (LE pattern)  |     0 |     0 |
| MMIO load from `0xFD0xxxxx` region (LE pattern)  |     0 |     0 |
| String `ESM`                                     |     0 |     0 |
| String `Gen4`                                    |     0 |     0 |
| String `DXIO`                                    |     0 |     0 |
| String `Strap`                                   |     0 |     0 |
| String `Rev` / `1.03`                            |     0 |     0 |
| String `Descriptor` / `Engine` / `Port`          |     0 |     0 |
| String `APCB` / `Token`                          |     0 |     0 |
| Immediate `0x40 00 00 00`                        |     1 |     1 |

The single hit on `0x40000000` immediate is at file offset `0x88` and is the literal `mov dword [eax+0x18], 0x80000000` style HOB descriptor field initializer (size = `0x80000000` sentinel — an UEFI HOB head/tail marker, not a Gen4 enable). It is identical in both versions.

`strings` confirms zero PCIe-relevant text:

```
.text   .data   .reloc   WWh{D|$}   $$A26P   h$A27P   h$A22P   h$A25P   h$A17P
Qj0V    GvgN    U2}2     4D5H5P5
```

The `$A2xP` fragments are not strings — they are ASCII-printable byte runs inside immediate values pushed onto the stack as part of GUID-pointer arguments to PPI install routines (`PeiServicesInstallPpi` callers). They do not denote a string-mode operation.

---

## What this PEIM actually does

Disassembling `.text` (file 0x80–0x340, image RVA 0x240–0x500) reveals a textbook PI dispatcher stub of three small functions:

- `entry0` (0x2e8 file / 0x4a8 RVA) — 54 bytes. Reads the FileHandle, retrieves the PEI services table, calls into `main`.
- `main` (0x240 file / 0x400 RVA) — 104 bytes. Walks an array of GUIDed structures, calling indirect through service-table offsets `+0x18` (`InstallPpi`), `+0x4C` (`LocatePpi`), `+0x54` (`NotifyPpi`). Five iterations correspond to the five `$A2xP` GUID fragments visible above (five PPI/notify entries).
- `fcn.000000f0` (0x2b0 file / 0x470 RVA) — 12 bytes. Trivial helper.

The code structure matches the EDK2 idiom for a "PPI registration shim": no I/O, no PCI config access, no MMIO, no SMN access. It cannot itself produce a DXIO descriptor — it has no code to do so.

The companion `AmdCpmPcieInitDxe.efi` (2 080 B, byte-identical between versions) is similarly small and almost certainly the equivalent DXE-phase shim.

The actual PCIe descriptor producer must be elsewhere. Likely candidates remain (in priority order):

1. `AmdNbioBaseSspDxe` — main NBIO init driver. Largest PCIe-related module on disk.
2. `AmdNbioSmuV2Dxe` / `AmdNbioSmuV9Dxe` — SMU mailbox path that some AGESA versions use to push Gen4 enable straps.
3. `AmdPlatformRasSspDxe` — platform-RAS may run before NBIO and stuff the GPU-slot descriptors.
4. ASRock's `Setup` HII module (large, board-specific) — could intercept and rewrite the descriptor table during `gAmdCpmTablePpiGuid` notification.

---

## Cross-check: P3.70 ↔ P3.80 diff at the FFS directory level

To make sure nothing relevant got renamed/moved between versions, the FFS file-tree was compared:

```
$ diff <(find extracted/all/P3.70/img.bin.dump -iname '*CpmPcie*' | sort) \
       <(find extracted/all/P3.80/img.bin.dump -iname '*CpmPcie*' | sort)
```

Output: identical paths, same indices. No new `AmdCpmPcie*` module was added in P3.80 and none was removed.

---

## Implications

- **`AmdCpmPcieInitPeim` is ruled out** as the descriptor producer or as the rev-1.03 gate. It is a PPI shim, not init logic; and its only difference between P3.70 and P3.80 is one ImageBase byte.
- The +64 B in `AmdApcbDxeV3` (per `docs/APCB_DXEV3_DIFF.md`) and the +320 B in `CbsSetupDxeSSP` (per `docs/CBSSETUP_DIFF.md`) are now both falsified leads. Combined with the present negative result, **none of the AMD Cpm/Apcb/Cbs DXE/PEI modules grown in P3.80 contain bit-6 manipulation**.
- This narrows the producer search significantly. The bit-6 setter must live in one of: `AmdNbioBaseSspDxe`, `AmdCpmOemInitDxe`, `AmdPlatformRasSspDxe`, `AmdNbioSmuV2Dxe`, `AmdNbioSmuV9Dxe`, `AmdNbioPcieMacSspDxe`, or the ASRock `Setup` HII / OEM driver.
- Cross-version diff (`docs/CROSS_VERSION_DIFF.md`) should be re-consulted to identify which of those modules grew in P3.80 — those are the next disassembly targets.

---

## Next-step recommendation

1. Re-run the cross-version size diff filtered to all modules whose name matches `Amd.*Nbio.*` or `Amd.*Pcie.*` or `AmdCpm.*Init.*Dxe`, and rank by P3.70→P3.80 size delta. The next disassembly subagent gets the top non-zero entry that hasn't been examined.
2. If `AmdNbioBaseSspDxe` is byte-identical (very plausible — that's what the AGESA pattern would predict, since AGESA is "frozen" once shipped), the bit-6 setter must be in OEM glue code: `AmdCpmOemInitDxe` / ASRock `Setup` callback / `AmdPlatformRasSspDxe`.
3. If **all** Rome-side AMD modules are byte-identical between P3.70 and P3.80, the unlock likely lives in a code path that synthesizes descriptors *unconditionally* but reads its source data from a token table that *did* change between versions. Subagent #1 already showed APCB body bytes are identical, so the source must be either (a) a non-APCB hard-coded table inside one of the larger DXE drivers, or (b) the BIOS build-time platform configuration baked into one of ASRock's `Setup`/OEM modules.

The single highest-leverage next move is a **size-delta-ranked diff of every Rome-side DXE module**, then disassembly of the largest delta. `docs/CROSS_VERSION_DIFF.md` already has most of this data — needs filtering and re-prioritization given the cumulative negative results from `AmdApcbDxeV3` (#1b), `CbsSetupDxeSSP` (item 6), and now `AmdCpmPcieInitPeim`.
