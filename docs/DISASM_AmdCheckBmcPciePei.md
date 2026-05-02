# AmdCheckBmcPciePei P3.70 vs P3.80 — disassembly diff

**Date:** 2026-04-27
**Goal:** determine whether `AmdCheckBmcPciePei.efi` is the producer of the per-port DXIO descriptor (the source of bit 6 of `+0x2E`), or otherwise responsible for the BMC sideband and `40:01.3` Gen4 advertisement, and whether it gates Gen4 by board rev.
**Verdict (executive summary):** **Not the producer. Not a Gen-cap participant.** This PEIM is a small (1472 B TE image) PCIe link-stability fixup utility that walks the PCIe topology, looks for endpoints whose link parameters indicate marginal training, and pokes two non-PCIe-spec vendor registers (`+0x44`, `+0x50`) on the affected device — not the descriptor or strap. It is **functionally byte-identical across P3.70/P3.80/P3.90** (only relocation deltas — same code) and grew in P4.10 only. Closes this hypothesis.

---

## Tool availability

- `radare2 6.1.4-1` — installed and working
- `python3` — installed
- All four TE images located and copied to `/tmp/AmdCheckBmcPciePei_P3{70,80,90}.bin` and `/tmp/AmdCheckBmcPciePei_P410.bin`

Module is a **TE (Terse Executable) i386 image**, 1472 B (P3.70/P3.80/P3.90) or 2152 B (P4.10). Image base `0xFFD810B0` in P3.70.

---

## Cross-version size + identity table

| Version | TE-section md5                          | size  | functional?                                  |
|---------|------------------------------------------|-------|----------------------------------------------|
| P3.11   | (module absent)                          | —     | **First introduced at P3.70**                |
| P3.70   | `4fcd72e5b74609f462cb3e7f1ca025e1`       | 1472  | baseline                                     |
| P3.80   | `4fcd72e5b74609f462cb3e7f1ca025e1`       | 1472  | **byte-identical to P3.70**                  |
| P3.90   | `667b2eb429989cd791d747f9d17707d4`       | 1472  | only 26 B differ — **all relocation fixups** |
| P4.10   | `d0fbf4b39b16d6c0192d728428281a16`       | 2152  | +680 B — actual code change (out of scope)   |

The 26 P3.70 → P3.90 byte deltas are exclusively in image-base-derived absolute pointers. Each cluster shows `+8 / +8 / -2` patterns at offsets that radare2 confirms are immediates referencing `.data` GUID/PPI tables and the image-base field — i.e. the same code re-linked at a slightly higher VA. Functionally **P3.70 == P3.80 == P3.90**. The PEIM was not modified during the rev-1.02A→1.03 unlock window.

---

## Module identity (PPI dependency)

PEI dependency expression (from FFS dependency section):

```
PUSH E6AF1F7B-FC3F-46DA-A828-A3B457A44282     ; AMD CPM Table PPI
PUSH 057A449A-1FDC-4C06-BFC9-F53F6A99BB92     ; EFI_PEI_PCI_CFG2_PPI (standard)
PUSH 5E133105-E9B6-4D52-9694-6054D5B44AE6     ; AMD-internal services PPI
PUSH 01F34D25-4DE2-23AD-3FF3-36353FF323F1     ; AMD-internal PPI
AND AND AND END
```

The same three GUIDs appear in `.data` (file offset `0x4E0..0x510`) plus what looks like an offset/handle table at `0x510`.

`fcn.00000493` does `sidt [eax]` — a classic PEI trick to recover the PEI Services Table pointer from IDT base in 32-bit code. Used only to locate other PPIs.

No imports of `Gen4`, `ESM`, `DXIO`, `Strap`, `Rev`, `Board`, `BMC`, `descriptor`, `port`, or any AGESA NBIO PPI. **No string literals at all** — no debug prints, no error messages. Pure logic module.

---

## Functional reconstruction

The single substantive function is `fcn.000001f1` (~580 B). Decompiled control flow:

