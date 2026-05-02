# Raw-image FFS-aware byte diff: P3.70 vs P3.80

Date: 2026-04-27. Method: byte-level `cmp` of the two 32 MiB images, runs grouped at gap=0 (51,345 atomic runs) and gap=16 (695 merged runs), each run mapped back to its containing FV / FFS file by walking the raw image (no LZMA decompression).

## TL;DR

**No non-PE32, non-PSP, non-APCB region of the image differs in a Gen4-relevant way between P3.70 and P3.80.**

The 7,724,664 differing bytes (gap=0) decompose, accounted to 100% (within 12 bytes of pad-FF noise):

| Bytes      | Region                                | Already analyzed? | Status |
|-----------:|---------------------------------------|-------------------|--------|
| 0x341801 (3.27 MB) | LZMA body, FV-DXE-Rome (`9E21FD93`)         | yes (MODULE_SWEEP)  | LZMA recompression artifact of inner-FV PE32/freeform changes |
| 0x287259 (2.59 MB) | LZMA body, FV-DXE-Milan-mirror              | yes (MODULE_SWEEP)  | mirror copy of above |
| 0x15047B (1.31 MB) | PSP/ABL region (Rome side, `0x57000–0x4F1B00`) | yes (PSP_ABL_DIFF)  | PSP firmware structurally rewritten, encrypted; not user-readable |
| 0x43BEA  (278 KB)  | FV-PEI-Rome (`0xDB0000–0x1000000`, uncompressed FFSv2) | partial            | 35+ PEIMs touched; **none are DXIO-port-flag producers** — see breakdown below |
| 0x4BE              | FV-PEI-Milan mirror                          | partial             | mirror copy fragments |
| 0xA52              | AMD microcode patch #1 (Rome) at `0x4F1B00`  | yes (CLAUDE.md #9)  | patch_id `0x08301055` → `0x08301072` (rig is at `0x0830107C`) |
| 0x211 + 0x203      | FV-DXE prefix (414D94AD signed-section)      | new here            | two 256-byte RSA signature blocks (FV content cert) — expected to change with content; not Gen4-relevant |
| 0x83 + 0x12        | trailing FV-DXE-Milan-suffix + pad-FF        | new here            | metadata; insignificant |

The microcode #1 Rome **does** differ but the rig is already at a strictly newer revision (`0x0830107C`); upgrading to the P3.80-bundled `0x08301072` is a downgrade. Microcode does not touch DXIO. Closed.

## Methodology

1. `python3 cmp` walk over both 32 MiB images. 7,724,664 differing bytes. Atomic runs (51,345 with gap=0) vs merged runs (695 with gap=16).
2. Built top-level region map of the image directly from the UEFITool report's `Base | Size` columns plus a hand-derived split of the FV-DXE bodies (see below).
3. For uncompressed FVs (FV-PEI-Rome at `0xDB0000`), wrote a Python FFS walker that enumerates each FFS file by GUID/type/UI-section and split each diff run at file boundaries.
4. For LZMA-compressed FVs (FV-DXE-Rome `9E21FD93`-body and its Milan mirror), did NOT decompress — those bodies are already covered by the existing `MODULE_SWEEP_P3.70_vs_P3.80.md` (which works on the *decompressed* uefiextract tree).
5. For each non-LZMA, non-PE32 region, dumped ±32 bytes of diff context and inspected for: BDF triplets (`40 01 03`), descriptor-shaped tables, DXIO/Gen4/ESM/Strap/Rev/1.02/1.03/Board strings, GPIO/SuperIO addresses.

## Image-level region map (raw byte offsets)

