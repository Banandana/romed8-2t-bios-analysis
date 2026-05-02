# `AmdCpmOemInitPeim` — P3.70 vs P3.80 disassembly diff (FV8/43, 43,280 B)

**Verdict: NEGATIVE. This module is NOT the Gen4 producer.**

The hash difference between P3.70's and P3.80's FV8/43 instance of `AmdCpmOemInitPeim` is **100% explained by absolute-pointer rebasing**. The two binaries are functionally byte-identical. ASRock's OEM PEIM shim was not touched between P3.70 and P3.80.

## Inputs

```
P3.70  FV8/43  TE  43280 B  sha256[:16]=03123583e8bd3e03   image_base=0xffe32f80
P3.80  FV8/43  TE  43280 B  sha256[:16]=f67b4964d6bd4c14   image_base=0xffe32f60
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^ delta = -0x20
P3.70  FV21/40 TE  45568 B  sha256[:16]=cf5a5f6122635403  } identical
P3.80  FV21/40 TE  45568 B  sha256[:16]=cf5a5f6122635403  }
```

Both files extracted from:
`extracted/all/P{ver}/img.bin.dump/8 61C0F511-A691-4F54-974F-B9A42172CE53/43 AmdCpmOemInitPeim/1 TE image section/body.bin`

TE header parse (identical for both except `image_base`):
```
sig=VZ  machine=0x14c (i386, 32-bit)  numsec=3  subsys=11 (EFI_RUNTIME_DRIVER)
stripped_size=0x1b8  entry=0x240  base_code=0x240
.text   vaddr=0x240   rawsize=0xe60   file_off=0x88
.data   vaddr=0x10a0  rawsize=0x9900  file_off=0xee8
.reloc  vaddr=0xa9a0  rawsize=0x100   file_off=0xa7e8
DataDirectory[0] (BASE_RELOC) va=0xa9a0  sz=0x100
```

## Diff analysis

Raw byte-diff: **127 differing bytes** across 84 contiguous groups (gap ≤ 8). All concentrated in `.text`, a small block in `.data`, and the `.reloc` section.

### Step 1 — image_base rebase fingerprint

P3.80's `image_base` is `0xffe32f60`, P3.70's is `0xffe32f80`. Delta = **-0x20**.

Sampling the diffs:

| Diff offset | P3.70 byte | P3.80 byte | Δ |
|---|---|---|---|
| 0x10 (TE header `image_base[0]`) | 0x80 | 0x60 | -0x20 |
| 0xb7 (`.text`) | 0x50 | 0x30 | -0x20 |
| 0xd7 (`.text`) | 0x30 | 0x10 | -0x20 |
| 0x469-0x46a (`.text`) | `0c d9` | `ec d8` | -0x20 with borrow |
| 0x13b0 (`.data` LE32) | `a8 3a e3 ff` (=`0xffe33aa8`) | `88 3a e3 ff` (=`0xffe33a88`) | pointer -0x20 |
| 0x13b4 (`.data` LE32) | `0xffe33a25` | `0xffe33a05` | -0x20 |
| 0xa744 (`.data` LE32) | `0xffe34040` | `0xffe34020` | -0x20 |
| 0xa7c8…0xa7f4 (`.data` ptr table, 11 entries) | all `0xffe3....` | all `0xffe3.... - 0x20` | -0x20 |

Every differing byte sits inside a 32-bit little-endian word whose high half is `0xffe3` — i.e., an absolute pointer into the module's load image. Each such word is exactly `0x20` smaller in P3.80.

### Step 2 — exhaustive verification

Algorithm: walk every `.text`/`.data` diff offset; find the 4-byte alignment (within `i-3..i`) where the LE32 word in P3.70 equals `0xffe3....`; verify P3.80 has the same word minus `0x20`; if so, mark all four bytes "explained as rebase".

Result:
```
Total differing bytes:                   127
Explained as image_base rebase (-0x20):  126
Remaining unexplained:                     1
  └─ offset 0x10: TE header image_base low byte itself
```

After patching all rebased pointers in P3.70 to match P3.80, the only remaining 1-byte difference is the `image_base` field in the TE header at file offset `0x10` — which is the *cause* of all the rebases, not a code change.

**Conclusion: the `.text` and `.data` of `AmdCpmOemInitPeim` (FV8/43) are functionally identical between P3.70 and P3.80.** No new instructions, no new functions, no new tables, no new strings.

### Step 3 — content sanity check (P3.70)

Strings scan for: `Gen4`, `Gen 4`, `ESM`, `DXIO`, `Engine`, `Port`, `Strap`, `Rev`, `1.02`, `1.03`, `Board`, `Descriptor`, `OEM`, `ASRock`, `ASR`, `RomeD8`, `ROMED8`, `BMC`, `Pcie`, `PCIE`.