1. **Locate PPIs** via `fcn.0000047c` → `fcn.00000493` (sidt-trick PEI Services lookup).
2. **CPUID leaf 1** (`0f a2`) → extract `family + extFamily` (top byte of EAX after the standard combine: `(eax>>20)&0xff + (eax>>8)&0xf`).
3. **Branch on family**:
   - family `== 0x17` (Zen / Zen 2 / Zen 3 — Rome/Milan): set inner-loop bound to `2`.
   - else: bound to `9`.
   This is a CPU-family fork only — there is no board-rev MMIO read, no SMN access, no strap fetch.
4. **Outer loop** over `bh` (NBIO/socket index), tested against `8`. So 8 iterations max — one per NBIO root complex (4 NBIOs × 2 sockets).
5. **Inner loop** over `bl` (device number 0..7). Mask test `(1<<bl) & 0xA7` — i.e. **only devices 0, 1, 2, 5, 7**. Devices skipped: 3, 4, 6. This pattern matches the AMD Zen IOD root-port enumeration (the live root-complex device numbers).
6. **For each (NBIO, device)**: builds a `(seg=0, bus=NBIO*0x18, dev, fn=2, reg=0xb8)` PCIe config address — `0xb8` is the **Link Control 2 register** within the standard PCIe Capability when the cap is at offset `0x58`. Reads it via `Pci.Read(Width=2, ...)`.
7. **Tests three flags on the LCTL2 word**:
   - `& 0x2000` (bit 13) — *if set*, **skip device**. Bit 13 of LCTL2 is **Hardware Autonomous Speed Disable**: the firmware skips devices that already have HW autonomous speed disabled (i.e. already locked).
   - `& 0x03F0` after a `>>16` shift — equivalence test against `0x10`. After the shift this masks the original LinkStatus2 fields. The exact equivalence (`==0x10`) selects a specific de-emphasis / equalization-phase encoding.
   - `& 0x0800` (bit 11) — secondary skip.
   Devices passing **all three** filters fall into the action arm.
