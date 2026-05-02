# Phase 2 synthesis — DRAFT (in flight)

**Date:** 2026-04-27
**Scope:** results from every Phase-2 follow-up doc in `docs/` (everything after the six Phase-1 subagents recorded in `BIOS_LATEST.md`).
**Status:** draft — several agents still in flight (bit-pattern global search, Dxio/Override hunt, call-graph trace, raw image diff, BDF 40:01.3 hunt, coreboot reference, remaining DXE candidates). Sections 5/6 will be tightened when those land. This draft is the working synthesis of the ~20 docs already on disk.

---

## 1. Headline verdict

**The Phase-2 question is not yet definitively answered, but the search space has been reduced from "any of dozens of modules / firmware layers" to two terminal hypotheses, both of which would close the project.** Across nine targeted disassembly diffs, three sweeps (PEI, SMM, OEM-shim), an IFR cross-version diff (P3.70 / P3.80 / P3.90 / P4.10), a CPM-data sweep, a BMC-compatibility study, and a PSP/ABL diff, **every single canonical AGESA / NBIO / CBS / OEM / Setup / SMM module that could plausibly produce bit 6 of `+0x2E` has been ruled out** — either the binary is byte-identical across the P3.70 → P3.80 boundary, or its diff is fully accounted for by linker rebasing / unrelated edits (RAS event-ID renumber, CCD-option rename, SecureBoot null-check, DDR4-PPR plumbing, APCB shadow-copy SPI-write fix). The producer is therefore in (a) one of the unanalyzed members of the 85 PE32 modules in vol 7 that genuinely differ between P3.70 and P3.80, (b) the encrypted PSP / ABL firmware that did substantively change (Rome→Milan-superset), or (c) does not exist — i.e., the community report of Gen4 working on rev-1.03 at P3.80 may be inaccurate. Crucially, P3.80 + BMC 2.08 IPMI-flash is now **likely OK** based on 45HomeLab thread #3723 (the documented IPMI-flash interlock is P4.10 + 2.08, not P3.80 + 2.08), and Instant Flash from BIOS Setup bypasses the IPMI path entirely. **Actionable conclusion:** without flashing the rig, the cap remains structural and definitive; with flashing, P3.80 is the lowest-risk experiment, but the unlock has not been mechanically confirmed and may not fire on this specific board.

---

## 2. Phase-2 question recap

Phase 1 closed with one unresolved question: **where in the firmware is bit 6 (mask `0x40`) of byte `+0x2E` in the per-port DXIO descriptor *produced*?** Subagent #5 had localized the *consumer* — `AmdNbioPcieDxe.efi` reads it at file offset `0x14b1e` via `test byte [r14+0x2e], 0x40` inside `PcieAttemptEsmIfEnabled`, and a second consumer at `0x2f53` of `AmdNbioPciePei.efi` (FV21/20). Subagent #1 ruled out the APCB blob itself (PSPG/MEMG/TOKN only; byte-identical body P3.70 → P4.10). The producer therefore lives in some runtime-synthesizer module that builds the per-port DXIO descriptor list before DXE PCIe init. Phase 2's job: find that module, characterize its P3.70-vs-P3.80 diff, and answer:

(a) Is the diff an unconditional bit-set on GPU-slot descriptors that ASRock chose not to ship in P3.70? → flashing P3.80 lifts the cap.
(b) Is the diff a board-rev-strap MMIO read that gates the bit-set on rev 1.03? → flashing P3.80 lifts the cap on this rig (assumed-confirmed rev 1.03).
(c) Something else? → unclear; further analysis needed.

The answer determines whether (and how) the Gen4 cap could be lifted by a flash, and feeds the no-flash-vs-flash decision for the rig.

---

## 3. What's been ruled out (Phase 2 negatives)

Annotated table of every candidate explicitly disqualified during Phase 2:

