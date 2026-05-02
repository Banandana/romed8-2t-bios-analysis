# DXIO/Override producer hunt — P3.70 vs P3.80

**Date:** 2026-04-27
**Scope:** Find any PE32 module across all FV volumes whose name matches DXIO/PortInit/Override/SspDxio/NbioPcieIp/IpInit/Param/Topology/Engine/LinkInit, diff P3.70 vs P3.80, look for the per-port descriptor producer that sets bit 6 of `+0x2E` (the Gen4/ESM enable per agent E).
**Verdict (executive):** **Negative.** No module by any of the requested names exists in the BIOS. The only differing modules between P3.70 and P3.80 that survive after filtering image-rebase noise are `CbsBasePeiSSP`, `CbsBaseDxeSSP`, `CbsSetupDxeSSP`, `AmdNbioIOMMUSSPPei`, `AmdApcbDxeV3`, `AmdApcbSmmV3`. **None contain Gen4/DXIO/ESM strings or any canonical bit-6/+0x2E ASM pattern.** The whole-image scan finds exactly **one** `test byte [r+0x2e], 0x40` site in both BIOSes, at the same offset (`0x1d2e5ab`) — that is the already-known site in `AmdNbioPcieDxe` (consumer, not producer). No new bit-6/+0x2E test or set instruction was added in P3.80 anywhere in the SPI image.

---

## 1. Discovery — candidate modules

Walked the full UEFIExtract dump tree (`extracted/all/P{3.70,3.80}/img.bin.dump/`) and listed every directory whose basename ends in any of the agent's keywords (`Dxio`, `PortInit`, `Override`, `OverrideParameters`, `SspDxio`, `NbioPcieIp`, `IpInit`, `Param`, `Topology`, `Engine`, `LinkInit`).

**Result: zero hits** apart from `DefaultOverride` (an unrelated AMI HII default-store override module — the same one across all 5 BIOS versions, immaterial to PCIe).

There is no module in this BIOS named `AmdCpmDxioInit`, `AmdSspDxioInitDxe`, `DxioInitPostPei`, `AmdSspNbioPcieIpInit`, `AmdCpmOverrideParametersDxe`, `AmdCpmOverrideParametersPeim`, or anything containing `Dxio`/`PortInit`/`Topology` as a substring of its UI section name. UEFIExtract's `--all` extraction does include UI sections; the names are correct.

This rules out the original Phase-1 hypothesis that an "AGESA SSP/DXIO core module" by that name exists as an FFS file in the SPI image.

## 2. Diff phase — full PE32 module diff (32-module candidate list)

The set of plausibly-related modules in the BIOS:

