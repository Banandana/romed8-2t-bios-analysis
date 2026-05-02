# Radare2 analysis — `AmdNbioPcieDxe` (P3.70)

Static analysis of the AGESA `AmdNbioPcieDxe` PE32+ binary to find the per-port
gating logic that decides whether a root port attempts ESM (Gen4) speed
training.

**Binary:** `extracted/P3.70/.../37 AmdNbioPcieDxe/1 PE32 image section/body.bin`
**Size:** 72,640 bytes. **Arch:** x86_64 PE32+ EFI Boot Service Driver.
**Image base (in r2):** `0x10000`.

## Tool install

`radare2 6.1.4-1` was already installed from `extra` (`/usr/bin/r2`). No install
needed. Cmd flow:

```
cp body.bin /tmp/nbio.bin
r2 -A /tmp/nbio.bin
# In r2:
iz~ESM         # ESM-related strings
axt @ <addr>   # xrefs
af @ <addr>    # force-define a function
pdf @ <addr>   # disassemble
```

## Function map (top hits, 127 total functions)

The binary is stripped except for embedded `__FILE__`-style logging strings.
Function names below are inferred from the `%a` log strings each function
passes to the logger (`fcn.00016608`).

| Address | Size | Inferred name | Notes |
|---|---|---|---|
| `0x00010cd8` | 182 | (per-port AER+misc init) | Calls into all per-port walkers. |
| `0x00011c84` | 985 | `NbioPcieAerFeatureEnable` | AER setup walker. |
| `0x00012060` | 835 | (per-port misc) | |
| `0x000126ac` | 694 | (per-port speed/cap programming) | |
| `0x00012964` | 406 | (per-port walker) | |
| `0x00013be0` | 1752 | (large per-port routine) | |
| `0x000142f0` | 303 | helper | |
| `0x00014420` | 479 | helper | |
| `0x00014600` | 382 | helper called from ESM-attempt logic | |
| `0x0001481c` | 497 | PCI-config helper used by ESM attempt | |
| **`0x00014a10`** | **2242** | **`PcieAttemptEsmIfEnabled`** | **The ESM gating function — see below.** |
| `0x000153c4` | 1598 | (large) | |
| `0x00016140` | 462 | (PreferIo printer area helper) | |
| `0x00016608` | — | `LogPrint` (DEBUG print) | Used by every function via `lea r8, "<func name>"` + `lea rdx, "<fmt>"`. |
| `0x000177**4c**` | 120 | **`PcieDescriptorWalker`** | **Walks descriptor tree, invokes callback per leaf. Generic dispatcher.** |
| `0x00019f98` | 520 | `PciePreferredIoOrder` | Chooses preferred-IO bus. |
| `0x0001a2a0` | 488 | (per-port routine) | |
| `0x0001ae4c` | 682 | (large) | |
| `0x0001b0f8` | 1307 | (large per-port) | |

The `0x00016608` logger takes `(channel, fmt, fname, ...)` — the inferred names
of every other function come from the `lea r8, "<funcname>"` immediately before
each call to it.

## The ESM gating function — `PcieAttemptEsmIfEnabled` @ 0x14a10

Confirmed by the embedded function-tag string at +0x7B:

```
0x00014a8b      lea rbx, str.PcieAttemptEsmIfEnabled    ; 0x1e5f0
0x00014a92      mov r13d, 0x100000                       ; debug channel
0x00014aa5      call fcn.00016608                        ; "%a Entry\n"
```

It receives the per-port descriptor in `rcx`, immediately stashed into `r14`:

```
0x00014a2e      mov r15, rcx           ; arg1
0x00014a31      mov r14, rcx           ; arg1   ← port descriptor pointer
```

### The gate (the answer)

After printing `Entry`, the function checks two conditions on the descriptor:

