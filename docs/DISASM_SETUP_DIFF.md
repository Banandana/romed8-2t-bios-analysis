# `Setup` PE32 — P3.70 vs P3.80 disassembly diff

**Date:** 2026-04-27
**Goal:** at the **code level** (not IFR), determine whether ASRock's `Setup` HII module carries any change between P3.70 and P3.80 that could enable / participate in a PCIe Gen4 unlock on rev-1.03 boards (new DXE callback, new SetVariable call, new hard-coded BDF/lane table, bit-6/`+0x2E` byte-pattern, etc.).

**Verdict (executive summary):** **No.** The only functional change in `Setup` between P3.70 and P3.80 is a **5-byte null/error-return check inserted into a SecureBoot HII variable callback** (`fcn @ file 0xcdc0`, references the string `"SecureBootSetup"` and `"SetupMode"`). Everything else is mechanical: every later function in `.text` shifted by +4 bytes (relocation-byte cascade), and `.data` carries a function-pointer table whose entries each got +4 added at every 16 B stride (matching the `.text` shift). `.rsrc` (HII / IFR / strings) is **byte-identical**, and `.reloc` / `.xdata` are **byte-identical**. Setup is **not** the location of the Gen4 unlock and contains zero new strings, callbacks, varstore writes, or data tables of any kind that touch PCIe / DXIO / Gen-cap.

This closes the "the Gen4 unlock lives in ASRock's Setup HII / OEM driver" hypothesis.

---

## Files analyzed

This BIOS contains **two** `Setup` PE32 modules (one per DXE volume). Both were diffed.

| Volume / FFS index            | Size (B) | P3.70 sha256(12)  | P3.80 sha256(12)  | Total diffs (B) |
|-------------------------------|---------:|-------------------|-------------------|----------------:|
| Vol `7 4F1C…` / idx 75 ("Setup") — canonical, listed in `CROSS_VERSION_DIFF.md` | 293 504  | `e5c535eb7a91…`   | `7b36880acde7…`   | 30 037          |
| Vol `20 4F1C…` / idx 72 ("Setup") — second copy, smaller variant                | 241 280  | `ff356d779053…`   | `178ff85ec762…`   | 13              |

The 241 280 B copy's diff is **trivial: 13 bytes total**, all build-info (one-byte version constant `0x46→0x50` at file offset 0x6c2 = ASCII "70"→"80" mapping; date/version-string ASCII bytes around 0x128e0 and 0x14450). Zero functional change. It is dropped from the rest of this analysis.

The 293 504 B copy carries 30 037 differing bytes; the rest of this document analyzes that diff.

---

## PE section coverage (293 504 B Setup, both versions identical layout)

```
section    VirtAddr      VirtSize      RawOff        RawSize
.text      0x000002c0    0x00019363    0x000002c0    0x00019380
.data      0x00019640    0x00006e90    0x00019640    0x00006ea0
<unnamed>  0x000204e0    0x00000c00    0x000204e0    0x00000c00
.xdata     0x000210e0    0x00000a54    0x000210e0    0x00000a60
.rsrc      0x00021b40    0x00025cb8    0x00021b40    0x00025cc0
.reloc     0x00047800    0x0000027c    0x00047800    0x00000280
```

PE headers, ImageBase (0x0), entry point (0x2c0), section count, and every section's VA / size are **bit-for-bit identical** between P3.70 and P3.80. No new section, no resized section.

### Per-section diff counts (P3.70 → P3.80)

| section    | bytes-different / section-size | comment                                            |
|------------|-------------------------------:|----------------------------------------------------|
| `.text`    | 29 962 / 103 296 (29 %)        | one real change + cascading relocation shifts      |
| `.data`    | 75 / 28 320 (0.3 %)            | function-pointer table bumps tracking `.text` shift|
| unnamed    | 0 / 3 072                      | byte-identical                                     |
| `.xdata`   | 0 / 2 656                      | byte-identical (no new fn-frame layout)            |
| `.rsrc`    | 0 / 154 816                    | **byte-identical** — HII / IFR / strings unchanged |
| `.reloc`   | 0 / 640                        | byte-identical (no new relocations)                |

`.rsrc` byte-identical confirms — at the binary level — what subagents #3 (suppressed-IFR enumeration) and #4 (DefaultStore) found at the IFR level: **no new menu options, no new HII strings, no new VarStore declarations, no new DefaultStore entries** were added in P3.80's Setup. It also rules out any chance that a hidden HII string referencing Gen4 / DXIO / 1.03 was added.

`.reloc` and `.xdata` byte-identical jointly rule out: any newly-added function (would require new `.xdata` unwind entries and new `.reloc` fixups), any function whose stack frame layout changed (would shift `.xdata`), any new global pointer (would shift `.reloc`).

So the only candidate locus of change is **inside an existing function** in `.text`, with the change small enough not to require new relocations.

---

## `.text` change locality

Bucketing `.text` byte-diffs into 256 B chunks reveals **one tight contiguous run** that contains 99.9 % of all the differences:

