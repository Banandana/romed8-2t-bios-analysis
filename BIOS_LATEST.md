# ROMED8-2T BIOS investigation — Phases 1 + 2 final report

**Date:** 2026-04-27
**Rig:** ASRock Rack ROMED8-2T, EPYC 7532, BIOS P3.70, PCB rev 1.03 (mfg 2025-08-29, assumed-confirmed), 8× RTX 3090
**Constraint:** no BIOS flashing of the rig
**Question driving the work:** can the GPU-slots-Gen3 cap be lifted without flashing?
**Verdict:** **no.** The cap is structural at HwInit, sourced from a build-time constant in AGESA `.data` that is byte-identical between every BIOS version on disk. Any rev-1.03 / P3.80 unlock would have to live in encrypted PSP/ABL firmware (which substantively changed in P3.80 but is unverifiable without per-silicon IKEK), or it does not exist as a BIOS-level change at all.

---

## TL;DR

1. **All 8 GPU root ports are capped at PCIe Gen3** by `EsmControl` (bit 6, mask `0x40`) being clear in byte `+0x2E` of their per-port DXIO descriptors. Confirmed bit name from AMD's openSIL Genoa source (`xUSL/NBIO/GnbDxio.h`) — see `docs/AGESA_DESCRIPTOR_REFERENCE.md`.
2. **`EsmControl` is built-time-baked, not set by code.** Phase 2 exhaustively scanned every PE32 and TE module in all 5 BIOS versions (~1000 modules per version, all encoding forms including non-canonical sliding-window load-OR-store): **zero producer instructions exist anywhere**. Only consumer sites exist (one in `AmdNbioPcieDxe` DXE, one in `AmdNbioPciePei` PEI). The bit value is constant data linked into AGESA `.data`, copied wholesale into the descriptor at HOB-build time.
3. **The producer chain is byte-identical between P3.70 and P3.80.** `AmdNbioPciePei` (HOB builder), `AmdNbioPcieDxe` (protocol installer + consumer), `AmdNbioBaseSspDxe`, `AmdNbioBaseSspPei`, `AmdNbioBaseGnDxe`, `AmdCpmPcieInitDxe/Peim`, `AmdCheckBmcPciePei`, `AmdNbioAlibDxe/ZpDxe` — all byte-identical. Combined with #2, **no BIOS PE32 carries any P3.70→P3.80 difference that could enable Gen4**.
4. **PSP/ABL firmware was substantively rewritten in P3.80** (Rome-PI → Milan-PI-superset; ABL stack `10.F.20.10 → 34.24.20.10`; PSP_FW_BOOT_LOADER `0.C.0.87 → 0.C.0.88`). Bodies are AES-CCM-encrypted with silicon-fuse-derived IKEK and statically unreadable. This is the only BIOS layer with substantive change between the two versions, and the only place a real rev-1.03 unlock could plausibly live undetected.
5. **The cap is silicon-side, latched at HwInit before any OS code runs.** Phase 1 confirmed `LC_GEN4_EN_STRAP` (SMN `0x111402A4`) is HwInit-locked; Phase 2's SMM inventory confirmed no SMM trap intercepts LCTL2/SMN writes; Phase 2's IFR sweep across 4 versions confirmed no Gen4 setting is hidden anywhere in NVRAM. **No userspace runtime fix is possible.**
6. **The user's BIOS click did write 6 NVRAM bytes** (per-slot Link Speed offsets `0x123/0x124/0x129/0x12A/0x12B/0x12C`) from `0x00` (Auto) to `0x01` (GEN1, not GEN3). They landed on the vestigial ASRock-board IFR menu that AGESA does not consume. The IFR menu does offer GEN4=`0x04` as an option (correction to the older claim that it only offered up through GEN3), but writing `0x04` would be ignored too — these bytes are vestigial regardless of value.
7. **BMC 2.08 + P3.80 IPMI flash is likely OK.** The documented IPMI-flash interlock is P4.10 + BMC 2.08, not P3.80. Instant Flash from BIOS Setup bypasses the IPMI WebUI path entirely. Risk profile for P3.80 flashing is materially lower than previously assessed — but the BIOS-side analysis suggests the unlock probably won't materialize either, so the expected outcome is "still Gen3, no harm".

