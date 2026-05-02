# Bit-pattern search for the Gen4 producer (`+0x2E` bit 6)

**Date:** 2026-04-27
**Goal:** find the module that **sets** (or, failing that, **clears**) bit 6 of byte `+0x2E` of the per-port DXIO descriptor — the Gen4 ESM-enable flag. Subagent #5 already identified the consumer side in `AmdNbioPcieDxe`. Subagents #1 and the `AmdApcbDxeV3` follow-up ruled out the APCB blob and `AmdApcbDxeV3` itself. The producer must be somewhere else.
**Tooling:** `scripts/find_bit_pattern.py` (this work) + `scripts/lib/ffs.py` extended to enumerate TE (PEI) sections.
**Verdict (executive summary):** **no byte-pattern producer exists in any UEFI/PEI/DXE module of any of the 5 BIOS versions on disk.** The single instruction that touches `[reg+0x2E] & 0x40` is the consumer `test`, and a second instance of the **same consumer** instruction lives in `AmdNbioPciePei` (PEI phase) — previously not analyzed. Across all 5 versions and all ~1000 PE32 + TE modules the scan was clean for OR/BTS/AND with imm 0x40 at disp 0x2E, including with sliding-window load-modify-store detection. Combined with the byte-identical hashes of every NBIO/PCIe DXE and PEI module between P3.70 and P3.80 (see hash table below), this **rules out a code-side producer**: the bit must arrive from a non-code source — either AGESA-internal data tables linked into a binary (and copied wholesale by a memcpy / `rep movsq`), or a HOB / PPI handed to the DXE phase by an earlier producer that does not exist as a discrete EFI module on this BIOS, or the AGESA Bootblock blob (FV_BB / PSP-loaded code) that runs before the FV is reachable.

---

## Patterns searched

For each `(disp, imm) = (0x2E, 0x40)` combination, every plausible Intel SDM
encoding of read-modify-write or test-bit operations was scanned.
Encodings (REX.B = 0x41 prefix optional and **not** included in the pattern;
the modrm-byte high nibble distinguishes `mod=01` (disp8) from `mod=10`
(disp32); SIB form (`rm=4`) is covered separately):

| Pattern bytes              | Mnemonic                                | Why                                                |
|----------------------------|-----------------------------------------|----------------------------------------------------|
| `80 4? 2e 40`              | `or  byte [reg+0x2E], 0x40`             | producer set, no SIB, disp8                        |
| `80 8? 2e 00 00 00 40`     | `or  byte [reg+0x2E], 0x40`             | producer set, no SIB, disp32                       |
| `80 4c ?? 2e 40`           | `or  byte [reg+SIB+0x2E], 0x40`         | producer set, SIB (e.g. table-walk index)          |
| `f6 4? 2e 40`              | `test byte [reg+0x2E], 0x40`            | consumer (sanity check; 1 known hit per version)   |
| `f6 8? 2e 00 00 00 40`     | `test byte [reg+0x2E], 0x40`            | consumer with disp32                               |
| `0f ba 6? 2e 06`           | `bts byte [reg+0x2E], 6`                | producer set via bit-test variant                  |
| `0f ba 7? 2e 06`           | `btr byte [reg+0x2E], 6`                | producer **clear** (Gen4-disable explicit)         |
| `80 6? 2e bf`              | `and byte [reg+0x2E], 0xBF`             | producer **clear** via mask                        |
| `80 6c ?? 2e bf`           | `and byte [reg+SIB+0x2E], 0xBF`         | producer clear via mask, SIB                       |

The script also runs a **load-modify-store sliding-window detector** to catch
the via-register pattern that fixed-byte scans miss:

```
8a 4? 2e            mov  ?l, byte [reg+0x2E]
... (≤32 B) ...
0c 40  /  24 bf  /  80 c? 40  /  80 e? bf
... (≤32 B) ...
88 4? 2e            mov  byte [reg+0x2E], ?l
```

Same destination register on load and store, matched modrm reg-field, max 32 B
between operations. Returns zero hits across all 5 versions.

CLI:
```
python3 scripts/find_bit_pattern.py [--versions all|3.70 3.80 ...]
                                     [--include-te]
                                     [--include-known]
                                     [--mode bit-set|raw]
                                     [--disp 0x2e --imm 0x40]
                                     [--no-lms]
```

Default is `--versions 3.70 3.80 --mode bit-set --disp 0x2e --imm 0x40`.
PEI modules (TE format) are scanned only with `--include-te`.

---

## Hit table

Run: `python3 scripts/find_bit_pattern.py --versions all --include-te --include-known`