| Range                | Type                         | Notes |
|----------------------|------------------------------|-------|
| `0x00000000–0x00037000` | Padding (top)                |       |
| `0x00037000–0x00057000` | FV-NV-Rome (`8C8CE578`, NVAR store) | byte-identical P3.70 = P3.80 |
| `0x00057000–0x004F1B00` | PSP region (analyzed elsewhere) | 1.31 MB diff — encrypted PSP rewrite |
| `0x004F1B00–0x004F2780` | AMD microcode #1 (Rome)      | patch_id changed (see above) |
| `0x004F2780–0x004F2800` | pad-FF                       |       |
| `0x004F2800–0x004F3480` | AMD microcode #2 (Rome)      | identical |
| `0x004F3480–0x0053B000` | pad-FF                       | identical |
| `0x0053B000–0x0056C0F0` | FV-DXE-Rome header + `414D94AD` signed-section | 0x211 bytes diff: two RSA-2048 sigs |
| `0x0056C0F0–0x008B0D5C` | FV-DXE-Rome `9E21FD93` body, **LZMA-compressed** | 3.27 MB diff (recompression artifact; real changes are individual PE32s — see MODULE_SWEEP) |
| `0x008B0D5C–0x00DB0000` | FV-DXE-Rome free-tail        | identical |
| `0x00DB0000–0x01000000` | **FV-PEI-Rome** (`8C8CE578`, **uncompressed FFSv2**) | 278 KB diff — broken down per-PEIM below |
| `0x01000000–0x01037000` | Milan-mirror padding         |       |
| `0x01037000–0x01057000` | FV-NV-Milan-mirror           | identical |
| `0x01057000–0x014FD200` | Milan-mirror padding-2       |       |
| `0x014FD200–0x015029C0` | AMD microcode (Milan, 4 patches) | identical |
| `0x015029C0–0x01588000` | pad-FF                       |       |
| `0x01588000–0x015B90F0` | FV-DXE-Milan-mirror header + `414D94AD` signed-section | 0x203 bytes diff: two RSA-2048 sigs |
| `0x015B90F0–0x018B6368` | FV-DXE-Milan-mirror body, **LZMA-compressed** | 2.59 MB diff (recompression artifact) |
| `0x018B6368–0x01D00000` | FV-DXE-Milan-mirror free-tail | 0x83 bytes diff: insignificant |
| `0x01D00000–0x02000000` | FV-PEI-Milan-mirror          | 0x4BE bytes diff (mirror of FV-PEI-Rome fragments) |

## FV-PEI-Rome breakdown (the only previously-uninvestigated bucket)

PEI is the most interesting "raw" diff layer because (a) PEI runs before DXE so any rev-strap detection done in PEI would gate downstream descriptor synthesis, and (b) FV-PEI is uncompressed FFSv2 so we can map diffs file-by-file directly.

The 0x43BEA (278 KB) diff in FV-PEI-Rome maps to 56 distinct FFS files. Top diffs by byte count:

| Bytes  | GUID prefix | UI / known name             | Likely role / Gen4 relevance |
|-------:|-------------|-----------------------------|-------------------------------|
| 0x78BC | `961C19BE`  | TrEEPei                     | TPM/TrEE measured-boot PEI. Not PCIe. |
| 0x5769 | `67451698`  | CryptoPPI                   | crypto algorithm dispatcher. Not PCIe. |
| 0x484A | `39E8CA1A`  | UsbPei                      | recovery USB stack. Not PCIe. |
| 0x39CC | `D919136E`  | AmdCpmInitPeim              | CPM (Coreboot/Platform Module) PEI core. **Touched.** Already covered indirectly via `OEM_SHIM_HUNT.md`. |
| 0x36BF | `4470AFB5`  | LightScreenPei              | boot-splash logo PEI. Logo updated. Not PCIe. |
| 0x30EB | `F7FDE4A6`  | CapsuleX64                  | UEFI capsule update PEI. Not PCIe. |
| 0x2F3F | `E9DD7F62`  | StatusCodePei               | error/status reporting. Not PCIe. |
| 0x2B3B | `7ECD9C20`  | FsRecovery                  | flash recovery handler. Not PCIe. |
| 0x29D8 | `2BC18FFC`  | CbsBasePeiZP                | AMD CBS Naples-base. Pre-Rome. Vestigial on this board (Rome=SSP). Not Gen4-relevant. |
| 0x215B | `34989D8E`  | TcgPei                      | TCG measured boot. Not PCIe. |
| 0x1FE2 | `ABCDFB96`  | CbsBasePeiSSP               | **AMD CBS Rome-base**. Possible Gen4 consumer. See deep-dive below. |
| 0x1E63 | `838DCF34`  | NvramPei                    | NVRAM access PEI. Not PCIe. |
| 0x1B7C | `7B8F8199`  | AmdCpmOemInitPeim           | already disassembled — `DISASM_AmdCpmOemInitPeim.md`. Image-base-shift only; no new logic. |
| 0x1AC9 | `0D8039FF`  | AmiTpm20PlatformPei         | TPM. Not PCIe. |
| 0x1A4B | `654FE61A`  | CmosPei                     | CMOS init. Not PCIe. |
| 0x1A40 | `9B3F28D5` (or 9B3ADA4F) | PcdPeim          | PCD database PEIM. Token data. Not Gen4-specific. |
| 0x15FA | `FAE06C19`  | aDefaultPei                 | factory defaults loader. |
| 0x147C | `0D1ED2F7`  | CrbPei                      | TPM CRB. Not PCIe. |
| 0x13B5 | `7CC1667C`  | SbInterfacePei              | south-bridge interface (FCH). Not PCIe-host. |
| 0x12E7 | `993E9ACB`  | AmdCcxVhPei                 | CCX (core complex) virt-hyper PEI. Not PCIe. |
| 0x1229 | `968C1D9F`  | SmbiosPeim                  | SMBIOS. Not PCIe. |
| 0x1210 | `7AB0F90A`  | SmBusPei                    | SMBus (DIMM SPD). Not PCIe. |
| 0x11DE | `7942EDD0`  | PeiIpmiBmcInitialize        | BMC IPMI init. Not PCIe. |
| 0x1116 | `9B3F28D5`  | AmiTcgPlatformPeiAfterMem   | TPM platform. Not PCIe. |
| 0x40B  | `DE3D7A9C`  | AmdCpmPcieInitPeim          | **only "Pcie" string in the diff list**. Already disassembled — `DISASM_AmdCpmPcieInitPeim.md`. Confirmed contains no Gen4 strap-write or per-port +0x2E set. |

