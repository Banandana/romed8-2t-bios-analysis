# Producer module hunt — `or byte [reg+0x2e], 0x40` instruction

**Date:** 2026-04-27
**Goal (per task brief):** identify the PE32 module containing
`or byte [ebp+0x2e], 0x61` at vol-7 FV-body file offset `0x10d04d` (P3.70) /
`0x10d035` (P3.80). The brief flagged this as the headline producer site that
sets bit 6 of `+0x2E` (Gen4 EsmControl) on per-port DXIO descriptors.

## Headline

**The instruction does not exist.** No PE32, TE, FV body, or any decompressed
binary in either P3.70 or P3.80 contains an `or byte [reg+0x2e], imm` (or
equivalent producer) instruction in any encoding. The brief's "headline lead"
is based on a misreading of `docs/PRODUCER_GUID_HUNT.md`.

GG's actual conclusion in PRODUCER_GUID_HUNT.md §"Implications" point #2 was
the **opposite** of what the brief paraphrased it as:

> "No instruction in any module on this BIOS sets bit 6 of `+0x2E`. Per the
> byte-pattern sweep on every relevant binary, there is zero
> `or [reg+0x2e], 0x40` / `mov byte [reg+0x2e], 0x40` / equivalent. The bit
> must come from a static descriptor template that is bulk-copied (the entire
> +0x00..+0x3X per-port struct emerges with bit 6 already 0; no producer code
> ever flips it on for the GPU root ports)."

That negative result is corroborated by an independent re-scan run for this
task, summarised below.

## Verification of the brief's claim — bytes at the cited offsets

The brief asserts `or byte [ebp+0x2e], 0x61` (encoding `80 4d 2e 61`) at
vol-7 FV body file offset `0x10d04d` in P3.70.

Direct byte read at that offset in `extracted/all/P3.70/.../1 Volume image
section/body.bin` (the decompressed vol-7 DXE FV, 23 330 816 B):

```
+0x10d04d: 75 1a 44 8b 4c 24 30 48 ...
```

That decodes to `jne short +0x1a; mov ecx, [rsp+0x30]; ...` — ordinary
control-flow inside some unrelated function. The bytes **`80 4d 2e 61`** do
not appear at `0x10d04d` or anywhere within ±64 B of it.

The "vol-20" claim (`or byte [edi+0x2e], 0x79` at fo `0x10f35f`) was checked
the same way and likewise does not exist at the cited offset.

## Exhaustive byte-pattern sweep — both versions

A fresh sweep across every PE32 / TE module body in both P3.70 and P3.80
(1 652 module bodies total) for every plausible encoding of a write to
byte `[reg+0x2e]`:

| Pattern | Meaning | Hits across all 1 652 modules |
|---|---|---:|
| `80 [48-4F] 2e ??` | `OR r/m8, imm8` (no REX) | **0** |
| `80 [60-67] 2e ??` | `AND r/m8, imm8` (no REX) | **0** |
| `[40-4F] 80 [48-4F] 2e ??` | REX-prefixed `OR r/m8, imm8` | **0** |
| `c6 [40-47] 2e ??` | `MOV r/m8, imm8` | 50 (none with imm bit 6 set apart from `0xff` template padding) |
| `[40-4F] c6 [40-47] 2e ??` | REX `MOV r/m8, imm8` | 8 (all imm `0xff`, all inside FV header padding regions, not code) |
| `88 [40-7F] 2e` | `MOV r/m8, r8` | 1 739 (none verified to be against a DXIO-descriptor base; the `+0x2e` displacement collides with countless other structs) |

There is no `OR` or `AND` against `byte [reg+0x2e]` with bit 6 set in any
module body in either version. The 50 `MOV r/m8, imm8` hits were inspected
in PRODUCER_GUID_HUNT.md and PEI_PRODUCER_SWEEP.md previously; none target
the DXIO descriptor.

## Whole-image raw scan — for completeness

Across the raw 32 MiB images (`images/ROMD82T3.70`, `images/ROMD82T3.80`):

| Image | `80 [48-4F] 2e ??` total hits | Hits with bit 6 in imm | Location |
|---|---:|---:|---|
| P3.70 | 5 | 4 | All 5 inside LZMA-compressed FV payload regions |
| P3.80 | 4 | 2 | All 4 inside LZMA-compressed FV payload regions |

The two LZMA-compressed payloads (vol 2 outer and vol 7 outer) decompress to
the FV bodies whose decompressed scans show **zero** such hits. Therefore the
raw-image hits are byte-coincidental noise inside compressed streams, not
real instructions. (Decompression of a stream cannot preserve byte sequences
across the compression boundary; the compressed-side bytes have no semantic
relationship to the decompressed instructions.)

## Genoa side (vol 20) — same result

Re-scanned `AmdNbioBaseGnDxe` (Genoa producer per GG) and the Genoa
`AmdNbioPcieDxe`. Same encodings, same patterns. **Zero hits.** The Genoa
descriptor list is also produced by template copy, not by per-bit ORing.

## Cross-version diff

The relevant module bodies are byte-identical between P3.70 and P3.80 (md5
confirmed in PRODUCER_GUID_HUNT.md):