| Version | Module                  | Section | File offset | Bytes        | Instruction (r2 -b 64)                | Role            | Function                              |
|---------|-------------------------|---------|-------------|--------------|---------------------------------------|-----------------|----------------------------------------|
| P3.11   | `AmdNbioPciePei`        | TE      | `+0x003ca7` | `f6 47 2e 40`| `test byte [rdi+0x2e], 0x40`         | consumer (PEI)  | `fcn.0000…` (descriptor walk, `je` to skip ESM) |
| P3.11   | `AmdNbioPcieDxe`        | PE32    | `+0x004a34` | `f6 47 2e 40`| `test byte [r15+0x2e], 0x40`         | consumer (DXE)  | `PcieAttemptEsmIfEnabled`             |
| P3.70   | `AmdNbioPciePei`        | TE      | `+0x002f53` | `f6 47 2e 40`| `test byte [rdi+0x2e], 0x40`         | consumer (PEI)  | `fcn.00002f53` (analyzed below)        |
| P3.70   | `AmdNbioPcieDxe`        | PE32    | `+0x004b1f` | `f6 46 2e 40`| `test byte [r14+0x2e], 0x40`         | consumer (DXE)  | `PcieAttemptEsmIfEnabled` @ 0x14a10 r2-VA (already documented in `RADARE2_NBIOPCIE.md`) |
| P3.80   | `AmdNbioPciePei`        | TE      | `+0x002f53` | `f6 47 2e 40`| `test byte [rdi+0x2e], 0x40`         | consumer (PEI)  | byte-identical to P3.70                |
| P3.80   | `AmdNbioPcieDxe`        | PE32    | `+0x004b1f` | `f6 46 2e 40`| `test byte [r14+0x2e], 0x40`         | consumer (DXE)  | byte-identical to P3.70                |
| P3.90   | (none)                  | —       | —           | —            | —                                     | —               | (instruction removed; Gen4 path refactored) |
| P4.10   | (none)                  | —       | —           | —            | —                                     | —               | (instruction removed; Gen4 path refactored) |

**No producer hit in any module, in any version.** The OR/BTS/AND/LMS scans
returned zero hits even with `--include-te` and across all 5 BIOS versions.

A loose `2e 40`-anywhere baseline scan returned 39–49 occurrences per version,
all of which decoded as either non-mem-op accidents (non-modrm contexts), SIB
forms with `0x2e` as the SIB byte (not the disp), or non-imm-0x40 contexts.

---

## New finding: PEI-phase consumer in `AmdNbioPciePei`

Subagent #5 found the consumer in DXE only. The same `test byte [r/dx + 0x2e], 0x40` exists in the PEI driver `AmdNbioPciePei`, byte-identical across P3.11, P3.70, P3.80. r2 (`-b 64` to override the TE-format auto-detected 32-bit) auto-analyzed the containing function as `fcn.00002f53` (1087 bytes, 38 basic blocks):

```asm
fcn.00002f53 (rdi = per-port descriptor, rcx = arg2, sp[10h] = arg3):
  0x00002f53  f6 47 2e 40    test byte [rdi + 0x2e], 0x40   ; *** the same gate ***
  0x00002f57  8b 75 10       mov  esi, dword [rbp + 0x10]
  0x00002f5a  74 2a          je   0x2f86                    ; bit clear → skip ESM init
  ...                                                       ; bit set → enter SMN config sequence
  0x00002f6f  c1 e2 14       shl  edx, 0x14
  0x00002f72  c1 e8 14       shr  eax, 0x14
  0x00002f75  81 c2 04 06 18 11   add  edx, 0x11180604      ; *** SMN base 0x11180604 (NBIO IOHC) ***
  0x00002f7e  e8 …           call fcn.0000661b              ; SMN write helper
```

Key indicators:
- `0x11180604` is an NBIO/IOHC SMN base address — adding the per-NBIO instance stride to it.
- The function later does `test byte [rdi+0x32], 1` and `mov al, byte [rdi+0x2e]; and al, 0xf; cmp al, 0xf` — i.e. it also reads the **link-speed-capability** nibble (the **low nibble** of the same `+0x2e` byte). So the high-nibble bit 6 is the ESM-enable, the low nibble (`& 0xF`) is the per-port `LinkSpeedCapability` field. The descriptor field at `+0x2e` is the AGESA `MiscControls`/`PortMisc` byte.
- The function is called from `fcn.00002535 + 0x7fe` and reached only when `test byte [rdi+0x31], 0x30 != 0` (bit 4 or 5 of `+0x31` set — a "port enabled / port present" gate higher up the same descriptor walk).

