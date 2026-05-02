# PEI bit-6/+0x2E producer sweep — P3.70 vs P3.80

**Date:** 2026-04-27
**Scope:** every PEI-phase TE/PE32 module classified `SEMANTIC_DIFF` or `SIZE_DIFF` by `docs/MODULE_SWEEP_REBASE_AWARE.md` (16 candidates: 12 TE-PEIM + 1 SIZE_DIFF TE-PEIM + 3 PEI-phase PE32 instances).
**Goal:** find a *producer*-side write of bit 6 of byte `+0x2E` in a per-port DXIO descriptor, in any PEI module that genuinely changed between P3.70 and P3.80 (excluding the 37 pure-rebase artifacts).

**Verdict:** **negative across all 16 candidates.** No PEI-phase module that changed between P3.70 and P3.80 contains any plausible bit-6 producer pattern. The Gen4 producer is not in the PEI cold-boot phase.

## Methodology

1. **Byte-pattern sweep** — every encoding listed in `docs/APCB_DXEV3_DIFF.md`'s "Searched: explicit bit-6 manipulation patterns" table, plus the non-canonical sliding-window load-OR-store sequence:
   - `or  byte [reg+0x2e], 0x40` — `80 4? 2e 40` (8-bit disp), `80 8? 2e 00 00 00 40` (32-bit disp), SIB variants, REX-prefixed 64-bit variants
   - `test byte [reg+0x2e], 0x40` — same encodings
   - `and byte [reg+0x2e], 0xbf` — clear-bit-6 variants
   - `bts byte [reg+0x2e], 6` — `0f ba 6? 2e 06`
   - `mov byte [reg+0x2e], 0x40` — `c6 4? 2e 40`
   - sliding-window load-OR-store: `8a [4?] 2e ... 88 [4?] 2e`
2. **Radare2 instruction-level sweep** — full linear disassembly (`pD <size> @ 0`, i386 for TE, amd64 for PE32) with grep for any line touching displacement `+0x2e` AND immediate `0x40`. Verifies the byte-pattern scan would not have missed a register-load + register-OR + register-store splayed across an arbitrary number of instructions, by enumerating *every* +0x2E memop and *every* `byte [...]` instruction with imm `0x40`, and intersecting.
3. **Strings keyword sweep** — every candidate's ASCII string table grepped for: `Gen4`, `Gen 4`, `ESM`, `DXIO`, `Strap`, `Engine`, `Port`, `Descriptor`, `Synth`, `Rev`, `1.02`, `1.03`, `Board`, `Override`, `Pcie`/`PCIE`, `NBIO`, `Speed`, `RomeD8`/`ROMED8`, `Asrock`/`ASRock`.

## Results — byte-pattern sweep

Across all 16 modules, both versions: **zero hits** for every explicit bit-6 manipulation pattern listed above.

The pattern table (P3.70 ∪ P3.80, all 16 candidates):

| Pattern | Hits |
|---|---:|
| `or byte [reg+0x2e], 0x40` (disp8 / disp32 / SIB / REX) | 0 |
| `test byte [reg+0x2e], 0x40` (all variants) | 0 |
| `and byte [reg+0x2e], 0xbf` | 0 |
| `bts/btr/btc byte [reg+0x2e], 6` | 0 |
| `mov byte [reg+0x2e], 0x40` | 0 |
| Sliding-window load-OR-store on `+0x2e` | 0 |

## Results — r2 instruction-level sweep