---

## The cap, at byte/bit precision

| Location | Detail |
|---|---|
| Field | `EsmControl` (1-bit) inside the per-port DXIO descriptor's "miscellaneous controls" byte |
| Byte offset (P3.11–P3.80) | `+0x2E` |
| Byte offset (P3.90+) | `+0x32` (descriptor schema bumped +4 B) |
| Bit position | bit 6 (mask `0x40`) |
| Producer | constant data in AGESA `.data`, baked at build time |
| Consumer (DXE) | `AmdNbioPcieDxe::PcieAttemptEsmIfEnabled` at file offset `0x14b1e`: `test byte [r14+0x2e], 0x40` |
| Consumer (PEI) | `AmdNbioPciePei::fcn_0x2f53`: `test byte [edi+0x2e], 0x40`, branches to SMN write at `0x11180604` |
| Debug strings (PEI consumer) | `"EsmSpeedBump"`, `"Forcing Gen3 on this PCIe port for ESM sequence later."` |
| Strap register | `LC_GEN4_EN_STRAP`, SMN `0x111402A4` per IOHC, HwInit-locked |
| Producer-protocol GUID | `gAmdNbioPcieServicesProtocolGuid` = `756DB75C-BB9D-4289-813A-DF2105C4F80E`, vtable[0] = `PcieGetTopology` |
| Producer HOB GUID | `gGnbPcieHobInfoGuid` = `03EB1D90-CE14-40D8-A6BA-103A8D7BD32D` |
| HOB builder | `AmdNbioPciePei.efi` (TE PEIM, 73,704 B, byte-identical P3.70 = P3.80) |

The producer module *zero-fills* the HOB at build time, then the AGESA descriptor synthesizer (in some module that is byte-identical between P3.70 and P3.80) populates it from a constant template. The template encodes `EsmControl=0` for the GPU root ports and `EsmControl=1` for the lone BMC-side port `40:01.3`. ASRock's choice of which ports get the bit set is baked at AGESA build time and unchanged across the P3.70/P3.80 boundary.

---

## Phase 2 — what was investigated

