# CbsBaseDxeSSP P3.70 vs P3.80 — byte-by-byte disassembly diff

**Date:** 2026-04-27
**Goal:** Characterize the `CbsBaseDxeSSP.efi` PE32 difference between BIOS P3.70 and P3.80. The module sweep flagged it as a same-size hash change (+0 B), which can mean a constant-table flip, a linker re-layout, or a patched immediate. Determine whether any change touches the PCIe Gen4 / ESM gate.

**Verdict (executive summary):** **(b) linker re-layout artifact, with one trivial source-level edit.** The single semantic change between P3.70 and P3.80 is the **removal of one default-initializer instruction** in a CBS struct-defaults function — the line `mov byte [rcx+0x15a], 0x0f` was deleted. Field `+0x15a` is no longer initialized to the AGESA-Auto sentinel `0x0f`; it is now left at whatever the caller's allocator pre-set (typically zero). Every other byte change in the binary (4068 of 4069 raw byte-diffs) is a mechanical relocation/displacement adjustment caused by the resulting 7-byte deletion + linker re-padding. **No Gen4/ESM/DXIO bytes, no `+0x2E` bit-6 logic, no board-rev MMIO read, no strap-default flip.** The change is unrelated to the Gen4 unlock.

---

## Tool availability

- `radare2 6.1.4-1` — installed and working
- `python3` + `pefile` — installed and working
- both PE32 bodies copied to `/tmp/cbsbase_p3{70,80}.bin`

