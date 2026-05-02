# AmdNbioBaseSspPei P3.70 vs P3.80 — disassembly

**Date:** 2026-04-27
**Goal:** determine whether `AmdNbioBaseSspPei.efi` is the per-port DXIO descriptor producer that sets bit 6 of `+0x2E` on the per-port descriptor, and whether anything about it changed between P3.70 and P3.80.
**Verdict (executive summary):** **NOT THE PRODUCER.** This PEIM does HDAudio verb-table programming, NonPCI-device MMIO BAR allocation, GNB TOM2/TOM3 setup, IDS NV table provisioning, and GNB PCD blast-table dispatch. It contains **no** access to byte offset `+0x2E` of any structure, **no** uses of immediate `0x40` against a `+0x2E` displacement (in any encoding), **no** DXIO/Gen4/ESM/Strap/Descriptor strings, and **no** APCB-token getter calls. It is also **byte-identical between P3.70 and P3.80** (md5 `2023043750d0df5309e6b32975924e72`), so it cannot be the host of any rev-1.03 / P3.80 unlock logic.

---

## Locating

Single instance per BIOS image, in FV `61C0F511-A691-4F54-974F-B9A42172CE53` (FV8):

| version | path | TE-section size | FFS body size |
|---|---|---:|---:|
| P3.70 | `extracted/all/P3.70/img.bin.dump/8 .../29 AmdNbioBaseSspPei/1 TE image section/body.bin` | 39 712 | 39 846 |
| P3.80 | `extracted/all/P3.80/img.bin.dump/8 .../29 AmdNbioBaseSspPei/1 TE image section/body.bin` | 39 712 | 39 846 |

```
md5 P3.70: 2023043750d0df5309e6b32975924e72
md5 P3.80: 2023043750d0df5309e6b32975924e72
```

**Byte-identical.** No other instance exists in either image. FV21 (`61C0F511-...`) contains `AmdNbioBaseGnPei` (Genoa-family variant; different SoC, irrelevant on this Rome board). The DXE counterpart `AmdNbioBaseSspDxe` lives in a different FV; per `docs/DISASM_AmdNbioBaseSspDxe.md` it has no `+0x2E` access either.

Format: TE (Terse Executable), Intel i386, 32-bit, EFI Boot Service Driver, base `0xffdf4af8`. Loaded with radare2 6.1.4 (`r2 -A`), 336 functions discovered.

---

## Pattern scan for the Gen4 marker

Scanned the full 39 712-byte `.text+.data` blob for every encoding of "touch byte at `+0x2E`":

| pattern | meaning | hits |
|---|---|---:|
| `80 4? 2E 40` | `or byte ptr [reg+0x2E], 0x40` (disp8) | **0** |
| `F6 4? 2E 40` | `test byte ptr [reg+0x2E], 0x40` | **0** |
| `C6 4? 2E 40` | `mov byte ptr [reg+0x2E], 0x40` | **0** |
| `80 6? 2E ??` | `and byte ptr [reg+0x2E], imm8` | **0** |
| `80 7? 2E 40` | `cmp byte ptr [reg+0x2E], 0x40` | **0** |
| `2E 40` anywhere | sliding-window catch-all | **0** |
| `40 2E` anywhere | reverse sliding-window | **0** |

Zero hits in any form. The producer-of-`+0x2E`-bit-6 is not in this binary.