Twenty-two parallel agents (counting Phase 2's bit-pattern, module sweep, OEM hunt, PEI sweep, SMM inventory, IFR diff, PSP/ABL diff, plus 14 targeted module disassemblies and the GUID-trace pipeline) attacked the question from every direction. Detailed per-agent reports in `docs/`. Highlights:

### Modules ruled out as the producer (each byte-pattern + string-scanned + cross-version diffed)

`AmdApcbDxeV3`, `CbsSetupDxeSSP`, `CbsBaseDxeSSP`, `AmdNbioBaseSspDxe`, `AmdCpmPcieInitPeim`, `AmdCpmPcieInitDxe`, `AmdCheckBmcPciePei`, `AmdNbioPciePei`, `AmdCpmOemInitPeim`, `AmdNbioBaseSspPei`, `Setup` (ASRock HII), `AmdRasSspDxe`, `AmdRasSspSmm`, `PciDxeInit`, `PciBus`, `PciRootBridge`, `AmdPlatformRasSspDxe`, `AmdPlatformRasZpDxe`, `AmdSmbiosDxe`, `GenericSio`. Plus the full PEI sweep (16 truly-changed PEIMs, all negative) and SMM inventory (91 modules, 7 differ, none Gen4-relevant).

### Sweeps with all-negative results

- **Whole-image bit-pattern scan** across all 5 versions, both DXE and PEI, every encoding form including non-canonical sliding-window load-OR-store: **zero producer hits**. Only one consumer instruction per binary, all byte-identical across versions.
- **Module sweep** rebase-aware: 85 of 651 PE32 modules genuinely differ between P3.70 and P3.80 (mostly RAS event-ID renumbering, PCD token shifts, build-info ASCII). None contains a Gen4 producer.
- **PEI cold-boot phase**: exhausted negative.
- **SMM enumeration**: no SMM module is Gen4-related; 7 differing modules are all unrelated (PSP mailbox, NVRAM, OFBD, etc).
- **IFR cross-version diff** (P3.70/P3.80/P3.90/P4.10): zero new Gen4-related settings in any version.
- **OEM-shim hunt**: ASRock did not ship a `*Oem*` / `*Asrock*` / `*Rs1*` / `*Strap*` named module. Per-board config is embedded inside `AmdCpmOemInitPeim`'s `.data`, byte-identical between versions modulo rebase.
- **CpmData / PlatformData hunt**: no separately-linked OEM data module exists.
- **Whole-image FFS-aware byte diff**: zero non-PE32, non-PSP, non-APCB region differs in a Gen4-relevant way.
- **BDF `40:01.3` static-table hunt**: the lone Gen4-capable port's BDF does not appear as static data anywhere — definitively confirms runtime synthesis from a template, not a baked descriptor list.

### Confirmed positive findings

- **PSP/ABL firmware substantively rewritten** between P3.70 and P3.80. Rome-PI stack collapsed; both ROMs now run Milan-PI-superset (which handles Rome silicon). Bodies AES-CCM-encrypted; statically unreadable.
- **Producer-protocol GUID identified**: `gAmdNbioPcieServicesProtocolGuid`, defined in AMD's open `edk2-platforms/Platform/AMD/AgesaModulePkg/AgesaModuleNbioPkg.dec`. Vtable[0] = `PcieGetTopology`. Returns a tree of `PCIE_DESCRIPTOR_HEADER` nodes via `gGnbPcieHobInfoGuid`.
- **HOB builder is `AmdNbioPciePei`**, byte-identical P3.70 = P3.80. The builder zero-fills; the descriptor template is populated by a byte-identical module elsewhere in the AGESA pipeline.
- **Consumer evolution**: descriptor schema bumped +4 B between P3.80 and P3.90 (ESM byte moved `+0x2E` → `+0x32`), but gating shape unchanged since L3.11.
- **BMC compatibility**: documented IPMI-flash interlock applies to **P4.10 + BMC 2.08, not P3.80 + 2.08**. P3.80 + 2.08 is shipping in the field on HL15 V2.0 systems with no reported issue. Instant Flash from BIOS Setup bypasses the IPMI path anyway.

---

## Three terminal hypotheses for the rev-1.03 / P3.80 unlock

After Phase 2's exhaustive analysis, exactly three possibilities remain, in order of plausibility:

### (a) Encrypted PSP / ABL firmware [most likely]

ABL is the documented AGESA layer that consumes APCB tokens and platform-init data at boot. The Rome→Milan-PI-superset ABL swap between P3.70 and P3.80 is the single biggest functional change between the two BIOSes, and it is the only layer with substantive change that we cannot statically verify. If ABL contains a board-rev gate that mutates the AGESA descriptor template before HOB build, that's the rev-1.03 unlock.

**Verifiability:** none from offline analysis. AES-CCM body, IKEK derived from per-silicon PSP fuses, no public Rome IKEK leak. Cannot decrypt, cannot patch, cannot re-sign without OEM key `1DC2`.

**Path to confirmation:** flash P3.80 to the rig (or any rev-1.03 ROMED8-2T) and observe `lspci LnkCap2` on the GPU root ports.

### (b) Doesn't exist [cannot be ruled out from offline alone]

The community report (ASRock Forum TID 24737) of P3.80 enabling Gen4 on rev-1.03 may be (i) misattribution (BMC port `40:01.3` already advertised Gen4 on P3.70; someone may have misread that), (ii) confusion with an unrelated rev-1.03 improvement (different PCB trace lengths, retimer config), or (iii) a legitimate report from a different SKU/build that doesn't match this rig's silicon stepping.

**Indistinguishability:** observationally identical to (a) from the offline side. Only first-hand `lspci` data from a rev-1.03 P3.80 owner would distinguish.

### (c) Non-canonical bit-6 instruction in some unanalyzed module [unlikely]

A producer using register-loaded base + register-immediate ORs that escape every byte-pattern encoding form. Phase 2's exhaustive search included sliding-window load-OR-store detection, so this would require a truly non-canonical instruction sequence (e.g. constructed via dispatch tables or vtable callbacks). Possible but very unlikely given AGESA's idiomatic code patterns.

**Caveat:** if such an instruction exists, it would still need to run for GPU root ports specifically and only on rev-1.03, which would mean adding board-rev MMIO/strap reads — and Phase 2 found no such reads in any AGESA NBIO module (`AmdCheckBmcPciePei`, `AmdBoardIdPei`, etc., all byte-identical or rebase-only).

---

## Decision tree for the rig

### Path A — no flash (current hard constraint)

- **Cap is permanent at Gen3.** Confirmed across every avenue.
- Investigation pivots to **hardware-side**: GPU 7's recurring Xid 79 is happening at Gen3 (always was — never was Gen4 on this BIOS). Every slot has 2+ board-integrated retimers. Misprogrammed retimer / cable / connector / link-margin issues should be the focus. Out of BIOS-analysis scope; parent-project owns.
- Throughput baseline correction: prior 76/394 t/s "Gen4" numbers are **not corroborated by BIOS evidence**. Current 40/92 t/s match the actual Gen3 cap. The earlier baseline was likely never at Gen4 on this rig.

### Path B — flash to P3.80 (if the user reconsiders)

Phase 2 has materially reduced the risk profile but also materially reduced the expected payoff. Updated assessment:

- **BMC compatibility:** P3.80 + BMC 2.08 IPMI-flash is **likely OK**. Even if it weren't, **Instant Flash from BIOS Setup** bypasses the IPMI WebUI path. The only documented interlock is P4.10 + 2.08.
- **Risk profile:** flash failure → no-POST. Mitigations: pre-flash dump (`flashrom -p internal -r romed8-pre.bin` first); pre-stage external CH341A + 1.8V level shifter + Pomona 5250 SOIC-8 clip; verify on a sacrificial chip before touching the rig.
- **Expected outcome:** if hypothesis (a) holds and rev-1.03 unlock is real, GPU root ports come up at Gen4. If (b) holds, they stay at Gen3. **Cannot predict from offline analysis.** The BIOS-level evidence weakly suggests (b) is more likely than (a) — every layer except encrypted PSP/ABL was identical between P3.70 and P3.80.
- **Sequence:** (i) backup SPI; (ii) Instant Flash P3.80 from USB stick; (iii) verify with `lspci -vv | grep -i lnkcap2` on all 8 GPU root ports. If Gen4 → success. If Gen3 → no harm, P3.80 is functionally equivalent to P3.70 for Gen-cap purposes; can stay or revert.
- **BMC update is not required for P3.80** — the public 45HomeLab data only requires BMC update for P4.10 specifically.

### Path C — flash to L4.11 / P4.10

- **Strongly disrecommended.** L4.11 is private (support-ticket only). P4.10 + BMC 2.08 is the documented broken combo. No incremental Gen4 unlock benefit over P3.80.

### Path D — non-flash hardware intervention

- **Trace `40:01.3`'s endpoint** — the lone Gen4-capable root port; if it terminates at an unused / repurpose-able lane, an analogous re-routing could give one GPU Gen4. (See `docs/BDF_40_01_03_HUNT.md` for the static-table hunt; the descriptor is runtime-synthesized so this is rig-side investigation only.)
- **Replace marginal retimers / cabling / risers** — addresses GPU 7's Xid 79 even at the current Gen3 cap. Out of BIOS-analysis scope.

### Path E — residual cheap experiment (Phase 1 leftover)

`docs/RIG_RUNBOOK_GEN4_OVERRIDE.md` documents the exact sequence to test `LC_TARGET_LINK_SPEED_OVERRIDE` on one GPU root port. Strong prior says still drops to Gen3 (TS1/TS2 rate set is gated by `LC_GEN4_EN_STRAP` = HwInit, not by the override field). Test is cheap, definitive if attempted, requires `/dev/mem` write authorization on the rig — not yet authorized.

---

## Empirical state of the rig (canonical, as of 2026-04-27, unchanged since Phase 1)

```
CPU              : AMD EPYC 7532 (32C/64T, Rome / Zen 2, family 17h model 31h)
Microcode        : 0x0830107C (current — no update available)
NBIOs            : 4 (ivhd0–ivhd3)
NUMA             : 1 (NPS=1)
Board            : ASRock Rack ROMED8-2T
Board mfg date   : 2025-08-29 (per ipmitool fru); PCB rev 1.03 (assumed-confirmed)
Board PN field   : 3.08 (BIOS-reported, not silkscreen)
BIOS             : P3.70 (American Megatrends, 2023-05-30)
BMC firmware     : 2.08
Driver           : nvidia 595.58.03 (proprietary, NOT nvidia-open)
GSP firmware     : disabled (NVreg_EnableGpuFirmware=0)
Kernel           : Linux 6.19.12-arch1-1
Kernel cmdline   : pcie_aspm=off
```

All 8 GPU root ports: `LnkCap2: 2.5–8GT/s` (Gen3-capped). One non-slot root port `40:01.3` (x4): `LnkCap2: 2.5–16GT/s` (Gen4 advertised; endpoint identity unconfirmed). Per-slot Link Speed NVRAM has 6 user-written `0x01` (GEN1) bytes that AGESA ignores (vestigial menu).

Throughput (Qwen3.5-122B-A10B AWQ, TP=8, vLLM v0.19.0): 40/92 t/s — matches actual Gen3 cap. The prior "Gen4" 76/394 t/s baseline is not corroborated by BIOS evidence and was likely never measured at Gen4 on this rig.

---

## Topology

7 × Gen4 x16 CPU-direct slots (PCIE1–PCIE7) + 2 × M.2 + 2 × OCU SlimSAS (sharing PCIE2 lanes) + dual X550 NICs. All 128 IOD lanes accounted for. **Every slot has 2+ board-integrated retimers in the path** — relevant for Gen4 SI and for diagnosing GPU 7's Xid 79 even at the current Gen3 cap.

---

## Index of detailed reports

### Phase 1 (closed)
| File | Verdict |
|------|---------|
| `docs/AMD_IOPM_UTIL.md` | negative — wrong layer |
| `docs/APCB_DECODE.md` | negative redirect — APCB has no DXIO descriptors |
| `docs/PPR_REGISTER_NOTES.md` | negative — strap is HwInit-locked |
| `docs/SUPPRESSED_OPTIONS.md` | negative — no hidden Gen4 IFR option |
| `docs/DEFAULT_STORE_DIFF.md` | partial — user wrote 6 vestigial NVRAM bytes |
| `docs/RADARE2_NBIOPCIE.md` | breakthrough — gate identified at bit/byte |

### Phase 2 — module disassembly diffs
| File | Verdict |
|------|---------|
| `docs/APCB_DXEV3_DIFF.md` | negative — +64 B is APCB shadow-copy plumbing |
| `docs/CBSSETUP_DIFF.md` | negative — +320 B is HII string churn |
| `docs/DISASM_AmdNbioBaseSspDxe.md` | negative — byte-identical, no `+0x2E` access |
| `docs/DISASM_AmdNbioPciePei.md` | negative as producer; identifies 3rd consumer site |
| `docs/DISASM_AmdCpmPcieInitPeim.md` | negative — pure rebase artifact |
| `docs/DISASM_AmdCheckBmcPciePei.md` | negative — PCIe equalization workaround, not Gen-cap |
| `docs/DISASM_AmdCpmPcieInitDxe.md` | negative — CPM tag-dispatcher, byte-identical |
| `docs/DISASM_AmdCpmOemInitPeim.md` | negative — pure ImageBase rebase artifact |
| `docs/DISASM_AmdNbioBaseSspPei.md` | negative — byte-identical, no `+0x2E` access |
| `docs/DISASM_CbsBaseDxeSSP.md` | negative — linker re-layout artifact |
| `docs/DISASM_SETUP_DIFF.md` | negative — single SecureBoot null-check |
| `docs/DISASM_CPM_DATA.md` | negative — no separately-linked CPM data module exists |
| `docs/DISASM_REMAINING_DXE.md` | negative — PCD token-table renumbering across all 5 |
| `docs/APCB_CALLER_FCN13DF4.md` | negative — DDR4 PPR plumbing, not Gen4 |

### Phase 2 — sweeps and reference research
| File | Verdict |
|------|---------|
| `docs/MODULE_SWEEP_P3.70_vs_P3.80.md` | 85 of 651 PE32 differ; none are Gen4-related |
| `docs/MODULE_SWEEP_REBASE_AWARE.md` | confirms 85 are real diffs, not rebase artifacts |
| `docs/PEI_PRODUCER_SWEEP.md` | exhausts PEI cold-boot phase as a search space |
| `docs/SMM_INVENTORY.md` | 91 SMM modules; 7 differ; none Gen4-related |
| `docs/OEM_SHIM_HUNT.md` | no ASRock OEM-shim module exists |
| `docs/IFR_VERSION_DIFF.md` | no new Gen4 IFR option in any of 4 versions |
| `docs/BIT_PATTERN_SEARCH.md` | exhaustive — zero producer hits in any module |
| `docs/RAW_IMAGE_DIFF.md` | no non-PE32 region carries Gen4-relevant change |
| `docs/BDF_40_01_03_HUNT.md` | confirms runtime synthesis (no static descriptor) |
| `docs/CALLGRAPH_TRACE.md` | identifies producer-protocol GUID |
| `docs/PRODUCER_GUID_HUNT.md` | identifies producer module = `AmdNbioPcieDxe` itself |
| `docs/PRODUCER_GUID_IDENTITY.md` | GUID = `gAmdNbioPcieServicesProtocolGuid` (AMD edk2-platforms) |
| `docs/PRODUCER_MODULE_FOUND.md` | clarifies: HOB builder = `AmdNbioPciePei`, byte-identical |
| `docs/AGESA_DESCRIPTOR_REFERENCE.md` | bit 6 = `EsmControl` (openSIL Genoa) |
| `docs/CONSUMER_EVOLUTION.md` | descriptor schema bump +4 B between P3.80 and P3.90 |
| `docs/PSP_ABL_DIFF.md` | PSP firmware substantively rewritten; encrypted |
| `docs/BMC_COMPAT.md` | P3.80 + BMC 2.08 IPMI-flash likely OK |
| `docs/RIG_RUNBOOK_GEN4_OVERRIDE.md` | runbook for residual `/dev/mem` experiment |

### Phase 1 reference (still relevant)
- `docs/CROSS_VERSION_DIFF.md` — original module hash diff across 5 versions
- `docs/BIOS_REFERENCE_P3.70.md` — full IFR setting reference
- `docs/BIOS_REFERENCE_P3.80.md`, `P3.90.md`, `P4.10.md` — IFR references for later versions
- `docs/SUPPRESSED_OPTIONS_P3.{70,80,90,4.10}.md` — per-version suppressed option dumps

---

## Closing

The BIOS-side investigation is complete. Across Phase 1 + Phase 2 the project produced byte-level certainty about where the cap is, where it is enforced, what the gating bit's canonical AGESA name is, and — crucially — **where the cap is NOT**. The producer of `EsmControl` is build-time-baked AGESA constant data that does not change between any of the 5 BIOS versions on disk. No userspace fix exists, no IFR setting controls it, no NVRAM byte controls it, no SMM trap intercepts it, and no PE32/TE module sets it as code.

The only remaining offline question — whether P3.80's encrypted PSP/ABL firmware contains a board-rev gate that mutates the AGESA descriptor template before HOB build — is structurally unanswerable without per-silicon IKEK keys we do not have.

The actionable conclusion is unchanged from Phase 1: under the no-flash constraint, the rig stays at Gen3 indefinitely. The throughput baseline numbers attributed to Gen4 in earlier project notes were almost certainly never measured at Gen4 on this rig. The parent project's path forward is hardware-side: GPU 7's Xid 79 at Gen3, retimer config, slot contact, and the open question of whether `40:01.3`'s Gen4-capable lane could be repurposed for one GPU.

If the user ever lifts the no-flash constraint, P3.80 is materially safer to flash than previously assessed (BMC 2.08 + P3.80 IPMI is likely OK; Instant Flash bypasses any path issues) — but the BIOS-side analysis suggests a Gen4 unlock is more likely to NOT materialize than to materialize, since every layer except encrypted PSP/ABL is identical between P3.70 and P3.80.
