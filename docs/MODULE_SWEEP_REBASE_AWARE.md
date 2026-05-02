# Module sweep — rebase-aware re-diff (P3.70 vs P3.80)

**Date:** 2026-04-27
**Driver:** `/tmp/rebase_diff.py`. Raw results: `/tmp/rebase_diff_results.json`.
**Predecessor:** `docs/MODULE_SWEEP_P3.70_vs_P3.80.md` (PE32-only, ignored TE files).
**Trigger:** the `AmdCpmOemInitPeim` finding in `docs/DISASM_AmdCpmOemInitPeim.md` showed that the entire FV8 cold-boot volume was re-laid-out between P3.70 and P3.80 (image_base shift `-0x20` per module), producing pointer-rebase diffs on every PEIM regardless of source change.

## Methodology

1. Walk every `body.bin` under `extracted/all/P{3.70,3.80}/img.bin.dump/**/{PE32,TE} image section/`. Index by `(volume_index, module_name, kind, instance_within_name)`.
2. For each pair, classify:
   - **BYTE_IDENTICAL**: sha256 same.
   - **SIZE_DIFF**: file sizes differ (or only present in one version).
   - **REBASE_ONLY**: bytes differ; `image_base` shifted; every diff byte explained by absolute-pointer rebase.
   - **SEMANTIC_DIFF**: bytes differ AND at least one diff byte is *not* explained by rebase.
3. PE32: parse OPTIONAL_HEADER.ImageBase + walk DIRECTORY_ENTRY_BASERELOC; for each TYPE 3 / TYPE 10 reloc, read the LE32/LE64 word and check `value_b - value_a == image_base_b - image_base_a`. Mark explained bytes.
4. TE: image_base lives at TE-header offset `0x10` (UINT64). TE strips `.reloc`, so use the prior agent's heuristic — for each diff offset, scan the four overlapping 4-byte aligned windows; mark a window REBASE-explained iff its high 16 bits match `image_base >> 16` AND `value_b - value_a == delta`.

## Counts

| Kind | Total modules | BYTE_IDENTICAL | REBASE_ONLY | SEMANTIC_DIFF | SIZE_DIFF | ONLY_one_side |
|---|---:|---:|---:|---:|---:|---:|
| PE32 | 652 | 567 | **0** | 55 | 28 | 2 |
| TE   | 175 | 125 | **37** | 12 | 1 | 0 |
| **Total** | **827** | 692 | **37** | 67 | 29 | 2 |

### Reconciliation with original sweep

- **Original sweep flagged 85 differing PE32 modules**, all in vol 7 (DXE/SMM) and vol 20.
  Rebase-aware result: **0 of those 85 are pure rebase artifacts.** Vol 7's `image_base` did not shift between P3.70 and P3.80 — only vol 8 did. The 85 PE32 differs are real.
- **Original sweep ignored TE files entirely** (the `iter_pe32_bodies` helper filters on "PE32 image section"). Vol 8 (cold-boot PEI volume) is overwhelmingly TE-format. Adding TE coverage exposed 50 byte-differing TE-PEIMs; the rebase-aware filter shows **37 are pure linker artifacts** and **only 13 are genuine PEI-phase changes**.
- The original PE32-only sweep listed only 3 PEI-phase changes (the `EE4E5898-3914-4259-9D6E-DC7BD79403CF` GUID instances that happened to be stored as PE32 instead of TE). All 3 remain SEMANTIC_DIFF after rebase filtering.

### Image-base deltas observed

| Volume | image_base delta P3.70 → P3.80 | Affected modules |
|---|---|---|
| 7 (DXE/SMM main, FV2) | 0 | PE32: vol 7's load address did not shift; all 85 differs are semantic. |
| 8 (PEI cold-boot, FV8) | **-0x20 (most), -0x28 (a few)** | 37 TE PEIMs are pure rebase artifacts; 13 are genuine. |
| 20 (DXE recovery mirror, FV20) | 0 | 14 differs, all semantic (recovery copies of vol 7 modules). |
| 21 (PEI recovery mirror, FV21) | 0 | 2 differs, both semantic. |

The volume-level `image_base` shift is consistent with what `DISASM_AmdCpmOemInitPeim.md` observed for one specific module — confirmed here as a global FV8 re-layout, not a per-module change.

## REBASE_ONLY — pure linker artifacts (37 modules, all in FV8/PEI)