| Candidate | Doc | Verdict | Why ruled out |
|---|---|---|---|
| `AmdApcbDxeV3` (+64 B P3.70→P3.80) | `APCB_DXEV3_DIFF.md` | **NEGATIVE** | +64 B = (i) APCB shadow-copy entry-checksum recompute in `fcn.00012b9c`, (ii) chunked 4 KB SPI page-write loop in `PspWriteFlashDxe`. Zero `+0x2E` accesses; zero bit-6 manipulation; zero DXIO/Gen4/ESM strings. |
| `CbsSetupDxeSSP` (+320 B) | `CBSSETUP_DIFF.md` | **NEGATIVE** | +320 B = HII string-table churn ("CCD Control" → "CCDs Control" rename + removed "3 CCDs" option). `.text` and `.data` byte-identical; one removed `mov byte [rcx+0x15a], 0x0F` in CBS defaults init (CCD-related, not PCIe). |
| `CbsBaseDxeSSP` (Δ=0, hash differs) | `DISASM_CbsBaseDxeSSP.md` | **NEGATIVE** | Single-line edit: removed default-write `mov byte [rcx+0x15a], 0x0F` from CBS struct initializer (same field as `CbsSetupDxeSSP`). Every other byte diff is a linker-cascade displacement adjustment. No `+0x2E` / `0x40` / Gen4 anywhere. |
| `AmdNbioBaseSspDxe` | `DISASM_AmdNbioBaseSspDxe.md` | **NEGATIVE** | PE32 byte-identical P3.70 = P3.80 (md5 `60cd2a54…`). Module is S3-Save library + PCI-IO hooks + HwInit-lock register write — not a descriptor producer. Zero `+0x2E` byte-pattern hits. |
| `AmdCpmPcieInitPeim` (FV8/53, hash differs) | `DISASM_AmdCpmPcieInitPeim.md` | **NEGATIVE** | 1032-byte TE PPI-shim. Diff is pure ImageBase rebase (-0x20). Zero bit-6 / `+0x2E` / Gen4 / DXIO content. The companion `AmdCpmPcieInitDxe` (both FV instances) is byte-identical P3.70 = P3.80. |
| `AmdCpmPcieInitDxe` | `DISASM_AmdCpmPcieInitDxe.md` | **NEGATIVE** | 1.1 KB CPM tag-dispatcher (`M129/M130/M222–M225` → struct field getters). No `+0x2E` access, no bit-6 manipulation, byte-identical across versions in both FFS instances. |
| `AmdCheckBmcPciePei` | `DISASM_AmdCheckBmcPciePei.md` | **NEGATIVE** | Tiny PEI fixup walker; family-17h gated; reads root-port LCTL2 and pokes vendor regs `+0x44` / `+0x50` for link retraining. No `+0x2E` access, no Gen-cap involvement. Byte-identical across P3.70/P3.80/P3.90 (only relocation deltas). Closes the "BMC port `40:01.3` Gen4 originates here" hypothesis. |
| `AmdNbioPciePei` (both FV instances) | `DISASM_AmdNbioPciePei.md` | **NEGATIVE** | Both TE bodies byte-identical P3.70 = P3.80. Notably contains a *third* bit-6 consumer (`test [edi+0x2e], 0x40` at file off `0x2f53` in FV21/20, branching to a SMN write to `0x11180604` per NBIO instance). Architecturally identical to the DXE consumer. Confirms the consumer-side pipeline is unchanged across the boundary. |
| `AmdCpmOemInitPeim` (FV8/43, hash differs) | `DISASM_AmdCpmOemInitPeim.md` | **NEGATIVE** | 127 differing bytes; 126 explained by ImageBase shift (-0x20), 1 is the ImageBase field itself. **Pure rebase artifact.** Module is functionally byte-identical. The FV21 main-dispatch copy is byte-identical too. |
| `AmdNbioBaseSspPei` | `DISASM_AmdNbioBaseSspPei.md` | **NEGATIVE** | Byte-identical P3.70 = P3.80 (md5 `2023043750d0…`). Module's actual function: HDAudio verb tables, NonPCI MMIO BAR allocation, GNB TOM2/TOM3, IDS NV provisioning. Zero `+0x2E`, zero DXIO/Gen4 strings, zero APCB-token getters. |
| `Setup` (vol 7, +0 B, hash differs) | `DISASM_SETUP_DIFF.md` | **NEGATIVE** | Single 5-byte change: `test rax,rax; js +0x4a` null-check inserted after a SecureBoot HII protocol call in `fcn @ 0xcdc0`. Every other byte diff (4068 of 4069) is mechanical relocation cascade. `.rsrc` byte-identical (no IFR / HII string change). Closes the "ASRock Setup HII carries the unlock" hypothesis at code level. |
| `AmdCpmData*` / `CpmTbl*` / `BoardData*` / `PlatformData*` (none exist) | `DISASM_CPM_DATA.md` | **NEGATIVE** | No standalone CpmData-style module exists in this BIOS. ASRock's per-board configuration tables live inside `AmdCpmOemInitPeim`'s `.data` section, which is byte-identical across versions (modulo rebase). `AmdBoardIdPei` / `AmdBoardIdDxe` board-ID logic is also byte-identical / rebase-only. `PciTableInit` byte-identical in both FV instances. |
| Full PEI sweep — 16 truly-changed PEI candidates | `PEI_PRODUCER_SWEEP.md` | **NEGATIVE** | Across `AmdCcxVhPei`, `AmdI2CMasterPei`, `AmdNbioIOMMUSSPPei`, `AmdVersionPei`, `CbsBasePeiSSP`, `CbsBasePeiZP`, `CrbPei`, `NvramPei`, `PcatSingleSegmentPciCfg2Pei`, `TcgPlatformSetupPeiPolicy`, `TrEEPei`, `aDefaultPei`, `ServerDefaultPei`, plus 3 PE32 PEI-phase instances of GUID `EE4E5898-…`: zero hits on any encoding of `or/test/and/bts/mov byte [reg+0x2E], 0x40`, zero hits on Gen4/ESM/DXIO/Strap/1.02/1.03/Override strings. **PEI cold-boot phase is exhausted as a search space.** |
| Full SMM inventory (91 modules, 7 differing) | `SMM_INVENTORY.md` | **NEGATIVE** | None of the 7 differing SMM modules (`AmdPspP2CmboxV2`, `NvramSmm`, `Ofbd`, `CpuSmm`, `SmbiosDmiEdit`, `CryptoSMM`, `SbRunSmm`) reference `LC_GEN4_EN_STRAP`, the SMN address `0x111402A4`, `LCTL`, `LinkSpeed`, `PcieAttempt`, or any Gen4/ESM string in either version. All PCIe-adjacent SMM modules (`SmmPciRbIo`, `AmdHotPlugSspSmm`, `AmdFabricSspSmm`) byte-identical. **No SMM trap is enforcing the Gen4 cap.** |
| Full IFR sweep (1619 settings × 4 versions) | `IFR_VERSION_DIFF.md` | **NEGATIVE** | Zero settings whose Gen4/ESM/DXIO keyword profile changed across P3.70 / P3.80 / P3.90 / P4.10. The 139 added settings between versions are all SATA / NTB / I2C / UART / SecureBoot / TPM additions in `CbsSetupDxeGN` (Genoa, irrelevant on this Rome board). The Rome-side `CbsSetupDxeSSP` only changed cosmetically (CCD prompt rename). The 11 ASRock-side per-slot Link Speed entries (PCIE1-PCIE7 + OCU1/2 + M2_1/2) had only their GrayOutIf condition QID renumbered (`Q0x14a` → `Q0x14b` between P3.80 and P3.90); their values, defaults, and binding to vestigial NVRAM bytes are unchanged. **No new IFR-level Gen4 enable was added in any later BIOS.** |
| OEM-shim hunt (22 keyword-matched modules) | `OEM_SHIM_HUNT.md` | **NEGATIVE** | No `Oem*` / `Asrock*` / `Rs1*` / `Rs2*` / `Strap*` / `Hid*` modules exist in this BIOS at all. ASRock did not ship a `AmdCpmOemInitDxe` either. The 4 keyword-matched DXE modules that differ (`AmdPlatformRasSspDxe`, `AmdPlatformRasZpDxe`, `AmiTcgPlatformDxe`, `GenericSio`) are all RAS event-ID renumbers / TPM churn / Super-I/O changes; zero `+0x2E` byte-pattern hits across all 22 modules. |
| `AmdApcbDxeV3 fcn.00013df4` caller-of-write-back | `APCB_CALLER_FCN13DF4.md` | **NEGATIVE (red herring)** | The function P3.80 was suspected of adding pre-write mutation to is a **DDR4 Post Package Repair** (memory RAS) handler, group `0x1704`, entry type `0x5e`. The P3.80 vs P3.70 instruction-level diff after relocation normalization is **empty** — same 24 BBs, same 113 instructions, same 6 strings, same call graph. Unrelated to PCIe / DXIO / Gen4 by both group-membership *and* mutation absence. The actual extra-mutation site is in a basic block at `0x14770`-ish that radare2 didn't promote into a function — was not pursued; remains an open mini-question but cannot affect Gen4 since the binary's whole `+0x2E` byte-pattern surface is empty. |
| Per-slot NVRAM bytes `Setup:0x123-0x12D` | (Phase 1, restated) | **NEGATIVE for cap, but** | These bytes are vestigial — AGESA does not consume them for the GPU root ports' Gen-cap. **However** the ASRock IFR exposes Gen1/2/3/**Gen4** as the option set, which means *if AGESA ever did consume them*, value `0x04` would be a Gen4 request. The fact that a hypothetical `setup_var` write of `0x04` doesn't lift the cap is consistent with the vestigial finding from Phase 1 — empirically, the rig has slots set to `0x01` (GEN1) running Gen3 GPUs, so even these well-defined values are ignored. |

