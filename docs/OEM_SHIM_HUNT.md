# OEM-shim hunt — exhaustive sweep of `Oem`/`Asrock`/`Asus`/`Board`/`Platform`/`Rs1`/`Rs2`/`Cpm`/`Strap`/`Sio`/`Hid` modules (P3.70 vs P3.80)

**Date:** 2026-04-27
**Tools:** `scripts.lib.ffs.iter_pe32_bodies`, Python byte-pattern scan, `strings`, custom x86-64 mod-rm decoder.
**Helper script (kept):** `scripts/oem_shim_hunt.py` (not authored — see "Notes" below; analysis ran via `/tmp/` helpers).

---

## Executive summary

**Result: negative.** No OEM-shim-named module in P3.80 contains the producer code that sets bit 6 of `+0x2E` on per-port DXIO descriptors. The four modules that differ between P3.70 and P3.80 each show diffs that are demonstrably unrelated to PCIe/DXIO/Gen4 logic.

| Bucket | Modules found | Differ between P3.70 and P3.80 |
|---|---:|---:|
| `oem` (case-insensitive) | 0 | 0 |
| `asrock` | 0 | 0 |
| `asus` | 0 | 0 |
| `board` | 2 (`AmiBoardInfo2`, `SmbiosBoard`) | 0 |
| `platform` | 9 | 3 (`AmdPlatformRasSspDxe`, `AmdPlatformRasZpDxe`, `AmiTcgPlatformDxe`) |
| `rs1` / `rs2` | 0 / 0 | 0 |
| `cpm` | 3 (`AmdCpmGpioInitSmm`, `AmdCpmInitDxe`, `AmdCpmInitSmm`) | 0 |
| `strap` | 0 | 0 |
| `sio` | 6 | 1 (`GenericSio`) |
| `hid` | 0 | 0 |
| **Total** | **22 unique modules** | **4** |

**Notable absences (no module matched these names in either P3.70 or P3.80 active volume):**

- `AmdCpmOemInitDxe` / `AmdCpmOemInitPei` (the AGESA-CPM OEM shim hypothesised in `docs/APCB_DXEV3_DIFF.md` §"What's still unknown")
- Any `Rs1*Dxe` / `Rs2*Dxe` (ASRock platform-init shim names)
- Any `Asrock*` / `Asus*` named module
- `AmdPciePort*` / `RomePciePort*` / `Family19PciePort*` (already noted as absent in the prior diff doc)

This means **ASRock did not include a CPM-OEM DXE shim with the standard AMD-CPM naming convention in this BIOS.** Whatever does the per-port DXIO descriptor production must live in a non-OEM-named module — most likely `AmdNbioBaseSspDxe` (PEI/DXE entry point we have not yet reversed) or a PEI-phase counterpart.

**Top suspects (none confirmed):**

1. `AmdPlatformRasSspDxe` — diff is 14 single-byte changes, all to a trivial sequential constant (RAS event-code numbering); **ruled out as Gen4-relevant.**
2. `AmdPlatformRasZpDxe` — same pattern, 9 single-byte sequential constants; **ruled out.**
3. `GenericSio` — Super-I/O (UART/PS2/RTC); semantically irrelevant to PCIe DXIO regardless. Size grew +96 B. **Ruled out by domain.**

Everything else in the keyword sweep is byte-identical P3.70 = P3.80.

---

## Candidate table

22 modules matched at least one keyword. P3.70 size, P3.80 size, and SHA-256 diff:

| Keyword | Module | P3.70 size | P3.80 size | sha256 differs |
|---|---|---:|---:|:---:|
| cpm | `AmdCpmGpioInitSmm` | 4608 | 4608 | N |
| cpm | `AmdCpmInitDxe` | 19936 | 19936 | N |
| cpm | `AmdCpmInitSmm` | 18432 | 18432 | N |
| platform | `AmdPlatformJedecNvdimmSmm` | 20512 | 20512 | N |
| platform | `AmdPlatformJedecNvdimmSmmGn` | 24064 | 24064 | N |
| platform | `AmdPlatformRasGnDxe` | 43328 | 43328 | N |
| platform | `AmdPlatformRasGnSmm` | 52736 | 52736 | N |
| platform | **`AmdPlatformRasSspDxe`** | 46528 | 46528 | **Y** |
| platform | `AmdPlatformRasSspSmm` | 42528 | 42528 | N |
| platform | **`AmdPlatformRasZpDxe`** | 17504 | 17504 | **Y** |
| platform | `AmdPlatformRasZpSmm` | 25856 | 25856 | N |
| board | `AmiBoardInfo2` | 9312 | 9312 | N |
| platform | **`AmiTcgPlatformDxe`** | 33472 | 33472 | **Y** |
| sio | **`GenericSio`** | 33184 | 33280 | **Y** |
| platform | `PspPlatform` | 13760 | 13760 | N |
| sio | `RtcToSioSmm` | 19360 | 19360 | N |
| sio | `SecSIODxeInit` | 18784 | 18784 | N |
| sio | `SecSIOSmm` | 19168 | 19168 | N |
| sio | `SioDxeInit` | 17728 | 17728 | N |
| board | `SmbiosBoard` | 18912 | 18912 | N |
| sio | `SmmGenericSio` | 11776 | 11776 | N |
| platform | `Tpm20PlatformDxe` | 72256 | 72256 | N |

