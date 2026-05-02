# AmdNbioPciePei P3.70 vs P3.80 — disassembly diff

**Date:** 2026-04-27
**Goal:** disassemble `AmdNbioPciePei.efi` in P3.70 and P3.80 and diff them. Hypothesis: this PEI sibling of `AmdNbioPcieDxe` (already known byte-identical P3.70=P3.80 per `docs/CROSS_VERSION_DIFF.md` and `docs/RADARE2_NBIOPCIE.md`) may be where the per-port DXIO descriptor list is initially built before DXE consumers see it; the rev-1.03 / Gen4 unlock could plausibly live in this PEIM.

**Verdict (executive summary):** **null result.** Both `AmdNbioPciePei` instances in the BIOS image are **byte-identical between P3.70 and P3.80** (md5-confirmed, full file body and TE image section). No disassembly diff is meaningful — there are zero bytes to diff. The PEIM is structurally identical across the rev-1.03 / Gen4 boundary.

**Ancillary positive finding:** Although the diff is null, characterising the binary itself produced **a third confirmed bit-6 / `+0x2E` consumer site**, joining `AmdNbioPcieDxe` (subagent #5). The bit-6 read-and-act pattern is therefore present in both PEI and DXE phases, and is unchanged across P3.70/P3.80.

---

## File location and identity

Two distinct `AmdNbioPciePei.efi` binaries ship per image, in different firmware volumes:

| FV path | TE image size | md5 (TE body) | role |
|---|---|---|---|
| `8 61C0F511…/30 AmdNbioPciePei` | 73 704 B | `768db554a9ee219314b117169b4a6e89` | unknown — likely cold-boot / boot block PEIM |
| `21 61C0F511…/20 AmdNbioPciePei` | 63 968 B | `120c2997df10fa597dead6c06497878b` | unknown — likely main PEI dispatch volume |

Both md5s are **identical between P3.70 and P3.80**. Body-section md5s also identical:

```
P3.70/8/30  AmdNbioPciePei body.bin md5 = 8106856d6c65c27c0e8cd32d2c7269e9
P3.80/8/30  AmdNbioPciePei body.bin md5 = 8106856d6c65c27c0e8cd32d2c7269e9   IDENTICAL
P3.70/21/20 AmdNbioPciePei body.bin md5 = 99390e728e1c4fdd13cd4052aed74c4d
P3.80/21/20 AmdNbioPciePei body.bin md5 = 99390e728e1c4fdd13cd4052aed74c4d   IDENTICAL
```

`cmp` confirms zero differing bytes for both pairs.

`file(1)` characterisation:

```
TE (Terse Executable), Intel i386, sections 3 efi_boot_service_driver, stripped.
FV8/30:   image_base=0xffdfe6f8, entry=0x240, base_of_code=0x240
FV21/20:  image_base=0xffd2b4b8, entry=0x380, base_of_code=0x240
```

Both are **32-bit (i386) PEIMs**, distinct from the X64 DXE drivers we have analysed previously. PEIMs run in the Pre-EFI initialisation phase under the AMD AGESA PEI dispatch.

---

## What was actually checked

Since the task is a diff and the diff is null, the rest of this document is an **outline characterisation** of the PEIM, intended (a) to confirm the binary content is what the task hypothesis assumed it might be, and (b) to redirect the search to where it must actually live.

### 1. String-content scan

Both PEIMs contain DXIO/PCIe-init strings that are *substantively related* to the Gen4-enable question:

```
PcieSetSpeed                                  AmdNbioPciePeiEntry
PcieConfigurationInit                         DxioInitializationCallbackPpi
DxioCleanUpEarlyInitSP3                       DxioFindEarlyLink
DxioTopologyWorkarounds                       DxioManageTopology
DxioCfgBeforeDxioInit                         DxioCfgAfterReconfig
DxioCfgBeforeReconfig                         DxioUserCfgOverride
PcieEnablePorts                               PcieControlPorts
PcieGetDpcStatusData                          PcieConfigBeforeDxioInitCallback
"//////// PCIe Training Data /////////"
"DELI INFO for SocketId = %d InstanceId = %d, DescriptorId = %d"
"PCIe Port" / "SATA Port" / "Ethernet Port"
"  Engine Type - %a"  /  "    PortPresent - %d"
"<---------- PCIe User Config Start------------->"
"<---------- PCIe User Config End-------------->"
"Configure Port %d for CCIX"
" - writing strap 0x%x"  /  " - WrapId = 0x%x, StrapValue = 0x%x"
"set STRAP_LOWER_SKP_OS_GEN_SUPPORT = 0x%x"
"  Forcing Gen3 on this PCIe port for ESM sequence later."
"      EsmSupport     - %d"
"      EsmSpeedBump   - %d"
"    LinkSpeedCapability - %d"
"    maxLinkSpeedCap - %d"
"    targetLinkSpeed = %d"      (FV21 only)
"SPC: start/end [%d:%03d/%03d] gen3: %d"
```

i.e. this PEIM **does** participate in PCIe link-speed / ESM / DXIO descriptor processing. The hypothesis was structurally correct — it just didn't change.

**No** strings related to *board revision*, *board ID*, *strap shadow MMIO*, *rev 1.0\d*, or anything that would indicate a board-rev gating decision. Same in both versions, since both versions are the same bytes.

### 2. Bit-6 / `+0x2E` pattern scan

Subagent #5 located the Gen4-enable bit-6 read in `AmdNbioPcieDxe` at file off `0x14b1e`:

```
test byte [r14 + 0x2e], 0x40    ; X64
```

Pattern-scan of the PEIMs for the i386 32-bit equivalents (`test byte [reg+0x2e], 0x40` → `F6 4? 2e 40`, `mov` and `or` variants) finds **one occurrence** in the FV21/20 PEIM, **zero** in the FV8/30 PEIM.

```
FV21 (63 968 B):  test [edi+0x2e], 0x40   ;  F6 47 2e 40   at file off 0x2f53
                  je   +0x2a                                   off 0x2f57
FV8  (73 704 B):  no occurrences of the bit-6 / +0x2e pattern
```

Both versions of FV21 contain this byte sequence at the same offset (file is byte-identical).

The site sits inside `fcn.000026d1` (a large per-port configuration function, ~3 KB of code, called from elsewhere with two arguments — `arg_8h` is the per-port descriptor pointer in `edi`, `arg_10h` is a higher-level NBIO context structure). Decompiled excerpt:

```c
// fcn.000026d1 @ 0x2f53
v = byte [edi + 0x2e] & 0x40;
esi = arg_10h;
if (v) {
    // SMN write to 0x11180604 + (instance offset)
    eax = byte [ebx + 0xc];          // bus number / NBIO bus base
    ecx = byte [esi + 0xa];           // some sub-index
    edx = (eax + ecx*4) << 8;
    edx |= ((eax = byte [edi + 0x1d]) >> 4) & 7;   // NBIO instance from desc +0x1D
    edx <<= 0x14;
    edx += 0x11180604;                 // SMN target
    fcn.0000661b(edx, mask=0xfffffffe, value=1);  // SMN write helper
}
```

This is **the same architectural pattern** as `AmdNbioPcieDxe`'s `PcieAttemptEsmIfEnabled`: read bit 6 of `+0x2E` of the per-port descriptor, branch on it, perform a per-port SMN poke. Different SMN target (`0x11180604`, in the `0x111800xx` NBIF/PCIe-PHY-wrapper region — *not* the `0x11140xxx` IOHC strap region that hosts `LC_GEN4_EN_STRAP`), and different code phase (PEI, executed earlier than DXE), but **same gating bit and same descriptor field**.

### 3. SMN/MMIO-target enumeration

Looking for board-rev MMIO reads (`0xfedXXXXX` or `0xfd0XXXXX`, the AMD MP1/SMU/strap-shadow apertures): **zero occurrences** in either PEIM (same in P3.70 and P3.80). No board-rev gate in this binary — consistent with subagent #5's finding for the DXE counterpart.

SMN literals present (NBIO IOHC / NBIF wrapper region only):

```
0x11140008   0x11140040   0x11140080   0x11140084
0x11140280   0x11140284   0x11140288   0x11140290
0x11140294   0x111402c4   0x111402d4   0x111402d8
0x111402dc   0x111402ec   0x11140300   0x11140304
0x11140374   0x1114038c   0x11140390
0x11180040   0x11180070   0x11180078   0x11180080
0x11180100   0x1118018c   0x111802c0   0x11180428
0x11180460   0x111804d4   0x111804d8   0x11180604
```

Notable: `0x11140290` / `0x11140294` are very near `LC_GEN4_EN_STRAP`'s documented per-IOHC stride of `0x111402A4`. The PEIM does access this address neighbourhood — but we already know from subagent #2 that `LC_GEN4_EN_STRAP` is HwInit-locked and the relevant decision has already been made by the PSP/ABL by the time these PEIM SMN writes execute. This PEIM is touching adjacent registers (likely link-control / equalisation), not the strap itself.

Crucially, none of these literals or their fields differ between P3.70 and P3.80 — by definition, the binary is byte-identical.

### 4. Function map

`r2 -A` discovers 226 functions in the FV21 PEIM. By construction this count is identical in P3.70 and P3.80, and every byte at every offset matches — no diffing meaningful.

---

## Implications for the rev-1.03 / Gen4 unlock

This adds another binary to the **byte-identical-across-the-boundary** list. Updated table for the immediate per-port-descriptor pipeline:

| binary                | P3.70 vs P3.80 | role                                              |
|-----------------------|----------------|---------------------------------------------------|
| `AmdNbioPcieDxe`      | identical      | DXE consumer of bit 6 of `+0x2E` (subagent #5)    |
| `AmdNbioPciePei` (FV8 + FV21) | **identical** *(this analysis)* | PEI consumer of bit 6 of `+0x2E` |
| `AmdApcbDxeV3`        | +64 B (changed) | not the source — checksum/SPI-write fix only (`docs/APCB_DXEV3_DIFF.md`) |
| `AmdNbioBaseGnPei`    | identical      | NBIO PEI base library (this analysis, sibling check) |
| `AmdNbioIOMMUGNPei`   | identical      | IOMMU PEI                                         |
| `AmdNbioIOAPICPei`    | identical      | IOAPIC PEI                                        |
| `CbsBasePeiGN`        | identical      | CBS / setup base PEI                              |
| `AmdCpmOemInitPeim` (FV21/40) | identical | CPM OEM init (main copy)                         |
| `AmdCpmOemInitPeim` (FV8/43)  | **changed** (size 43 280 B, hash differs) | CPM OEM init (reset/early copy) — **new lead** |
| `AmdCpmPcieInitPeim` (FV21/49) | identical | CPM PCIe init (main copy)                        |
| `AmdCpmPcieInitPeim` (FV8/53)  | **changed** (size 1 032 B, hash differs)  | CPM PCIe init (early copy) — **new lead** |
| `AmdCheckBmcPciePei`  | identical      | BMC PCIe sideband detection                       |

Both consumer-side modules of bit 6 of `+0x2E` (`AmdNbioPcieDxe`, `AmdNbioPciePei`) are unchanged. The descriptor-list **producer** must therefore live elsewhere, and `AmdApcbDxeV3` has already been ruled out (`docs/APCB_DXEV3_DIFF.md`). Two **new** candidates surface from the sibling-PEIM hash table above:

1. **`AmdCpmOemInitPeim` (FV8/entry 43, 43 280 B)** — same size in P3.70 and P3.80 but **different content**. CPM ("Common Platform Module") OEM init runs in PEI with board-specific overrides. This is exactly the layer where ASRock would inject a board-rev-specific descriptor patch. **Highest-leverage offline lead remaining.**
2. **`AmdCpmPcieInitPeim` (FV8/entry 53, 1 032 B)** — same size, different content. Tiny — but at 1 KB, even a single bit-set on the descriptor list is structurally trivial to drop in. The early/reset-vector copy specifically; the main FV21/49 copy is byte-identical.

The fact that **only the FV8 (early/cold-boot) copies** of these two CPM PEIMs changed — while the FV21 (main dispatch) copies stayed identical — is itself a strong tell. The early/reset boot path is exactly where pre-PSP-handoff descriptor staging would live, and it is the only path that fired for both rev-1.02A and rev-1.03 boards uniformly until P3.80.

---

## Next steps (recommendations, not commits)

1. **Disassemble `AmdCpmOemInitPeim` FV8/43 P3.70 vs P3.80** (radare2). Same workflow as `AmdApcbDxeV3` diff. Goals:
   - Look for `or byte [reg+0x2e], 0x40` or `mov byte [reg+0x2e], imm8 with bit 6 set` writes (the producer mirror of the consumer pattern documented here and in `RADARE2_NBIOPCIE.md`).
   - Look for board-rev-strap MMIO reads (`0xfedXXXXX`, `0xfd0XXXXX`) — the rev-1.02A vs rev-1.03 gate.
   - Compare new functions / new strings; previous diff workflow in `docs/APCB_DXEV3_DIFF.md` is the template.

2. **Disassemble `AmdCpmPcieInitPeim` FV8/53 P3.70 vs P3.80** — small (1 032 B), should diff in minutes. May be where the actual descriptor patch lives.

3. **Defer further PEI/DXE consumer-side analysis** — both bit-6/+0x2E *consumers* are now confirmed unchanged across the boundary. The unlock is on the producer side, and the producer is no longer in the modules originally suspected.

---

## Provenance

- Files: `extracted/all/P{3.70,3.80}/img.bin.dump/{8,21} 61C0F511…/{30,20} AmdNbioPciePei/{1 TE image section/,}body.bin`
- Hashes: md5sum(1), GNU coreutils
- Disassembly: radare2 6.1.4-1, `aaa` analysis on FV21 P3.70 instance (loaded as raw TE; sections paddr==vaddr)
- Pattern scans: Python 3 + `re` (binary regex)
- All work in `/tmp/peipei/` (per task constraints — no commits, no `scripts/lib/` modification, no rig contact)