```
file 0x00cdc0 - 0x0146c0  (29 903 / 29 962 diff bytes — 99.8 %)
```

Outside this run, `.text` has only 59 scattered single-byte / few-byte deltas, every one of which is a recomputed RIP-relative `lea` / `call` / `jmp` displacement (verified by manual inspection — every diff is at offsets 4 / 5 from a `48 8d` `e8` `0f 84` opcode prefix). These are **purely the linker's response to the size change of the one modified function**: every later RIP-relative reference moved by ±4 bytes, so its 4-byte displacement immediate flipped.

---

## The single modified function: `fcn @ file 0xcdc0` (r2 addr `0x1cde0`)

| version | start  | size  | end (excl) | nbbs | ninstrs |
|---------|--------|------:|-----------:|-----:|--------:|
| P3.70   | 0xcdc0 | 203 B | 0xceab     | 13   | 43      |
| P3.80   | 0xcdc0 | 208 B | 0xceb0     | 13   | 45      |

**Δ = +5 bytes / +2 instructions.** Every function whose address is ≥ 0xceab in P3.70 is shifted forward by +4 in P3.80 (+5 minus 1 byte recovered from a trailing alignment/pad byte). 55 P3.70 functions in the cluster appear at offset+4 in P3.80; this matches the diff cluster size exactly.

### What the function does

Decompilation in radare2 + string cross-reference identifies this as the **HII setup-form callback for the SecureBoot menu**. Confirmed by:

- The function loads the wide string `"SecureBootSetup"` (RIP-rel @ +0x10f1c → string at file offset ~0x2dd18) into r9.
- Loads `"SetupMode"` (RIP-rel @ +0xde59 → file offset ~0x2ac60) into r8.
- Calls into the EFI Variable Services / HII registration code at `fcn.00026370` with those two name strings.
- Touches a global flag at file offset `0x3024e` (a "callback-in-progress" guard flag).

There is **no** PCIe / DXIO / Gen-cap / NBIO / port / strap / link-speed string referenced from this function or its callees. None of the strings `Gen4`, `Gen3`, `ESM`, `DXIO`, `Strap`, `Engine`, `Port`, `Descriptor`, `LinkSpeed`, `0x40`, `1.02`, `1.03`, `Board`, `Override`, `TargetLink` appear anywhere in the `Setup` module's string table at all (filter applied to the full `.rsrc` and `.data` strings via radare2; only PCIe-adjacent strings present are the two boilerplate `"%s: Size %d MB, Speed %d MT/s"` and `"PcieRoot(0x%x)"`).

### What the diff is

Hex byte-level diff at the change point inside `fcn 0xcdc0`:

```
P3.70:  ... ff 50 48                   4c 8b 44 24 30 ...
P3.80:  ... ff 50 48   48 85 c0 78 4a  4c 8b 44 24 30 ...
        |             |              |
        |             |              + body continues unchanged
        |             + 5 new bytes inserted
        + call qword [rax+0x48]   (a HII-services protocol call)
```

The 5 inserted bytes decode as:

```asm
test  rax, rax        ; 48 85 c0
js    +0x4a           ; 78 4a   — branch to existing error-return tail if rax<0
```

This is a textbook **null/error-return-value check inserted after a protocol invocation**. P3.70 unconditionally proceeded to the next call after the protocol returned; P3.80 skips ahead to the function epilogue if the protocol returned a negative `EFI_STATUS` (high bit set).

In context: the protocol call at `ff 50 48` is one of the SecureBoot-related HII variable-service callbacks. The hardening makes the SecureBoot setup form bail out cleanly on protocol failure instead of dereferencing whatever was in rax. This is unrelated to PCIe in any way — it's a generic SecureBoot menu robustness fix, exactly the kind of small UI-callback hardening that AMI / ASRock routinely sneak into successive BIOS revs.

---

## `.data` change explained

The 75 differing `.data` bytes split into three groups (all mechanical):

1. **0x1b8b0 — 0x1bb58 (≈ 30 single-byte diffs at 16 B stride):** every diff is +4 to a low byte of a function pointer / RVA. This is one of `Setup`'s function-pointer dispatch tables (likely the HII callback pointer table). Each entry's RVA points into `.text` after the modified function — every one needed its RVA bumped by +4. Pure consequence of the `.text` shift; no semantic change.

2. **0x1c640 — 0x1c660 (8 ASCII bytes):** date / version build string. Bytes change `'1','6','1','1','6','5','3','0'` → `'0','9','3','3','5','8','0','1'`. ASRock build timestamp / build counter.

3. **0x1f5e8 — 0x1f8e8 (≈ 35 single-byte diffs at 16 B stride):** identical pattern to group 1. A second function-pointer table.