There is exactly **one** `CbsBaseDxeSSP` instance in each BIOS image (FFS entry 52 inside the standard volume). Sizes are identical at 15 008 bytes (per the module sweep's "+0 B" classification).

```
P3.70 sha256 = df4912b37c5cec4cf3cb78159503d4c2537895dc7519a1cb09d76cfd71ef27eb
P3.80 sha256 = 75457db65fa60afa34539c9ee8db3c3b5d0b28c48c7607568637789efb2f583c
```

## PE section breakdown

Sections are byte-for-byte the same size in both versions (this is what makes it a "+0 B" diff):

| section   | VA / RawOff      | VirtSize / RawSize  |
|-----------|------------------|---------------------|
| `.text`   | `0x002a0`        | `0x2a43 / 0x2a60`   |
| `.data`   | `0x02d00`        | `0x0b18 / 0x0b20`   |
| (unnamed) | `0x03820`        | `0x015c / 0x0160`   |
| `.xdata`  | `0x03980`        | `0x00c4 / 0x00e0`   |
| `.reloc`  | `0x03a60`        | `0x0040 / 0x0040`   |

ImageBase=0, EntryPoint=0x2a0. Identical across both versions.

## Raw byte-diff distribution

`cmp -l` reports **4069 differing bytes**. Naive interpretation would suggest a major rewrite. It is not.

Mapped to PE sections:

| section   | differing bytes |
|-----------|-----------------|
| `.text`   | 4066            |
| `.data`   | 3               |
| (unnamed) | 0               |
| `.xdata`  | 0               |
| `.reloc`  | 0               |

Run `difflib.SequenceMatcher` on `.text`: **99.6% (10805/10848 B) is structurally identical via shifted alignment.** Reduced to a clean edit script:

```
delete   P3.70[0x15f2..0x15f9] (7 B)  -> P3.80[0x15f2]
insert   P3.70[0x2ae9]                -> P3.80[0x2ae1..0x2ae9] (8 B of 0xCC padding)
35 single-byte replacements throughout .text, all displacement-immediate adjustments
```

The 7-byte delete + 8-byte CC-padding insert is the linker keeping the section size constant. The 35 single-byte changes are call/RIP-relative offsets re-targeted because the deletion shortened a function; everything after it shifts by `-8` (rounded to instruction boundary inside the affected function, then re-padded).

Histogram of the 35 single-byte deltas — every change is preceded by a `0xe8` (CALL rel32) or a `0x05`/`0x0d` (ModRM byte for `MOV/LEA RIP+disp32`):

```
delta=-8:    15 occurrences   (calls within or just after the modified function)
delta=-13..-238: 19 occurrences (cumulative shifts later in .text after additional small relocations)
delta=+1, +65, +80, +147: 4 occurrences (calls into earlier-located functions whose targets stayed put, but call site moved)
```

The 3 `.data` diffs are PE runtime-function-table RVAs at offsets `0x35d0`, `0x3610`, `0x3630`, all shifting by exactly `-0x8`:

```
0x35d0:   0x0000263c -> 0x00002634   (-8)
0x3610:   0x00001cf0 -> 0x00001ce8   (-8)
0x3630:   0x00001cf0 -> 0x00001ce8   (-8)
```

Same pattern: function start RVAs shifted up by 8 because the modified function got 8 bytes shorter.

## The semantic change

Located in a CBS-struct default-initializer function at file offset `0xfd4` (size ~3352 B in P3.70, ~3344 B in P3.80). This function takes `rcx` = pointer to a CBS settings struct, fills 421 fields at offsets `+0x80` through `+0x285`, then returns `eax = 0xff5` (likely the struct size constant). It is the AGESA "load defaults" routine for one of the CBS sub-feature blocks.

Surrounding instruction context at the deletion site:

```
P3.70 instructions:                          P3.80 instructions:
  0x15e2: mov byte [rcx+0x158], 0x0f           0x15e2: mov byte [rcx+0x158], 0x0f
  0x15e9: mov byte [rcx+0x159], 0x0f           0x15e9: mov byte [rcx+0x159], 0x0f
  0x15f0: mov byte [rcx+0x15a], 0x0f   <--- DELETED in P3.80
  0x15f7: mov byte [rcx+0x15b], 0x0f           0x15f0: mov byte [rcx+0x15b], 0x0f
  0x15fe: mov byte [rcx+0x15c], r8b            0x15f7: mov byte [rcx+0x15c], r8b
  0x1605: mov byte [rcx+0x15d], 0x0f           0x15fe: mov byte [rcx+0x15d], 0x0f
  ...                                          ...
```

Field-level diff in the `+0x150..+0x170` window:

| field    | P3.70    | P3.80    |
|----------|----------|----------|
| +0x150   | = 0x02   | = 0x02   |
| +0x152   | = 0x02   | = 0x02   |
| +0x154   | = r8b    | = r8b    |
| +0x155   | = 0x0f   | = 0x0f   |
| +0x156   | = 0x0f   | = 0x0f   |
| +0x157   | = r8b    | = r8b    |
| +0x158   | = 0x0f   | = 0x0f   |
| +0x159   | = 0x0f   | = 0x0f   |
| **+0x15a** | **= 0x0f** | **(not written)** |
| +0x15b   | = 0x0f   | = 0x0f   |
| +0x15c   | = r8b    | = r8b    |
| ...      | ...      | ...      |

Only `+0x15a` is affected. Every other field across all 421 unique offsets is byte-identical in value and write order between P3.70 and P3.80.

`0x0f` is the standard AMD CBS sentinel for "Auto / use platform default" (it appears in dozens of nearby fields). The semantic of removing this write is "the field is now zeroed by the caller and not explicitly defaulted to Auto" — equivalent to changing the default from `0x0f` (Auto) to `0x00` (whatever 0 means for that field, often "Disabled" or "platform default again, just by a different convention").

## Is `+0x15a` the Gen4 gate?

**No.**

1. The DXIO per-port descriptor's Gen4 bit is at **`+0x2E` bit 6** of a per-port descriptor (per `docs/RADARE2_NBIOPCIE.md`). `+0x15a` is in a completely different struct — a CBS settings struct, ~`0x300 B` in size, accessed `rcx`-relative, never crossed by `AmdNbioPcieDxe`'s code.
2. The CBS struct field offset `+0x15a` is not topologically near any DXIO descriptor pointer. The struct's field range (`+0x80..+0x285`) and field-fill cadence (one byte every 7 instruction bytes) is consistent with a flat configuration block, not an array of port descriptors.
3. Bit-6 / `0x40` byte-pattern scan of both binaries for any `mov byte [reg+0x2e], 0x40` or `or byte [reg+0x2e], 0x40` returns **zero matches** in both P3.70 and P3.80. CbsBase never touches a `+0x2E` byte.
4. String scan for `Gen[0-9]` / `ESM` / `DXIO` / `Strap` / `Override` / `LinkSpeed`: **zero matches** in both versions. No new strings introduced.
5. `AmdNbioPcieDxe` is byte-identical between P3.70 and P3.80 (per `docs/CROSS_VERSION_DIFF.md` and subagent #5's findings) and reads its descriptors from a producer that is not CbsBase.
6. The user-facing AGESA NBIO globals near offset `0x15c..0x16a` in the rig's NVRAM `Setup` VarStore are unrelated — the CBS struct is an in-memory AGESA config struct at runtime, the VarStore is HII variable storage. Offsets just happen to overlap numerically. The CBS field at `+0x15a` is not the VarStore byte at `0x15a`; they are different containers.

The most likely explanation for the change is a routine internal-cleanup edit by AMD: some CBS feature whose default was `0x0f` (Auto) was either deprecated, removed from the CBS schema, or had its default changed from "Auto" to "platform-zeroed" between the AGESA versions bundled with P3.70 and P3.80. Without symbol info or AGESA source, we cannot identify the exact CBS sub-setting at `+0x15a`, but the change pattern is consistent with single-line maintenance, not feature work.

## Position in the Phase 2 picture

Combined with the earlier subagent results, the module-sweep follow-ups now show:

- `AmdApcbDxeV3` (+64 B) — ruled out (`docs/APCB_DXEV3_DIFF.md`): two unrelated APCB shadow-write fixes.
- `CbsSetupDxeSSP` (+320 B) — ruled out (`docs/CBSSETUP_DIFF.md`): HII string-table churn.
- `CbsBaseDxeSSP` (+0 B) — **ruled out (this document):** one CBS default removed for a non-PCIe field.
- `AmdNbioPcieDxe` — byte-identical P3.70 = P3.80.

**The Gen4 unlock is not in any of the four main AGESA-related modules that change between P3.70 and P3.80.** If P3.80 truly enables Gen4 on rev-1.03 boards (per the ASRock Forum reports cited in `CLAUDE.md`), the responsible code must live in one of the smaller / earlier-stage modules flagged by `docs/MODULE_SWEEP_P3.70_vs_P3.80.md` that was not yet investigated, or in PEI-stage code that runs before DXE producers fire. The candidate list narrows to the remaining unchecked entries in the module sweep table.

## Artifacts

- `/tmp/cbsbase_p370.bin`, `/tmp/cbsbase_p380.bin` — extracted PE32 bodies (not committed).

(Helper analysis scripts are inline / one-shot; nothing persistent created in `scripts/`.)
