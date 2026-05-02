# AmdApcbDxeV3 P3.70 vs P3.80 — disassembly diff

**Date:** 2026-04-27
**Goal:** find what changed in the +64-byte-larger `AmdApcbDxeV3.efi` PE32 between BIOS P3.70 and P3.80, and determine whether that change is what enables PCIe Gen4 on rev-1.03 boards.
**Verdict (executive summary):** **(d) something else.** The +64 bytes have **nothing to do with bit 6 of `+0x2E`**. The deltas are two unrelated APCB shadow-copy write-back fixes (entry-checksum recalculation, and chunked 4 KB SPI page writes). `AmdApcbDxeV3` is a generic APCB token storage library; it does **not** synthesize per-port DXIO descriptors and does **not** touch the Gen4-enable bit. Subagent #1's hypothesis pointing the Gen4 unlock at `AmdApcbDxeV3` is **falsified** by this disassembly.

---

## Tool availability

- `radare2 6.1.4-1` — installed and working
- `python3` + `pefile` — installed and working
- both PE32 bodies located and copied to `apcb_work/dxev3_diff/p3{70,80}_apcb_dxev3.bin`

There are **two** `AmdApcbDxeV3` instances per BIOS image (FFS entries 25 and 43 inside the same volume). Entry 25 is **byte-identical** at 48 640 bytes between P3.70 and P3.80. Only entry 43 grew, from 50 848 → 50 912 bytes (+64 B). The analysis below is on entry 43; this is the file referenced in the project brief.

```
P3.70 entry 25: 48640 bytes  (P3.80 entry 25: 48640 bytes — identical)
P3.70 entry 43: 50848 bytes  (P3.80 entry 43: 50912 bytes — +64 B)
```

PE section sizes (entry 43):

| section   | P3.70 vsize / rawsize | P3.80 vsize / rawsize | delta             |
|-----------|-----------------------|-----------------------|-------------------|
| `.text`   | `0x8783 / 0x87a0`     | `0x8813 / 0x8820`     | **+0x90 / +0x80** |
| `.data`   | `0x3130 / 0x3140`     | `0x30f0 / 0x3100`     | -0x40 / -0x40     |
| `.dG2_PEI`| `0x0032 / 0x0040`     | `0x0032 / 0x0040`     | 0                 |
| (unnamed) | `0x063c / 0x0640`     | `0x063c / 0x0640`     | 0                 |
| `.xdata`  | `0x0348 / 0x0360`     | `0x0350 / 0x0360`     | **+0x8** virt     |
| `.reloc`  | `0x0100 / 0x0100`     | `0x0100 / 0x0100`     | 0                 |

`.text` grew by 144 B virtual (+128 B raw). `.data` shrank by 64 B. `.xdata` (Win64 unwind info) grew by 8 B virtual — exactly one new RUNTIME_FUNCTION entry's worth (or one extra unwind opcode), implying **one** newly-introduced or restructured function.

---

## Function map deltas (entry 43)

Auto-analyzed function counts are equal: 119 functions in each binary. After accounting for the constant address shift caused by `.text` growth, two functions are **structurally** modified:

| function (P3.70 addr) | P3.70 (bb / bytes) | function (P3.80 addr) | P3.80 (bb / bytes) | structural change       |
|-----------------------|--------------------|------------------------|--------------------|-------------------------|
| `fcn.00012b9c`        | 27 / 481           | `fcn.00012b9c`         | 29 / 514           | **+2 bb / +33 B** (same address) |
| `fcn.00018440`        | 12 / 173           | `fcn.00018460`         | 9 / 146            | -3 bb / -27 B           |
| `fcn.000184f0`        | 11 / 288           | `fcn.000184f4`         | 21 / 413           | **+10 bb / +125 B**     |

All other 116 functions differ only by the constant relocation offset (+0x20 in `.text`).

String-table diff confirms the same:
- removed: `"AmdPspFlashAccLibDxe locate gPspFlashAccSmmCommReadyProtocol fail \n"`
- renamed: `"PspWriteFlash [%x] %x %x %x \n"` → `"PspWriteFlashDxe [%x] %x %x %x \n"`

No new strings related to **Gen4, ESM, DXIO, descriptor, engine, port, strap, board rev**. (The full string table contains *no* such strings in either version. This module never speaks PCIe.)

---

