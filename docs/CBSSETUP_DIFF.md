# CbsSetupDxeSSP P3.70 vs P3.80 — diff analysis

**Question:** Does the `CbsSetupDxeSSP.efi` +320 B size growth between P3.70 and P3.80
contain Gen4-unlock logic (CBS/AGESA companion of the DXIO descriptor `+0x2E` bit-6 flag)?

**Verdict (one-liner):** **NO.** `CbsSetupDxeSSP` is irrelevant to the Gen4 cap. The +320 B
growth is entirely in the HII resource section (`.rsrc`), driven by a cosmetic IFR change
("CCD Control" → "CCDs Control") and the removal of one CCD-count option ("3 CCDs"). The
`.text` and `.data` sections are functionally byte-identical; the only code delta is one
removed `mov` instruction in a CBS defaults-struct initializer at struct offset `+0x15a`,
in the same defaults struct that holds the renamed CCD knob. No DXIO / PCIe / NBIO /
descriptor / Gen4 / ESM / board-rev related change exists.

The full +64 B mystery still must lie in `AmdApcbDxeV3` (or in the descriptor producer that
parses APCB). The parallel agent investigating `AmdApcbDxeV3` is not contradicted by these
findings.

---

## Tool/file availability

- `radare2 6.1.4-1`: works.
- `ifrextractor 1.6.1`: works.
- P3.70 body: `extracted/all/P3.70/.../54 CbsSetupDxeSSP/1 PE32 image section/body.bin` — 194976 B
- P3.80 body: `extracted/all/P3.80/.../54 CbsSetupDxeSSP/1 PE32 image section/body.bin` — 195296 B
- Size delta: **+320 B**, exactly as expected.
- Working copies: `/tmp/cbs_diff/cbs_p370.bin`, `/tmp/cbs_diff/cbs_p380.bin`.
- IFR text:
  - P3.70: pre-existing at `ifr/P3.70/CbsSetupDxeSSP.pe32.0.0.en-US.uefi.ifr.txt`
  - P3.80: extracted to `/tmp/cbs_diff/cbs_p380.bin.0.0.en-US.uefi.ifr.txt`

## PE section sizes (the answer falls out of this single table)

| Section  | P3.70 size | P3.80 size | Delta   | Notes |
|----------|-----------:|-----------:|--------:|-------|
| `.text`  | 0x8560     | 0x8560     | 0       | identical raw size |
| `.data`  | 0x1d60     | 0x1d60     | 0       | identical raw size; **byte-identical** (sha256 match) |
| sect_2   | 0x400      | 0x400      | 0       | identical |
| `.xdata` | 0x2a0      | 0x2a0      | 0       | identical |
| `.rsrc`  | 0x24c80    | 0x24dc0    | **+0x140 (+320)** | HII string + IFR forms |
| `.reloc` | 0xe0       | 0xe0       | 0       | identical |

The +320-byte file delta is wholly inside `.rsrc`. `.data` is bitwise-identical
(sha256 `44c4fcc1…`).

## IFR diff summary

`diff` of the two `*.ifr.txt` files — full output (excluding the SHA256 header line):

```
@@ -706 +706 @@
- OneOf Prompt: "CCD Control",  Help: "...", QuestionId: 0x31, VarStoreId: 0x5000, VarOffset: 0x9A
+ OneOf Prompt: "CCDs Control", Help: "...", QuestionId: 0x31, VarStoreId: 0x5000, VarOffset: 0x9A
@@ -709 +708,0 @@
- OneOfOption Option: "3 CCDs" Value: 3
```

That is the **entirety** of IFR-level difference between P3.70 and P3.80 in this driver:

1. Cosmetic prompt rename `"CCD Control"` → `"CCDs Control"` (typo fix).
2. Removal of one option (`"3 CCDs"` value 3) from the CCD-count OneOf.

No new OneOf, Numeric, CheckBox, SuppressIf, GrayOutIf, Default, or DefaultStore.
No new question targeting any DXIO / NBIO / PCIe / ESM / Gen4 / Strap / Override / Board /
APCB var. No varstore changes. No new IFR opcode of any kind.

## String diff

`r2 -e bin.cache=true … iz` and narrow + wide-string passes through `.rsrc`:

- Strings only in P3.80: `CCDs Control` (the renamed prompt above).
- Strings only in P3.70: `3 CCDs` (the removed option text — disappears with its
  `OneOfOption`).
- A single 1-byte change in a debug tag string (`\t\aR` → `\t\aS`); negligible.

Specifically searched and **not found** in either binary's added strings: `Gen4`, `Gen 4`,
`ESM`, `Strap`, `Rev`, `1.03`, `Override`, `Board`, `APCB`, `Cap`, `DXIO`, `Force`. None
of these appear as additions or modifications.

## Function diff

- Function counts identical: **101 functions in P3.70, 101 in P3.80**.
- Function sorted-size diff: **exactly one function size differs** — `fcn.0x00013e7c`
  shrinks from 3353 B to 3346 B (Δ = −7 bytes).
- All other 100 functions: identical size.

### The only changed function: `fcn.0x00013e7c`

Single basic block, ~3.3 KB of straight-line `mov`s — i.e., a struct default-initializer.
It writes literal default values into a CBS configuration struct via `rcx` (the `arg1`
struct pointer).