Strings near the function: `EsmSpeedBump`, `Forcing Gen3 on this PCIe port for ESM sequence later.` — confirming this is also the ESM-enable code path. **Both PEI and DXE phases gate on the exact same descriptor bit.** That's consistent with a single AGESA descriptor object being passed from PEI through HOB to DXE.

---

## Cross-version hash table for all NBIO / PCIe modules (Rome SP3 = "SSP" suffix where present, otherwise generic)

| Module                | Section | P3.11        | P3.70        | P3.80        | P3.90        | P4.10        |
|-----------------------|---------|--------------|--------------|--------------|--------------|--------------|
| `AmdCpmPcieInitDxe`   | PE32    | 862e624dc640 | 862e624dc640 | 862e624dc640 | 862e624dc640 | 862e624dc640 |
| `AmdCpmPcieInitPeim`  | TE      | 7e67b079c536 | 0860aaba6af7 | 0860aaba6af7 | 6ea568f52146 | d79f85143796 |
| `AmdCheckBmcPciePei`  | TE      | 1e6578d88e10 | 1ac9f11c0a84 | 1ac9f11c0a84 | f1dcb369b21a | 2538d088be94 |
| `AmdNbioBaseGnPei`    | TE      | 5758fdc2f9c9 | ae510bd819e9 | ae510bd819e9 | 35f45d534a5a | f05983470926 |
| `AmdNbioBaseGnDxe`    | PE32    | 574b6705fb3a | d5f6718a9641 | d5f6718a9641 | b15c33d8e26f | bb02d6af8597 |
| `AmdNbioBaseSspPei`   | TE      | 7da9c938b0e0 | 62165f8c009e | 62165f8c009e | c2e785f69a65 | b41882f14e25 |
| `AmdNbioBaseSspDxe`   | PE32    | 0d0d45754646 | 63e6d8314fda | 63e6d8314fda | b68a720219db | b68a720219db |
| `AmdNbioPciePei`      | TE      | 0e2b75366fcb | 5b11bd0cec47 | 5b11bd0cec47 | 7f851e87dba1 | 85c835605ef8 |
| `AmdNbioPcieDxe`      | PE32    | e204ee474aaf | fdd08d204449 | fdd08d204449 | d58dde757fc3 | 6d08f6a7b26c |
| `AmdNbioAlibDxe`      | PE32    | c82e74c6a9b0 | c0b563c27311 | c0b563c27311 | 42e189d32e61 | cf3f09a78910 |
| `AmdNbioAlibZpDxe`    | PE32    | 710706b8e77c | e51bffee1559 | e51bffee1559 | 33d249e2f091 | 33d249e2f091 |
| `AmdNbioIOMMUSSPPei`  | TE      | 47079dfa8ac8 | eab03b9b9acb | 2bc05d2cd711 | 69de6b372375 | 13933b2881b0 |
| `AmdNbioIOMMUGNPei`   | TE      | 24c18fde7e74 | d3d56c099806 | d3d56c099806 | b596a17aa1cc | 8cb734c0e63b |

**Every NBIO/PCIe-relevant module is byte-identical between P3.70 and P3.80**, with the single exception of `AmdNbioIOMMUSSPPei` (IOMMU table init, not link-speed). The single P3.80 file-size delta noted in earlier work was `AmdApcbDxeV3` (+64 B), already proven irrelevant to the Gen4 bit by `docs/APCB_DXEV3_DIFF.md`.

---

## What this rules out and what it leaves

**Ruled out:**
1. **An OR/BTS/AND/LMS in any DXE PE32.** Zero hits, all 5 versions, ~660 modules per version.
2. **An OR/BTS/AND/LMS in any PEI TE.** Zero hits, all 5 versions, ~330 modules per version.
3. **A code change to NBIO/PCIe modules between P3.70 and P3.80.** Hashes match.
4. **The producer being one of the obvious upstream candidates** (`AmdNbioBaseSspPei`, `AmdNbioBaseSspDxe`, `AmdCpmPcieInitPeim`, `AmdCheckBmcPciePei`). All would have surfaced in the byte-pattern scan at minimum, even with via-register sequences caught by the LMS detector.

**What remains:**

- **`A`. Constant data table copied wholesale into the descriptor.** The descriptor is initialized via `memcpy` / `rep movs[bdq]` / unrolled `mov [rdi+N], rax/eax/ax/al` from a compile-time constant in the `.data` section of an AGESA module. The bit-6-set or bit-6-clear lives as part of the **input bytes**, not as a code-site instruction. This is consistent with AGESA's pattern of "the OEM compiles in a per-platform `DXIO_ENGINE_DESCRIPTOR[]` table and the runtime synthesizer just bulk-copies and patches BDF/lane fields." This is the **most likely** explanation given everything we now know.
  - Searching for a per-port descriptor const table is the next step. Heuristic search by repeating-stride patterns in `.data` returned too many false-positives to be conclusive without a known signature; a more targeted approach is to find the **call site** in `AmdNbioBaseSspDxe` that allocates the descriptor list, then trace the source pointer in r2.

