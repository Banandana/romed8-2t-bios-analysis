# AmdNbioBaseSspDxe P3.70 vs P3.80 — disassembly diff

**Date:** 2026-04-27
**Goal:** test the candidate from `docs/APCB_DXEV3_DIFF.md` § "What's still unknown" — is `AmdNbioBaseSspDxe` the producer of the per-port DXIO descriptor that `AmdNbioPcieDxe` reads at byte `+0x2E` bit 6 (the Gen4-enable gate identified in `docs/RADARE2_NBIOPCIE.md`)? Equivalently, does this module differ between P3.70 and P3.80, and does it touch byte `+0x2E` of any structure?

**Verdict (executive summary): NO — this is not the producer, and not the carrier of the rev-1.03 / P3.80 unlock.**

Three hard negatives, all from this binary alone:

1. The `AmdNbioBaseSspDxe.efi` PE32 body is **byte-identical** between P3.70 and P3.80 (MD5 `60cd2a544435758e154708e5d4025a75`, 16 416 bytes). The FFS-level body (parent `body.bin`, 16 534 B, MD5 `708e5b39…`) is also identical. **Anything ASRock added in P3.80 is not in this module.**
2. **Zero byte-pattern hits** for any access at displacement `+0x2e` (`OR / AND / XOR / TEST / MOV` byte forms with a `disp8 == 0x2e` MODRM, REX-prefixed and unprefixed). The module never reads or writes byte `+0x2E` of any struct.
3. **Strings are pure S3-save and PCI-IO hook scaffolding** — `NbioBaseSetHwInitLock`, `NbioBaseHookPciIO`, `AmdNbioBaseDxeEntry`, `AmdS3Lib*`, `AmdS3Save*`, plus the standard EFI status name table. No `DXIO`, `Engine`, `Port`, `ESM`, `Gen4`, `Strap`, `Descriptor`, `Synthesize`, `Build engine`, `Initialize port`, or any APCB-token string. This module's actual job is the AMD S3 boot-script library + PCI-IO hooking + HwInit-lock register write; not descriptor synthesis.

The candidate is falsified. The descriptor producer is elsewhere — see § "What to look at next."

---

## Tool availability

- `radare2 6.1.4-1` — used (auto-analysis on both binaries; `afl`, `pd`)
- `python3` + `pefile` (just installed) — used for PE section table
- Custom byte-pattern scanner — `/tmp/`-scoped Python, scanned for all 8086-64 byte-access encodings against `disp8 == 0x2e`
- both PE32 bodies copied to `/tmp/nbiobase_p3{70,80}.bin`

```
P3.70 PE32 body: 16 416 B  md5 60cd2a544435758e154708e5d4025a75
P3.80 PE32 body: 16 416 B  md5 60cd2a544435758e154708e5d4025a75   ← identical
P3.70 FFS body:  16 534 B  md5 708e5b399469a9abc7565684eff6b09f
P3.80 FFS body:  16 534 B  md5 708e5b399469a9abc7565684eff6b09f   ← identical
```

Only one `AmdNbioBaseSspDxe` instance per BIOS image (FFS entry 39 inside the main DXE volume `5C60F367-A505-419A-859E-2A4FF6CA6FE5`). Unlike `AmdApcbDxeV3` there is no second instance to consider.

---

## PE section sizes

Identical in both versions (since the binary is byte-identical):

| section  | vsize / rawsize     | notes                                                |
|----------|---------------------|------------------------------------------------------|
| `.text`  | `0x2f92 / 0x2fa0`   | ~12.2 KB code — small module                          |
| `.data`  | `0x09c8 / 0x09e0`   | string table + statics                                |
| (unnamed)| `0x0240 / 0x0240`   | ~580 B; runtime section                               |
| `.xdata` | `0x0130 / 0x0140`   | Win64 unwind info                                     |
| `.reloc` | `0x0080 / 0x0080`   | base relocations                                      |

EntryPoint `0x2a0`. Machine `x86_64`. ImageBase `0`.

---

## Function map (auto-analysis)

`r2 -A` finds **60 functions**, total ~12 KB code. Largest function:

| addr        | bb / bytes  | role (inferred)                                    |
|-------------|-------------|----------------------------------------------------|
| `0x11ef0`   | 276 / 3901  | printf-style formatter (parses `%a %x %d` etc; the basic-block explosion at `0x121e0+` is the EFI digit-table format scanner) |
| `0x10cdc`   | 26 /  496   | S3 save library helper                             |
| `0x11070`   | 15 /  492   | `AmdS3SaveCloseTableCallBack`                      |
| `0x11139c`  | 24 /  248   | (S3 helper)                                        |
| `0x11ba0`   | 19 /  320   | (S3 helper)                                        |
| `0x10b04`   | 23 /  324   | (S3 helper)                                        |
| `0x11070+`  | various     | `AmdS3SaveLib*` helpers                            |
| `0x102ec`   | 13 /  317   | likely `AmdNbioBaseDxeEntry` (matches string)      |