These are **NOT** Gen4 producer candidates. They were flagged as "differing" only because FV8 was re-laid-out, shifting every PEIM's `image_base` and rebasing absolute pointers.

| Vol | Module | Δ base | Raw diff bytes | Explained |
|---|---|---:|---:|---:|
| 8 | `ASM108XPei` | -0x20 | 8 | 8 |
| 8 | `AST2500PeiInit` | -0x20 | 12 | 12 |
| 8 | `AcPowerLossByBmcPei` | -0x20 | 4 | 4 |
| 8 | `AmdBoardIdPei` | -0x20 | 4 | 4 |
| 8 | `AmdCpmGpioInitPeim` | -0x20 | 22 | 22 |
| 8 | `AmdCpmInitPeim` | -0x20 | 216 | 216 |
| 8 | `AmdCpmOemInitPeim` | -0x20 | 127 | 127 |
| 8 | `AmdCpmPcieInitPeim` | -0x20 | 15 | 15 |
| 8 | `AmdPlatformRasSspPei` | -0x20 | 3 | 3 |
| 8 | `AmdSataWorkaround` | -0x20 | 4 | 4 |
| 8 | `AmiAgesaPei` | -0x20 | 11 | 11 |
| 8 | `AmiTcgPlatformPeiAfterMem` | -0x20 | 56 | 56 |
| 8 | `AmiTcgPlatformPeiBeforeMem` | -0x20 | 11 | 11 |
| 8 | `AmiTpm20PlatformPei` | -0x20 | 39 | 39 |
| 8 | `CapsuleX64` | -0x20 | 106 | 106 |
| 8 | `CmosPei` | -0x28 | 54 | 54 |
| 8 | `Ds125Br401aPei` | -0x20 | 11 | 11 |
| 8 | `IsSecRecoveryPEI` | -0x20 | 18 | 18 |
| 8 | `LightScreenPei` | -0x20 | 130 | 130 |
| 8 | `M24Lc128Pei` | -0x20 | 10 | 10 |
| 8 | `Pca9535aPei` | -0x20 | 10 | 10 |
| 8 | `Pca9545aPei` | -0x20 | 8 | 8 |
| 8 | `PcdPeim` | -0x20 | 78 | 78 |
| 8 | `PeiFrb` | -0x20 | 10 | 10 |
| 8 | `PeiIpmiBmcInitialize` | -0x20 | 27 | 27 |
| 8 | `PeiSelStatusCode` | -0x20 | 19 | 19 |
| 8 | `PlatformCustomizePei` | -0x20 | 5 | 5 |
| 8 | `SbInterfacePei` | -0x20 | 63 | 63 |
| 8 | `SecSIOPeiInit` | -0x28 | 9 | 9 |
| 8 | `Sff8472Pei` | -0x20 | 10 | 10 |
| 8 | `SmBusPei` | -0x20 | 45 | 45 |
| 8 | `SmartFanControl` | -0x20 | 16 | 16 |
| 8 | `SmbiosPeim` | -0x20 | 52 | 52 |
| 8 | `StatusCodePei` | -0x20 | 167 | 167 |
| 8 | `TCMPEI` | -0x20 | 13 | 13 |
| 8 | `TcgPei` | -0x20 | 48 | 48 |
| 8 | `TcgPeiplatform` | -0x20 | 8 | 8 |

**Headline:** the most prominent name on this list — `AmdCpmPcieInitPeim` — is rebase-only. Its content did **not** change between P3.70 and P3.80. This is independently consistent with the AMD-side AGESA APCB/PCIe init logic being unchanged across the two BIOS revisions.

## SEMANTIC_DIFF / SIZE_DIFF / one-sided — truly changed (98 modules)

The full table is in `/tmp/rebase_diff_results.json`. Only the PEI-phase subset is reproduced here (the DXE-phase 85 PE32 list has not changed from the original sweep — see `docs/MODULE_SWEEP_P3.70_vs_P3.80.md`).

### PEI-phase truly-changed (13 modules)