8. **Action**: writes `0x01` to register `+0x50` (offset 5, value 1) and `0x00` to register `+0x44` (offset 4, value 0) on the matched device, then on a fall-through second pass writes `0x00` and `0x00` to the same two registers. Registers `+0x44` and `+0x50` from a PCIe Cap base of `0x58` are **non-PCIe-spec vendor-defined registers in AMD root-port config space** (LC_LINK_MANAGEMENT or LC_CNTL family — link-management / equalization control bits in AMD's vendor-specific section). These are link-retraining / equalization-fixup pokes, not Gen-cap.
9. **Falls through to a generic error path** at `0x42b` (eax = 0, return).

---

## What this module does NOT do

Cross-checked the entire 1472 B image against the brief's lookouts:

| Pattern searched                                        | Found?         |
|---------------------------------------------------------|----------------|
| Bit-6 / `0x40` test or set on byte `+0x2E` of any struct | **No.** No `test ..., 0x40` instruction; no `or byte [reg+0x2e], 0x40` instruction. |
| Reference to BDF `40:01.3` (bus=0x40, dev=1, func=3)    | **No.** Bus calculations are `nbio_idx * 0x18`, not anchored at 0x40. Function field iterated via `bh` (loop variable), 0..7 — yes, function 3 is touched, but as one of 8 iterations, not a hard-coded target. |
| Board-rev MMIO read (`0xfedXXXXX` / `0xfd0XXXXX`)       | **No.** No `mov ..., [0xfed*]` or `[0xfd0*]` anywhere. Only PCI-config reads via the PCI_CFG2 PPI. |
| Strings: `Gen4`, `ESM`, `BMC`, `Strap`, `Rev`, `Board`  | **No strings at all in the binary.** Even Unicode/UTF-16 sweep returns nothing relevant. |
| AGESA / NBIO PPI imports                                | **No.** Only PCI_CFG2 + AMD CPM + 2 unidentified internal PPIs. None are NBIO. |
| Per-port DXIO descriptor pointer manipulation           | **No.** No struct walks, no pointer-list traversal, no `+0x2E` field reference. The module exclusively addresses device-config registers. |
| LCTL2 *write* of speed-related fields                   | **No write to `+0xb8`/`+0xbc`** other than the read. Writes go to `+0x44` and `+0x50` (vendor-specific, not LCTL/LCTL2). |

---

## Why it's named `CheckBmcPcie` — best-fit interpretation

The naming + the device mask `0xA7` (devices 0/1/2/5/7) + the family-17h gate + the LCTL2 inspect + the vendor-specific register poke is consistent with an **AGESA-supplied PEI workaround for BMC-sideband PCIe link training instability**: walks AMD root ports, identifies a port whose LinkStatus2 indicates suboptimal Gen3 equalization (or one already in a stuck state), and twiddles two AMD-vendor link-management bits to nudge it. The "BMC" in the name probably refers to the use case (BMC ASPEED is wired on PCIE2 group on this board, and ASPEED PCIe link training quirks are well-documented — c.f. AMD Family 17h erratum-class workarounds). It does **not** touch the BMC's link speed cap or the BMC root port's Gen4 advertisement.

This is consistent with `40:01.3` (bus 0x40 = NBIO #2/3, device 1, func 3) being the BMC ASPEED root port — but `40:01.3`'s Gen4 advertisement comes from its DXIO descriptor (`+0x2E` bit 6), produced upstream, not from this PEIM. This PEIM only retrains it after producer code has set the cap.

---

## Verdict

**`AmdCheckBmcPciePei` is not the bit-6/+0x2E producer.** It is a small, write-once, family-gated PCIe equalization fixup PEIM, byte-identical (modulo relocation) across P3.70/P3.80/P3.90, that does not consume DXIO descriptors, does not perform board-rev detection, and does not write LCTL2 speed fields. The hypothesis that "the BMC's Gen4 cap is set here, possibly with a rev-strap gate" is **falsified**.

The Gen4 enable for `40:01.3` must originate in whichever module **builds the per-port DXIO descriptor** for that port. Since `AmdApcbDxeV3` (DXE) was already eliminated (`docs/APCB_DXEV3_DIFF.md`) and `AmdNbioPcieDxe` (DXE) is the consumer (`docs/RADARE2_NBIOPCIE.md`), the producer is upstream of DXE — i.e. a **PEIM** that publishes the AMD NBIO topology HOB consumed later by `AmdNbioPcieDxe`.

---

## Next steps (highest leverage)

The remaining producer candidates, in order of suspicion:

1. **`AmdNbioBaseSspPei`** (or `AmdNbioPciePei` — see entry 30 / entry 20 in the FFS tree). These DRY-run the DXIO topology in PEI and publish a HOB. **This is now the prime suspect.** Diff P3.70 vs P3.80 (and P3.80 vs P4.10 for confirmation that the unlock crystallized in P3.80 only). The byte mask `0x40` on field `+0x2E` should appear here if anywhere.
2. **`AmdCpmPcieInitPeim`** (entry 49 in the FFS tree) — ASRock's CPM customization layer. The OEM-specific bit-6 set, if it's a build-time choice rather than AGESA-internal, would live here. This is also the most likely host for any board-rev-strap MMIO read.
3. **`AmdPspPeiV2`** + APCB-token PEI consumers — only if both above come back negative. Lower priority because the APCB body itself was already eliminated as a content source (`docs/APCB_DECODE.md`).

If `AmdNbioBaseSspPei` or `AmdCpmPcieInitPeim` shows the same byte-identical-across-versions story as this module did, then the `40:01.3` Gen4 advertisement may be coming from a runtime AGESA-internal default (per-port descriptor populated from a hard-coded "ASPEED-class device" rule) rather than any board-rev-conditional logic — which would mean **flashing P3.80 would not change the GPU-slot caps** because the ASRock build-time decision predates the entire DXIO synthesizer chain.