## What changed — function 1: `fcn.00012b9c` (`AmdPspWriteBackApcbShadowCopy`)

Identified by debug-print prologue: `"[APCB Lib V3] AmdPspWriteBackApcbShadowCopy Enter\n"`.

This function walks an array of 0x38-byte APCB-entry descriptors at `[rdi]`, comparing each in-memory shadow-copy entry against the SPI flash copy, and writing back any entry that differs.

### What P3.80 added

**A new ~33-byte block** that recomputes the entry checksum *after* incrementing the instance counter and *before* writing back to SPI. P3.70's code path simply `inc dword [rdi + 0xc]` (instance counter), `dec byte [rdi + 0x10]` (checksum byte), then writes — relying on the dec to keep the byte sum unchanged. P3.80 zeros the checksum byte, sums every byte of the entry, two's-complements the sum, and stores it back:

```asm
; P3.80, fcn.00012b9c, 0x12cd6 — only present in P3.80
0x12cd6  mov  eax, [rbx + 0x08]    ; eax = entry size in bytes
0x12cd9  inc  dword [rbx + 0x0c]   ; ++instance_id
0x12cdc  xor  dl, dl                ; running sum = 0
0x12cde  mov  byte [rbx + 0x10], 0  ; clear checksum field
0x12ce2  mov  rcx, rbx              ; cursor = entry base
0x12ce5  test eax, eax
0x12ce7  je   0x12cf3
0x12ce9  add  dl, byte [rcx]        ; sum byte
0x12ceb  inc  rcx
0x12cee  add  eax, -1
0x12cf1  jne  0x12ce9
0x12cf3  not  dl
0x12cf5  mov  rcx, r12               ; (later: HOB pointer for log)
0x12cf8  inc  dl                     ; two's complement = ~sum + 1
0x12cfa  mov  byte [rbx + 0x10], dl ; store recomputed checksum
```

P3.70 instead just did:
```asm
0x12cd3  inc  dword [rdi + 0xc]
0x12cd6  dec  byte  [rdi + 0x10]
```

**Interpretation:** in P3.70, only the instance counter changed before write, and the checksum was kept consistent by simply decrementing it (counter +1, checksum −1 → byte sum unchanged). In P3.80, *more than just the instance counter is mutated* before write-back, so the checksum is no longer recoverable by a single dec — it has to be recomputed in full. The new code does that.

This is consistent with the parent function (`fcn.00013df4` → `fcn.00013e14`, the caller of `0x12b9c`) doing extra mutations to the entry payload before triggering the SPI write-back. We did not pursue what those mutations are; they are outside this report's scope and could be APCB token edits to anything (memory training, tokens, voltage tables, etc.).

### What it is NOT

- Not an OR/test/BTS on `byte [reg + 0x2e]` with `0x40`.
- Not anywhere near the per-port DXIO descriptor pipeline.
- Not gated by an MMIO read, GPIO sample, or board-rev compare.
- Not gated by an APCB-token getter.

The new block is unconditionally executed on the same code path that already wrote back differing entries in P3.70. No predicate change.

---

## What changed — function 2: `fcn.000184f0` → `fcn.000184f4` (`PspWriteFlash` → `PspWriteFlashDxe`)

`PspWriteFlash` (P3.70) walks one buffer of arbitrary size and submits a single SMM PSP-Flash-write request. `PspWriteFlashDxe` (P3.80) **chunks the write into 0x1000-byte (4 KB) blocks** and loops:

```asm
; P3.80 fcn.000184f4, the new chunked-write loop
0x185b1  mov  ecx, 0x1000             ; chunk size = 4 KB
0x185b6  mov  rbp, qword [rsi]        ; remaining bytes
0x185b9  lea  rax, [r12 + r15]        ; src cursor
0x185bd  lea  rdi, [r12 + r14]        ; dst cursor
0x185c1  sub  rbp, r12                ; bytes left = total − offset
0x185c4  mov  qword [rbx + 0x20], rax
0x185c8  cmp  rbp, rcx
0x185cb  cmova rbp, rcx               ; clamp to 0x1000
0x185cf  mov  qword [rbx + 0x28], rbp
...
0x18654  mov  ecx, 0x1000
0x18659  cmp  r12, qword [rsi]
0x1865c  jb   0x185b6                 ; loop until all bytes written
```

