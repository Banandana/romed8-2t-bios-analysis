# `AmdCpmPcieInitDxe` disassembly diff: P3.70 vs P3.80

**Investigation date:** 2026-04-27
**Question:** Is `AmdCpmPcieInitDxe` the producer of bit 6 of byte `+0x2E` in the per-port DXIO descriptor that `AmdNbioPcieDxe` consumes (the Gen4-enable gate)?

## Executive verdict

**NO. Eliminated.** `AmdCpmPcieInitDxe` is a tiny CPM tag-dispatcher shim (~1.1 KB of `.text`), byte-identical between P3.70 and P3.80 in both FFS instances (60 and 68). It contains:

- No `+0x2E` reads or writes of any kind.
- No bit-6 set/test/clear instructions anywhere.
- No DXIO/Gen4/ESM/Engine/Port/Strap-related strings.
- Only a 6-way tag dispatch (`M129/M130/M222/M223/M224/M225`) returning struct fields, plus a single 64-byte AllocatePool.

This module is structurally too small to be the descriptor producer. Both byte-identical instances rule out a P3.70-vs-P3.80 board-rev gating change inside this DXE.

## Tool / file availability

- `radare2` 6.1.4-1 — used for disassembly.
- `python3` + `pefile` — used for PE section sizing.
- Working directory: `/tmp/cpmdxe/` (binaries copied from `extracted/all/{P3.70,P3.80}/img.bin.dump/.../{20,7}/.../{60,68} AmdCpmPcieInitDxe/1 PE32 image section/body.bin`).

## Files on disk

| Logical name | Location |
|---|---|
| P3.70 instance 60 | `extracted/all/P3.70/img.bin.dump/20 .../60 AmdCpmPcieInitDxe/1 PE32 image section/body.bin` |
| P3.70 instance 68 | `extracted/all/P3.70/img.bin.dump/7 .../68 AmdCpmPcieInitDxe/1 PE32 image section/body.bin` |
| P3.80 instance 60 | `extracted/all/P3.80/img.bin.dump/20 .../60 AmdCpmPcieInitDxe/1 PE32 image section/body.bin` |
| P3.80 instance 68 | `extracted/all/P3.80/img.bin.dump/7 .../68 AmdCpmPcieInitDxe/1 PE32 image section/body.bin` |

The two FFS instances per BIOS are sub-volume vs main-volume duplicates with different content (different sizes), but the per-instance content is unchanged across versions.

## Byte-identity check (cross-version)

```
SHA-256:
370060f8...  p370_60.efi   (2112 B)
370060f8...  p380_60.efi   (2112 B)   ← byte-identical to P3.70
862e624d...  p370_68.efi   (2080 B)
862e624d...  p380_68.efi   (2080 B)   ← byte-identical to P3.70
```

`cmp p370_60.efi p380_60.efi` → no output (identical).
`cmp p370_68.efi p380_68.efi` → no output (identical).

**Like `AmdNbioBaseSspDxe`, this DXE was unchanged across the rev-1.03 / Gen4 unlock boundary.** Whatever changed in P3.80 was not here.

## PE section sizes

### Instance 60 (both versions)
| Section | VirtualSize | RawSize | Entropy |
|---|---|---|---|
| `.text` | 0x473 (1139 B) | 0x480 | 6.00 |
| `.data` | 0x110 (272 B) | 0x120 | 1.98 |
| (unnamed) | 0x18 | 0x20 | 0.00 |
| `.xdata` | 0x1c | 0x20 | 0.00 |

### Instance 68 (both versions)
| Section | VirtualSize | RawSize | Entropy |
|---|---|---|---|
| `.text` | 0x49d (1181 B) | 0x4a0 | — |
| `.data` | 0x70 (112 B) | 0x80 | — |
| (unnamed) | 0x18 | 0x20 | — |
| `.xdata` | 0x18 | 0x20 | — |
| `.reloc` | 0x8 | 0x20 | — |

These are tiny modules. Compare to `AmdNbioPcieDxe` (~120 KB), `AmdApcbDxeV3` (~150 KB). Far too small to contain DXIO descriptor synthesis logic.

## Bit-6 / `+0x2E` byte-pattern search

Searched both binaries (all 4 files) for the full APCB_DXEV3_DIFF pattern set:

| Pattern | Mnemonic | Hits |
|---|---|---|
| `80 4? 2e 40` | `or byte [reg+0x2e], 0x40` (8-bit disp) | **0** |
| `80 8? 2e 00 00 00 40` | `or byte [reg+0x2e], 0x40` (32-bit disp) | **0** |
| `80 4c ?? 2e 40` | `or byte [reg+rsi+0x2e], 0x40` (SIB) | **0** |
| `f6 4? 2e 40` | `test byte [reg+0x2e], 0x40` | **0** |
| `0f ba 6? 2e 06` | `bts byte [reg+0x2e], 6` | **0** |
| `0f ba 7? 2e 06` | `btr byte [reg+0x2e], 6` | **0** |
| `80 6? 2e bf` | `and byte [reg+0x2e], 0xbf` (clear bit 6) | **0** |
| `[88|8a] 4? 2e` | `mov ?l, [reg+0x2e]` / `mov [reg+0x2e], ?l` | **0** |

**Zero hits across all 4 binaries.** No bit-6 manipulation, no `+0x2E` reads, no `+0x2E` writes.

The only `0x40` immediate that appears is `mov ecx, 0x40` (decimal 64) at the AllocatePool call site — i.e. allocate 64 bytes for an internal context. Not a bit-set operation.

## Strings inventory

Complete string set (from `iz`):

```
.text                       ; PE section name
.data
.xdata
.reloc                      ; only in instance 68
M130                        ; CPM tag
M222                        ; CPM tag
M223                        ; CPM tag
M224                        ; CPM tag
M225                        ; CPM tag
M129                        ; CPM tag
$A22                        ; CPM lookup key
$A25                        ; CPM lookup key
$A20                        ; CPM lookup key
$A26                        ; CPM lookup key
```

**No DXIO, ESM, Gen4, Engine, Port, Strap, Rev, 1.02, 1.03, Board, Descriptor, Synth, BMC strings.** Nothing that would even hint at PCIe descriptor construction.

## Function map / behaviour

Despite radare2's `aa` reporting 226 functions, that is an artifact of misalignment — the actual `.text` section is `0x260 - 0x6d3` (≈ 1.1 KB) and contains essentially three logical regions:

### `entry0` @ `0x2c0` (78 bytes)

Standard UEFI DXE entry. Stores ImageHandle / SystemTable, then calls `BootServices->AllocatePool(EfiBootServicesData, 0x200, &ptr)` (entry `+0x170`). Stub init.

### Tag dispatcher @ `0x310`

```asm
cmp dword [rdx], 'M130'   ; 0x4d313330
je  0x1035d               ; → mov eax, [r8+0x04]
cmp dword [rdx], 'M222'
je  0x10357               ; → mov eax, [r8+0x20]
cmp dword [rdx], 'M223'
je  0x10351               ; → mov eax, [r8+0x24]
cmp dword [rdx], 'M224'
je  0x1034b               ; → mov eax, [r8+0x28]
cmp dword [rdx], 'M225'
je  0x10345               ; → mov eax, [r8+0x2c]
cmp dword [rdx], 'M129'
jne 0x10367               ; → return 0
mov eax, [r8+0x00]
...
mov dword [rdx], eax       ; store result
xor al, al
ret
```

This is a **CPM table-field getter** — given a 4-character tag, return the corresponding offset in a CPM struct pointed to by `r8`. The offsets touched are `+0x00, +0x04, +0x20, +0x24, +0x28, +0x2C`. **Notably absent: `+0x2E`.**

### CPM-protocol-using region @ `0x36c`

```asm
mov rax, [SystemTable]
lea r8,  [some_buffer]
xor edx, edx
lea rcx, [some_GUID]
call qword [rax + 0x140]   ; BootServices->LocateProtocol
...
mov rax, [protocol_ptr]
mov ecx, 0x40              ; 64 bytes  ← NOT bit-6, just AllocatePool size
call qword [rax + 0x1d8]   ; CpmProtocol method (allocate context?)
...
mov edx, '$A22'            ; CPM lookup key
call [rax + 0x2e0]         ; CpmProtocol->LookupTable / similar
mov edx, '$A25'
call [r8  + 0x2e0]
mov edx, '$A20'
call [r8  + 0x2e0]
mov edx, '$A26'
call [r8  + 0x2e0]
...
```

This is the canonical CPM-protocol consumer pattern: locate protocol, allocate scratch, look up four `$Axx` table entries, do something with the results. The `$Axx` keys are AGESA Customer Portal Module data-table identifiers. **Zero reference to `+0x2E` or bit 6.**