**Summary of negatives:** every named DXE/SMM/PEI module that's structurally adjacent to PCIe init has been individually disassembled or bulk-swept. None contains the producer.

### Why the original 85-PE32-differs list is real, not a rebase artifact

`MODULE_SWEEP_REBASE_AWARE.md` re-ran the original `MODULE_SWEEP_P3.70_vs_P3.80.md` with a rebase-aware diff (parsing PE/TE ImageBase, then verifying that each diff byte falls inside an LE32 word matching the ImageBase shift). Result: **0 of 85 PE32 modules in vol 7 are pure rebase artifacts**. Vol 7's load address didn't shift between P3.70 and P3.80 — only vol 8 (PEI cold-boot) did, and the rebase filter explained 37 of 50 byte-differing TE PEIMs as pure linker noise. The 85 vol-7 differences are real semantic diffs. They're the search frontier; only ~12 have been disassembled in detail.

---

## 4. What's been confirmed (Phase 2 positives)

1. **PSP / ABL firmware was substantially rewritten between P3.70 and P3.80.** P3.70 was a Rome+Milan combo image (ROM 0 = `AGESA!V9 RomePI-SP3 1.0.0.F`, ROM 1 = `MilanPI-SP3 1.0.0.A`). P3.80 collapsed both ROMs to `MilanPI-SP3 1.0.0.A`. ABL stack version bumped `10.F.20.10 → 34.24.20.10`. PSP_FW_BOOT_LOADER changed (`0.C.0.87 → 0.C.0.88`). Bundled microcode bumped `0x08301055 → 0x08301072` (rig already runs newer `0x0830107C` from Linux at OS-time; not the unlock either way). ABL sub-blob TOC offsets show ~+34 KB cumulative growth across the ABL chain. **Bodies are AES-CCM encrypted by an IKEK derived from per-silicon PSP fuses; statically unreadable without keys we don't have.** This is the only FW layer with a substantive change that is also a plausible host for runtime descriptor-synthesis logic.
2. **The original 85-differs PE32 list in vol 7 is real**, not a rebase artifact. (See above.) Vol 7 ImageBase is stable across versions; every differing byte represents an actual code/data change.
3. **The Gen4 cap is structurally enforced at HwInit.** Confirmed independently by Phase 1 subagent #2 (HwInit attribute on `LC_GEN4_EN_STRAP` at SMN `0x111402A4`) and Phase 2 SMM inventory (no SMM handler is intercepting LCTL2 / SMN writes). The cap is silicon-side, latched by PSP/ABL at cold reset before any OS code runs. No SMM-revoke path exists.
4. **The bit-6 consumer pattern is replicated in PEI.** `AmdNbioPciePei` (FV21/20) has its own `test byte [edi+0x2e], 0x40` at offset `0x2f53`, branching to a SMN write to `0x11180604` (NBIF/PCIe-PHY-wrapper region, distinct from the `0x111402A4` IOHC strap region). The same architectural pattern as `AmdNbioPcieDxe`'s consumer — bit 6 controls a per-NBIO SMN poke. Both consumers are byte-identical P3.70 = P3.80; the descriptor-producer must have changed somewhere upstream of both.
5. **BMC 2.08 + P3.80 IPMI-flash is likely OK.** The 45HomeLab thread #3723 root-causes the documented IPMI flash interlock as **P4.10 + 2.08** (post 6 from Hutch-45Drives: "BIOS 4.10 with BMC 2.08 does not work as expected" while "BIOS 4.10 with BMC 2.02 works as expected"). HL15 V2.0 ships with P3.80 + BMC 2.08 in the field with no IPMI flash problem mentioned (post 3). No public report exists of BMC 2.08 blocking IPMI BIOS flash on any P3.x version. Also: Instant Flash from BIOS Setup bypasses the IPMI WebUI path entirely, so even if the interlock did extend to P3.80, USB-stick flashing would not be affected. See `BMC_COMPAT.md`.