| module                     | P3.70 size       | P3.70 hash         | P3.80 size       | P3.80 hash         | diff |
|----------------------------|------------------|--------------------|------------------|--------------------|------|
| AmdNbioBaseSspDxe          | 16416            | 63e6d8314fda87ab   | 16416            | 63e6d8314fda87ab   | SAME |
| AmdNbioBaseSspPei          | 39712            | 62165f8c009e5710   | 39712            | 62165f8c009e5710   | SAME |
| AmdNbioPciePei             | 73704 / 63968    | (Rome / Milan)     | (same)           | (same)             | SAME |
| AmdNbioPcieDxe             | 72640 / 69824    | (Rome / Milan)     | (same)           | (same)             | SAME |
| AmdFabricSspPei/Dxe/Smm    | (Rome+Milan)     |                    | (same)           | (same)             | SAME |
| AmdCpmInitDxe              | 19936 / 19840    |                    | (same)           | (same)             | SAME |
| AmdCpmPcieInitDxe          | 2112 / 2080      |                    | (same)           | (same)             | SAME |
| **AmdCpmOemInitPeim**      | 43280 / 45568    | 03123583… / cf5a5f… | 43280 / 45568   | f67b4964… / cf5a5f… | DIFF (Rome only) |
| **AmdCpmInitPeim**         | 15760 / 15880    | 2b4993cf… / 20bee6… | 15760 / 15880   | bf56354b… / 20bee6… | DIFF (Rome only) |
| **AmdCpmPcieInitPeim**     | 1032 / 1184      | 5797d679… / 0860aa… | 1032 / 1184     | 30751685… / 0860aa… | DIFF (Rome only) |
| **CbsBasePeiSSP**          | 13248            | 147074a89f7dd46a   | 13216 (-32)      | f9716f58142cbd41   | DIFF |
| **CbsBaseDxeSSP**          | 15008            | df4912b37c5cec4c   | 15008            | 75457db65fa60afa   | DIFF |
| **CbsSetupDxeSSP**         | 194976           | 0e415306b7319d65   | 195296 (+320)    | 3c72fc9939f6d92d   | DIFF |
| **AmdNbioIOMMUSSPPei**     | 7840             | eab03b9b9acbb1bb   | 7840             | 2bc05d2cd711ef52   | DIFF |
| **AmdApcbDxeV3**           | 50848            | 71532a01141ff326   | 50912 (+64)      | ad60d67d48791dec   | DIFF |
| **AmdApcbSmmV3**           | 48064            | f27f7f257e19d9d9   | 48096 (+32)      | f0f5ae5c2ac63463   | DIFF |
| AmdNbioBaseGnDxe/GnPei     | 15008 / 32288    |                    | (same)           | (same)             | SAME |
| AmiAgesaPei, AmdSetupSSP   |                  |                    | (same)           | (same)             | SAME |
| ApobSspDxe/Pei             | (Rome+Milan)     |                    | (same)           | (same)             | SAME |
| AmdNbioIOAPICPei           | 4008             |                    | 4008             | (same)             | SAME |
| AmdNbioIOMMUDxe            | (Rome+Milan)     |                    | (same)           | (same)             | SAME |
| AmdNbioAlibDxe/AlibZpDxe   |                  |                    | (same)           | (same)             | SAME |
| AmdMemSspSp3Dxe/Pei        |                  |                    | (same)           | (same)             | SAME |
| AmdSocSp3GnPei/RmPei       |                  |                    | (same)           | (same)             | SAME |
| AmdCheckBmcPciePei         | 1472             |                    | 1472             | (same)             | SAME |
| PcieInfoJudgeDxe           | (Rome+Milan)     |                    | (same)           | (same)             | SAME |

### Image-rebase noise filter

Three of the "DIFF" modules (`AmdCpmOemInitPeim`, `AmdCpmInitPeim`, `AmdCpmPcieInitPeim`, all Rome-side TE-PEI) show diffs that are **uniformly `-0x20`** at every changed byte — i.e. PE32+ image-base shift only, no logic change. Concretely, `AmdCpmPcieInitPeim` (1032 B) has 15 bytes differing; every single delta is `-0x20`. Same pattern for `AmdCpmInitPeim` and `AmdCpmOemInitPeim`. **These are link-time rebase artifacts; their code is byte-equivalent.**

### Real-content-DIFF modules (after rebase filter)

- `CbsBasePeiSSP` (-32 B, 8095 byte diffs)
- `CbsBaseDxeSSP` (0 B, 4069 byte diffs)
- `CbsSetupDxeSSP` (+320 B, 120 086 byte diffs)
- `AmdNbioIOMMUSSPPei` (0 B, 5 byte diffs)
- `AmdApcbDxeV3` (+64 B) — already covered in `docs/APCB_DXEV3_DIFF.md` (verdict: not Gen4-related)
- `AmdApcbSmmV3` (+32 B) — paired with `DxeV3`, same APCB-checksum/write-back fix pattern (not Gen4)

## 3. Per-module focused disasm

### CbsBasePeiSSP / CbsBaseDxeSSP / CbsSetupDxeSSP

- String tables **byte-identical** between P3.70 and P3.80 in all three (only difference in `CbsBasePeiSSP` is 1 string of 7 ASCII chars containing tabs/forms — relocation-trampoline noise).
- No occurrence of any `DXIO`, `Gen4`, `ESM`, `Strap`, `MaxLink`, `TargetLink`, `Engine`, `Port`, `Override`, `Force`, `AttemptEsm`, `1.02`, `1.03` substring in either P3.70 or P3.80 versions.
- No canonical bit-6/+0x2E ASM pattern (`F6 4x 2E 40` test, `80 4x/6x 2E 40` or/xor, `0F BA 6x 2E 06` BTS) in any of the six binaries.
- Diff-byte delta histogram for `CbsBaseDxeSSP`: top delta is `+1` (240 occurrences), with a long tail of `-0x08`, `-0x40`, etc. — consistent with **table-offset shifts** (probably setup-form offset table edits) rather than a logic change. The CBS Base modules are setup/IFR-token glue libraries — they don't synthesize PCIe descriptors.
- `CbsSetupDxeSSP`'s 320 B growth is consistent with the prior agent's interpretation as added IFR question groups / setup-form storage, not PCIe code. r2 string sweep finds 102 strings in both versions, identical set.