(For comparison: `AmdNbioPcieDxe` P3.70 has the canonical `F6 46 2E 40` at file offset `0x14B1E`, the consumer site identified by subagent #5; `AmdNbioPciePei` has another bit-6 consumer at `0x2F53` per `docs/DISASM_AmdNbioPciePei.md`.)

---

## Strings inventory — what this PEIM actually does

Every human-readable string extracted (only the meaningful ones shown):

```
HDAudioVerbTableSetting              -- HDAudio codec verb-table programming
HDAudio ID = 0x%x
NbioConfigureVerbTable: ...
::SendCodecCommand Data = %x
::CodecStateMap = %x
ERROR::HdaBaseAddress == 0 || VerbTableAddress == NULL

AmdNbioBaseInit                      -- entry function tag
AmdNbioBasePeiEntry
NbioTopologyConfigureCallbackPpi     -- topology PPI consumer
%a Entry / %a Exit                   -- generic trace prologue/epilogue

AmdMemoryInfoHob NOT FOUND!!         -- consumes memory-info HOB
MSR TOP_MEM2[63:32] is 0x%08x        -- TOM2 MSR programming
MSR TOP_MEM2[31:0] is 0x%08x
GnbSetTomSSP setting GnbTom2 to 0x%x
GnbSetTomSSP setting GnbTom3 to 0x%x
upper_tom2 / lower_tom2 / tom3_limit -- TOM3 limit programming
R S3 SAVE Script: Address ...        -- S3 resume save-script entry

FabricAllocateMmio v3                -- non-PCI device MMIO allocation
NON_PCI_DEVICE_BELOW_4G / ABOVE_4G
ERROR: No below 4G MMIO on Socket %X Rb %X
PcdAmdMmioSizePerRbForNonPciDevice
PcdAmdAbove4GMmioSizePerRbForNonPciDevice
NonPCIBarInit
%a : Begin to allocate bars for SMN low %x high %x ...

DeterminePcdValue                    -- token-driven PCD evaluator
GNB_ENTRY_PCD_WR / GNB_ENTRY_PCD_RMW -- generic register-table parser
Blasted PCD WR entry. / Blasted PCD RMW entry.
GnbBlastTable / OtherTypeHandler     -- AGESA "blast table" dispatcher
GnbEntryCpuDeadLoop                  -- diagnostic halt
STALL is not needed nor implemented as of now.
ERROR!!! Register table parse

IdsHookFunc HookId %x                -- IDS NV-table provisioning
IdsNvTableSize return 0, exit
Get IdsNV table size 0x%x
Allocate Heap fail, exit
GetIdsNvTable Status return fail, exit
CBS data exceed the boundary
```

**Not present anywhere** (substring-searched the raw `.text`+`.data`):

```
Gen4   ESM   DXIO   Engine   Port
Strap   Rev   1.02   1.03   Descriptor
PcieEngine   PciePort   PcieEsm   AttemptEsm
APCB_TOKEN   ApcbToken   PSP_TOKEN
```

---

## Function-call surface

`r2 -A` discovered 336 functions, none symbolic (TE strips). Strings indicate the only PPI this PEIM publishes/consumes is **`NbioTopologyConfigureCallbackPpi`** — i.e. it registers itself for the *topology configuration* phase, but the strings in the body show it only supplies HDAudio + non-PCI MMIO + TOM/TOM2/TOM3 + IDS-NV during that callback, not per-port DXIO descriptors. There is no `BuildGuidHob`-style descriptor publication string ("PortDescriptorHob", "DxioComplexHob", "GnbHob") and no string referencing per-port slot identifiers.

Memory-mapped IO immediates (32-bit LE constants):
- 36 occurrences of `0xFD0xxxxx` / `0xFEDxxxxx` — i.e. NBIO SMN fabric base + LAPIC/HPET addresses. Consistent with TOM/MMIO programming and S3 save-script generation. **None** are GPIO bank addresses (`0xFED81500`/`0xFED81100`-style) used for board-rev strap detection — verified by inspection of the address list. No board-rev MMIO read.

---

## P3.70 vs P3.80 diff

```
$ md5sum P3.70/.../1\ TE\ image\ section/body.bin
2023043750d0df5309e6b32975924e72  body.bin
$ md5sum P3.80/.../1\ TE\ image\ section/body.bin
2023043750d0df5309e6b32975924e72  body.bin
```

**Byte-identical.** No diff to disassemble; whatever changed in P3.80 to enable Gen4 on rev-1.03 boards, it is **not** in this PEIM.

---

## Conclusion

`AmdNbioBaseSspPei` is **not** the per-port DXIO descriptor producer. It is a non-DXIO infrastructure PEIM responsible for:

1. HDAudio codec verb-table programming
2. Non-PCI device MMIO BAR allocation (FabricAllocateMmio v3)
3. GNB TOM2 / TOM3 MSR setup
4. AGESA "blast table" PCD register dispatch
5. IDS NV table provisioning
6. S3 save-script entry

It does not touch byte `+0x2E` of any structure, never uses immediate `0x40` against a `+0x2E` displacement, has no DXIO/Gen4/ESM strings, and has no APCB-token getter calls. It is also unchanged between P3.70 and P3.80, so cannot host the rev-1.03 unlock.

Combined with the prior negative results on `AmdNbioBaseSspDxe` (DXE counterpart, also no `+0x2E`), `AmdApcbDxeV3` (the +64 B was unrelated APCB-shadow plumbing — see `docs/APCB_DXEV3_DIFF.md`), and the APCB blob itself (PSPG/MEMG/TOKN only — see `docs/APCB_DECODE.md`), the producer must lie elsewhere. The remaining viable candidates from the OEM-shim hunt are:

- **`AmdCpmPcieInitPeim`** — confirmed setter of bit 6 in `docs/DISASM_AmdCpmPcieInitPeim.md`; this remains the strongest producer candidate.
- **`AmdNbioPciePei`** — has the FV21/FV20 instance with a third bit-6 consumer at `0x2F53` per `docs/DISASM_AmdNbioPciePei.md`; needs follow-up to determine whether that site reads or writes.
- **`AmdCheckBmcPciePei`** — see `docs/DISASM_AmdCheckBmcPciePei.md`; consumer-side, not producer.

Recommended next step: sweep the remaining FV8/FV21 PEIMs that differ between P3.70 and P3.80 (`docs/MODULE_SWEEP_P3.70_vs_P3.80.md`) for the `+0x2E`/`0x40` pattern. The producer is one of those, or `AmdCpmPcieInitPeim`'s bit-6 set is the actual unlock site reached via a different path.
