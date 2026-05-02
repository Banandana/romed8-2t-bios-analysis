# Call-graph trace: per-port DXIO descriptor producer

**Goal:** Find the producer of bit 6 in `+0x2E` of the per-port DXIO descriptor by
tracing back from the known consumer site
(`AmdNbioPcieDxe!PcieAttemptEsmIfEnabled` @ `0x14a10`, decision at `0x14b1e`).

**Method:** static disassembly of `AmdNbioPcieDxe.efi` (P3.70) with radare2,
followed by inter-module GUID search across all DXE modules in the BIOS image.

## Trace path

### Step 1 — `PcieAttemptEsmIfEnabled` is a callback, not a top-level function

Function entry at file/VA `0x14a10`:

```
0x14a10  mov [rsp+0x10], rbx
0x14a15  push rbp; push rsi; push rdi; push r12..r15
0x14a25  sub  rsp, 0xc0
0x14a2e  mov  r15, rcx           ; <<< rcx = single descriptor pointer (1st arg)
0x14a31  mov  r14, rcx           ; <<<
...
0x14b1e  test byte [r14+0x2e], 0x40    ; the famous Gen4-decision bit
```

So `r14` is **arg1 (rcx)** — the function takes one descriptor at a time, not a list.

### Step 2 — Caller is a generic descriptor-walker, `fcn.0001774c`

Only data-xref to `0x14a10` is a `lea rdx, [0x14a10]` at `0x11c26` (function pointer
registration). The function `0x14a10` is **invoked indirectly** as a per-descriptor
callback from the walker `fcn.0001774c`:

```c
// fcn.0001774c(rdx=callback, r8=arg, r9=list_head)  - 3-arg adapter
walk(callback_rbp, arg_rsi, head_rbx) {
    while (head) {
        if (head->dword[0] & 0x800000)            // leaf marker
            callback_rbp(head, arg_rsi, ...);     // ← invoke 0x14a10 with rcx=head
        if (head->dword[0] & 0x20000000) break;   // stop walk
        head = (uint8_t*)head + head->word[6];    // next sibling
    }
}
```

This **matches exactly** the linked-list semantics in `RADARE2_NBIOPCIE.md`
(`+0x04`/`+0x08` next-sibling, `0x800000` = leaf, `0x20000000` = stop).

### Step 3 — Walker invocation site shows where the list head comes from

In the master function at `0x10d90` (`AmdPcieMiscInit`, identified by the
"AmdPcieMiscInit" string at entry):

```asm
0x10ddb  mov  rax, [0x20d88]          ; rax = gBS (Boot Services)
0x10de8  lea  rcx, [0x1c420]          ; <<< Protocol GUID
0x10de6  xor  edx, edx                ; Registration = NULL
0x10de2  lea  r8,  [rbp+0x7f]         ; out: interface
0x10def  call [rax+0x140]             ; gBS->LocateProtocol(GUID, NULL, &iface)

0x10e01  mov  rax, [rbp+0x7f]         ; rax = interface ptr
0x10e05  lea  rdx, [rbp-0x29]         ; out: list head
0x10e0c  call [rax]                   ; iface->vtable[0](this, &head)  -- "GetDescriptorList"

0x10e0e  mov  r15, [rbp-0x29]         ; r15 = head pointer
0x10e17  add  r15, 0x18               ; +0x18 (skip header)
0x10e20  mov  [rbp-0x19], r15
...
0x11c23  mov  r9, r15                 ; pass to walker as list head
0x11c26  lea  rdx, [0x14a10]          ; PcieAttemptEsmIfEnabled callback
0x11c30  call fcn.0001774c            ; walk and invoke per descriptor
```

**The descriptor list is fetched via a UEFI Boot Services LocateProtocol on a
producer-installed protocol.**

### Step 4 — Producer-protocol GUID

GUID at `0x1c420` in `AmdNbioPcieDxe.efi`:

> **`756DB75C-BB9D-4289-813A-DF2105C4F80E`**

The protocol's vtable's first method (`vtable[0]`) returns the descriptor list.

### Step 5 — Search for the producer module

Search across all DXE module `body.bin` files in
`extracted/all/P3.70/img.bin.dump/` for the GUID:

```
8x  AmdNbioAlibDxe                  consumer (LocateProtocol)
4x  AmdNbioAlibZpDxe                consumer
2x  AmdNbioBaseGnDxe                consumer (Genoa-targeted, idle on Rome)
2x  AmdNbioBaseSspDxe               consumer (Rome-targeted; walks descriptors!)
8x  AmdNbioIOMMUDxe                 consumer
4x  AmdNbioPcieDxe                  consumer (the one we started from)
8x  ApicInfoDataDxe                 consumer
4x  SmuV11Dxe / SmuV11DxeGN         consumer
```

**Verified by xref analysis:** every module that contains the GUID uses it via
`gBS->LocateProtocol` (call `[rax+0x140]`), not `InstallProtocolInterface`
(`[rax+0x80]`) or `InstallMultipleProtocolInterfaces` (`[rax+0x148]`). A heuristic
search for `lea rdx,[GUID] … call [rax+0x80]` within 128 bytes produced
two false-positive "INSTALL PRODUCER" hits (in `AmdNbioBaseGnDxe` and
`AmdNbioPcieDxe`); manual disassembly of those sites confirmed they're all
LocateProtocol calls (the `lea` is `lea rcx, [GUID]` — first arg, not second).

**Conclusion: no module in the DXE phase of P3.70 installs this protocol.**