Plus a CopyMem-style block (`fcn.00018940`, the new ~+0x18 B helper) and a `fcn.00018a20` zero-fill before each chunk.

### Sibling `fcn.00018440` → `fcn.00018460` (`AmdPspFlashAccLibDxe` init)

P3.70 located **two** SMM protocols (`gPspFlashAccSmmCommReadyProtocol` *and* `SmmCommunicationProtocol`). P3.80 only locates `SmmCommunicationProtocol`. The "ready" protocol lookup and its associated debug-string ("AmdPspFlashAccLibDxe locate gPspFlashAccSmmCommReadyProtocol fail") were removed. This is a code-cleanup / API-modernization change, not a behavioral gate.

### What it is NOT

Same as function 1: not a `+0x2E`/bit-6 manipulation, not gated by board rev, not a new APCB-token consumer. It changes *how* APCB updates are committed to SPI flash, not *what* gets committed.

---

## Searched: explicit bit-6 manipulation patterns

Across both binaries, full byte-pattern scans for every plausible encoding of "set bit 6 of `[reg + 0x2e]`":

| pattern                                                | encoding                                  | P3.70 hits | P3.80 hits |
|--------------------------------------------------------|-------------------------------------------|-----------:|-----------:|
| `or  byte [reg + 0x2e], 0x40` (no SIB, 8-bit disp)     | `80 4? 2e 40`                             |          0 |          0 |
| `or  byte [reg + 0x2e], 0x40` (32-bit disp)            | `80 8? 2e 00 00 00 40`                    |          0 |          0 |
| `or  byte [reg + SIB + 0x2e], 0x40`                    | `80 4c ?? 2e 40`                          |          0 |          0 |
| `test byte [reg + 0x2e], 0x40` (no SIB)                | `f6 4? 2e 40`                             |          0 |          0 |
| `test byte [reg + 0x2e], 0x40` (32-bit disp)           | `f6 8? 2e 00 00 00 40`                    |          0 |          0 |
| `and byte [reg + 0x2e], 0xbf` (clear bit 6)            | `80 6? 2e bf`                             |          0 |          0 |

**Result: zero hits in either P3.70 or P3.80 for any direct manipulation of bit 6 at offset `+0x2E`.** This module cannot be the producer that subagent #5 was looking for.

(Caveat: a producer could load via register, OR a register-immediate, and store back — pattern would not match. But combined with the absence of any DXIO/Engine/Port/Gen4/ESM strings, and the overwhelmingly debug-log-rich nature of this module — every other major code path has trace prints — it is implausible that a stealth bit-6 manipulation lives here.)

---

## Verdict

The +64-byte growth in `AmdApcbDxeV3.efi` between P3.70 and P3.80 is composed of **two changes, both inside the APCB shadow-copy SPI write-back path:**

1. **Entry-checksum recomputation** added in `AmdPspWriteBackApcbShadowCopy` (≈ +33 bytes). Required because the caller now mutates more than just the instance counter before write-back.
2. **Chunked 4 KB-page SPI write loop** in `PspWriteFlash` (renamed `PspWriteFlashDxe`, net ≈ +98 bytes) plus `AmdPspFlashAccLibDxe` init cleanup (-27 bytes).

Net `.text` change: +128 B raw, offset by `.data` shrink (-64 B) → +64 B file size.

**Neither change touches PCIe, DXIO, ESM, or bit 6 / offset `+0x2E` of any descriptor.** `AmdApcbDxeV3` does not own the Gen4-enable bit and never has. Its job is APCB-token storage and committing modified tokens back to SPI.

This **falsifies** subagent #1's redirect ("descriptors are runtime-synthesized by `AmdApcbDxeV3`"). The DXE that synthesizes per-port DXIO descriptors is somewhere else — most likely `AmdCpmOemInitDxe`, `AmdPlatformRasSspDxe`, an ASRock `Rs1AcpiDxe`/`OemSetup*` shim, or an AGESA module like `Rome*Dxe`/`AmdNbioBaseSmm`. The producer for bit 6 of `+0x2E` is not in this binary.

**Mapping to the brief's options:**