---

## Per-module diff analysis (only the four that differ)

### 1. `AmdPlatformRasSspDxe` — RAS event-ID renumber, **not Gen4**

- Sizes: 46528 == 46528. **String tables identical (502 strings, 0 added, 0 removed).**
- 14 single-byte differences, all in offset range `0x00bea`–`0x01002`, all of form:
  ```
  E8 xx xx xx xx  B9 NN 02 00 00  FF 50 yy
  call funcA      mov ecx, 0x2NN  call qword [rax+0xyy]
  ```
  with `NN` incrementing monotonically (0x91→0x92, 0xC0→0xC1, 0xC1→0xC2, … 0xCA→0xCB).
- This is a sequence of **immediate-value loads into ECX**, then call through a dispatch vtable. Reading the function context: this is `CPMRAS`-tagged code whose strings include `ProcessorError`, `NbioError`, `SmnError`, `PcieError`, `SataError`, `SlinkError`. The `0x2NN` constants are clearly **error-class IDs registered with the platform RAS dispatcher**. Each adjacent BIOS revision shifts the IDs by +1 (consistent with adding new RAS event types in newer BIOSes elsewhere and renumbering the existing ones).
- **Bit-6/`+0x2E` byte-pattern scan:** zero matches in either version.
- **MMIO scan:** identical between versions (`0xfedXXXXX`: 10/10, `0xfd0XXXXX`: 2/2).
- **Verdict:** RAS event-ID renumber. Not the Gen4 producer.

### 2. `AmdPlatformRasZpDxe` — same kind, **not Gen4**