None of the `.data` deltas alter any constant value, BDF, lane number, mask byte, or feature flag. There is no new table, no resized table, and no encoded `0x40` (the `+0x2E` bit-6 mask we were looking for). The hex constant `0x40` does occur in `.data` of both versions but at offsets that are byte-identical between P3.70 and P3.80 (i.e. they're not new in P3.80).

---

## Items affirmatively ruled out

The seven targeted checks from the task brief, each ruled out:

| # | Looked for                                                   | Result      | How                                                               |
|---|--------------------------------------------------------------|-------------|-------------------------------------------------------------------|
| 1 | New PE section / resized section                              | not found   | section table identical                                           |
| 2 | New / restructured function (fn count, `.xdata`, `.reloc`)   | not found   | `.xdata` and `.reloc` byte-identical; +4 shift consistent w/ in-place edit only |
| 3 | New strings: Gen4 / ESM / DXIO / Strap / Engine / Port / Descriptor / 1.02 / 1.03 / Board / Override / TargetLink | not found   | `.rsrc` byte-identical; full `.data` + `.text` string scan via r2 |
| 4 | New `SetVariable` / `gEfiVariableWriteServicesProtocol` call | not found   | the only new code is a `test rax,rax; js` after an existing call  |
| 5 | New / changed hard-coded data table (`.data` / `.rdata`)     | not found   | every `.data` diff is mechanical RVA-bump or ASCII build-info     |
| 6 | Bit pattern / constant `0x40` in any new context             | not found   | `0x40` constants in `.data` are at byte-identical offsets         |
| 7 | Reference to BDF `40:01.3`                                   | not found   | string scan negative; numeric scan negative                       |

The one functional change is the +5-byte SecureBoot callback null-check.

---

## Closure of hypothesis

Setup is the ASRock board-specific HII module. Both subagents #3 and #4 ruled it out at the IFR level (no hidden Gen4 setting, no Manufacturing-only default). This disassembly diff confirms the same conclusion **at the code level**:

- The `Setup` HII binary in P3.80 differs from P3.70 only in:
  - one 5-byte null-pointer-check insertion in a SecureBoot callback (zero PCIe relevance), and
  - cosmetic build-version / build-date string updates in the smaller (vol-20) Setup variant.
- No new code path that touches PCIe, DXIO, Gen-cap, NBIO, root ports, lanes, speed, or board-rev detection exists in P3.80's Setup that didn't exist in P3.70.

The Gen4 unlock that P3.80 plausibly delivers on rev-1.03 boards is **not** carried by `Setup`. Combined with `docs/APCB_DXEV3_DIFF.md`'s finding that `AmdApcbDxeV3`'s +64 B is also not the unlock, the remaining live candidates per the prioritized roadmap are:

- `CbsSetupDxeSSP` (+320 B P3.70 → P3.80) — never disassembled. **Highest remaining offline lead.**
- `CbsBaseDxeSSP` (small change L3.11→P3.70→P3.80→P3.90, finally frozen P3.90=P4.10).
- The producer modules upstream of `AmdNbioPcieDxe` that build descriptors at runtime: `AmdNbioBaseSspDxe` (changed only L3.11→P3.70 then frozen — almost certainly not it) and any `AmdCpmPcieInitDxe` / `AmdCpmPcieInitPeim` (not present in this BIOS image — listed `(missing)` in the cross-version diff).
- A possibility now strengthened by the negative results so far: the Gen4 unlock may not be in any one obvious "PCIe driver" but in `CbsSetupDxeSSP`, which is AGESA's CBS-token consumer. That driver is the one that actually decides per-NBIO / per-port speed-cap policy from CBS tokens at DXE time and is the only DXE PCIe-adjacent module with a meaningful size growth in P3.80 not yet investigated.

---

## Reproduction

```bash
# Extract both Setup PE32s (the canonical 293 504 B one)
P370="extracted/all/P3.70/img.bin.dump/7 4F1C52D3-D824-4D2A-A2F0-EC40C23C5916/2 9E21FD93-9C72-4C15-8C4B-E77F1DB2D792/0 EE4E5898-3914-4259-9D6E-DC7BD79403CF/1 Volume image section/0 5C60F367-A505-419A-859E-2A4FF6CA6FE5/75 Setup/1 PE32 image section/body.bin"
P380="extracted/all/P3.80/img.bin.dump/7 4F1C52D3-D824-4D2A-A2F0-EC40C23C5916/2 9E21FD93-9C72-4C15-8C4B-E77F1DB2D792/0 EE4E5898-3914-4259-9D6E-DC7BD79403CF/1 Volume image section/0 5C60F367-A505-419A-859E-2A4FF6CA6FE5/75 Setup/1 PE32 image section/body.bin"

# Per-section diff:
python3 -c '
import pefile
pe = pefile.PE("setup_p370.bin")
for s in pe.sections: print(s.Name, hex(s.PointerToRawData), hex(s.SizeOfRawData))
'

# Function-level diff via radare2:
r2 -q -A -c "aflj" setup_p370.bin > p370_funcs.json
r2 -q -A -c "aflj" setup_p380.bin > p380_funcs.json
# Compare by addr; the only common-by-addr fn with size change is at r2 addr 0x1cde0.

# Decompile the modified function:
r2 -A -c "pdf @ 0x1cde0" setup_p370.bin
r2 -A -c "pdf @ 0x1cde0" setup_p380.bin
```