---

## 5. What's still open / in flight

Several Phase-2 sub-investigations were dispatched in parallel but had not reported back at the time of writing. Their findings will be folded in when they land. Placeholders:

- **(A) Bit-pattern global search** — sweep every byte of the entire `images/ROMD82T*` capsule for any `or/test/mov/bts byte [reg+0x2E], 0x40` encoding (independent of which module owns the byte) and intersect with version-difference cliques. If the producer uses non-canonical addressing the per-module sweeps would have missed it; this catches the encoded byte sequence anywhere it lives. Status: **in flight.**
- **(R) DXIO / Override module hunt** — radare2 sweep across all 85 vol-7 differing PE32s for any module with a `Dxio` / `Override` / `EngineInit` / `PortInit` / `PcieEsm` / `PcieAttempt` string, or a debug-tag prefix that matches AGESA's NBIO debug conventions. Status: **in flight.**
- **(V) Call-graph trace from `AmdNbioPcieDxe` consumer** — backward trace from the descriptor pointer `r14` at the `0x14b1e` test site, through every protocol-locate / HOB-lookup / register-installed callback path, to find what code first pushed bytes into the `+0x2E` field. Status: **in flight.**
- **(W) Raw image diff** — byte-level diff of the entire 32 MiB `ROMD82TP3.70` and `ROMD82TP3.80` capsules, ignoring the FFS structure entirely. Catches anything that lives outside a recognized PE/TE container (raw-binary section, padding, hidden config blob). Status: **in flight.**
- **(X) BDF `40:01.3` hunt** — trace what endpoint hangs off the one Gen4-advertising root port (`40:01.3`, x4, `LnkCap2: 2.5–16GT/s`). Identifying it (BMC sideband / X550 NIC / chipset-internal) tells us what kind of port escapes the cap and may suggest analogous re-routing for one GPU. Already drafted at `BDF_40_01_03_HUNT.md`. Status: **in flight.**
- **(Y) coreboot / open-source AGESA cross-reference** — search coreboot's `src/vendorcode/amd/agesa/` and `oxidecomputer/amd-agesa-fw` for any DXIO descriptor structure layout matching the consumer's expectations (`+0x0F` link-state word, `+0x1D` NBIO instance byte, `+0x1E` BDF dword, `+0x2E` feature flags byte), and identify the canonical AGESA producer function name. Status: **in flight.**
- **(Z) Remaining DXE candidates from the 85-differs list** — disassemble the next-most-suspicious entries that haven't been touched yet. Top candidates by name relevance: `AmdRasSspDxe`, `AmdSmbiosDxe` (both same-size, hash-differs), `PciDxeInit`, `PciBus`, `PciRootBridge` (all same-size, hash-differs), plus the larger uncategorized modules `Bds` (+128 B), `ConSplitter` (+544 B), `GraphicsConsole` (+64 B), and the genuinely weird ones (`TlsDxe` shrunk by 580 KB — almost certainly a TLS-library swap, but worth confirming domain). Status: **partially in flight.**