No function near the size of `AmdNbioPcieDxe`'s `PcieAttemptEsmIfEnabled` (which is ~700 B per `docs/RADARE2_NBIOPCIE.md`), and no function with the structural shape of a descriptor walker (linked-list traversal pattern, dword/byte field-load chains keyed off a port-pointer register).

A diff between P3.70 and P3.80 function maps is moot since the binaries are identical, but for completeness: P3.80 also has 60 functions at the same offsets with the same byte counts.

---

## Searched: explicit bit-6 manipulation patterns

Following the same byte-pattern taxonomy used in `docs/APCB_DXEV3_DIFF.md`:

| Pattern (x86-64)                               | Encoding regex                  | Hits in P3.70 | Hits in P3.80 |
|------------------------------------------------|----------------------------------|---------------|---------------|
| `OR  byte ptr [reg+0x2e], imm8`                | `80 4? 2e ??`                    | 0             | 0             |
| `AND byte ptr [reg+0x2e], imm8`                | `80 6? 2e ??`                    | 0             | 0             |
| `XOR byte ptr [reg+0x2e], imm8`                | `80 7? 2e ??`                    | 0             | 0             |
| `TEST byte ptr [reg+0x2e], imm8`               | `f6 4? 2e ??`                    | 0             | 0             |
| `MOV byte ptr [reg+0x2e], imm8`                | `c6 4? 2e ??`                    | 0             | 0             |
| `MOV byte ptr [reg+0x2e], r8`                  | `88 ?? 2e`  (modrm w/ disp8)     | 0             | 0             |
| `MOV r8, byte ptr [reg+0x2e]`                  | `8a ?? 2e`  (modrm w/ disp8)     | 0             | 0             |
| REX-prefixed any-of-above with `disp8 == 0x2e` | `[40-4f] 80 [40-7f] 2e`, etc.    | 0             | 0             |
| Specific bit-6 OR `[reg+0x2e], 0x40`           | `80 4? 2e 40`                    | 0             | 0             |

**Total disp8=0x2e byte-access hits across all encodings: 0.** Not a single instruction in this module dereferences byte `+0x2E` of anything.

For comparison the consumer `AmdNbioPcieDxe.efi` (per `docs/RADARE2_NBIOPCIE.md`) has at least the `f6 46 2e 40` site (`test byte [r14+0x2e], 0x40`) at file offset `0x14b1e` — that's the gate. A producer would have to *write* to the same offset (`80 4? 2e 40` or `c6 4? 2e ??`). Zero such writes here.

---

## Searched: MMIO board-rev strap reads

Looked for absolute 32-bit immediates with the high nibble `0xfedXXXXX` or `0xfd0XXXXX` (the typical Rome NBIO IOHC SMN / strap MMIO range).

Six byte-aligned hits in the binary, but **all six are false positives** — they appear inside larger 64-bit immediates or in the middle of operand bytes for unrelated instructions, not at the start of a `mov rax, imm64` / `lea rax, [rip + ...]` operand. Sample disassembly verification of the highest-byte hits at `0x986`, `0x11f9`, `0x21ec`, `0x261b`, `0x2622` shows they fall inside printf-format helper code and S3-save code paths — no MMIO load instructions involved.

No real MMIO reads of strap-range addresses in this module.

---

## Searched: APCB-token getter calls / AGESA debug-tag strings

No `[APCB Lib V3]`, no APCB-token-getter-shaped function call (the AGESA token getter has a recognizable signature: a thunk that loads a 32-bit token ID, calls into a registered handler array). The strings table in this module is exclusively S3-Save / EFI-status / AMD-S3-Lib material.

---

## Verdict mapping

Per the verdict taxonomy from `docs/APCB_DXEV3_DIFF.md` (a/b/c/d):

- **(a) Unconditional bit-6 set on GPU-slot descriptors that ASRock chose not to ship in P3.70:** ruled out — module byte-identical P3.70/P3.80, and contains zero `+0x2E` writes.
- **(b) Conditional gated on a board-rev-strap MMIO read:** ruled out — no real strap-range MMIO loads, and no version-to-version delta to gate.
- **(c) Module is the descriptor producer:** ruled out — module never touches byte `+0x2E`, has no DXIO/Engine/Port strings, and has no descriptor-walker shaped functions. Its actual job (per strings + function shape) is **AMD S3 boot-script save library + PCI-IO hook + HwInit-lock register write** — i.e. it's the DXE-side glue that *latches* the HwInit-attribute already set by PEI, plus the AGESA S3 boot-script infra.
- **(d) Something else:** N/A — there is no per-version delta to characterize.

Net: this candidate from `docs/APCB_DXEV3_DIFF.md` is **falsified**. `AmdNbioBaseSspDxe` is not the producer of `+0x2E` and not where the rev-1.03 / Gen4 unlock lives.

---

## Cross-version NBIO module survey (bonus negative)

While this analysis was running, I diffed every `*Nbio*` module in the DXE/PEI volumes between P3.70 and P3.80:

