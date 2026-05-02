# DefaultStore enumeration & shipped-vs-rig diff (ROMED8-2T P3.70)

Scope: answers the two related questions about (Q1) whether AMI's per-DefaultId
default-stores hide a "Manufacturing-on / Standard-off" Gen4-enable byte that
"Load Manufacturing Defaults" would activate, and (Q2) whether the rig's
current `Setup` UEFI variable has any bytes the user/factory wrote since
shipping (i.e. did any BIOS GUI click leave a trace on the chip).

All evidence is local file analysis only — no rig contact.

---

## 1. DefaultStore enumeration summary

Two DefaultStore IDs are declared anywhere in the IFR for P3.70:

| DefaultId | Conventional name        | Declared in       |
|-----------|--------------------------|-------------------|
| `0x0`     | Standard / Default       | every FormSet     |
| `0x1`     | Manufacturing            | every FormSet     |
| `0x2`     | Failsafe (EDK2 standard) | **NOT PRESENT**   |

Source: `grep -hoE "DefaultId: 0x[0-9A-Fa-f]+" ifr/P3.70/_all/*.uefi.ifr.txt`
returns exactly `0x0` and `0x1`. `grep "DefaultStore"` confirms only the two
storage declarations per FormSet.

Implication: there is no Failsafe store to activate. The only relevant
question for Q1 is whether DefaultId 0x0 ever differs from DefaultId 0x1.

---

## 2. Standard vs Manufacturing across every setting

A scan over **all** OneOf / Numeric / CheckBox questions in every IFR module
extracts both DefaultId 0x0 and DefaultId 0x1 values (encoded either as
`Default DefaultId: …` opcodes or as `Default, MfgDefault` flags on a
`OneOfOption`).

Result:

| Metric                                              | Count |
|-----------------------------------------------------|-------|
| Questions declaring both Std (0x0) and Mfg (0x1)    |  261  |
| Questions where Std value ≠ Mfg value               |  **0** |

**Across every PCIe-related setting** in `72_Setup`, `50_CbsSetupDxeGN`,
`CbsSetupDxeSSP`, `CbsSetupDxeZP`, `89_PciDynamicSetup`,
`91_PciOutOfResourceSetupPage`: zero entries have a Std≠Mfg disagreement.

Concretely the per-slot AMD PCIE Link Speed entries
(`PCIE1..7 / OCU1..2 / M2_1..2`, offsets `0x123–0x12D` in VarStore `Setup`,
QuestionIds `0xE1–0xEB`) are all declared as:

```
OneOfOption Option: "Auto" Value: 0, Default, MfgDefault
```

i.e. Auto is *both* the Standard default and the Manufacturing default. No
"manufacturing-only Gen4-enable" byte exists in this BIOS at the IFR level.

### Conclusion for Q1

> "Load Manufacturing Defaults" on P3.70 is functionally equivalent to "Load
> Optimized Defaults". It cannot flip a Gen4-enable byte, because no such
> byte exists in any DefaultStore. Pre-populating `Setup` from
> `setup_var.efi` with Manufacturing-store values would not differ from
> Standard-store values for any setting in this BIOS.

Caveat: this only covers the IFR-visible default-store records. If a SMM /
DXE driver applies platform-policy overrides at runtime that depend on a
non-IFR variable, those would not show up here. But the IFR exhaustively
enumerates every HII-driven Setup question, and every one was checked.

---

## 3. PCIe settings table (Standard vs Manufacturing)

Showing only PCIe-related settings whose Std/Mfg defaults could be parsed.
Empty diff column means values are identical (which is the case for **every**
row).

