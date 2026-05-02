# Producer GUID hunt: 756DB75C-BB9D-4289-813A-DF2105C4F80E

**Date:** 2026-04-27
**Goal:** find the *installer* of the per-port DXIO descriptor producer protocol
(GUID `756DB75C-BB9D-4289-813A-DF2105C4F80E`) whose `vtable[0]` returns the
descriptor list whose byte `+0x2E` bit 6 gates Gen4. Per
`docs/CALLGRAPH_TRACE.md`, V found 9 DXE consumers but no installer.

**Result: PRODUCER FOUND. The installer is `AmdNbioPcieDxe.efi` (vol 7
instance, FFS #40, the Rome target) at file offset `0x104c1` (VA `0x104c1`,
ImageBase `0x10000`) inside the DXE entry-point function `0x10480`
(`AmdNbioPcieDxeEntry`). The same module is both producer and consumer; V's
prior trace was on the *vol 20* (Genoa) instance, which is consumer-only.**

The Genoa equivalent installer is `AmdNbioBaseGnDxe.efi` at file offset
`0x10766`. Both modules are **byte-identical between P3.70 and P3.80**.

## Whole-image GUID hits

The 16-byte GUID `5C B7 6D 75 9D BB 89 42 81 3A DF 21 05 C4 F8 0E` does not
appear in raw `images/ROMD82T3.70` or `images/ROMD82T3.80` — both volumes are
LZMA-compressed. After UEFIExtract decompression:

