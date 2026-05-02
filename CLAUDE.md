# ROMED8-2T BIOS reverse-engineering — agent operational context

> **Canonical project narrative is in `BIOS_LATEST.md`** — read it first for the full Phase 1 + Phase 2 story, the cap's byte/bit precision, the three terminal hypotheses, and the decision tree.
>
> This file is agent-operational context only: project state, constraints, tooling, and directory layout.

## Project state (2026-04-27, post-Phase 2)

**Phase 1 + Phase 2 both complete.** ~28 parallel agent dispatches across the two phases. The Gen4 cap is structural at HwInit, sourced from a build-time AGESA constant that is byte-identical between every BIOS version on disk. Detailed verdict, evidence chain, and decision tree in `BIOS_LATEST.md`.

**TL;DR for agents picking this up:**
- The cap is `EsmControl` bit (bit 6 of byte `+0x2E` in P3.11–P3.80, `+0x32` in P3.90+) of the per-port DXIO descriptor. Confirmed AGESA name from openSIL Genoa source.
- Phase 2 exhaustively ruled out every BIOS PE32/TE module as the bit-6 setter. The bit is build-time constant data, not code.
- All AGESA NBIO modules are byte-identical between P3.70 and P3.80.
- The only BIOS layer with substantive change is the encrypted PSP/ABL firmware, which is statically unverifiable.
- Three terminal hypotheses: (a) encrypted PSP/ABL [most likely], (b) doesn't exist, (c) non-canonical instruction in unanalyzed module [unlikely].
- No-flash conclusion: cap is permanent at Gen3.
- Flash decision: P3.80 is materially safer than previously assessed (BMC 2.08 + P3.80 IPMI is likely OK; Instant Flash bypasses the path anyway), but the BIOS-side analysis suggests the unlock is more likely to NOT materialize than to materialize.

## Hard user constraints (binding)

- **No flashing the rig.** Hard.
- **No NVRAM writes to the rig** unless explicitly authorized.
- **Read-only on rig.** All "writes" are local on this machine.
- **Treat dumped BIOS as sensitive.** May contain board-specific keys. Don't post images publicly.
- **If a tool fails, document the failure, try an alternative, don't paper over it.**

## What is and isn't in this repo

**Committed:**
- All Phase 1 + Phase 2 finding docs in `docs/`
- `BIOS_LATEST.md` (canonical synthesis), `report/` (long-form Phase 1 narrative, split per part), `FINDINGS.md` (Phase 1 baseline)
- All scripts in `scripts/` and shared lib `scripts/lib/`
- `README.md` with onboarding procedure

**Gitignored (regenerated locally):**
- `images/ROMD82T<version>` — raw BIOS images, ~33 MiB each. Re-download from archive.org via the procedure in `README.md`.
- `extracted/all/P<version>/` — UEFIExtract dump trees. Re-generate with `uefiextract images/ROMD82T<v>` after staging the image into `extracted/all/P<v>/img.bin`.
- `ifr/P<version>/` — per-version IFR text dumps.
- `apcb_work/` — extracted APCB blobs.
- `tools/` — source-built UEFITool tree.

## Tools (verified installed on this machine 2026-04-27)

| Tool | Source | Path | Purpose |
|------|--------|------|---------|
| `uefiextract` | LongSoft NE alpha 75, built from `tools/UEFITool/UEFIExtract/` | `~/.local/bin/uefiextract` | Dump UEFI capsule into per-module FFS tree |
| `uefifind` | LongSoft, built from `tools/UEFITool/UEFIFind/` | `~/.local/bin/uefifind` | Search for GUIDs / patterns inside capsule |
| `uefitool` | AUR `uefitool` 0.28.0-3 | `/usr/bin/uefitool` | GUI viewer |
| `ifrextractor` | AUR `ifrextractor-rs-bin` 1.6.1-1 | `/usr/bin/ifrextractor` | Decode AMI Setup IFR |
| `binwalk` | repo 3.1.0 | `/usr/bin/binwalk` | Generic firmware structure inspection |
| `radare2` | repo 6.1.4-1 | `/usr/bin/radare2` | PE32/TE disassembly |
| `psptool` | pip user-install | (python module) | Decode PSP firmware directory |
| `r2mcp` | r2pm | `~/.local/share/radare2/prefix/bin/r2mcp` | Radare2 MCP server (registered in `~/.claude.json`) |
| `flashrom` | repo 1.7.0 | `/usr/bin/flashrom` | **DO NOT RUN ON THIS MACHINE** — would flash this machine's SPI |