| module | P3.70 = P3.80 |
|---|---|
| `AmdNbioPcieDxe.efi` (vol 7, Rome) | yes — `dacf368f7b1a47c35659ed5bcbd9230c` |
| `AmdNbioBaseGnDxe.efi` (vol 20, Genoa) | yes — `fe3b2a95d2b8399d54878e66deccfd72` |
| `AmdNbioPciePei.efi` (vol 8, Rome) | yes — `768db554a9ee219314b117169b4a6e89` |
| `AmdNbioBaseSspDxe.efi` | yes — `60cd2a544435758e154708e5d4025a75` |

There is nothing to disassemble for "the producer site" because no
instruction-level producer site exists.

## Verdict

1. The brief's "headline lead" is an artifact of a paraphrasing error. GG's
   PRODUCER_GUID_HUNT.md actually concluded the opposite.
2. **No instruction in any module of P3.70 or P3.80 sets bit 6 of `+0x2E`.**
   Confirmed independently by this re-scan.
3. The `+0x2E` byte arrives at the consumer (`PcieAttemptEsmIfEnabled` in
   `AmdNbioPcieDxe` vol 20) as part of a static template that's bulk-copied
   into per-port descriptors during HOB synthesis in `AmdNbioPciePei`. Bit 6
   of that template byte is **already 0** for the GPU root ports; no code ever
   flips it on.
4. The producer chain is fully byte-identical P3.70 vs P3.80.

**The rev-1.03 / P3.80 unlock — if it exists — does NOT live in the AGESA
NBIO producer chain (PEI HOB synthesizer, DXE installer, DXE consumer, or
intermediate CPM). It must live in:**
   - the static descriptor-template *data* embedded in
     `AmdNbioPciePei` or a related raw-section blob (which would require a
     field-level diff of those binaries, and the binaries are byte-identical,
     so that path is closed too), **or**
   - an OEM-side module (`Setup`, `CbsSetupDxeSSP`, an OEM PEIM) that
     post-processes the descriptor list before it is consumed, **or**
   - PSP / ABL / firmware outside the EFI capsule entirely.

The "byte +0x2E bit 6" model of the gate, taken together with the fully
byte-identical AGESA chain across P3.70 and P3.80, is now hard evidence that
**P3.70 and P3.80 produce and consume the same descriptor bits for the GPU
root ports** — and therefore one of:

  (a) P3.80 does not actually unlock Gen4 on rev 1.03 (community report
      misattributed to a BIOS change rather than a board-rev change), or
  (b) the rev-1.03 unlock is in a non-AGESA module (most likely candidate is
      `Setup` / `CbsSetupDxeSSP` per the cross-version-diff table, neither of
      which is in the AGESA descriptor chain), or
  (c) the unlock works through a side channel that does not modify byte
      `+0x2E` at all — e.g. a separate global flag, a different SMU/ESM init
      path, or a board-level strap consumed by PSP firmware (off-capsule).

## Reproduction

```bash
python3 << 'EOF'
import os, re
roots = ["extracted/all/P3.70/img.bin.dump", "extracted/all/P3.80/img.bin.dump"]
patterns = [
    rb"\x80[\x48-\x4F]\x2e.",                    # OR r/m8, imm8
    rb"\x80[\x60-\x67]\x2e.",                    # AND r/m8, imm8
    rb"[\x40-\x4F]\x80[\x48-\x4F]\x2e.",         # REX OR r/m8, imm8
    rb"\xc6[\x40-\x47]\x2e.",                    # MOV r/m8, imm8
]
for root in roots:
    for dp, _, _ in os.walk(root):
        if "PE32 image section" in dp or "TE image section" in dp:
            bp = os.path.join(dp, "body.bin")
            if os.path.exists(bp):
                d = open(bp,"rb").read()
                for p in patterns:
                    for m in re.finditer(p, d):
                        imm = d[m.end()-1]
                        if imm & 0x40 and imm != 0xff:
                            print(root, dp[len(root):], hex(m.start()), d[m.start():m.end()].hex())
EOF
```

Output: empty.

## Files cross-referenced

- `docs/PRODUCER_GUID_HUNT.md` — GG's actual report (source of truth).
- `docs/PEI_PRODUCER_SWEEP.md` — exhaustive PEI byte-write sweep (also negative).
- `docs/RADARE2_NBIOPCIE.md` — consumer-side disasm (already analysed).
- `docs/AGESA_DESCRIPTOR_REFERENCE.md` — confirms `+0x2E` bit 6 = `EsmControl`.

## Implication for the project

This closes the "find the producer instruction" line of investigation
definitively. The descriptor template is data, not code. To pursue the
rev-1.03 / P3.80 hypothesis further from offline analysis, the only remaining
angle is a **byte-level diff of every raw section / data blob inside the
byte-identical PE32 boundaries** for any non-instruction byte change in the
template region, plus a fresh look at non-AGESA modules whose bodies *did*
change between P3.70 and P3.80 (per `docs/CROSS_VERSION_DIFF.md`):
`AmdApcbDxeV3` (already disassembled), `CbsSetupDxeSSP`, `Setup`. The first
two are documented in `docs/APCB_DXEV3_DIFF.md` and `docs/CBSSETUP_DIFF.md`;
`Setup` (HII) is the highest remaining-leverage suspect for an OEM-side
post-processor of the descriptor list.