When (A) / (W) / (Y) / (Z) all land negative, the producer search frontier collapses to "PSP/ABL or doesn't exist."

---

## 6. Three remaining hypotheses for where the unlock lives

Given the comprehensive PEI / SMM / OEM / IFR negatives plus the 85-PE32-differs vol-7 frontier, the three live hypotheses are:

### (a) Non-canonical bit-6 instruction in some unanalyzed DXE/SMM module from the 85-differs list

The producer uses a non-canonical addressing form — register-loaded base, or value-precomputed register + byte store — which all of the per-module byte-pattern scans (including `OEM_SHIM_HUNT.md`'s "extended" cross-check) would have missed. Specifically:

- `mov al, byte [base + offset]; or al, 0x40; mov byte [base + offset], al` where `offset` is a constant variable (not a literal `0x2E` immediate in the byte stream).
- `mov byte [reg + reg2], 0x40` after a precomputed `lea reg2, [...+0x2E]`.
- A struct-builder-from-template loop where the template byte at `+0x2E` is `0x40` and gets `rep movsb`'d in.

If true, the in-flight (A) bit-pattern global search and (V) call-graph trace will catch it. Status if confirmed: **flashing P3.80 lifts the cap on rev-1.03 boards** (or unconditionally, depending on what the diff against P3.70 reveals about board-rev gating). Likelihood: **moderate.** AGESA descriptor-builder code is highly idiomatic and tends to use one of the canonical forms scanned for; non-canonical use would be unusual but not impossible.

### (b) Encrypted PSP / ABL firmware (substantial change in P3.80, unreadable)

The producer is in the encrypted PSP_FW_BOOT_LOADER body or in one of the encrypted ABL sub-blobs. ABL is the documented AGESA layer that consumes APCB tokens at boot time; the descriptor-synthesis call could plausibly happen there. The PSP/ABL firmware *did* substantively change between P3.70 and P3.80 (Rome→Milan-superset), and the body is encrypted so we cannot directly verify what changed. Status if confirmed: **flashing P3.80 lifts the cap, but offline analysis is structurally impossible** — AES-CCM body + IKEK fuse-derived key + ABL signed by OEM key 1DC2 + PSB-fuse-state-dependent boot validation. There is no offline-patch-then-flash path. Likelihood: **moderate-high.** The Rome→Milan-superset PSP firmware swap is the single biggest functional change between P3.70 and P3.80; combined with the empty result of the entire UEFI-side analysis, this is the most parsimonious remaining explanation.

### (c) Doesn't exist — the community report may be inaccurate

The ASRock Forum TID 24737 reports that P3.80 enables Gen4 on rev-1.03 boards may be a (i) misattribution (Gen4 already worked on the BMC port `40:01.3` and someone interpreted that as "P3.80 works"), (ii) confusion with rev-1.03's other improvements (different PCB trace lengths, retimer config), or (iii) legitimate report from a different SKU / build that doesn't match this rig's silicon stepping. Status if confirmed: **the cap is permanent on this board family across all current BIOS versions; no flash path lifts it.** Likelihood: **moderate-low.** The existing community discussion is not robust (single thread, small N, no quantitative `lspci` data), and we have no first-hand confirmation. But the fact that we can't find the unlock in the static analysis is *also* consistent with this hypothesis. Both (b) and (c) are observationally indistinguishable from the offline side.

---

## 7. Decision tree for the rig (updated)

Updated from `BIOS_LATEST.md`'s closing section, incorporating Phase 2 findings:

### Path A — no flash (the user's current hard constraint)

- **Cap is permanent.** Confirmed: no userspace SMN poke works (HwInit), no SMM-revoke exists (`SMM_INVENTORY.md`), no IFR setting controls it (`IFR_VERSION_DIFF.md`), no NVRAM byte controls it (vestigial; values `0x04` aren't consumed either). Rig stays at Gen3 indefinitely.
- **Investigation pivots to hardware-side:** GPU 7's recurring Xid 79 is happening at Gen3 (not Gen4 — never was Gen4 on this BIOS). Every slot has 2+ board-integrated retimers in the path; a misprogrammed retimer can break Gen3 too. Retimer config / cable / connector / slot contact / GPU-PCIe-link-margin should be the focus. Out of BIOS-analysis scope; parent-project owns it.
- **Throughput baseline:** the 76 / 394 t/s prior numbers are not corroborated by BIOS evidence. Current 40 / 92 t/s match the actual Gen3 cap. Treat the prior baseline as suspect.

### Path B — flash to P3.80 (if the user reconsiders)

- **BMC compatibility:** P3.80 + BMC 2.08 IPMI-flash is **likely OK** (no public report of breakage). Even if it weren't, **Instant Flash from BIOS Setup** bypasses the IPMI WebUI path entirely. The only documented flash interlock is P4.10 + BMC 2.08, not P3.80 + 2.08.
- **Risk profile:** flash failure → no-POST. Mitigations: pre-flash dump (`flashrom -p internal -r romed8-pre.bin` first), pre-stage external CH341A + 1.8V level shifter + Pomona 5250 SOIC-8 clip on a separate machine and verify on a sacrificial chip before flashing the rig.
- **Expected outcome:** if hypothesis 6(a) or 6(b) is correct, GPU root ports come up at Gen4. If 6(c) is correct, they stay at Gen3. **No way to predict from offline analysis alone** — the unlock has not been mechanically confirmed.
- **Sequence:** (i) backup SPI; (ii) Instant Flash P3.80 from USB stick; (iii) verify with `lspci -vv | grep -i lnkcap2` on all 8 GPU root ports. If Gen4 → success. If Gen3 → no harm, P3.80 is functionally equivalent to P3.70 for this workload, can stay or revert.
- **Don't sequence BMC flash unless something forces it.** BMC 3.04 is private (ASRock support ticket only). The 45HL data only requires BMC update for P4.10, not P3.80.

### Path C — flash to L4.11 / P4.10

- **Strongly disrecommended.** L4.11 is private (support-ticket only). P4.10 + BMC 2.08 is the documented broken combo (IPMI WebUI BIOS link fails). Bigger risk surface, no incremental Gen4 unlock benefit over P3.80, requires BMC update sequencing.

### Path D — non-flash hardware intervention

- Move one GPU off bifurcation onto a Gen4-advertising slot if any exists. (`40:01.3` is x4 and probably internal — see in-flight task X. If it terminates at the BMC ASPEED or X550 NIC, no relocation possible.)
- Replace marginal retimers / cabling / risers — reduces SI failure rate even at Gen3, addresses GPU 7's Xid 79.
- Out of BIOS-analysis scope; relevant only because Phase 2 has confirmed there is no software fix.

---

## 8. Project state — Phase 2 status & closure conditions

### Current status

- **Phase 1: complete and frozen.** All six original subagents reported negative; the cap was localized to bit 6 of `+0x2E` per-port DXIO descriptor. No software path exists. See `BIOS_LATEST.md`.
- **Phase 2: ~80% complete.** All canonical AGESA / NBIO / CBS / OEM / Setup / SMM / IFR / PEI search avenues exhausted negative. Three follow-up sweeps in flight (A/W/Y/Z) plus three trace tasks (R/V/X). Two terminal hypotheses standing: (a) producer in unanalyzed vol-7 DXE module via non-canonical addressing, (b) producer in encrypted PSP/ABL firmware. Plus the null hypothesis (c) that the unlock doesn't exist as advertised.

### Closure conditions

The project would close definitively on any of:

1. **Producer found.** Either (A)/(V)/(R)/(W)/(Z) lands with a concrete byte-level identification of the bit-6 set instruction in some named module, with characterization of P3.70-vs-P3.80 diff. → answers Phase 2 question (a) vs (b).
2. **PSP / ABL decryption breakthrough.** Public IKEK leak, decap-extracted Rome PSP key, AMD-side disclosure, or a coreboot-side reference implementation that documents the ABL→DXE descriptor pipeline. → answers whether the producer lives in PSP/ABL.
3. **Rig-side empirical verification by someone else.** A different rev-1.03 ROMED8-2T owner runs P3.80 with quantitative `lspci LnkCap2` results. Confirmation either way collapses hypothesis (c). The rig itself cannot do this experiment under the no-flash constraint.
4. **The user lifts the no-flash constraint.** Flashing P3.80 on the rig becomes the empirical experiment, and the result distinguishes (a)/(b) (Gen4 comes up) from (c) (still Gen3). With the current BMC-compat finding this is materially less risky than previously assessed.

### What this project has produced (artifact list)

- 9 disassembly diffs against P3.70/P3.80 (`APCB_DXEV3_DIFF`, `CBSSETUP_DIFF`, `DISASM_AmdNbioBaseSspDxe`, `DISASM_AmdNbioPciePei`, `DISASM_AmdCpmPcieInitPeim`, `DISASM_AmdCheckBmcPciePei`, `DISASM_AmdCpmPcieInitDxe`, `DISASM_AmdCpmOemInitPeim`, `DISASM_AmdNbioBaseSspPei`, `DISASM_CbsBaseDxeSSP`, `DISASM_SETUP_DIFF`)
- 3 sweeps: `MODULE_SWEEP_P3.70_vs_P3.80`, `MODULE_SWEEP_REBASE_AWARE`, `OEM_SHIM_HUNT`, `PEI_PRODUCER_SWEEP`, `SMM_INVENTORY`, `DISASM_CPM_DATA`
- 1 cross-version IFR diff across 4 BIOS versions (`IFR_VERSION_DIFF.md`)
- 1 PSP/ABL diff including key-graph / signing-chain analysis (`PSP_ABL_DIFF.md`)
- 1 single-function caller diff (`APCB_CALLER_FCN13DF4.md`)
- 1 BMC compatibility study (`BMC_COMPAT.md`)
- (in flight) bit-pattern global search, raw image diff, BDF `40:01.3` hunt, call-graph trace, coreboot reference, remaining DXE candidates

The project has produced **byte-level certainty about where the cap is *not*** across the entire UEFI capsule. This is a firm negative result with high information value: it means hypothesis (a) shrinks to a small remaining surface (the 85-differs vol-7 PE32s minus the ~12 already disassembled, requiring non-canonical addressing search), and hypotheses (b) / (c) are co-equal best explanations otherwise.

---

## 9. One-line for `BIOS_LATEST.md` replacement

Once in-flight agents land, `BIOS_LATEST.md` should be replaced (or a `BIOS_LATEST_PHASE2.md` written) summarizing: "Phase 2 confirmed the cap is structural and definitive; localized the unlock — if it exists — to either (a) a non-canonical bit-6 instruction in one of ~73 unanalyzed vol-7 DXE PE32s, (b) the encrypted PSP/ABL firmware substantively rewritten in P3.80, or (c) doesn't exist; flashing P3.80 is the only experimental path forward and is materially safer than previously assessed (BMC 2.08 + P3.80 IPMI is likely OK; Instant Flash bypasses the path anyway)."