| Vol | Kind | Module | Class | P3.70 size | P3.80 size | Notes |
|---|---|---|---|---:|---:|---|
| 8 | TE   | `AmdCcxVhPei` | SEMANTIC_DIFF | 30096 | 30096 | image_base same; non-rebase code/data diff |
| 8 | TE   | `AmdI2CMasterPei` | SEMANTIC_DIFF | 2448 | 2448 | base shift -0x20 + 11 unexplained bytes |
| 8 | TE   | `AmdNbioIOMMUSSPPei` | SEMANTIC_DIFF | 7840 | 7840 | image_base same; semantic diff |
| 8 | TE   | `AmdVersionPei` | SEMANTIC_DIFF | 496 | 496 | image_base same; expected version-string bump |
| 8 | TE   | `CbsBasePeiSSP` | SIZE_DIFF | 13248 | 13216 | -32 B (rare PEI shrink — minor refactor) |
| 8 | TE   | `CbsBasePeiZP` | SEMANTIC_DIFF | 12424 | 12424 | -0x20 + 29 unexplained bytes |
| 8 | TE   | `CrbPei` | SEMANTIC_DIFF | 7072 | 7072 | -0x28 + 1 unexplained byte (almost pure rebase) |
| 8 | TE   | `NvramPei` | SEMANTIC_DIFF | 8400 | 8400 | -0x20 + 68 unexplained bytes (matches DXE NvramDxe/Smm changes) |
| 8 | TE   | `PcatSingleSegmentPciCfg2Pei` | SEMANTIC_DIFF | 2008 | 2008 | -0x28 + 6 unexplained bytes |
| 8 | TE   | `TcgPlatformSetupPeiPolicy` | SEMANTIC_DIFF | 1000 | 1000 | -0x20 + 283 unexplained (heavily rewritten — small module though) |
| 8 | TE   | `TrEEPei` | SEMANTIC_DIFF | 32120 | 32120 | -0x20 + 60 unexplained |
| 8 | TE   | `aDefaultPei` | SEMANTIC_DIFF | 6480 | 6480 | -0x20 + 4 unexplained |
| 21 | TE  | `ServerDefaultPei` | SEMANTIC_DIFF | 928 | 928 | image_base same; semantic |
| 8 | PE32 | `EE4E5898-3914-4259-9D6E-DC7BD79403CF` (inst 0) | SEMANTIC_DIFF | 40032 | 40032 | already in original sweep |
| 8 | PE32 | `EE4E5898-3914-4259-9D6E-DC7BD79403CF` (inst 3) | SEMANTIC_DIFF | 18944 | 18944 | already in original sweep |
| 21 | PE32 | `EE4E5898-3914-4259-9D6E-DC7BD79403CF` (inst 1) | SEMANTIC_DIFF | 42656 | 42656 | already in original sweep |

(15 PEI rows; the count "13 TE genuinely changed" + 3 PE32 PEI-phase = 16 total candidates entered into Phase 2.)

**No `Pcie`/`Nbio`/`Cpm`/`Apcb`/`Dxio` PEIM** appears in this PEI semantic-diff list. The closest hit is `AmdNbioIOMMUSSPPei` — the IOMMU sub-module of NBIO, not the PCIe init path. All four `AmdCpm*Peim` entries (`Init`, `OemInit`, `GpioInit`, `PcieInit`) are confirmed REBASE_ONLY.

## Implications

1. **The `MODULE_SWEEP_P3.70_vs_P3.80.md` PE32 list of 85 differing DXE/SMM modules is unaffected by the rebase artifact.** Vol 7 is a different FV with stable load address; every diff there is real.
2. **All four `AmdCpm*Peim` entries are confirmed source-identical between P3.70 and P3.80.** The producer for bit 6 of `+0x2E` is *not* in any AMD CPM PEIM. This corroborates the prior `AmdCpmOemInitPeim` finding and extends it.
3. **No PEI-phase module with a PCIe/NBIO/DXIO/APCB-related name made it onto the truly-changed list.** The only NBIO-named PEI is `AmdNbioIOMMUSSPPei` — IOMMU is unrelated to link-speed gating.
4. **Phase 2 (PEI bit-6 byte-pattern + strings sweep) ran on all 16 candidates and found zero producer-side hits** — see `docs/PEI_PRODUCER_SWEEP.md`.

The PEI phase is now exhausted as a search space for the Gen4 producer. The producer must live in the DXE/SMM layer (vol 7 — already enumerated by the original sweep) or in an AGESA module loaded later. The 85 DXE/SMM PE32 modules — none of which are rebase artifacts — remain the search frontier.

## Reproduction

```bash
python3 /tmp/rebase_diff.py    # writes /tmp/rebase_diff_results.json (827 entries)
python3 /tmp/pei_bit6_scan.py > /tmp/pei_phase2.md
```