Disassembly diff (only meaningful change):

```
P3.70 @ 0x14498:  mov byte [rcx + 0x15a], 0xf          ; 7-byte instruction
P3.70 @ 0x1449f:  mov byte [rcx + 0x15b], 0xf
...
P3.80 @ 0x14498:  mov byte [rcx + 0x15b], 0xf          ; 0x15a write removed
...
```

The `+0x15a` byte-default write was removed. Everything after that point is identical
content shifted −7 bytes. The −7 B exactly accounts for the function shrink.

Same function also writes `[rcx + 0x9a]` (the CCD Control VarOffset 0x9A from the IFR),
confirming this is the same defaults struct the renamed CCD OneOf points at. The
removed `+0x15a` initializer is consistent with the simultaneous CCD-option removal —
they belong to the same logical change ("rework CCD enumeration in defaults struct").

### Per-port DXIO descriptor relevance check

Recall: the Gen4-enable bit lives at `+0x2E` bit 6 of a per-port DXIO descriptor consumed
by `AmdNbioPcieDxe`.

- The struct touched here is at `VarStoreId 0x5000` (CBS Setup namespace) — wrong varstore.
- The byte offset of the change is `+0x15a` (decimal 346) — not `+0x2E`.
- The struct does have `+0x2E` writes (offset 0x13ec1: `mov dword [rcx+0x2a],…` covers
  0x2a..0x2d, then `mov word [rcx+0x30],…` jumps to 0x30; so 0x2e/0x2f are touched in
  general init, but nowhere is bit 6 of byte 0x2e specifically twiddled differently
  between versions).
- No write of value `0x40` to any byte offset is added or removed.
- No new function calls, no new conditional branches, no new MMIO/SMN reads in either
  version.

## Code-cache .text diff (sanity check)

Naive byte-level `cmp` of the two `.text` sections shows ~14720 differing bytes despite
zero functional change. Cause: PE absolute-address relocations into `.rsrc`. Because
`.rsrc` grew by 0x140, every `lea`/`mov imm64` that references a `.rsrc` symbol past the
insertion point gets its 4-byte displacement rewritten by the linker, producing thousands
of low-Hamming-weight byte deltas. This is exactly the pattern observed (small clusters
of 1-byte deltas in `cmp -l`, almost all in `0x[02468ace]` low nibbles of an immediate).
This is not a code change.

## Verdict

**`CbsSetupDxeSSP` is irrelevant to the Gen4 cap question.** The +320 B size delta is
fully accounted for by:

1. **HII string package re-layout** (~313 B). One added string `CCDs Control`, one removed
   string `3 CCDs`, plus padding/alignment churn in the IFR forms package and the string
   pool.
2. **One removed `mov` instruction** (−7 B in `.text`, exactly cancelling the +7 B that
   would otherwise accumulate after .rsrc grew, leaving `.text` raw size unchanged at
   0x8560 — yes, the linker pads the section, so the freed 7 B inside `fcn.0x00013e7c`
   ends up as trailing zero-padding inside the same `.text` allocation). Functionally
   removes the default-value write `[CBS_struct + 0x15a] = 0x0F` for whatever sub-knob
   that byte represents.

Both changes are CCD/topology cleanup with zero PCIe/DXIO impact. There is no callback,
suppression, gate, default-store entry, or hidden code path in this driver that
participates in setting `+0x2E` bit 6 of any DXIO descriptor.

The Gen4 unlock between P3.70 and P3.80 must come from `AmdApcbDxeV3` (the +64 B grow
reported by the parallel agent) or its consumer/descriptor-producer chain
(`AmdNbioBaseSspDxe`, `AmdCpmPcieInitDxe`, etc.). `CbsSetupDxeSSP` can be **closed as a
lead**.

## Artifacts

- `/tmp/cbs_diff/cbs_p370.bin`, `/tmp/cbs_diff/cbs_p380.bin` — staged copies
- `/tmp/cbs_diff/cbs_p380.bin.0.0.en-US.uefi.ifr.txt` — extracted P3.80 IFR
- `/tmp/cbs_diff/ifr.diff` — IFR text diff (10 lines)
- `/tmp/cbs_diff/funcs_p370.txt`, `/tmp/cbs_diff/funcs_p380.txt` — `afl` output
- `/tmp/cbs_diff/sizes_p370.txt`, `/tmp/cbs_diff/sizes_p380.txt` — sorted (bb_count, size)
- `/tmp/cbs_diff/fn_p370.asm`, `/tmp/cbs_diff/fn_p380.asm` — disasm of changed function
- `/tmp/cbs_diff/text_p370.bin`, `/tmp/cbs_diff/text_p380.bin` — extracted .text
- `/tmp/cbs_diff/data_p370.bin`, `/tmp/cbs_diff/data_p380.bin` — extracted .data (sha256 match)
- `/tmp/cbs_diff/rsrc_p370.bin`, `/tmp/cbs_diff/rsrc_p380.bin` — extracted .rsrc
- `/tmp/cbs_diff/rsrc_wstr370.txt`, `/tmp/cbs_diff/rsrc_wstr380.txt` — wide strings (UTF-16)