```
0x00014aaa      cmp word [r14 + 0xf], 8            ; "is link trained?" (LinkState == 8?)
0x00014ab7      je   0x14b1e                       ; if trained, fall through to ESM check
                                                   ; else: log "Device did not train successfully"

0x00014b1e      test byte [r14 + 0x2e], 0x40       ; *** THE GEN4 GATE ***
0x00014b23      jne  0x14b42                       ; bit 6 set → take ESM path
                                                   ; bit 6 clear → fall into the "no ESM" log

0x00014b25      lea  rdx, "%a Port does not have ESM enabled\n"
0x00014b2c      mov  rcx, r13                       ; debug channel
0x00014b2f      call fcn.00016608                   ; <-- NEGATIVE PATH

0x00014b42      ...  Attempt ESM Sequence: Bus%d Dev%d Func%d ...   ; <-- POSITIVE PATH
```

**English summary.** For each port, AGESA examines the per-port descriptor at
offset +0x2E and tests bit 0x40 (bit 6). If that bit is set, the function
proceeds with the full ESM/Gen4 sequence (read ESM extended capability, set
`PCIE_LC_SPEED_CNTL.LC_GEN4_EN_STRAP=1`, set `ESM_CONTROL` register, poll
`LC_ESM_PLL_INIT_DONE`, attempt speed change to Gen4, fallback to Gen1 on
failure). If the bit is clear, it logs `"Port does not have ESM enabled"` and
returns immediately without touching the link-control hardware.

### Inferred port-descriptor layout (the struct in `r14`)

Every field-offset access of `r14` inside this function:

| Offset | Width | Use | Inference |
|---|---|---|---|
| +0x00 | dword | flag bits, descriptor-type tag — masked against `0x1000000`, `0x2000000` in the head-walker at 0x14a40 | descriptor header / type |
| +0x04 | word | offset to previous descriptor (rev traversal) | linked-list back-pointer |
| +0x0F | word | compared to `8` | link state / training-result code |
| +0x1D | byte | `>> 4 & 7` then used as register-block index in many SMN reads | NBIO instance / wrapper |
| +0x1E | dword | decomposed by `>>20`, `>>15 & 0x1f`, `>>12 & 7` | **PCI BDF (Bus/Dev/Func)** |
| **+0x2E** | **byte** | **`& 0x40` is the ESM-enable gate** | **per-port feature flags; bit 6 = "Attempt ESM"** |
| +0x34 | byte | secondary "vendor-id-cached" flag | runtime cache for AMD vendor in ESM ext-cap |

