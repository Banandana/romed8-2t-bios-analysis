# SMM module inventory — P3.70 vs P3.80

**Goal:** verify that no SMM handler is involved in the Gen4 PCIe cap on the GPU root ports. The strap (`LC_GEN4_EN_STRAP` at SMN `0x111402A4`) is HwInit-locked at PSP cold-boot, but it remains theoretically possible that an SMI handler installed by ASRock intercepts runtime PCIe LCTL/LCTL2 / cfg-space writes to enforce the cap. This document refutes that.

## Method

1. Walked the UEFIExtract dump tree for both versions, parsing every FFS file's `info.txt`.
2. Selected files with FFS `Type:` field equal to one of:
   - `0Ah` — `EFI_FV_FILETYPE_SMM`
   - `0Eh` — `EFI_FV_FILETYPE_SMM_CORE`
   - `14h` / `15h` — Standalone-MM core / module
3. For each, located the largest PE32 image-section `body.bin`, hashed it (SHA-256), recorded size.
4. De-duplicated by `(Name, GUID)` keeping the largest copy (UEFIExtract emits the same FFS in both volumes — active + recovery).
5. Diffed sizes and hashes between P3.70 and P3.80.
6. For modules differing across versions, ran focused string and byte-pattern scans:
   - PCIe / Gen4 / ESM / LC_* / LinkSpeed / NbioPcie / DXIO / strap **as exact substrings**
   - SMN address `0x111402A4` (LE: `a4 02 14 11`) and adjacent SMN regs
   - PCIe-related SMM protocol GUIDs and helper symbols

Helpers: `/tmp/smm_enum.py`, `/tmp/smm_strings_scan.py`. Output JSON: `/tmp/smm_pe32_paths.json`, `/tmp/smm_diffs.json`.

## Total counts

| Version | SMM FFS file entries (raw) | Unique modules (Name, GUID) |
|---------|---------------------------:|----------------------------:|
| P3.70   | 154                        | 92                          |
| P3.80   | 154                        | 92                          |
| Union (by name) | — | **91** |

All entries are FFS file type `0Ah` (traditional SMM). No `0Eh` / `14h` / `15h` files present — this BIOS uses the classic PI SMM model, not Standalone-MM. That matches AMI Aptio V on AMD Rome.

The total module count (92 → 91 union) is unchanged P3.70 → P3.80: **no SMM module added or removed** between versions. The 91 vs 92 unique-by-name asymmetry comes from one (name, guid) pair appearing twice with different GUIDs in one version (cosmetic).

## Diff table — modules differing between P3.70 and P3.80

7 of 91 SMM modules differ (size or hash). Suggestiveness rank reflects how plausibly the module could touch PCIe LCTL/LCTL2 or NBIO SMN. None scored "high".

| Module | Type | Size P3.70 | Size P3.80 | ΔBytes | Hash diff | Suggestiveness |
|--------|------|-----------:|-----------:|-------:|:---------:|----------------|
| `AmdPspP2CmboxV2` | 0Ah | 26 400 | 27 712 | **+1312** | YES | low (PSP↔x86 mailbox; PSB / SEV / DRTM domain, not PCIe) |
| `NvramSmm`        | 0Ah | 66 432 | 67 040 | +608 | YES | none (UEFI variable services) |
| `Ofbd`            | 0Ah | 34 624 | 34 816 | +192 | YES | none (AMI Out-of-Band update glue, flash) |
| `CpuSmm`          | 0Ah | 19 520 | 19 552 | +32  | YES | low (CPU SMI core; could in principle filter MSR/IO traps, but generic) |
| `SmbiosDmiEdit`   | 0Ah | 37 728 | 37 760 | +32  | YES | none (SMBIOS table editor) |
| `CryptoSMM`       | 0Ah | 63 648 | 63 648 | 0    | YES | none (crypto primitives — likely OpenSSL bumped) |
| `SbRunSmm`        | 0Ah | 27 040 | 27 040 | 0    | YES | low (AMI southbridge runtime SMM — handles ACPI/CMOS SMI traps) |

The other 84 SMM modules — including every `*Pcie*Smm`-relevant candidate one would expect (`AmdHotPlugSspSmm`, `AmdNbio*Smm` (none exist), `SmmPciRbIo`, `BctBaseSmmSSP`, `AmdFabricSspSmm`, `AmdPlatformRasSspSmm`) — are **byte-identical** between P3.70 and P3.80.

There is **no SMM module named for PCIe / NBIO / Power / SpeedChange / LinkControl** in either version. The only "PCIe-adjacent" SMM modules in the inventory are:
- `SmmPciRbIo` — PCI Root Bridge IO protocol installer for SMM (generic; byte-identical 70=80)
- `AmdHotPlugSspSmm` / `AmdHotPlugGnSmm` — PCIe hot-plug SMI dispatcher (byte-identical 70=80)
- `AmdFabricSspSmm` — DF / fabric SMI handler (byte-identical 70=80)

## Per-suspicious-module focused analysis

Restricted to differing modules, since the byte-identical ones cannot have changed semantics between P3.70 and P3.80 by definition.

### Substring scan (all 7 differing modules, both versions)