**Zero matches.** No descriptor-synthesizer or Gen-cap strings present.

Bit-6 / `+0x2e` instruction-pattern scan in `.text` (3,680 B):
```
or byte [reg+0x2e], 0x40       — 0 matches
or byte [reg+disp32+0x2e], 0x40 — 0 matches
bts [reg+0x2e], 6              — 0 matches
0x40 immediate bytes total     — 19 (none in a +0x2e context)
0x2e displacement bytes total  —  5 (none with a 0x40 OR adjacent)
```

The `.text` is too small (3,680 B) to plausibly contain a per-port DXIO descriptor producer; the bulk of the module (`.data`, 39,168 B) is a static blob that did not change.

## Why the module size differs from G's report (43,280 vs 43,470)

`docs/OEM_SHIM_HUNT.md` cited 43,470 B for the FV8 instance. That was the FFS *body* size (`body.bin` = 43,470 B) which includes the FFS section headers around the TE image. The TE image itself is 43,280 B — matches the task framing, and matches between P3.70 and P3.80.

## Conclusion

`AmdCpmOemInitPeim` (FV8/43, the early-boot copy that G's hash sweep flagged as differing) is **eliminated as the Gen4 producer candidate.** The hash diff between P3.70 and P3.80 is a pure linker artifact — `image_base` shifted by `0x20`, every absolute pointer rebased accordingly, no code or data was changed.

This means G's `MODULE_SWEEP_P3.70_vs_P3.80.md` "FV8 differs while FV21 identical" signal was a **false positive on this PEIM**. The same failure mode (image_base shift causing pointer-only diffs) probably explains the FV8/FV21 asymmetry: the FV21 main-dispatch volume happens to keep its image_base stable across the two BIOS builds while the FV8 cold-boot volume is re-laid-out, producing rebase noise on every module in FV8 regardless of whether its source changed.

**Recommendation:** revisit `MODULE_SWEEP_P3.70_vs_P3.80.md` with rebase-aware diffing. Modules whose only diff is image_base-explained should be reclassified as identical. Apply the algorithm in this doc (find LE32 words at diff offsets matching `image_base & 0xffff0000`, check delta == image_base delta) to all other "FV8 diffs but FV21 identical" entries before treating any of them as a producer lead.

## Next candidates

Given:
- APCB blob byte-identical (subagent #1).
- `AmdNbioPcieDxe` byte-identical P3.70=P3.80 (subagent #5).
- `AmdNbioPciePei` no producer hit (`DISASM_AmdNbioPciePei.md`).
- `AmdCpmPcieInitPeim` / `AmdCpmPcieInitDxe` examined (`DISASM_AmdCpmPcieInit*.md`).
- `AmdCpmOemInitPeim` FV8 — eliminated here (rebase artifact).
- `CbsSetupDxeSSP` — examined (`CBSSETUP_DIFF.md`).
- `AmdApcbDxeV3` — primary lead per `APCB_DXEV3_DIFF.md` (already disassembled).

The remaining producer-candidate space is shrinking. **Top two follow-ups:**

1. **Re-run `MODULE_SWEEP_P3.70_vs_P3.80.md` with rebase-aware diff** to filter out other false positives like this one, then any *real* P3.70→P3.80 diff in a PEIM/DXE near the PCIe init path becomes the new lead.
2. **`AmdCpmDataPeim`/`AmdCpmDataDxe`** (or any module with "Cpm" in the name that handles per-board configuration data tables) — these often hold static OEM data tables consumed by the CPM (Common Platform Module) framework. If the producer is data-driven rather than code-driven, the change might be in a PCD/HOB/data PEIM rather than executable code. Check whether such a module exists in this BIOS and diff with rebase awareness.

## Reproduction

```bash
# Extract
cp "extracted/all/P3.70/img.bin.dump/8 61C0F511-A691-4F54-974F-B9A42172CE53/43 AmdCpmOemInitPeim/1 TE image section/body.bin" /tmp/oem_p370.bin
cp "extracted/all/P3.80/img.bin.dump/8 61C0F511-A691-4F54-974F-B9A42172CE53/43 AmdCpmOemInitPeim/1 TE image section/body.bin" /tmp/oem_p380.bin

# Compare: 127 raw byte differences
cmp -l /tmp/oem_p370.bin /tmp/oem_p380.bin | wc -l   # 127

# Image base shift -0x20 visible in TE header at offset 0x10
xxd -s 0x10 -l 8 /tmp/oem_p370.bin   # 80 2f e3 ff 00 00 00 00
xxd -s 0x10 -l 8 /tmp/oem_p380.bin   # 60 2f e3 ff 00 00 00 00
```