| module                  | section type | size      | P3.70 vs P3.80 |
|-------------------------|--------------|-----------|----------------|
| `AmdNbioBaseSspDxe`     | PE32         |  16 416 B | **identical**  |
| `AmdNbioBaseSspPei`     | TE           |  39 712 B | **identical**  |
| `AmdNbioBaseGnDxe`      | PE32         |  15 008 B | **identical**  |
| `AmdNbioBaseGnPei`      | TE           |  32 288 B | **identical**  |
| `AmdNbioPcieDxe` (×2)   | PE32         | 69 824 / 72 640 B | **identical** (already known) |
| `AmdNbioPciePei` (×2)   | TE           | 63 968 / 73 704 B | **identical**  |
| `AmdNbioIOMMUDxe` (×2)  | PE32         | 41 440 / 46 336 B | **identical**  |
| `AmdNbioIOMMUSSPPei`    | TE           | (size unchanged) | **CONTENT differs** |
| `AmdNbioIOMMUGNPei`     | TE           |  13 824 B | **identical**  |
| `AmdNbioIOAPICPei`      | TE           |   4 008 B | **identical**  |
| `AmdNbioAlibDxe` (×2)   | PE32         | 46 592 / 59 072 B | **identical**  |
| `AmdNbioAlibZpDxe`      | PE32         |  53 152 B | **identical**  |

**Every NBIO module in the BIOS is byte-identical between P3.70 and P3.80, except `AmdNbioIOMMUSSPPei` (IOMMU configuration, unrelated to PCIe link speed and Gen-cap).** Combined with `AmdApcbDxeV3`'s deltas being unrelated APCB-shadow write-back fixes (per `docs/APCB_DXEV3_DIFF.md`) and `AmdNbioPcieDxe` being byte-identical (per `docs/CROSS_VERSION_DIFF.md`), **the entire NBIO + APCB DXE/PEI subsystem is functionally unchanged between P3.70 and P3.80.**

---

## Implication

If P3.80 actually does enable Gen4 on rev-1.03 boards (per ASRock Forum TID 24737 community reports), the change is *not* in any AGESA NBIO module. It must be in one of:

1. **`Setup` / OEM HII (ASRock's own module).** Modified in every BIOS version per `docs/CROSS_VERSION_DIFF.md`. If ASRock added a runtime-evaluated callback that conditionally writes a Setup variable that AGESA reads as a token, the actual gate could be ASRock-side, not AGESA-side. Worth examining the OEM `Setup` PE32 diff between P3.70 and P3.80.
2. **`CbsSetupDxeSSP` (+320 B P3.70→P3.80).** Currently characterized in `docs/CBSSETUP_DIFF.md` as adding a new IFR option. If that new IFR option is hidden / suppressed and writes to a token that AGESA's PEI-phase descriptor synthesizer reads, it would be the carrier. Re-read `docs/CBSSETUP_DIFF.md` with this in mind: are any of the new options writing to APCB tokens / NBIO straps?
3. **A module further upstream in PEI / SEC, before `Amd*Pei`.** Specifically the **AGESA SEC entry**, or **`AmdCpmPcieInitDxe`** (or whichever `AmdCpmPcie*` module is on this board — verify against `extracted/` listing). The CPM family is OEM-customizable AGESA glue that *can* contain ASRock-specific descriptor edits, and is the most likely remaining producer candidate.
4. **A non-NBIO, non-APCB module entirely.** E.g. an OEM PEI module that pre-publishes a HOB consumed by AGESA. The hash of every relevant FV between P3.70 and P3.80 from `docs/CROSS_VERSION_DIFF.md` should be re-examined for any module that grew or changed besides the ones already characterized.
5. **PSP firmware / ABL on the SPI but outside the EFI capsule.** APCB tokens can be augmented by ABL which runs before any DXE module loads. If ASRock shipped a different ABL between P3.70 and P3.80 with a per-board-rev token override, this would not appear in any DXE/PEI module hash. Worth checking the PSP directory hashes via `psptool -e` on both images.

The strongest single next move is **(3) `AmdCpmPcie*Dxe`** (OEM-specific) — disassemble that module's P3.70 vs P3.80 with the same workflow used here. CPM is where ASRock would put board-specific descriptor edits, by AMD's design.

---

## Files on disk

Source binaries (do not modify):

```
extracted/all/P3.70/img.bin.dump/7 4F1C52D3-…/2 9E21FD93-…/0 EE4E5898-…/1 Volume image section/0 5C60F367-…/39 AmdNbioBaseSspDxe/body.bin                        (FFS, 16 534 B, md5 708e5b39…)
extracted/all/P3.70/img.bin.dump/7 4F1C52D3-…/2 9E21FD93-…/0 EE4E5898-…/1 Volume image section/0 5C60F367-…/39 AmdNbioBaseSspDxe/1 PE32 image section/body.bin (PE32, 16 416 B, md5 60cd2a54…)
```

(Same paths under `P3.80/`, byte-identical.)

Working copies (this analysis):

```
/tmp/nbiobase_p370.bin   (16 416 B, copy of P3.70 PE32)
/tmp/nbiobase_p380.bin   (16 416 B, copy of P3.80 PE32)
```

No `apcb_work/`-style persistent scratch directory was created — the binaries are byte-identical, so there's nothing to retain beyond this writeup.

No scripts were modified. No commits made.