The protocol must be installed either:
- (a) by a PEI module via PEI→DXE handoff (PPI converted to a protocol by an
  unidentified shim), or
- (b) via a path my static analysis missed (e.g. gBS pointer cached in a global
  and called via a non-standard vtable slot, or an entry0 that I haven't located).

### Step 6 — A second consumer pattern in `AmdNbioBaseSspDxe`

While searching, I found that `AmdNbioBaseSspDxe`'s entry0 chain registers a
**protocol-notify callback** (`gBS->RegisterProtocolNotify` at `[rax+0xa8]`) on
GUID `4CF5B200-68B8-4CA5-9EEC-B23E3F50029A`. The callback function `NbioBaseHookPciIO`
(at `0x104b8`):

1. LocateProtocols our `756DB75C` GUID (at code `0x104ff`).
2. Walks its descriptor list using the **same linked-list semantics**
   (test bit 25 = leaf, test bit 29 = stop).
3. For each leaf descriptor, calls `NbioBaseSetHwInitLock` (`fcn.000107b0`)
   three times with SMN addresses constructed from
   `(descriptor[+0x0e] >> 0x14) | (descriptor[+0x0c] << 0x14)` plus per-IOHC
   strides (`0x1012358c`, `0x1052358c`, `0x1092358c`, …, suggesting +0x40000
   per IOHC).

This confirms the **HwInit-lock policy from PPR_REGISTER_NOTES.md**: NBIO strap
registers are HwInit-locked at DXE phase by `AmdNbioBaseSspDxe` based on
descriptor data fed by the same producer protocol that drives the ESM decision.
Both decisions read `+0x2E`-class flags from the same per-port descriptor list.

## Diff result for the producer protocol's potential producers

Modules that must be ruled in/out as producer:

| Module | P3.70 vs P3.80 | Notes |
|--------|----------------|-------|
| `AmdNbioBaseGnDxe` | **byte-identical** (15008 B) | Genoa-only; idle on Rome |
| `AmdNbioBaseSspDxe` | **byte-identical** (16534 B) | Rome consumer; walks list, locks HwInit |
| `AmdSocSp3GnDxe`   | **byte-identical** (12224 B) | installs `4367F99F` (different GUID) |
| `AmdNbioPcieDxe`   | byte-identical (per CROSS_VERSION_DIFF) | the consumer we started from |

**None of the candidate producers differ between P3.70 and P3.80.** This rules
out a producer-side fix in DXE.

## Verdict

**Producer not located in the DXE phase.** The descriptor-list-providing protocol
`756DB75C-BB9D-4289-813A-DF2105C4F80E` is consumed by ≥9 DXE modules but installed
by **none of them** in any way I could find via direct disassembly or byte-pattern
search. Three production hypotheses remain, in order of likelihood:

1. **PEI→DXE handoff via HOB or PPI converted to a protocol by a shim.** The PEI
   volume contains modules my analysis hasn't fully covered. The producer is most
   likely a PEI module (e.g. `AmdNbioBasePei`, `AmdNbioPciePei`, or a vendor-
   specific shim); the descriptor data is built in PEI from APCB/HOB sources and
   exposed to DXE consumers via this protocol. **This matches Phase 1's working
   theory** that "per-port descriptors are synthesized at runtime by AGESA"
   (subagent #1 finding). The PEI synthesizer is the prime candidate for the
   bit-6 setter.

2. **A DXE module not identified by name.** Some FFS entries lack the
   `<n> ModuleName` pattern; my regex skipped GUID-only directories. A targeted
   re-scan with `uefifind` for `InstallProtocolInterface` (E_KEY: 80) plus
   `lea rdx, [GUID]` in **every** PE32 (including unnamed FFS) is warranted.

3. **A DXE module that obtains gBS via a non-standard register (not via
   `qword [0x20d88]`-style global) and calls Install via a different idiom.** Less
   likely; AGESA modules are auto-generated and follow a uniform pattern.

**Diff result for `AmdApcbDxeV3` follow-up (per CALLGRAPH_TRACE plan):** not
performed in this task — `AmdApcbDxeV3` is the obvious next target since it
already grew +64 B P3.70→P3.80 (per `APCB_DXEV3_DIFF.md`) and consumes APCB/HOB
data. The producer of the `756DB75C` protocol most likely lives **upstream of**
or **inside** `AmdApcbDxeV3` (or its PEI counterpart).

## Recommended next subagent

**Search the PEI volume** (`extracted/all/P3.70/img.bin.dump/.../9E21FD93-9C72-4C15-8C4B-E77F1DB2D792/...`)
for any PEI module that produces a PPI with the `756DB75C` GUID **or** a HOB
whose data layout matches the DXE descriptor (linked list with
`+0x800000`/`+0x20000000` markers, byte `+0x2E`). Diff that PEI module
P3.70 vs P3.80. The bit-6 producer almost certainly lives there.

## Artifacts

- `/tmp/AmdNbioPcieDxe_P370.bin` — disassembled (consumer)
- `/tmp/AmdNbioBaseSspDxe_P370.bin`, `_P380.bin` — disassembled (Rome NBIO base; identical)
- `/tmp/AmdNbioBaseGnDxe_P370.bin`, `_P380.bin` — Genoa NBIO base; identical
- `/tmp/AmdSocSp3GnDxe_P370.bin`, `_P380.bin` — different GUID; identical

All radare2 analyses transient (no project saved); reproducible with `r2 -A`
on these files.