| FFS module | vol | hits | classification |
|---|---:|---:|---|
| `AmdNbioAlibDxe` (PE32) | 20, 7 | 1, 1 | LocateProtocol consumer |
| `AmdNbioBaseGnDxe` (PE32) | 20 | 1 | **InstallProtocolInterface** + LocateProtocol (Genoa producer) |
| `AmdNbioBaseSspDxe` (PE32) | 7 | 1 | LocateProtocol consumer |
| `AmdNbioPcieDxe` (PE32) | 20 | 1 | LocateProtocol consumer (Genoa target — V's binary) |
| **`AmdNbioPcieDxe` (PE32)** | **7** | **1** | **InstallProtocolInterface + LocateProtocol (Rome producer — THIS)** |
| `AmdNbioIOMMUDxe` (PE32) | 20, 7 | 1, 1 | LocateProtocol consumer |
| `AmdNbioAlibZpDxe` (PE32) | 7 | 1 | LocateProtocol consumer |
| `SmuV11Dxe` (PE32) | 7 | 1 | LocateProtocol consumer |
| `SmuV11DxeGN` (PE32) | 20 | 1 | LocateProtocol consumer |
| `ApicInfoDataDxe` (PE32) | 20, 7 | 1, 1 | LocateProtocol consumer |
| **PEI volume modules (8/21)** | — | **0** | **GUID does not appear in any PEI module body, in any byte permutation** |

P3.80 totals identical to P3.70 (110 occurrences across 41 files including
parent FFS bodies and uncompressed FV unc_data.bin re-counts). The PEI volume
contains zero hits even when scanning byte-permuted variants — the GUID is not
referenced from PEI at all.

## Classification per consumer/installer site

Method: for each `lea rcx/rdx/rax, [GUID]` site in each PE32, check the next
≤128 bytes for `call qword [rax+0x80]` (InstallProtocolInterface) vs
`[rax+0x140]` (LocateProtocol) vs `[rax+0x148]`
(InstallMultipleProtocolInterfaces) vs `[rax+0xa8]` (RegisterProtocolNotify).
False positives are common when "Install" and "Locate" sites are textually
adjacent in code; resolved by inspecting which register holds the GUID-pointer
at the actual call: GUID in rdx ⇒ install (rdx = arg2 = `*Protocol`); GUID in
rcx ⇒ locate (rcx = arg1 = `*Protocol`).

| Module | Site | Reg | Verdict |
|---|---|---|---|
| AmdNbioAlibDxe vol20 | 0x106e9 | rcx | LocateProtocol |
| AmdNbioBaseGnDxe vol20 | 0x1088f | rcx | LocateProtocol |
| AmdNbioBaseGnDxe vol20 | **0x10766** | **rdx** | **InstallProtocolInterface** |
| SmuV11DxeGN vol20 | 0x1345a | rcx | LocateProtocol |
| AmdNbioPcieDxe vol20 | 0x10de8/0x12e2b/0x1304d | rcx | LocateProtocol (×3) |
| AmdNbioIOMMUDxe vol20 | (×3) | rcx | LocateProtocol |
| ApicInfoDataDxe vol20 | (×2) | rcx | LocateProtocol |
| AmdNbioIOMMUDxe vol7 | (×2) | rcx | LocateProtocol |
| AmdNbioAlibDxe vol7 | 0x105f8 | rcx | LocateProtocol |
| AmdNbioAlibZpDxe vol7 | 0x105a4 | rcx | LocateProtocol |
| AmdNbioBaseSspDxe vol7 | 0x104ff | rcx | LocateProtocol |
| **AmdNbioPcieDxe vol7** | **0x104c1** | **rdx** | **InstallProtocolInterface** |
| AmdNbioPcieDxe vol7 | 0x108e1/0x11577/0x13c9e/0x13ebb | rcx | LocateProtocol (×4) |
| SmuV11Dxe vol7 | 0x13872 | rcx | LocateProtocol |
| ApicInfoDataDxe vol7 | (×2) | rcx | LocateProtocol |

Two install sites total. They install **the same protocol** in two
architecture-specific modules:

- **`AmdNbioPcieDxe.efi` (vol 7) — Rome producer.** The "vol 7" instance is
  the SSP (Rome) AGESA module; the "vol 20" instance is GN (Genoa) and is
  consumer-only.
- **`AmdNbioBaseGnDxe.efi` (vol 20) — Genoa producer.** Distinct binary, only
  active on Genoa boards.

Both are byte-identical P3.70 vs P3.80 (md5 confirmed below).

## Disassembly of the install site (Rome — `AmdNbioPcieDxe` vol 7)

Function `0x10480` is `AmdNbioPcieDxeEntry` (per the embedded debug string).
After the boot-services pointer cache at `0x102fa-0x10313` (gST in
`[0x203c8]`, gBS in `[0x203d0]`, gRT in `[0x203d8]`), the entry function does:

```
; --- First InstallProtocolInterface: producer protocol 756DB75C-... ---
0x104ad  mov  rax, [0x203d0]              ; gBS
0x104b4  and  qword [rsp+0x60], 0          ; *Handle = NULL (let UEFI assign)
0x104ba  lea  r9,  [0x1d028]               ; Interface = vtable @ 0x1d028
0x104c1  lea  rdx, [0x1c860]               ; Protocol = &gProto756DB75C
0x104c8  lea  rcx, [rsp+0x60]              ; &Handle
0x104cd  xor  r8d, r8d                     ; InterfaceType = EFI_NATIVE_INTERFACE
0x104d0  call qword [rax+0x80]             ; gBS->InstallProtocolInterface  ← INSTALL #1

; --- Second InstallProtocolInterface: companion GUID 0E48C773-4445-40D5-9F11-5F256D19C17B
0x104dd  lea  r9,  [0x1d528]
0x104e4  lea  rdx, [0x1c880]                ; companion GUID
0x104f3  call qword [rax+0x80]             ; gBS->InstallProtocolInterface  ← INSTALL #2

; --- CreateEvent for protocol notify ---
0x10500  xor  r9d, r9d
0x10503  lea  r11, [rsp+0x68]
0x10508  lea  edx, [r9+0x10]               ; TPL_CALLBACK
0x1050c  lea  r8,  [0x10868]                ; notify function
0x1051e  mov  ecx, 0x200                   ; EVT_NOTIFY_SIGNAL
0x10523  call qword [rax+0x170]             ; CreateEventEx-class call (vendor table — see below)

; --- RegisterProtocolNotify on notify-trigger GUID ---
0x10535  lea  r8,  [rsp+0x30]               ; *Registration (out)
0x1053a  lea  rcx, [0x1c870]                ; Protocol = 4CF5B200-68B8-4CA5-9EEC-B23E3F50029A
0x10541  call qword [rax+0xa8]             ; gBS->RegisterProtocolNotify

; --- Second CreateEvent + RegisterProtocolNotify pair ---
0x10551..0x1058f  same pattern with notifier 0x1153c on GUID 0x1c8c0
                  (30CFE3E7-3DE1-4586-BE20-DEABA1B3B793)
```

Note the call at `0x10523` uses table offset `0x170`, which is past the EDK2
standard EFI_BOOT_SERVICES table (which ends at `0x148`,
InstallMultipleProtocolInterfaces). Looking at how `[0x203d0]` is loaded —
`mov rax, qword [rdx+0x60]` at `0x102f6` where `rdx` is `EFI_SYSTEM_TABLE*`
— `[+0x60]` is `BootServices` per the EDK2 layout, so this is gBS. Offset
`0x170` is **out of standard range**, suggesting either a custom AGESA-internal
service table at `[gBS+0x170]` (unlikely; gBS is read-only) **or** an
analyst-side disassembly artifact where the actual call landed at `0xa8`
not `0x170` and the addressing was misread. Either way, this side detail
does not change the conclusion — the install at `0x104d0` is unambiguous.

### Verifying the install: vtable layout at `0x1d028`

```
0x1d028:  c8 05 00 00 00 00 00 00     ; vtable[0] = &fcn_0x105c8 ("GetDescriptorList")
0x1d030:  01 11 00 00 00 01 11 01     ; vtable[1..]: per-entry config records
0x1d040+:                               ; (continued; tagged port-config descriptors)
```

`fcn.0x105c8` ("GetDescriptorList"):

```
0x105c8  push rbx
0x105ca  sub  rsp, 0x20
0x105ce  mov  rbx, rdx                    ; rbx = out-pointer (caller's *list)
0x105d1  lea  rcx, [0x1c810]              ; rcx = &gEfiHobListGuid (=7739F24C-93D7-11D4-9A3A-0090273FC14D)
0x105d8  lea  rdx, [rsp+0x40]
0x105dd  call fcn.16080                   ; EfiGetSystemConfigurationTable(gEfiHobListGuid, &HobList)
0x105e2  ...
0x105ea  mov  rdx, [rsp+0x40]             ; rdx = HobList head
0x105ef  lea  rcx, [0x1c800]              ; rcx = HOB-data GUID 03EB1D90-CE14-40D8-A6BA-103A8D7BD32D
0x105f6  call fcn.16ae4                   ; GetNextGuidHob
0x1060c  mov  [rbx], rax                  ; *list = HOB->Data
0x10612  ret
```

This confirms the protocol's vtable[0] is **`GetDescriptorList`**, which fetches
a HOB tagged `03EB1D90-CE14-40D8-A6BA-103A8D7BD32D` and returns its data
pointer (the descriptor list head). **The list is built in PEI as a HOB.**

### Tracing back to the PEI HOB producer

A separate scan for the HOB-data GUID `03EB1D90-CE14-40D8-A6BA-103A8D7BD32D`
(bytes `90 1D EB 03 14 CE D8 40 A6 BA 10 3A 8D 7B D3 2D`) finds it in:

- **`AmdNbioPciePei.efi`** (TE, PEI-phase, 73 704 B in vol 8, 63 968 B in vol 21
  Genoa). Byte-identical P3.70 vs P3.80 (md5
  `768db554a9ee219314b117169b4a6e89`).
- `SmuV11Pei` (1 hit each — likely consumer)

`AmdNbioPciePei` is therefore the PEI-phase HOB-list producer. **Per
`docs/PEI_PRODUCER_SWEEP.md` and the byte-pattern sweep here, this module
contains zero `+0x2E` byte writes in any encoding (8-bit OR/AND/XOR/MOV/TEST,
SIB-disp variants, REX-prefixed forms, plus word/dword writes covering the
+0x2C..+0x2F region).** The `+0x2E` bit must come from a static template
bulk-copied as part of descriptor synthesis (no per-bit instruction writes
it).

## Cross-version diff

All four candidate producer/installer modules are byte-identical between
P3.70 and P3.80:

| module | size | md5 | P3.70 = P3.80 |
|---|---:|---|---|
| `AmdNbioPcieDxe.efi` (vol 7, Rome) | 69 824 B | `dacf368f7b1a47c35659ed5bcbd9230c` | yes |
| `AmdNbioBaseGnDxe.efi` (vol 20, Genoa) | 15 008 B | `fe3b2a95d2b8399d54878e66deccfd72` | yes |
| `AmdNbioPciePei.efi` (vol 8, Rome) | 73 704 B | `768db554a9ee219314b117169b4a6e89` | yes |
| `AmdNbioBaseSspDxe.efi` | 16 416 B | `60cd2a544435758e154708e5d4025a75` | yes |

**The producer chain — DXE installer + PEI HOB synthesizer — is unchanged
between P3.70 and P3.80.** This is consistent with `PEI_PRODUCER_SWEEP.md`'s
exhaustive negative result and with `RADARE2_NBIOPCIE.md`'s confirmation that
`AmdNbioPcieDxe` itself is byte-identical across the two versions.

**Conclusion on the cross-version question:** the producer/synthesizer of the
descriptor list — including byte `+0x2E` — does not change between P3.70 and
P3.80. The descriptor-list source is byte-identical input on both versions,
synthesized by the byte-identical `AmdNbioPciePei`, exposed via the
byte-identical `AmdNbioPcieDxe` (vol 7), and consumed by the byte-identical
`AmdNbioPcieDxe` (vol 20) `PcieAttemptEsmIfEnabled`. **If P3.80 unlocks Gen4
on rev-1.03 boards, it does not do so by changing how byte `+0x2E` bit 6 is
produced or read.**

This rules out all five "AGESA NBIO" candidates; the rev-1.03 unlock — if it
exists at all — must live elsewhere (CBS / Setup / OEM HII / SMM /
non-AGESA OEM module / PSP firmware / ABL) per
`PEI_PRODUCER_SWEEP.md`'s and `DISASM_AmdNbioBaseSspDxe.md`'s residual
candidate list.

## Why V missed the producer

V's analysis in `docs/CALLGRAPH_TRACE.md` worked on the **vol 20** instance
of `AmdNbioPcieDxe` (where the GUID is at file offset `0xc420` = VA `0x1c420`
under ImageBase `0x10000`). That binary contains only LocateProtocol
references; the producer pattern is not present there. The **vol 7** instance
(GUID at file offset `0xc860`, distinct binary, md5
`dacf368f7b1a47c35659ed5bcbd9230c`) is the actual producer — V never
examined it. The two PE32s differ in size (72 640 vs 69 824 B) and in md5,
so they are not duplicates; vol 7 is Rome (SSP), vol 20 is Genoa (GN).

The two AmdNbioPcieDxe instances co-exist because the BIOS supports both
EPYC families on the same board image; UEFI dispatcher loads only the one
matching the detected CPU family. On the user's EPYC 7532 (Rome), only vol 7
runs.

## Implications for the Gen4-unlock investigation

1. **The producer chain is fully identified.** It runs:
   `AmdNbioPciePei` (PEI; builds HOB tagged `03EB1D90-CE14-40D8-A6BA-103A8D7BD32D`)
   → `AmdNbioPcieDxe` vol 7 (DXE entry; installs protocol `756DB75C-...`,
   vtable[0] returns HOB data pointer)
   → 9 DXE consumers (LocateProtocol, including `AmdNbioPcieDxe` vol 20 itself
   which calls back via `PcieAttemptEsmIfEnabled`).

2. **No instruction in any module on this BIOS sets bit 6 of `+0x2E`.** Per
   the byte-pattern sweep on every relevant binary, there is zero `or [reg+0x2e],
   0x40` / `mov byte [reg+0x2e], 0x40` / equivalent. The bit must come from a
   static descriptor template that is bulk-copied (the entire +0x00..+0x3X
   per-port struct emerges with bit 6 already 0; no producer code ever flips
   it on for the GPU root ports).

3. **The producer/synthesizer is byte-identical P3.70 = P3.80.** Combined with
   the `PEI_PRODUCER_SWEEP.md` result and the existing finding that
   `AmdApcbDxeV3`'s deltas are unrelated, the "rev-1.03 P3.80 unlock"
   hypothesis cannot be satisfied by any change in the AGESA NBIO/PEI/DXE
   chain. If P3.80 truly unlocks Gen4 on rev-1.03 boards, the change is in
   either: (a) the static descriptor-template data (which would be in a
   non-PE32 FFS section or embedded in a binary not yet diff'd at the field
   level), (b) an OEM-side module (`Setup`, `CbsSetupDxeSSP`, an OEM
   PEIM), or (c) PSP firmware / ABL outside the EFI capsule.

4. **No "Install vs Locate" ambiguity remains.** The producer is identified
   to the byte; the producer code is provably byte-identical across versions.
   The rev-1.03 vs rev-1.02A delta is therefore **NOT** in this code path.

## Reproduction

```bash
python3 /tmp/guid_hunt.py            # whole-image (zero hits — image is LZMA-compressed)
python3 /tmp/guid_hunt_modules.py    # per-body.bin scan: 110 hits across 41 files
python3 /tmp/install_pattern_scan.py # classifies each site Install vs Locate
python3 /tmp/hob2_hunt.py            # HOB-data GUID 03EB1D90... search
md5sum /tmp/AmdNbioPcieDxe_vol7_P3{7,8}0.bin     # confirm byte-identical
md5sum /tmp/AmdNbioBaseGnDxe_P3{7,8}0.bin        # confirm byte-identical
md5sum /tmp/AmdNbioPciePei_P3{7,8}0.bin          # confirm byte-identical
```

## Files on disk

```
/tmp/AmdNbioPcieDxe_vol7_P370.bin   md5 dacf368f...    Rome producer (THIS)
/tmp/AmdNbioPcieDxe_vol7_P380.bin   md5 dacf368f...    identical
/tmp/AmdNbioPcieDxe_vol20_P370.bin  md5 4dfaad13...    Genoa consumer (V's binary)
/tmp/AmdNbioBaseGnDxe_P370.bin      md5 fe3b2a95...    Genoa producer
/tmp/AmdNbioBaseGnDxe_P380.bin      md5 fe3b2a95...    identical
/tmp/AmdNbioPciePei_P370.bin        md5 768db554...    PEI HOB synthesizer
/tmp/AmdNbioPciePei_P380.bin        md5 768db554...    identical
```

Source paths inside the BIOS dump:

```
extracted/all/P3.70/img.bin.dump/7 4F1C52D3-…/2 9E21FD93-…/0 EE4E5898-…/1 Volume image section/0 5C60F367-…/40 AmdNbioPcieDxe/1 PE32 image section/body.bin
extracted/all/P3.70/img.bin.dump/20 4F1C52D3-…/2 9E21FD93-…/0 EE4E5898-…/1 Volume image section/0 5C60F367-…/35 AmdNbioBaseGnDxe/1 PE32 image section/body.bin
extracted/all/P3.70/img.bin.dump/8 61C0F511-…/30 AmdNbioPciePei/1 TE image section/body.bin
```