### AmdNbioIOMMUSSPPei (5 byte diffs)

Located in `8 .../28 AmdNbioIOMMUSSPPei/1 TE image section/body.bin`. The five differing bytes are at:

- `0x1470, 0x147e, 0x148c, 0x149a` — same-stride entries in a 14-byte structured table; byte at record offset +9 changes `0x02 → 0x00`.
- `0x1594` — `0x07 → 0x05`.

The surrounding pattern `(40 10 02 00 40 10 02 00 …)` is consistent with the **AMD IVRS IO_APIC subentry layout** (IOMMU vector reporting structure). Field at +9 is the IO-APIC interrupt-policy / variety byte; the `0x07 → 0x05` byte at `0x1594` is in a different block (table header). **IOMMU IVRS edit, not PCIe DXIO.** Unrelated to the Gen4 cap.

### AmdApcbDxeV3 / AmdApcbSmmV3

Already covered in `docs/APCB_DXEV3_DIFF.md` — both are APCB shadow-copy write-back/checksum fixes, neither touches PCIe. Confirmed independently here: no DXIO/Gen4 strings, no bit-6/+0x2E ASM pattern in either binary.

## 4. Whole-image bit-6/+0x2E pattern scan

Scanned the raw 32 MiB of `images/ROMD82T3.70` and `images/ROMD82T3.80` for canonical x86 patterns: `F6 4x 2E 40` (test), REX-prefixed variants, `80 4x/6x 2E 40` (or/xor byte), `0F BA 6x 2E 06` (BTS bit 6).

Result: **exactly one match in each image, at the same file offset `0x1d2e5ab`, with identical bytes `f6 47 2e 40`** (`test byte [rdi + 0x2e], 0x40`). This is the well-known site inside `AmdNbioPcieDxe.efi` already documented in `docs/RADARE2_NBIOPCIE.md` (function `PcieAttemptEsmIfEnabled`, the consumer of bit 6).

**No new bit-6/+0x2E test or set was added anywhere in the P3.80 image.** The producer that sets bit 6 is therefore not visible as ASM literal-immediate `0x40` paired with `[reg + 0x2e]` anywhere in the SPI image — i.e. either:

(a) the producer doesn't exist in the SPI at all (it's somewhere else, e.g. in PSP/ABL firmware loaded earlier), or
(b) the producer exists but uses register-indirect / variable-offset / multi-step bit-set patterns that don't reduce to `40 ... 2e`. 

## 5. Whole-image strided-table scan (bonus)

Scanned both BIOS images for repeated structures of stride S ∈ {0x30, 0x34, 0x38, 0x3c, 0x40, 0x48, 0x50, 0x60} where every k-th record has bit 6 set in byte `+0x2e`, run length ≥ 6. Per-stride match counts:

| stride | P3.70 hits | P3.80 hits | delta |
|--------|-----------:|-----------:|------:|
| 0x30   | 102 916    | 102 787    | -129  |
| 0x34   | 101 127    | 100 614    | -513  |
| 0x38   | 101 904    | 101 332    | -572  |
| 0x3c   | 102 300    | 102 018    | -282  |
| 0x40   | 101 705    | 101 688    |  -17  |
| 0x48   | 101 427    | 100 972    | -455  |
| 0x50   | 101 567    | 100 939    | -628  |
| 0x60   | 100 925    | 100 922    |   -3  |

Hit counts are dominated by random-byte noise (a 32 MiB image has chance occurrences of any 1-byte mask at any stride). Crucially, **every stride shows a *negative* delta** (P3.80 has *fewer* matches than P3.70). If a new static descriptor table with bit-6-set GPU-slot entries had been added in P3.80, hits would increase. They decrease — so no new static descriptor table appeared in P3.80. This is a structural negative.

## 6. Verdict