| File          | Prompt                              | VarStore   | Offset | Std | Mfg | Diff |
|---------------|-------------------------------------|------------|--------|-----|-----|------|
| 72_Setup      | PCIE1 Link Speed                    | Setup      | 0x123  | 0   | 0   | —    |
| 72_Setup      | PCIE2 Link Speed                    | Setup      | 0x124  | 0   | 0   | —    |
| 72_Setup      | PCIE3 Link Speed                    | Setup      | 0x125  | 0   | 0   | —    |
| 72_Setup      | PCIE4 Link Speed                    | Setup      | 0x126  | 0   | 0   | —    |
| 72_Setup      | PCIE5 Link Speed                    | Setup      | 0x127  | 0   | 0   | —    |
| 72_Setup      | PCIE6 Link Speed                    | Setup      | 0x128  | 0   | 0   | —    |
| 72_Setup      | PCIE7 Link Speed                    | Setup      | 0x129  | 0   | 0   | —    |
| 72_Setup      | OCU1 Link Speed                     | Setup      | 0x12A  | 0   | 0   | —    |
| 72_Setup      | OCU2 Link Speed                     | Setup      | 0x12B  | 0   | 0   | —    |
| 72_Setup      | M2_1 Link Speed                     | Setup      | 0x12C  | 0   | 0   | —    |
| 72_Setup      | M2_2 Link Speed                     | Setup      | 0x12D  | 0   | 0   | —    |
| CbsSetupDxeSSP| Early Link Speed                    | AmdSetupSSP| 0x15C  | 0   | 0   | —    |
| CbsSetupDxeSSP| Multi Upstream Auto Speed Change    | AmdSetupSSP| 0x169  | 15  | 15  | —    |
| CbsSetupDxeSSP| Multi Auto Speed Change On Last Rate| AmdSetupSSP| 0x16A  | 255 | 255 | —    |
| CbsSetupDxeZP | Force PCIe gen speed                | AmdSetupZP | 0x1C6  | 15  | 15  | —    |

(Every other PCIe-tagged question has the same pattern; full sweep
returns `differences: 0` from 261 dual-default questions.)

---

## 4. Byte-level diff: factory `Setup` defaults vs rig current

The factory shipped defaults for `Setup` (GUID
`EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`) were extracted from the NVAR
StdDefaults entry at:

```
extracted/P3.70/image.bin.dump/10 FA4974FC-…/0 NVAR store/0 StdDefaults/0 Setup/body.bin
```

Verified properties:
- Body size: `0x174` bytes — exactly matches the IFR-declared VarStore size.
- Header (`NVAR…Setup`) confirms variable name and GUID.
- Spot-check: byte 0x123 = 0x00 (Auto) — matches the IFR
  `OneOfOption "Auto" Value: 0, Default` for PCIE1.

Diff against the rig values recorded in [`../report/part-3-empirical-followup.md`](../report/part-3-empirical-followup.md) §Q4
(only those bytes are known empirically; a full rig dump was not provided):

| Setup offset | Shipped factory | Rig current | Differs? | Setting          |
|--------------|-----------------|-------------|----------|------------------|
| 0x123        | 0x00            | 0x01        | **YES**  | PCIE1 Link Speed |
| 0x124        | 0x00            | 0x01        | **YES**  | PCIE2 Link Speed |
| 0x125        | 0x00            | 0x00        | no       | PCIE3 Link Speed |
| 0x126        | 0x00            | 0x00        | no       | PCIE4 Link Speed |
| 0x127        | 0x00            | 0x00        | no       | PCIE5 Link Speed |
| 0x128        | 0x00            | 0x00        | no       | PCIE6 Link Speed |
| 0x129        | 0x00            | 0x01        | **YES**  | PCIE7 Link Speed |
| 0x12A        | 0x00            | 0x01        | **YES**  | OCU1 Link Speed  |
| 0x12B        | 0x00            | 0x01        | **YES**  | OCU2 Link Speed  |
| 0x12C        | 0x00            | 0x01        | **YES**  | M2_1 Link Speed  |
| 0x12D        | 0x00            | 0x00        | no       | M2_2 Link Speed  |

**Six bytes differ.** Six PCIe slot bytes (`0x123, 0x124, 0x129, 0x12A,
0x12B, 0x12C`) carry value `0x01` (GEN1) on the rig. The shipped factory
default is `0x00` (Auto) for every slot. These six writes are not factory.

---

## 5. Byte-level diff: factory `AmdSetupSSP` defaults vs rig current