(`call [rax+0x2e0]` is a vtable call at offset 736 — the `0x2e` here is part of a 32-bit displacement to a function pointer, not a memory access at `+0x2E` of a per-port descriptor. The byte pattern `ff 90 e0 02 00 00` is a CALL through a function-pointer table, completely unrelated to descriptor manipulation.)

## Verdict mapping (per APCB_DXEV3_DIFF taxonomy)

- **(a) "ASRock simply did not flip bit 6 in P3.70, code exists":** **No** — no bit-6 code exists in this module at all.
- **(b) "Conditional gated on board-rev MMIO read":** **No** — no MMIO reads; no rev/strap strings; binaries are byte-identical across versions.
- **(c) "Hard-coded build-time decision":** **No** — module does not synthesize descriptors.
- **(d) "Module is unrelated to descriptor production":** **YES.** This module dispatches CPM tags and consults CPM tables. It is downstream of (or sibling to) any descriptor producer, not the producer itself.

## Implication

`AmdCpmPcieInitDxe` is **eliminated** as a producer candidate. Combined with the eliminations of:

- `AmdNbioPcieDxe` — read-only consumer of the bit (subagent #5)
- `AmdApcbDxeV3` — no `+0x2E` writes; +64 B was elsewhere (`docs/APCB_DXEV3_DIFF.md`)
- `AmdNbioBaseSspDxe` — byte-identical, no `+0x2E` accesses (`docs/DISASM_AmdNbioBaseSspDxe.md`)
- `AmdCpmPcieInitPeim` — see `docs/DISASM_AmdCpmPcieInitPeim.md` (concurrent agent D)

…the per-port descriptor producer that writes bit 6 of `+0x2E` is **not in any of the obvious DXE/PEI candidates examined so far**.

## Top follow-up candidates (not the producer; what next)

1. **AGESA core SSP DXIO/PCIe modules.** The descriptor synthesis is most likely in the closed AGESA core itself — typical names to grep extracted/all/{P3.70,P3.80} for: `AmdCpmDxioInit`, `AmdSspPcieDxe`, `AmdSspDxioInitDxe`, `DxioInitPostPei`, `DxioPcieInit`, `AmdSspNbioPcieIpInit`, anything with `Dxio` or `PortInit` in the name. Also check the larger generic-name modules whose function we have not yet identified.
2. **PEI-phase early descriptor build.** Per-port DXIO descriptors are typically constructed in PEI before DXE handoff. The PEIM sweep (subagent in progress) should be cross-referenced — anything with substantial `.text` and PCIe/DXIO strings is a candidate. `AmdCpmOemInitPeim` and `AmdInitPostPei` deserve specific inspection if not already done.
3. **`AmdCpmOverrideParametersDxe` / `AmdCpmOverrideParametersPeim`.** The CPM "override" modules are explicitly designed for OEM board-specific edits to AGESA parameters. If ASRock injects per-slot DXIO bit changes, this is exactly where they'd put them. Worth a r2 + bit-6 sweep.
4. **OEM blob scan.** Run a binary-wide search across both whole BIOS images for the literal byte patterns `80 4? 2e 40` / `f6 4? 2e 40` / `0f ba 6? 2e 06` to locate any module that touches `+0x2E`-bit-6 anywhere. If zero hits exist anywhere in P3.70 but appear in P3.80, the diff localises the producer immediately. (Subagent C / sweep-style methodology.)

## Reproduction

```bash
mkdir -p /tmp/cpmdxe
cp "extracted/all/P3.70/.../60 AmdCpmPcieInitDxe/1 PE32 image section/body.bin" /tmp/cpmdxe/p370_60.efi
cp "extracted/all/P3.70/.../68 AmdCpmPcieInitDxe/1 PE32 image section/body.bin" /tmp/cpmdxe/p370_68.efi
cp "extracted/all/P3.80/.../60 AmdCpmPcieInitDxe/1 PE32 image section/body.bin" /tmp/cpmdxe/p380_60.efi
cp "extracted/all/P3.80/.../68 AmdCpmPcieInitDxe/1 PE32 image section/body.bin" /tmp/cpmdxe/p380_68.efi

sha256sum /tmp/cpmdxe/*.efi
cmp /tmp/cpmdxe/p370_60.efi /tmp/cpmdxe/p380_60.efi
cmp /tmp/cpmdxe/p370_68.efi /tmp/cpmdxe/p380_68.efi

r2 -q -c "s entry0; pd 250" /tmp/cpmdxe/p370_60.efi
```