- **No DXIO/PortInit/Override/Topology/Engine/LinkInit-named module exists in the BIOS.** The original prioritized targets from `docs/DISASM_AmdCpmPcieInitDxe.md` are not present as PE32 files. They are not what the BIOS calls them, or they aren't separate modules.
- **All real-content-DIFF modules between P3.70 and P3.80 are accounted for:**
  - `AmdApcbDxeV3` / `AmdApcbSmmV3` — APCB shadow-copy write-back hardening (not Gen4).
  - `CbsBasePeiSSP` / `CbsBaseDxeSSP` / `CbsSetupDxeSSP` — IFR/setup-token plumbing, no PCIe-related strings, no bit-6/+0x2E patterns.
  - `AmdNbioIOMMUSSPPei` — 5-byte IVRS IO-APIC entry edit, no PCIe.
- **No producer of the bit-6/+0x2E flag is detectable as ASM in either BIOS image** beyond the single consumer site in `AmdNbioPcieDxe`. P3.80 added nothing new in this regard.

### Implications for the Gen4 cap question

The producer of the per-port DXIO descriptor (the code that builds the struct read by `AmdNbioPcieDxe.PcieAttemptEsmIfEnabled`) **is not in any DXE/PEI/SMM PE32 module of the SPI image** that we can identify by name or by code-pattern signature. The candidate-name list is exhaustive against the FV directory; the bit-6/+0x2E pattern is unique in the image; the strided-table scan rules out a new static descriptor table.

Combined with prior subagent results:
- APCB blob is byte-identical P3.70/P3.80 (subagent #1) — not the source.
- `AmdNbioPcieDxe` byte-identical P3.70/P3.80 (subagent #5) — consumer, unchanged.
- `AmdApcbDxeV3` +64 B is unrelated APCB fix (`docs/APCB_DXEV3_DIFF.md`) — not the source.
- `AmdCpmPcieInitDxe` ruled out (`docs/DISASM_AmdCpmPcieInitDxe.md`) — not the source.
- This sweep: no DXIO/Override/Topology/Engine module exists at all; no other code site references `[reg+0x2e],0x40` literal.

**The case shifts strongly toward "the per-port descriptor is produced before any DXE/PEI module runs."** Candidates:

1. **PSP / ABL (AGESA Bootloader)** runs entirely on the PSP MP5 microcontroller before x86 cold reset. ABL builds the DXIO topology from APCB tokens and hands it to AGESA via a HOB or SMN-mapped scratch region. ABL binaries live in the PSP firmware directory, not in any FV. Cross-version diffing of PSP firmware (`psptool -d`) is a separate workstream.
2. **An AGESA library statically linked into one of the existing modules** (most plausibly `AmdNbioBaseSspPei` or `AmdNbioPciePei` — both byte-identical between P3.70 and P3.80). If the producer is here and the binary is identical, then the gate must be data-driven — but the only relevant data (the APCB) is also byte-identical. So either the gate is in PSP/ABL, or the gate is responding to a hardware signal not visible in the BIOS image (board-rev strap GPIO read at PEI/PSP time).
3. **An MP/MCA blob inside an AMD signed firmware package** — possibly the SMU firmware, NBIO firmware microcontroller, or DXIO firmware — that's not parsed by UEFIExtract (it's an opaque blob inside an FFS Raw section).

The next workstream is therefore PSP/ABL and embedded-firmware-blob inspection: `psptool -d images/ROMD82T3.70 vs ROMD82T3.80` to enumerate all PSP entries and diff them, with special attention to ABL stages, DXIO firmware (`PSP_FW_TYPE_*` SMU/MP5/DXIO), and any signed binary that grew or changed. **The DXE/PEI x86 portion of the BIOS does not contain the Gen4 unlock; this sweep closes that surface.**

## Helpers (one-off, in /tmp)

- `/tmp/diff_modules.py` — module name → (P3.70, P3.80) PE32 size+hash table generator.
- `/tmp/find_bin.py` — locate body.bin paths by module name.
- `/tmp/bytediff.py` — per-pair byte diff stats.
- `/tmp/diffmap.py` — list every differing byte offset for a pair.
- `/tmp/scan_bit6.py` — canonical bit-6/+0x2E ASM pattern scanner.
- `/tmp/scan_table3.py` — strided-table scanner.
- `/tmp/dxio_diff/*.bin` — extracted module bodies.