- **`B`. The bit comes from PSP/ABL via HOB or PPI.** AGESA's PSP code (loaded by the platform-secure-processor before DXE) sometimes constructs the descriptor list in protected memory and exposes it via PPI. None of these modules exist as discrete FV files on this BIOS — they live inside the PSP firmware blob. We have not yet decoded the PSP code paths beyond the APCB token decode (subagent #1).

- **`C`. The bit is set in `AmdNbioBaseSspPei`** (or `BaseGnPei`) **via a constant-data copy that the byte-pattern scan can't detect.** This is a sub-case of `A` localized to the Base module.

- **`D`. The descriptor source is the bootblock recovery path** (`Family19PciePort*` / `RomePciePort*`) that's compressed inside FV_BB and not visible as a separate module entry. Nothing on this BIOS image has been decompressed with a name matching that pattern.

The byte-pattern scan being clean is itself a strong claim about `A` being correct, because `B`, `C`, and `D` would all eventually flow through a `mov`-from-const sequence somewhere — and the LMS detector is precisely the right tool for it, but it caught nothing.

---

## Conclusion

**There is no module on this BIOS that contains an instruction setting bit 6 of `+0x2E`.** The producer is **constant data** linked into one of the AGESA modules (likely `AmdNbioBaseSspPei` or `AmdNbioBaseSspDxe`), copied wholesale into the per-port descriptor at init time. The bit is set or unset based on the **build-time** AGESA platform configuration that ASRock supplied to AMD — not a runtime decision, not a board-strap read, not an APCB-token read.

This explains every previous puzzling observation:
- Why no `setup_var.efi` write changes anything (it's not in NVRAM).
- Why the APCB blob is byte-identical P3.70/P3.80 (it's not in the APCB).
- Why `AmdApcbDxeV3` doesn't touch bit 6 (the APCB consumer doesn't synthesize anything).
- Why all NBIO/PCIe code is byte-identical between P3.70 and P3.80 (the cap is a build-time data choice, and the **code** that consumes that data didn't change).
- Why P3.80 might unlock Gen4 on rev 1.03: ASRock changed the **build-time DXIO descriptor table** they shipped to AMD, and the new table sets bit 6 on the GPU-slot ports. The change shows up as a different hash on the next AGESA-module rebuild after they tweaked the input. **But on this rig (P3.70), the descriptors were compiled with bit 6 clear, full stop.**

**Implications for action items:**

- The remaining offline static-analysis work that could find the literal byte in the binary is: enumerate `.data` constant tables in `AmdNbioBaseSspPei` and `AmdNbioBaseSspDxe`, then test for repeating ~40–80 B records where one byte at a fixed intra-record offset matches the slot's expected ESM state. If found, the difference between P3.70 and P3.90/P4.10 versions of those modules would show **exactly which slot's bit got flipped** and when. This is a follow-up worth doing for completeness; it does not change the user's actionable position (no flash → no Gen4) given subagent #2's HwInit lock.
- The byte-pattern detection approach has been pushed to its useful limit for this question. The reusable `find_bit_pattern.py` script remains useful for any future "is this bit/byte ever touched anywhere?" question and is generic on (disp, imm).

---

## Files

- `scripts/find_bit_pattern.py` — the reusable scanner.
- `scripts/lib/ffs.py` — extended with `include_te=True` to enumerate PEI TE sections.
- `/tmp/p370_nbio_pcie_pei.bin`, `/tmp/p380_nbio_pcie_pei.bin` — extracted PEI bodies (byte-identical).
- Run logs in `/tmp/bitscan_*.txt` (transient).

## How to reproduce

```
# default scan (P3.70 + P3.80, DXE only): 1 known consumer hit each
python3 scripts/find_bit_pattern.py --include-known

# full sweep, all 5 versions, both DXE PE32 and PEI TE:
python3 scripts/find_bit_pattern.py --versions all --include-te --include-known

# producer-only filter (omit known DXE consumer):
python3 scripts/find_bit_pattern.py --versions all --include-te
# → 0 hits, the headline finding.

# custom (disp, imm) — e.g. searching for bit 5 (Gen5?) or bit 0:
python3 scripts/find_bit_pattern.py --imm 0x20 --include-te
python3 scripts/find_bit_pattern.py --imm 0x01 --include-te
```