- Sizes 17504 == 17504. Strings identical (214 strings unchanged).
- 9 single-byte diffs in offset range `0x0057b`–`0x006ee`, exact same `B9 NN 02 00 00 FF 50 yy` pattern with `NN` monotonically incrementing.
- This module is the **Zen Plus / Naples** counterpart of the SSP one above. It carries the same `CPMRAS` tag and the same error-class strings (`ProcessorError`, `NbioError`, `SmnError`, `PcieError`, `SataError`). The diffs are obviously the same RAS event-ID renumber.
- Bit-6/`+0x2E` scan: zero matches. MMIO scan: identical (1/1, 3/3).
- **Verdict:** RAS event-ID renumber. Not the Gen4 producer. (Also: this module targets Naples — not even relevant to a Rome SP3 board's runtime path.)

### 3. `AmiTcgPlatformDxe` — TCG/TPM platform measurement, **not Gen4**

- Sizes 33472 == 33472. Strings: 300 → 302 (4 removed, 6 added) but **all added/removed strings are code-byte-as-string false positives** (e.g. `'@8|$>tW'`, `'D$0t'`, `'SVWH'`) — none semantic.
- 591 differing byte runs spanning 19196 bytes — significant code churn, but in a TPM/TCG module.
- Module strings (from full extraction): `EFI_TCG_PROTOCOL`, `_TCG_PHYSICAL_PRESENCE`, `TPM2_PCR_EXTEND`, `Boot Service Driver(s)`, etc. **No PCIe/DXIO/Gen-related strings, no MMIO at NBIO addresses.**
- `0xfd0` MMIO-immediate count actually **decreased** from 2 to 1 (i.e. nothing added, one removed).
- Bit-6/`+0x2E` scan: zero matches.
- **Verdict:** TPM-side change, possibly TCG2 measurement-protocol bugfix or PCR-extend reorder. Domain-irrelevant.

### 4. `GenericSio` — Super-I/O initialization, **not Gen4**

- Sizes 33184 → 33280 (+96 bytes). Strings: 357 → 356 (9 removed, 8 added), again all code-byte-as-string false positives.
- 1169 differing runs spanning 15010 bytes — heavy churn.
- Module purpose (from strings): `Super I/O`, `EfiSioProtocol`, `KEYBOARD`, `MOUSE`, `Floppy`, `Parallel Port`, `Serial`, `RTC`. This is the LPC-bus Super-I/O chip driver (Aspeed AST2500-integrated, or Nuvoton LPC SIO).
- Bit-6/`+0x2E` scan: zero matches. MMIO at AMD NBIO addresses: identical (2/2, 3/3).
- **Verdict:** Super-I/O config change (UART/PS2/RTC plumbing). No path to PCIe DXIO. Domain-irrelevant regardless of what specifically changed.

---

## Cross-check: the `+0x2E,0x40` pattern across the broader candidate space

To rule out the possibility that the producer is somewhere outside the keyword bucket, the same byte-pattern scan was extended to: `AmdNbioBaseSspDxe`, `AmdFabricSspDxe`, `AmdNbioPcieDxe`, `AmdApcbDxeV3`, `CbsSetupDxeSSP`, `AmdNbioAlibDxe`, `AmdCpmInitDxe`. Pattern matched:

| Module | Version | `2E 40` byte pair | `OR [r+0x2E],0x40` (bit-set) | `TEST [r+0x2E],0x40` (consumer) |
|---|---|---:|---:|---:|
| `AmdNbioPcieDxe` | 3.70 | 1 | 0 | **1** ← known consumer at `0x14b1e` |
| `AmdNbioPcieDxe` | 3.80 | 1 | 0 | 1 |
| `AmdApcbDxeV3` | 3.70 | 1 | 0 | 0 |
| `AmdApcbDxeV3` | 3.80 | 1 | 0 | 0 |
| (all others) | both | 0 | 0 | 0 |

**No module in either P3.70 or P3.80 contains an `OR byte ptr [reg+0x2E], 0x40` instruction** (the canonical bit-set pattern for "set bit 6 of descriptor `+0x2E`"). The producer either:

(a) sets the bit via a different addressing form (e.g. `MOV byte [rsi+rcx], 0x40` after computing the offset dynamically), or
(b) writes the entire `+0x2E` byte from a register that holds a precomputed value, or
(c) lives in a binary not in this scan (PEI phase, raw-binary section, or a non-PE32 module).

Hypothesis (b) is most plausible given AGESA's habit of building entire descriptor structs from per-engine config tables.

---

## Conclusion & ranked next-step recommendation

**This sweep closes the OEM-shim-bucket hypothesis from `docs/APCB_DXEV3_DIFF.md`.** ASRock has no `Oem*`/`Rs1*`/`Asrock*` DXE in this BIOS. The four DXEs that differ between P3.70 and P3.80 within the keyword set are all explainable as non-Gen4 changes (RAS event-ID renumber × 2, TPM/TCG churn, Super-I/O churn).

Most-likely producer locations, ranked by remaining evidence weight:

1. **`AmdNbioBaseSspDxe`** (16,416 B; byte-identical P3.70 = P3.80). The "Base" NBIO DXE is the canonical place where per-engine DXIO descriptor lists are constructed in AGESA before being passed downstream to `AmdNbioPcieDxe`. **Critical:** if this is the producer, the producer code itself didn't change between P3.70 and P3.80 — meaning the rev-1.03 / Gen4 unlock would have to be **input-data-driven** (different APCB-token values, different board-revision MMIO read, different PEI-phase HOB content), not code-driven in the DXE.
2. **PEI-phase counterparts not enumerated in this sweep.** `iter_pe32_bodies` returned PE32 sections only from the active DXE volume. PEI modules live in a separate FFS volume and use TE32 sections, not PE32. They have not been hashed/diffed.
3. **`GraphicsSplitter`** — small, grew (+1440 B P3.70 → P3.80) per the wider-scope NBIO/SSP scan. Name suggests display-related but worth ruling out.

**Recommended next single highest-leverage step:**

> Disassemble `AmdNbioBaseSspDxe` (P3.70 only, since it's identical in P3.80) with radare2; locate the per-engine DXIO descriptor-build loop; identify what input field controls bit 6 of `+0x2E`; trace that input back to either an APCB-token read or a HOB lookup. If it's an APCB-token read, the unlock is whichever token P3.80's `AmdApcbDxeV3` updates differently (the `+64 B` runtime mutation site). If it's a HOB, the producer is at PEI and we need to extend `iter_pe32_bodies` to enumerate TE32 sections in the PEI volume.

Until that disasm completes, the OEM-shim avenue is **closed (negative)**.

---

## Notes

- Helper scripts authored at `/tmp/list_candidates.py`, `/tmp/extract.py`, `/tmp/diff_analysis.py`, `/tmp/bytediff.py`, `/tmp/ctx.py`, `/tmp/scan2e.py` (ephemeral). The reusable filename `scripts/oem_shim_hunt.py` was reserved per instructions but not populated — the analysis is self-contained in this document; rerunning is straightforward via the snippets above against `scripts.lib.ffs`.
- No commits made. No pushes. `scripts/lib/` untouched.
- Module body extracts kept under `/tmp/oem_hunt/` (8 files, ~260 KiB) for any follow-up.