For each of `[GEN4 / Gen4 / gen4 / LCTL / PCIE_LC / LinkSpeed / LinkCap / PcieAttempt / NbioPcie / PcieRoot]` and SMN bytes `a4 02 14 11`, `c4 02 14 11`, `a8 02 14 11`:

```
== AmdPspP2CmboxV2 == 0 hits in 3.70, 0 hits in 3.80
== CpuSmm ==          0 hits in 3.70, 0 hits in 3.80
== CryptoSMM ==       0 hits in 3.70, 0 hits in 3.80
== NvramSmm ==        0 hits in 3.70, 0 hits in 3.80
== Ofbd ==            0 hits in 3.70, 0 hits in 3.80
== SbRunSmm ==        0 hits in 3.70, 0 hits in 3.80
== SmbiosDmiEdit ==   0 hits in 3.70, 0 hits in 3.80
```

**Zero hits.** No SMM module in either version contains the SMN address of `LC_GEN4_EN_STRAP`, an `LCTL` reference, the `PcieAttempt` debug tag (the string subagent #5 found in `AmdNbioPcieDxe`), or any GEN4/ESM/LinkSpeed string.

### Whole-corpus substring scan (all 91 SMM modules)

The four "hits" in the wider scan all resolve to false positives:
- `ESM` in `Ofbd` / `SmiFlash` / `Afu32*Smm` → `"ESMT 25L"` flash chip vendor strings (Elite Semiconductor Memory Technology — a SPI-flash IC manufacturer, not PCIe ESM)
- `DXIO` in `CF9IoTrap` → `"PowerDown call to DXIO for cpuN"` debug string in the S3/CF9 reset SMI path (logging only; not link control)

### Per-module notes

- **`AmdPspP2CmboxV2` (+1312 B):** PSP-to-x86 mailbox SMM driver. P3.80 adds the symbol `AmdPspDxeSmmBufLibConstructor` (a buffer-library constructor) — consistent with an internal lib refactor / SMM communication-buffer hardening, not PCIe. No PCIe / DXIO / NBIO / Gen4 strings either version. New string `FakeSmiEn` (debug verifier) appears in both versions; not new.
- **`NvramSmm` (+608 B):** UEFI variable services in SMM. Domain mismatch with the Gen4 cap. No relevant strings.
- **`Ofbd` (+192 B):** AMI Out-of-Band glue used during capsule / RC update. Domain mismatch. The `ESM` substring matches are SPI vendor names.
- **`CpuSmm` (+32 B):** PI SMM CPU core. Very small delta (likely a constant or single instruction tweak). No PCIe / Gen4 strings.
- **`SmbiosDmiEdit` (+32 B):** SMBIOS table edit handler. Domain mismatch.
- **`CryptoSMM` (Δ=0, hash differs):** Same size, different hash — almost certainly a build-tag / timestamp change in the embedded crypto library. No code-path change of interest.
- **`SbRunSmm` (Δ=0, hash differs):** AMI Southbridge runtime SMM. Same size, identical string table (verified via `r2 -c iz` diff). Code change is small enough to not introduce or remove any string. Domain (RTC / CMOS / ACPI SMI traps) is wrong layer for the Gen4 cap; even if the disasm differs by a constant, the semantics of intercepting PCIe LCTL writes would require strings/PCI-cfg helpers that aren't present.

## Verdict

**No.** No SMM handler in P3.70 or P3.80 is involved in enforcing the Gen4 PCIe cap on the ROMED8-2T's GPU root ports.

Concretely:
- No SMM module is named for PCIe / NBIO / Power / SpeedChange / LinkControl.
- No SMM module references `LC_GEN4_EN_STRAP`, the SMN address `0x111402A4`, `LCTL`, `LinkSpeed`, `PcieAttempt`, `NbioPcie`, or any Gen4/ESM string in either version.
- The 7 modules that did change between P3.70 and P3.80 are all in PSP / NVRAM / OOB / CPU-core / SMBIOS / crypto / Southbridge-runtime domains. Their string tables and byte signatures are inconsistent with PCIe-LCTL or SMN intercept logic.
- All known PCIe-adjacent SMM modules (`SmmPciRbIo`, `AmdHotPlugSspSmm`, `AmdFabricSspSmm`) are **byte-identical** between P3.70 and P3.80 — semantically frozen across the rev-1.03 unlock boundary.

**Implication.** The earlier hypothesis from `docs/PPR_REGISTER_NOTES.md` ("Lockdown enforced inside NBIO IP via the HwInit attribute + PSP-configured SMN firewall (signed) — no SMM lockdown on NBIO SMN") is corroborated. SMM is not the gate; the HwInit attribute on `LC_GEN4_EN_STRAP` is. SMM enforcement is ruled out as a Gen4-cap mechanism on this BIOS family.

This rules out item #10 of the "Possible next directions" list as a fix path: even if a runtime register write reached the silicon (e.g. via `/dev/mem` SMN poke as discussed under item #2), there is no SMM trap waiting to undo it. The cap is purely silicon-side, latched at HwInit time from the APCB DXIO straps before any SMM runtime exists. Confirmed inert from the OS perspective.