The struct is reached by walking a tree (next-sibling at +0x08, prev at +0x04;
flag word at +0x00 with `0x800000` = "is leaf port", `0x20000000` = "stop
walk"). This is the canonical AGESA "engine descriptor" / DXIO descriptor
layout.

## Where does the +0x2E byte come from?

**This binary never writes to `[any+0x2e]`.** A full-binary search for byte
write encodings (`mov [reg+disp8], imm8` / `mov [reg+disp8], r8`) targeting
+0x2e turned up zero hits. The descriptor is **read-only** from `AmdNbioPcieDxe`'s
perspective.

Therefore the descriptor blob is constructed **before** this driver runs.
The walker (`fcn.0001774c`) takes the descriptor list head as `arg4` (`r9`) —
the head is supplied by the caller chain (`fcn.00010cd8` → `fcn.00019f98` →
`entry0`), and ultimately fetched from a HOB / EFI-protocol installed by an
earlier PEI/DXE module — the standard AGESA flow has `AmdCpmPcieInitDxe` /
`AmdNbioBaseDxe` parse the **APCB DXIO descriptor group** and publish it on
the `gAmdPcieComplexDataProtocolGuid` (or equivalent) protocol. We are NOT
consuming that producer in this binary.

There is also **no MMIO read of any board-revision strap** anywhere inside
`PcieAttemptEsmIfEnabled` or its callees within this binary — we searched for
loads from `0xfedXXXXX` / `0xfd0XXXXX` and for any movabs of a fixed
high-physical address; none. The string table contains zero "rev", "Board",
or "1.03"-style markers; the only `Strap`-substring strings refer to the
PCIE_LC_SPEED_CNTL strap-bit register (a hardware register name, not a
board-rev strap).

## Verdict

**Possibility (a) — per-port descriptor flag.** The Gen4-enable decision is
data-driven by **bit 6 of byte +0x2E in the per-port DXIO descriptor**. When
that bit is set, ESM/Gen4 is attempted; when clear, the port is silently left
at its baseline (Gen3) speed. The flag is not computed in this binary; it is
delivered to the driver from upstream (APCB → NBIO base driver → protocol
handoff).

**This rules out** (b) board-rev MMIO branch in this driver, (c) global flag
inside this driver, and (d) AGESA-side dead-code disablement. The ESM enable
path is fully alive in `AmdNbioPcieDxe` for P3.70; it just never gets reached
for the GPU root ports because their descriptors arrive at this driver with
bit 6 of +0x2E **clear**.

This is consistent with the machine-side observation that P3.80 unlocks Gen4
on rev-1.03 boards: the change between P3.70 and P3.80 must be either
(i) a different APCB descriptor blob that flips bit 6 of +0x2E for the GPU
slots, or (ii) a board-rev gate added to the **producer** of the descriptor
list — i.e. inside `AmdNbioBaseDxe` / `AmdCpmPcieInitDxe` — not inside
`AmdNbioPcieDxe`.

## Immediate next investigation steps

In priority order:

1. **Diff `AmdNbioPcieDxe` between P3.70 and P3.80** with this same r2
   procedure to confirm the gating instruction is byte-identical. Expected:
   no change (P3.70 and P3.80 have identical hashes for this module per
   `docs/CROSS_VERSION_DIFF.md`). That confirms the unlock is NOT in this
   binary.
2. **Find and disassemble `AmdNbioBaseDxe` (or whichever module produces the
   descriptor protocol)** in P3.70 and P3.80. Look for board-rev MMIO read
   plus a write to byte +0x2E of the descriptor structure with mask 0x40.
   That's the rev-strap branch.
3. **Decode the APCB DXIO descriptor group** in P3.70 vs P3.80 at the known
   APCB offsets (`0x247000`, `0x4cc000`–`0x4d0000+`). If the descriptor blob
   changed for the 8 GPU slots, the unlock is in the data, not the code.
   This is the highest-value diff because an APCB-only patch on P3.70 could
   set bit 6 directly without flashing AGESA code modules.
4. **Cross-reference the +0x2E layout with PPR / open-source AGESA.** The
   AGESA `PCIe_PORT_DESCRIPTOR` / `PCIe_ENGINE_DESCRIPTOR` typedefs in
   open coreboot trees (look under `src/vendorcode/amd/agesa/...`) name the
   bitfields. Bit 6 of byte 0x2E plausibly maps to a `PortFeatures` / 
   `LinkSpeedCap` / `EsmControl` flag — see `docs/PPR_REGISTER_NOTES.md`
   (parallel agent) once available, and an AGESA header dump.

## Reproducibility

```bash
cp "extracted/P3.70/.../37 AmdNbioPcieDxe/1 PE32 image section/body.bin" /tmp/nbio.bin
r2 -A -q -c 'iz~ESM' /tmp/nbio.bin                    # find ESM strings
r2 -A -q -c 'axt @ 0x1e7f0' /tmp/nbio.bin             # xref to LC_GEN4_EN_STRAP=1
r2 -A -q -c 'axt @ 0x1e658' /tmp/nbio.bin             # xref to "Port does not have ESM enabled"
r2 -A -q -c 'af @ 0x14a10; pdf @ 0x14a10' /tmp/nbio.bin
# Look for the gate at 0x14b1e:
#   test byte [r14 + 0x2e], 0x40
#   jne  0x14b42      ; bit set → ESM
#                     ; bit clear → "Port does not have ESM enabled"
```