The shipped NVAR StdDefaults entry for `AmdSetup` (GUID
`3A997502-647A-4C82-998E-52EF9486A247`) is at:

```
extracted/P3.70/image.bin.dump/10 FA4974FC-…/0 NVAR store/0 StdDefaults/11 AmdSetup/body.bin
```

with body size `0x6CB` (1739 bytes). The IFR-declared VarStore
`AmdSetupSSP` is `0x686` (1670 bytes). The discrepancy implies the NVAR
holds a unified blob covering both `AmdSetupSSP` and `AmdSetupZP` storage
(or a slightly oversized scratch region).

Decoding caveat (acknowledged): the NVAR body for `AmdSetup` is **not** a
pre-populated copy of all IFR defaults — most fields are zero. Spot
checks:

| AmdSetupSSP offset | NVAR body | IFR-declared default | Match? |
|--------------------|-----------|----------------------|--------|
| 0x020 (Combo CBS)  | 0xFE      | 254 (0xFE)           | yes    |
| 0x15C (Early Link) | 0x00      | 0   (Auto)           | yes    |
| 0x169 (MultiUp Auto)| 0x00     | 15  (Auto, 0x0F)     | **NO** |
| 0x16A (Last Rate)  | 0x00      | 255 (Auto, 0xFF)     | **NO** |

The NVAR blob is therefore a partial template — it captures *some* IFR
defaults but leaves most fields zero. AGESA / DXE installs the IFR-defined
defaults at first boot; the NVAR-body is not authoritative for offsets
that AGESA writes itself. This is consistent with how AMD CBS variables
are populated by `AmdCbsSetupDxe`.

Because the NVAR template doesn't reflect the IFR-defined Auto defaults
for `0x169` and `0x16A`, a strict byte diff against the rig is misleading.
Instead the relevant diffs use **IFR defaults** as the shipped baseline.

| AmdSetupSSP offset | IFR factory default | Rig current | Differs? | Note                                                    |
|--------------------|---------------------|-------------|----------|---------------------------------------------------------|
| 0x15C              | 0x00 (Auto)         | 0x00        | no       | factory                                                 |
| 0x169              | 0x0F (Auto)         | 0x0F        | no       | factory                                                 |
| 0x16A              | 0xFF (Auto)         | 0xFF        | no       | factory                                                 |