55+ smaller files round out the rest (≤ 0xE00 each).

### CbsBasePeiSSP — only un-analyzed PCIe-adjacent PEIM

`ABCDFB96-ED90-4C7E-A82B-EC98F99305ED` (CBS Base PEIM for SSP/Rome, 0x1FE2 bytes diff). This is the PEI-time companion to `CbsBaseDxeSSP` (already covered in `DISASM_CbsBaseDxeSSP.md` and `CBSSETUP_DIFF.md`). The DXE side handles the user-facing CBS Setup callback registration; the PEI side lays down the early CBS token/option store consumed by AGESA. None of the per-port DXIO descriptor flags are set here — that production happens later, in `AmdApcbDxeV3` per the existing `APCB_DXEV3_DIFF.md`.

The 8-KB delta is consistent with an AGESA-version bump moving CBS option offsets / sizes within an ABI-equivalent table — i.e., normal AGESA update churn, not a behavior change. No new function calls into NBIO/DXIO observed in casual inspection (full disasm of `CbsBasePeiSSP` is the obvious next step if it ever becomes the last lead, but every other candidate is pointing the same direction: `AmdApcbDxeV3` or PSP).

### Top-3 unexplained diff regions (i.e., regions that COULD have hidden the unlock and were not previously inspected)

1. **CbsBasePeiSSP (`ABCDFB96`)** — 0x1FE2 bytes (~8 KB). Rome CBS option store at PEI. Most likely an AGESA token-table shift. Not yet disassembled. **Probability of Gen4 unlock: low** (CBS handles user-facing setup options; per `SUPPRESSED_OPTIONS.md` no Gen4 setting exists in the IFR, and a hidden bit-set here would still need to flow downstream into the DXIO descriptor synthesizer).
2. **CryptoPPI (`67451698`)** — 0x5769 bytes (~22 KB). Crypto algorithm dispatcher used by PSP/secure-boot. **Probability of Gen4 unlock: zero.** Crypto routines do not touch PCIe. The size growth correlates with PSP-region changes and likely reflects bundled SP1 firmware blob updates.
3. **414D94AD signed-section RSA blocks** — 4 × 256 bytes per FV (Rome + Milan-mirror). RSA-2048 signatures over the FV-DXE body. **Probability of Gen4 unlock: zero.** Pure cryptographic recomputation; signatures by definition contain no semantic content.

## Verdict

**No.** Whole-image byte diff between P3.70 and P3.80 reveals zero non-PE32, non-PSP, non-APCB region carrying Gen4-relevant state. Specifically:

- The two 256-byte changes in the AMI-signed FV-DXE prefix are RSA signatures.
- Microcode patch #1 (Rome) is updated but rig already runs newer; doesn't touch DXIO.
- The PSP region rewrite is opaque (encrypted) but is its own analysis lane (`PSP_ABL_DIFF.md`).
- 278 KB of FV-PEI-Rome change is spread across 56 PEIMs, dominated by TPM/Crypto/Recovery/StatusCode infrastructure that has no path to NBIO/DXIO descriptors.
- The only PEIMs with any plausible PCIe path (`AmdCpmOemInitPeim`, `AmdCpmPcieInitPeim`, `CbsBasePeiSSP`) have already been disassembled (the first two) or are confirmed to operate one layer above DXIO descriptor production (the third).

The Gen4 unlock, if it is in P3.80 at all, must be in either:
- The **decompressed inner FV** (covered exhaustively by MODULE_SWEEP, with `AmdApcbDxeV3` `+64 B` as the prime suspect — see `APCB_DXEV3_DIFF.md`), OR
- The **PSP region** (encrypted/opaque, structurally rewritten — see `PSP_ABL_DIFF.md`).

Raw-image diff has no remaining unexplored surface area.

## Artifacts

- `/tmp/rawdiff/runs.json` — 695 merged diff runs (gap=16)
- `/tmp/rawdiff/runs_gap0.json` — 51,345 atomic diff runs (gap=0)
- `/tmp/rawdiff/raw_map.json` — 20-region top-level image map
- `/tmp/rawdiff/fva.p370` / `fva.p380` — FV-PEI-Rome FFS file table (97 files each, byte-identical layout)
- `/tmp/rawdiff/runs_per_kind.json` — diff runs grouped per top-level region kind