The radare2 MCP server is registered in `~/.claude.json` under `mcpServers.radare2` as `{"command": "r2pm", "args": ["-r", "r2mcp"]}`. Use `mcp__radare2__*` tools when an agent needs sustained disasm sessions instead of spawning many `r2` subprocesses.

## Directory layout

```
~/Desktop/romed8-2t-bios-analysis/
├── BIOS_LATEST.md                ← canonical synthesis (read this first)
├── REPORT.md                     ← stub; long-form report now under report/
├── report/                       ← Phase 1 long-form narrative, split per part
├── FINDINGS.md                   ← Phase 1 baseline
├── README.md                     ← onboarding / re-downloading BIOS images
├── CLAUDE.md                     ← this file
├── docs/                         ← all per-investigation findings (~40 files)
│   ├── PLANNED_SUBAGENTS.md      ← stale — see "PLANNED_SUBAGENTS.md status" below
│   ├── PHASE2_SYNTHESIS_DRAFT.md ← superseded by BIOS_LATEST.md
│   └── ...                       ← see BIOS_LATEST.md "Index of detailed reports"
├── scripts/                      ← reusable analysis tooling
│   ├── lib/                      ← shared modules (versions.py, ffs.py, pe32.py)
│   ├── module_sweep.py           ← Phase 2: full PE32 hash/size diff
│   ├── find_bit_pattern.py       ← Phase 2: byte-pattern hunter
│   ├── ifr_to_reference.py       ← Phase 1: IFR → structured markdown
│   ├── list_suppressed.py        ← Phase 1: SuppressIf enumerator
│   ├── diff_versions.py          ← Phase 1: original cross-version module diff
│   ├── extract_ifr_all.sh        ← Phase 2: bulk IFR extraction
│   └── diff_ifr_versions.py      ← Phase 2: IFR cross-version diff
├── images/                       ← raw BIOS images (gitignored)
└── extracted/all/P<v>/           ← UEFIExtract dump trees (gitignored)
```

## PLANNED_SUBAGENTS.md status

`docs/PLANNED_SUBAGENTS.md` describes 8 planned dispatches that were drafted on 2026-04-27 before the analyst machine migration. **All 8 ran during Phase 2 plus ~14 dynamically-dispatched follow-ups based on emerging findings.** The file remains for historical context but the planned items themselves are closed:

| Planned dispatch | Status | Output |
|------------------|--------|--------|
| 1. module_sweep | done | `scripts/module_sweep.py`, `docs/MODULE_SWEEP_*` |
| 2. AmdNbioBaseSspDxe disasm_diff | done | `docs/DISASM_AmdNbioBaseSspDxe.md` |
| 3. AmdCpmPcieInitPeim diff | done | `docs/DISASM_AmdCpmPcieInitPeim.md` |
| 4. AmdCheckBmcPciePei diff | done | `docs/DISASM_AmdCheckBmcPciePei.md` |
| 5. AmdNbioPciePei diff | done | `docs/DISASM_AmdNbioPciePei.md` |
| 6. OEM-shim hunt | done | `docs/OEM_SHIM_HUNT.md` |
| 7. Bit-pattern global search | done | `docs/BIT_PATTERN_SEARCH.md`, `scripts/find_bit_pattern.py` |
| 8. BMC compat web research | done | `docs/BMC_COMPAT.md` |

Plus dynamic follow-ups: `AmdCpmPcieInitDxe`, `AmdNbioBaseSspPei`, `AmdCpmOemInitPeim`, `CbsBaseDxeSSP`, `Setup`, `AmdCpmData*`, rebase-aware sweep, PEI producer sweep, SMM enumeration, IFR cross-version, PSP/ABL diff, raw image diff, BDF `40:01.3` hunt, AGESA reference research, call-graph trace, GUID hunt, GUID identity, producer-instruction verification, consumer evolution, rig runbook, remaining DXE candidates, AmdApcbDxeV3 fcn caller analysis. All in `docs/`.

## Empirical state of the rig (canonical, unchanged)

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

All 8 GPU root ports: `LnkCap2: 2.5–8GT/s` (Gen3-capped). Lone non-slot Gen4 port `40:01.3` (x4): `LnkCap2: 2.5–16GT/s`, endpoint identity unconfirmed.