The other 0x03 / 0x04 bytes scattered through `AmdSetupSSP` per
[`../report/part-3-empirical-followup.md`](../report/part-3-empirical-followup.md)
(`0x002, 0x026, 0x02e, 0x032, 0x0a8-0x0aa, 0x0b0-0x0b3, 0x0b6-0x0b7,
0x0be, 0x0ca-0x0cb, 0x0eb, 0x0ed, 0x106, 0x136, 0x14e, 0x1ba, 0x1bc,
0x1cc, 0x1ce`) sit at offsets that have no IFR-mapped question (verified
in [Part III](../report/part-3-empirical-followup.md): "none of the
`0x03` or `0x04` bytes…are at offsets backed by any PCIe-related IFR
setting"). They are AGESA-internal
state that DXE writes during init — not user clicks. Status: **not
user-writes; AGESA-init writes**.

What is **blocked**: a full byte-for-byte AmdSetupSSP shipped-vs-rig diff
would require either (a) decoding the NVAR template format end-to-end and
overlaying every IFR default to construct the *effective* shipped state,
or (b) intercepting the variable after first AGESA init on a clean board.
Both are out of scope here. For the question that matters — "did the user
write any PCIe-related byte to AmdSetupSSP" — the answer is derivable
from IFR alone: no PCIe-related offset in `AmdSetupSSP` shows a non-default
value on the rig.

---

## 6. Verdict on the user's BIOS interaction

The diff in §4 is conclusive.

**The user's BIOS GUI click did write to NVRAM.** Six bytes in the `Setup`
UEFI variable changed from the shipped factory default of `0x00` (Auto)
to `0x01` (GEN1):

| Slot                        | Setup offset |
|-----------------------------|--------------|
| PCIE1                       | 0x123        |
| PCIE2                       | 0x124        |
| PCIE7                       | 0x129        |
| OCU1 (SlimSAS)              | 0x12A        |
| OCU2 (SlimSAS)              | 0x12B        |
| M.2 #1                      | 0x12C        |

These six bytes cannot be factory defaults — the shipped NVAR template
has 0x00 at every slot offset, and the IFR declares `Auto, Default,
MfgDefault` (i.e. neither the Standard nor the Manufacturing store would
ever produce 0x01). The only way they become `0x01` is via a write to the
`Setup` variable. That write happened post-shipping.

Three bytes that were **not** changed (`0x125`/PCIE3, `0x126`/PCIE4,
`0x12D`/M2_2 still at 0x00) suggest a partial click pattern — the user
selected GEN1 for some slots but left others at Auto. (`0x127`/PCIE5,
`0x128`/PCIE6 unchanged is consistent with no card present at click time
or a similar reason for skipping; this is speculation.)

This is consistent with the symptom that motivated the project: the user
recalls "clicking something" in the AMD PCIE Link Speed menu. The click
**did** write the per-slot bytes. The fact that nothing changed at the
hardware level is explained — separately and already in `FINDINGS.md` /
[`../report/`](../report/README.md) — by AGESA / DXIO ignoring those bytes on P3.70 (per-slot
IFR is a UI placebo on this BIOS). But the click was not lost: the writes
took effect at the NVRAM-variable level. They simply have no consumer in
the platform-init path.

### Rephrased to match the question form

- Are the per-slot `0x01` bytes at `Setup:0x123/0x124/0x129/0x12A/0x12B/0x12C`
  factory-shipped? **No.**
- Did the user's click write to NVRAM? **Yes — six bytes.**
- Did the writes take effect at the hardware/PCIe level? **No, separately
  documented: AGESA ignores them on P3.70.**

### Implication for the Gen4 hypothesis

Q1 is closed: there is no manufacturing-store-only Gen4-enable byte
anywhere in this BIOS. "Load Manufacturing Defaults" is identical to "Load
Optimized Defaults" — both reset every PCIe slot to Auto (0x00).
Pre-populating `Setup` from `setup_var.efi` with Manufacturing-store
values changes nothing relative to Standard-store values, because the two
stores are byte-identical for all 261 dual-declared settings.

Q2 is closed: the rig has six confirmed user-writes in `Setup` (the
PCIe-slot GEN1 selections). No user writes are detectable in
`AmdSetupSSP` based on the IFR-mapped offsets. The 0x03 / 0x04 bytes
flagged in the empirical dump are AGESA-init state, not user writes.

---

## Appendix: scripts / commands used

```
# DefaultId enumeration
grep -hoE "DefaultId: 0x[0-9A-Fa-f]+" ifr/P3.70/_all/*.uefi.ifr.txt | sort -u

# DefaultStore declarations
grep -hE "DefaultStore" ifr/P3.70/_all/*.uefi.ifr.txt | sort -u

# Std vs Mfg sweep (Python, see §2)
# Setup byte-level diff (Python, see §4)
# AmdSetup body inspection (Python, see §5)
```

Files referenced:
- `extracted/P3.70/image.bin.dump/10 FA4974FC-AF1D-4E5D-BDC5-DACD6D27BAEC/0 NVAR store/0 StdDefaults/0 Setup/body.bin` (372 bytes — shipped Setup defaults)
- `extracted/P3.70/image.bin.dump/10 FA4974FC-AF1D-4E5D-BDC5-DACD6D27BAEC/0 NVAR store/0 StdDefaults/11 AmdSetup/body.bin` (1739 bytes — partial AmdSetup template)
- `ifr/P3.70/_all/72_Setup.pe32.0.0.en-US.uefi.ifr.txt`
- `ifr/P3.70/_all/CbsSetupDxeSSP.pe32.0.0.en-US.uefi.ifr.txt`
- `ifr/P3.70/_all/CbsSetupDxeZP.pe32.0.0.en-US.uefi.ifr.txt`
- [`../report/part-3-empirical-followup.md`](../report/part-3-empirical-followup.md) §Q4 (rig empirical bytes)