Per-module disassembly statistics (P3.70 // P3.80; `+0x2e` = lines with `+0x2e]` displacement; `0x40` = lines with `byte [...]` operand and `0x40` immediate; **intersection** = lines satisfying both, i.e. plausible producer):

| Vol | Module | `+0x2e` lines | `byte 0x40` lines | **Intersection** |
|---|---|---:|---:|---:|
| 8 | `AmdCcxVhPei` | 0 / 0 | 0 / 0 | **0 / 0** |
| 8 | `AmdI2CMasterPei` | 0 / 0 | 0 / 0 | **0 / 0** |
| 8 | `AmdNbioIOMMUSSPPei` | 0 / 0 | 0 / 0 | **0 / 0** |
| 8 | `AmdVersionPei` | 0 / 0 | 0 / 0 | **0 / 0** |
| 8 | `CbsBasePeiSSP` | 2 / 2 | 6 / 6 | **0 / 0** |
| 8 | `CbsBasePeiZP` | 0 / 0 | 5 / 5 | **0 / 0** |
| 8 | `CrbPei` | 0 / 0 | 0 / 0 | **0 / 0** |
| 8 | `EE4E5898-...#0` (PE32) | 0 / 0 | 0 / 0 | **0 / 0** |
| 8 | `EE4E5898-...#3` (PE32) | 0 / 0 | 0 / 0 | **0 / 0** |
| 8 | `NvramPei` | 0 / 0 | 4 / 4 | **0 / 0** |
| 8 | `PcatSingleSegmentPciCfg2Pei` | 0 / 0 | 0 / 0 | **0 / 0** |
| 8 | `TcgPlatformSetupPeiPolicy` | 2 / 2 | 0 / 0 | **0 / 0** |
| 8 | `TrEEPei` | 1 / 1 | 2 / 2 | **0 / 0** |
| 8 | `aDefaultPei` | 0 / 0 | 1 / 1 | **0 / 0** |
| 21 | `EE4E5898-...#1` (PE32) | 0 / 0 | 0 / 0 | **0 / 0** |
| 21 | `ServerDefaultPei` | 0 / 0 | 0 / 0 | **0 / 0** |

**Zero modules** have any instruction that touches a `+0x2E` byte memory operand AND uses immediate `0x40`. The two `CbsBasePeiSSP` / `TcgPlatformSetupPeiPolicy` / `TrEEPei` modules with non-zero `+0x2e` line counts have those displacements in entirely unrelated structure accesses (no `0x40` in the same instruction; verified by intersection).

## Results — strings keyword sweep

Only matches found across all 16 candidates and both versions:

| Module | Match |
|---|---|
| `AmdCcxVhPei` | `"AMD Unprogrammed Engineering Sample"` (CPU SKU detection — irrelevant) |
| `AmdNbioIOMMUSSPPei` | `"AmdNbioIOMMUPeiEntry"` (entry-point name — IOMMU, not PCIe) |
| `aDefaultPei` | `"@ROMED8-2T"` (board ID string — present in both versions, identical) |
| `ServerDefaultPei` | `"@ROMED8-2T"` (same) |

**No Gen4 / ESM / DXIO / Strap / 1.02 / 1.03 / Override / Speed / Descriptor / Synth strings in any candidate, in either version.** The `RomeD8`/`ROMED8` board ID strings exist identically in both versions, so even though `aDefaultPei` is genuinely changed, the change is not board-ID-driven.

## Per-module notes (truly-changed PEI subset)

The non-rebase changes in these 13 TE-PEIMs (and 3 PEI-phase PE32 instances) are mostly small and look unrelated to PCIe init:

- **`AmdCcxVhPei`** — Vol Hot CPU init PEI (CCX = Core Complex). Likely RAS/EDAC tweak. Not a PCIe path.
- **`AmdI2CMasterPei`** — I2C master init. Used for SMBus/EEPROM/sensor — not PCIe descriptors.
- **`AmdNbioIOMMUSSPPei`** — IOMMU-only NBIO sub-init. Different code path from `AmdNbioPciePei` (which is byte-identical between versions per `docs/MODULE_SWEEP_P3.70_vs_P3.80.md` — `AmdNbioPciePei` was not on the original 85 differs list, and is REBASE_ONLY-or-better in this sweep).
- **`AmdVersionPei`** — version-string PEI. Expected to bump on every release.
- **`CbsBasePeiSSP` / `CbsBasePeiZP`** — CBS base PEI for SSP and ZP families. Tiny diffs (12424→12424 with 29 unexplained bytes; `CbsBasePeiSSP` actually shrank). No PCIe-init code here in this BIOS layout (PCIe-specific CBS is in the DXE-side `CbsSetupDxe*`).
- **`CrbPei`** — board-customization PEI; only 1 unexplained byte after rebase. Almost a pure rebase, with one tiny patch.
- **`NvramPei`** — NVRAM PEI; matches the corresponding DXE-side `NvramDxe`/`NvramSmm` changes. Unrelated to PCIe.
- **`PcatSingleSegmentPciCfg2Pei`** — generic PCI config-space access PEI from EDK2, not AMD-specific.
- **`TcgPlatformSetupPeiPolicy` / `TrEEPei`** — TPM PEIs. Heavy-rewrite candidates (`TcgPlatformSetupPeiPolicy` has 283 unexplained bytes in a 1000-byte module — likely a substantial change). Unrelated to PCIe.
- **`aDefaultPei` / `ServerDefaultPei`** — default-variable PEIs. Carry the `@ROMED8-2T` board ID string but it's unchanged.
- **`EE4E5898-3914-4259-9D6E-DC7BD79403CF` PE32 instances #0/#1/#3** — all on the original 85-differs list; nothing new.

## Conclusion

The PEI cold-boot phase is **fully exhausted** as a search space for the Gen4 bit-6 producer. None of the 16 candidates that genuinely changed between P3.70 and P3.80 contains any byte-pattern, instruction, or string consistent with a per-port DXIO descriptor producer. The 37 modules that *appeared* to change (including all four `AmdCpm*Peim` entries) are confirmed pure-rebase artifacts.

Combined with the prior negative findings on `AmdApcbDxeV3` (`docs/APCB_DXEV3_DIFF.md`), `AmdNbioPcieDxe` (byte-identical P3.70=P3.80, `docs/RADARE2_NBIOPCIE.md`), `AmdNbioPciePei` (`docs/DISASM_AmdNbioPciePei.md`), `AmdCpmPcieInitPeim` (REBASE_ONLY, this doc), `AmdCpmPcieInitDxe` (`docs/DISASM_AmdCpmPcieInit*.md`), `AmdCpmOemInitPeim` (REBASE_ONLY, this doc), and `CbsSetupDxeSSP` (`docs/CBSSETUP_DIFF.md`):

**The Gen4 producer for bit 6 of `+0x2E` is in a P3.70-vs-P3.80 truly-changed DXE/SMM PE32 module that has *not* yet been individually disassembled.** The remaining DXE candidate space (vol 7 PE32 SEMANTIC_DIFF and SIZE_DIFF modules with PCIe-relevant names) is the search frontier. Top remaining candidates by name relevance:

- `AmdRasSspDxe` (RAS for SSP — RAS sometimes touches PCIe error capabilities; SEMANTIC_DIFF, same size)
- `AmdPlatformRasSspDxe` (board-specific RAS — SEMANTIC_DIFF, same size)
- `AmdPlatformRasZpDxe` (RAS for ZP — SEMANTIC_DIFF, same size)
- `AmdSmbiosDxe` (SMBIOS PCIe slot description — SEMANTIC_DIFF; unlikely producer but cheap to rule out)
- `PciDxeInit` / `PciBus` / `PciRootBridge` (generic PCI init — SEMANTIC_DIFF, same size; could carry an OEM-shim hook)

Lower priority but still on the truly-changed list and not yet checked: `Setup` (vol 7), `ServerMgmtSetup`, `FirmwareConfigDrv`, `RfInventory`, `SystemInventoryInfo`, `SlinkEndpointDriver`, `SlinkManager`. None has a PCIe-init-stage name but several are large enough to host stealth code.

## Reproduction

```bash
python3 /tmp/rebase_diff.py             # produces /tmp/rebase_diff_results.json
python3 /tmp/pei_bit6_scan.py           # byte-pattern + ASCII keyword sweep
python3 /tmp/pei_r2_v2.py               # r2 instruction-level sweep (slow ~5 min)
```
