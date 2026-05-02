# CpmData / OEM-data module sweep — P3.70 vs P3.80

**Verdict: NEGATIVE. There is no standalone `CpmData*` / `CpmTbl*` / `CpmDb*` / `BoardData*` / `PlatformData*` / `CpmRcConfig*` module in this BIOS, and every closely-adjacent OEM/Board/Platform module that *does* exist is either byte-identical or differs only by a pure absolute-pointer rebase. No CpmData-style module carries the Gen4 unlock.**

This continues the rebase-aware methodology established in `docs/DISASM_AmdCpmOemInitPeim.md`.

## 1. Discovery

Search performed on every PE32/TE module body in both `extracted/all/P3.70/img.bin.dump` and `extracted/all/P3.80/img.bin.dump` (810 modules per image; 809 common module names; 131 differ in hash).

Searched names (case-insensitive substring): `CpmData`, `CpmTbl`, `CpmTable`, `CpmDb`, `BoardData`, `OemData`, `PlatformData`, `CpmRcConfig`, `CpmInit*Lib`.
**Direct hits: zero.** ASRock did not ship a separately linked CpmData blob — the per-board configuration tables live inside `AmdCpmOemInitPeim` itself (consistent with the AGESA Customer Portal Module pattern where the OEM PEIM's `.data` section *is* the board table).

Adjacent matches (broader OEM/Board/Platform/Cpm/PciTable patterns) found in P3.70:

| Module | Vol | Section type | Size | P3.70 md5[:8] | P3.80 md5[:8] | Status |
|---|---|---|---|---|---|---|
| `AmdCpmOemInitPeim` | FV21/40 | TE | 45,568 | `69dfd5bb` | `69dfd5bb` | **identical** |
| `AmdCpmOemInitPeim` | FV8/43 | TE  | 43,280 | `950ff789` | `04c57380` | **rebase only** |
| `AmdBoardIdPei` | FV21/51 | TE | 640 | `99b81c78` | `99b81c78` | **identical** |
| `AmdBoardIdPei` | FV8/50 | TE | 520 | `72c7900a` | `dcba35da` | **rebase only** |
| `AmdBoardIdDxe` | FV20/62 | PE32 | 1,408 | `57f16b56` | `57f16b56` | **identical** |
| `AmdBoardIdDxe` | FV7/64 | PE32 | 1,376 | `4591869b` | `4591869b` | **identical** |
| `PciTableInit` | FV21/8 | TE | 992 | `58bcadee` | `58bcadee` | **identical** |
| `PciTableInit` | FV8/8 | TE | 2,088 | `cd1b007b` | `cd1b007b` | **identical** |

(FV20/FV21 are the live Rome-side volumes; FV7/FV8 are mirror copies for Milan.)

Only the FV8 (Milan-mirror) instances of `AmdBoardIdPei` and `AmdCpmOemInitPeim` differ between P3.70 and P3.80. Both are size-zero deltas.

## 2. Rebase-artifact verification

### `AmdBoardIdPei` FV8/50 (520 B)

- 4 differing bytes total (0.77 % of body).
- Diff at `+0x10` (TE header `ImageBase[0]`): `ec → cc` = -0x20.
- Other 3 diffs are isolated single bytes inside `.text`, each the high byte of an LE32 word whose top half is `0xffe3` — same `-0x20` rebase pattern as `AmdCpmOemInitPeim`.
- **Pure rebase. Zero semantic change.**

### `AmdCpmOemInitPeim` FV8/43 (43,280 B)

- 127 differing bytes (0.29 %); 115 sparse runs.
- TE `ImageBase`: P3.70 = `0xffe32f80`, P3.80 = `0xffe32f60`, delta = **-0x20** (identical to `docs/DISASM_AmdCpmOemInitPeim.md`'s finding for this same volume).
- Sampled diffs at `0xb7, 0xd7, 0x11f, 0x15c, 0x1c1, 0x1f2, 0x21f` — every one is the high byte of an absolute LE32 pointer; in every case `P3.70_word - P3.80_word == 0x20`.
- **Pure rebase. Already analyzed in dedicated doc; reproduced here for completeness.**

### Control: `PciTableInit` FV8/8 (2,088 B)

- 0 differing bytes. Demonstrates the rebase signature is real (the few modules that escape rebasing in FV8 are the ones whose code happens to contain no absolute self-references).

### Comprehensive whole-FV8 sweep

Every PE32/TE module in FV8 (`61C0F511-A691-4F54-974F-B9A42172CE53`) that differs between P3.70 and P3.80 has **delta = +0 bytes**, including: `AmdCpmGpioInitPeim`, `AmdCpmInitPeim`, `AmdCpmPcieInitPeim`, `AmdNbioIOMMUSSPPei`, `AmdPlatformRasSspPei`, `AmiTcgPlatformPeiAfterMem/BeforeMem`, `AmiTpm20PlatformPei`, `PlatformCustomizePei`, `TcgPeiplatform`, `TcgPlatformSetupPeiPolicy`. The whole FV was rebased (likely shifted by `-0x20`) when ASRock rebuilt its capsule for P3.80.

The only non-zero delta in the whole modules-of-interest set is `CbsSetupDxeSSP` (+320 B), already covered by `docs/CBSSETUP_DIFF.md`.

## 3. Static-data inspection of the Rome-side `AmdCpmOemInitPeim` (FV21/40)

This is the live Rome PEIM that consumes board-data tables. It is byte-identical between P3.70 and P3.80, but worth a structural check for descriptor-encoding patterns per the bonus task:

- BDF `40:01.3` raw byte signature (`40 01 03`): **0 hits**.
- BDF `0x400b` (encoded `(bus<<8)|(dev<<3)|fn`) little-endian (`0b 40`) or BE (`40 0b`): **0 hits**.

The per-port DXIO descriptors are not encoded in this module's data section as raw BDF arrays. Consistent with the broader finding (subagent #1, subagent #5, `docs/APCB_DECODE.md`) that descriptors are synthesized at runtime in `AmdApcbDxeV3` from APCB tokens, not lifted from a static OEM table.

## 4. Top three candidates examined and verdict

| Rank | Module | Why it was a candidate | Outcome |
|---|---|---|---|
| 1 | `AmdCpmOemInitPeim` (FV8 + FV21) | ASRock OEM PEIM shim; CPM framework hands its `.data` directly to AGESA. FV8 instance shows hash diff. | Hash diff is pure `-0x20` rebase; FV21 instance byte-identical. **No semantic change.** |
| 2 | `AmdBoardIdPei` / `AmdBoardIdDxe` | Literal "board ID" — naturally where rev-1.02A vs rev-1.03 detection would live. FV8 PEI instance shows hash diff. | 4-byte rebase only; DXE copies byte-identical. **Board-ID logic was not changed P3.70 → P3.80.** |
| 3 | `PciTableInit` (FV8 + FV21) | Name suggests a static PCI/PCIe topology table, possibly DXIO descriptors. | Both volumes byte-identical across versions. **Not the unlock and not even differential.** |

## 5. Implication

If P3.80 unlocks Gen4 on rev-1.03 boards (per ASRock Forum TID 24737 community reports), the gating logic is **not** in any OEM data module. The remaining viable suspects, in order of leverage, are unchanged from the parent task list:

1. **`AmdApcbDxeV3` (+64 B P3.70 → P3.80)** — already documented in `docs/APCB_DXEV3_DIFF.md`. Highest leverage.
2. **`CbsSetupDxeSSP` (+320 B)** — `docs/CBSSETUP_DIFF.md`.
3. The ASRock `Setup` HII module (FV20 and FV7 instances both differ, size-zero — likely IFR string/order changes only, but worth a follow-up rebase-aware diff if `AmdApcbDxeV3` proves uninformative).

ASRock's OEM PEIM and board-ID logic are out of the picture as a Gen4 unlock site. This closes the "CpmData module carries the unlock" branch of the investigation.

## 6. Files & helpers

Discovery and rebase-verification scripts run inline; no helper artifacts left in `/tmp/`. All commands reproducible via:

```
find extracted/all/P3.70/img.bin.dump -type d \
  -regex '.*/[0-9]+ \(AmdBoardId\(Dxe\|Pei\)\|PciTableInit\|AmdCpmOemInitPeim\)'
md5sum '<path>/1 TE image section/body.bin'
```

Rebase verification uses TE header `ImageBase` field at `+0x10` (8 bytes, little-endian); diff scan is plain `bytes` compare in Python.