- **(a) Unconditional bit-set in P3.80 — RULED OUT.** No bit-set instruction exists in this DXE in either version.
- **(b) Board-rev-conditional — RULED OUT for this DXE.** No board-rev MMIO/GPIO/strap read in the +64 B.
- **(c) APCB-token-conditional — RULED OUT for this DXE.** No new APCB-token getter call. The .data section shrank, no new token IDs.
- **(d) Something else — CONFIRMED.** The +64 B is APCB shadow-copy plumbing, unrelated to PCIe.

---

## Implication for flashing P3.80 on a rev-1.03 board

**Inconclusive from this analysis alone.** The information value of this disassembly turned out to be: it tells us where the Gen4 unlock **is not**. It says nothing about where it **is**, or whether flashing P3.80 would lift the cap on rev-1.03.

That said, the disassembly does establish one useful upper-bound observation. **`AmdApcbDxeV3` is byte-functionally equivalent for any APCB token consumer that doesn't trigger a write-back of the shadow copy.** I.e. if the rev-1.03 unlock were a new APCB token whose presence/value flips bit 6 elsewhere, that token would be parsed and served by this DXE (via its token-getter functions, which also live in this binary at `fcn.00013ae8` etc., relocated but unchanged). The unchanged token-getter code means **the APCB binary blob plus this DXE produces the same per-token answers in P3.70 and P3.80**. So either:

- the Gen4 unlock is in a *different* DXE that consumes existing APCB tokens differently in P3.80, **or**
- the Gen4 unlock is independent of APCB entirely (build-time #ifdef, board-rev MMIO/strap, or hard-coded engine-table differences in the producer DXE).

For the user's rev-1.03 board, this means the board-rev-conditional hypothesis (b) is *not* supported by P3.80's `AmdApcbDxeV3` — but it's still the most likely explanation, just relocated to whichever DXE actually builds the per-port DXIO engine list.

---

## What's still unknown / next steps

1. **Where bit 6 of `+0x2E` actually gets set.** Candidate DXEs to disassemble next, ordered by likelihood:
   - **`AmdNbioBaseDxe` / `AmdNbioPcieDxe`** (already analyzed in subagent #5 — but only the *consumer* side at offset `0x14b1e`; reverse the producer path that fills the descriptor before that test).
   - **`AmdCpmOemInitDxe` / ASRock `Rs1*Dxe`** — OEM platform-init shim, likely where ASRock encodes board-specific PCIe topology and per-slot rate caps.
   - **`AmdPciePort*` / `RomePciePort*` / `Family19PciePort*`** if present in the FFS.
   - The PEI-phase counterpart (`AmdNbioBasePei`, `AmdCpmOemInitPei`) — DXIO engine tables are sometimes built at PEI and consumed at DXE.

2. **Cross-version size-diff scan** of the FFS: which other DXEs/PEIMs grew between P3.70 and P3.80? `CROSS_VERSION_DIFF.md` exists but was inflated by ASCII false-positives per the BIOS_LATEST.md note. A clean comparison of FFS GUIDs by raw PE32 size would surface the right module quickly.

3. **`fcn.00013df4` → `fcn.00013e14` (caller of `AmdPspWriteBackApcbShadowCopy`)** — what extra mutation did P3.80 add such that the entry checksum needs full recomputation? It might be a new APCB-token edit performed at runtime that ASRock added in P3.80. Worth a single-function diff to see whether the new mutation targets something Gen4-relevant. (Lower priority — likely just memory training token edits, but cheap to check.)

4. **The two PSP-Flash-write changes (chunking + protocol cleanup) suggest** P3.80 may write back larger volumes of APCB data per boot than P3.70 did, which is consistent with new runtime APCB edits being introduced *somewhere* in the P3.80 boot path. That "somewhere" is what needs to be found.

---

## Files

- `apcb_work/dxev3_diff/p370_apcb_dxev3.bin` — P3.70 entry-43 PE32 body
- `apcb_work/dxev3_diff/p380_apcb_dxev3.bin` — P3.80 entry-43 PE32 body
- `apcb_work/dxev3_diff/p3{70,80}_afl.txt` — radare2 function listings
- `apcb_work/dxev3_diff/p3{70,80}_12b9c.txt` — disassembly of the modified `AmdPspWriteBackApcbShadowCopy`
- `apcb_work/dxev3_diff/p370_18440.txt` / `p370_184f0.txt` / `p380_18460.txt` / `p380_184f4.txt` — disassembly of the rewritten `PspWriteFlash{,Dxe}` and `AmdPspFlashAccLibDxe` init pair