Per-slot Link Speed NVRAM (Setup VarStore, GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`):
```
0x123 PCIE1 = 0x01 (GEN1)    ← user wrote
0x124 PCIE2 = 0x01 (GEN1)    ← user wrote
0x125 PCIE3 = 0x00 (Auto)
0x126 PCIE4 = 0x00 (Auto)
0x127 PCIE5 = 0x00 (Auto)
0x128 PCIE6 = 0x00 (Auto)
0x129 PCIE7 = 0x01 (GEN1)    ← user wrote
0x12A OCU1  = 0x01 (GEN1)    ← user wrote
0x12B OCU2  = 0x01 (GEN1)    ← user wrote
0x12C M2_1  = 0x01 (GEN1)    ← user wrote
0x12D M2_2  = 0x00 (Auto)
```

These bytes are vestigial — AGESA does not consume them. The IFR menu offers Auto/GEN1/GEN2/GEN3/GEN4=`0x04` as values, but writing GEN4=`0x04` would be ignored too (correction to the older "only Auto/GEN1/GEN2/GEN3" claim).

AGESA NBIO globals (AmdSetupSSP, GUID `3A997502-647A-4C82-998E-52EF9486A247`) at AGESA defaults:
```
0x15C Early Link Speed                 = 0x00 (Auto)
0x169 Multi Upstream Auto Speed Change = 0x0F (Auto sentinel)
0x16A Multi Auto Speed Change On Last  = 0xFF (Auto sentinel)
```

Throughput baseline (Qwen3.5-122B-A10B AWQ, TP=8, vLLM v0.19.0):

| Test | Now (Gen3) | CLAUDE.md prior ("Gen4") |
|------|-----------:|-------------------------:|
| Single-stream 512 tok | 40.4 tok/s | 76 |
| Concurrent ×4, 256 tok | 75 agg | — |
| Concurrent ×8, 256 tok | 91 agg | — |
| Concurrent ×16, 256 tok | 92.6 agg | 394 |

The prior "Gen4" baseline is not corroborated by BIOS evidence and was likely never measured at Gen4 on this rig.

## Topology (unchanged)

7 × Gen4 x16 CPU-direct slots (PCIE1–PCIE7) + 2 × M.2 + 2 × OCU SlimSAS (sharing PCIE2 lanes via PE8_SEL/PE16_SEL jumpers #26/#27) + dual X550 NICs. All 128 IOD lanes used. **Every slot has 2+ board-integrated retimers in the path** — relevant for Gen4 SI behavior, and highly relevant for diagnosing GPU 7's Xid 79 even at the current Gen3 cap.

## Re-run pipelines

```bash
# Re-extract all 5 BIOS images (after staging into extracted/all/P<v>/img.bin)
for v in 3.11 3.70 3.80 3.90 4.10; do
  (cd extracted/all/P${v} && uefiextract img.bin all)
done

# Re-build the BIOS reference
python3 scripts/ifr_to_reference.py ifr/P3.70/_all docs/BIOS_REFERENCE_P3.70.md

# Re-run the cross-version module sweep
python3 scripts/module_sweep.py 3.70 3.80

# Re-run the bit-pattern global search
python3 scripts/find_bit_pattern.py --versions 3.70 3.80
```

## What's still open

The project is effectively closed pending one of:

1. **PSP/ABL decryption breakthrough** — public IKEK leak, decap-extracted Rome key, AMD-side disclosure, or a coreboot-side reference implementation that documents the ABL→DXE descriptor pipeline. Would distinguish hypothesis (a) from (b).
2. **Rig-side empirical verification** — a different rev-1.03 ROMED8-2T owner runs P3.80 with quantitative `lspci LnkCap2` results. Distinguishes (b) from (a)/(c).
3. **The user lifts the no-flash constraint** — flashing P3.80 on the rig becomes the empirical experiment; the result distinguishes (a) (Gen4 comes up) from (b) (still Gen3). Per `docs/BMC_COMPAT.md` and `docs/RIG_RUNBOOK_GEN4_OVERRIDE.md`, this is materially safer than originally assessed.

Adjacent unanswered questions (low priority):
- What endpoint hangs off the lone Gen4-capable root port `40:01.3`? Rig-side `lspci -tvv` trace would tell. If it terminates on an unused / repurpose-able lane, an analogous re-routing could give one GPU Gen4. Out of BIOS-analysis scope; rig contact required.
- Cross-vendor APCB comparison (Supermicro H12SSL-i, TYAN S8030, Gigabyte MZ32-AR0) — would show whether other Rome SP3 boards have different `EsmControl` defaults for their slots. Heavy lift; not pursued. Listed in `docs/PLANNED_SUBAGENTS.md` (item 7) as background.

## BIOS version reference (extracted from images, since ASRock publishes nothing official)

| Version | Date | AGESA Rome | AGESA Milan | Microcode | Notes |
|---------|------|------------|-------------|-----------|-------|
| L3.11 | 2021-03-17 | 1.0.0.9 | — | (Naples-era) | first version analyzed |
| P3.70 | 2023-05-30 | 1.0.0.F | 1.0.0.A | 0x08301055 | rig's current |
| P3.80 | 2023-08-01 | 1.0.0.G | 1.0.0.A | 0x08301072 | rumored rev-1.03 Gen4 unlock |
| P3.90 | 2024-08-12 | 1.0.0.H | 1.0.0.C | 0x0830107B | minor refresh, NOT Sinkclose-patched |
| P4.10 | 2025-06-05 | 1.0.0.L | 1.0.0.G | 0x0830107D | first post-Sinkclose; P4.10+BMC2.08 IPMI broken |
| L4.11 | private | ? | ? | ? | hotfix, support-ticket only |

Microcode note: rig runs `0x0830107C` (Sinkclose-patched) from Linux microcode loader at OS time, regardless of BIOS-bundled value. So the BIOS-microcode column matters only for pre-OS code. CPU perf delta from BIOS microcode is zero for this rig.

P3.90-specific: see `docs/P3.90_UPDATE_INFO.md` (changelog absent, characterized via image strings + scan) and `docs/P3.90_MULTI_GPU_RESEARCH.md` (no documented multi-GPU regressions on any forum). P3.90 is unlikely to provide perf improvements on this rig — AGESA bump at this point in Rome's lifecycle is minor; Gen3 cap is structural and unchanged across all 5 versions; rig's actual bottleneck is PCIe Gen3 on TP=8 allreduce, not anything AGESA tunes.

## Background — do not re-derive

- ASRock Rack publishes no per-version BIOS changelogs. Cross-version diff IS the changelog.
- L1Techs ROMED8-2T thread (157449) — no useful Target Link Speed discussion.
- L1Techs KMPP-D32 thread (228014) — sibling EPYC board uses setup_var pattern that doesn't work here (vestigial NVRAM bytes).
- AMD CBS structural rule: per-NBIO (4 NBIOs × 32 lanes per socket). Per-slot menus only matter if the OEM wired a per-DXIO-engine override into IFR (ASRock did, but AGESA ignores it).
- ROMED8-2T manual does not enumerate AMD CBS / NBIO submenus — they are AGESA-generated, varying by AGESA version.
- L4.11 BIOS is private (ASRock Rack support ticket only). Not pursued.
- AMD-IOPM-UTIL is "I/O Power Management" (LCLK / DPM lock state), not link-speed. Wrong layer entirely. Closed in Phase 1.
- All 5 dead-end runtime registers (`LC_GEN2/3/4/5_EN_STRAP`, `LC_CURRENT_DATA_RATE`, `LC_DATA_RATE_ADVERTISED`, `LC_ESM_PLL_INIT_DONE`, `LinkCapabilities.MaxLinkSpeed`) are HwInit-locked. Don't re-research.
- No SMM module is involved in Gen4-cap enforcement (Phase 2 confirmed across 91 SMM modules).
- No IFR setting controls Gen4 (Phase 1 + Phase 2 IFR cross-version).
- No NVRAM byte controls Gen4 (Phase 1 + Phase 2; the per-slot "AMD PCIE Link Speed" entries are vestigial).

## Rig / parent-project context

8x RTX 3090 vLLM rig on the analyst's LAN. Parent project root at `<rig>:<project-path>`. Key file: `<rig>:<project-path>/CLAUDE.md`. Rig is in production. **No flashing.**

Hand-off to parent project's investigation focus (BIOS-side answers complete):
- GPU 7's recurring Xid 79 at Gen3 — likely retimer / cable / connector / link-margin, not BIOS Gen-cap.
- Replace marginal retimers / cabling / risers if SI failure persists.
- `40:01.3` endpoint trace via `lspci -tvv` — would tell us what kind of port escapes the cap and whether re-routing is possible.
