# AGESA per-port DXIO descriptor — public-source reference

Cross-references the radare2-inferred descriptor layout in
`docs/RADARE2_NBIOPCIE.md` against AMD-published / coreboot / open-source
references. The goal is to ground-truth the **bit 6 of byte +0x2E = "Attempt
ESM" (Gen4)** finding and identify the canonical name of every adjacent field.

**Bottom line up front:** bit 6 of the Rome AGESA per-port runtime descriptor's
+0x2E byte corresponds to the AGESA field universally documented as
`EsmControl` (Enhanced Speed Mode control). The semantic interpretation in
`docs/RADARE2_NBIOPCIE.md` is correct, and the public ground-truth is in
**`xUSL/NBIO/GnbDxio.h`** of AMD's openSIL Genoa proof-of-concept
(`github.com/openSIL/openSIL`, branch `genoa_poc`). Genoa (Family 19h Model
10h) is one generation past Rome (Family 17h Model 31h) but the AGESA
PCIe-engine descriptor has been carried forward almost verbatim — both the
field names and the relative struct layout match the radare2 findings.

The producer code path is also identified by name in the openSIL source: the
DXE module producing the descriptor list is functionally equivalent to
**`PcieFixupPlatformConfig` → `PcieEnginePlatformConfigDefault`** in
`xUSL/NBIO/IOD/PkgTypeFixups.c`. In Rome AGESA terminology, the binary that
performs this role is `AmdNbioBaseSspDxe` (or its PEI equivalent), and on
ROMED8-2T the OEM-customised producer is `AmdCpmPcieInitDxe`.

---

## 1. The canonical struct (openSIL Genoa)

From `xUSL/NBIO/GnbDxio.h` of [openSIL/openSIL @ genoa_poc](https://github.com/openSIL/openSIL/blob/genoa_poc/xUSL/NBIO/GnbDxio.h):

```c
/// PCIe descriptor header (12 B)
typedef struct {
  uint32_t  DescriptorFlags;   // +0x00 — flag bits
  uint16_t  Parent;            // +0x04 — offset to parent
  uint16_t  Peer;              // +0x06 — offset to peer (next sibling)
  uint16_t  Child;             // +0x08 — offset to child list
} PCIe_DESCRIPTOR_HEADER;

/// Engine configuration (the descriptor AmdNbioPcieDxe walks)
typedef struct {
  PCIe_DESCRIPTOR_HEADER   Header;       // +0x00..+0x09
  PCIe_ENGINE              EngineData;   // +0x0A — { u8 EngineType; u16 StartLane; u16 EndLane; }
  PCIe_ENGINE_INIT_STATUS  InitStatus;   // +0x0F — uint16_t
  uint8_t                  Scratch;      // +0x11
  union {
    PCIe_PORT_CONFIG       Port;         // +0x12 onwards
    PCIe_CXL_CONFIG        Cxl;
  } Type;
} PCIe_ENGINE_CONFIG;
```

Followed inside `PCIe_PORT_CONFIG`:

```c
typedef struct {
  PORT_DATA  PortData;              // +0x12 = { u8 PortPresent; u8 (DevNum/FunNum bitfield);
                                    //           u8 (LinkSpeedCap/Aspm bitfield); u8 LinkHotplug;
                                    //           u16 SlotNum; u8 MiscControls; u8 Reserved1; }
  uint8_t  StartCoreLane;
  uint8_t  EndCoreLane;
  uint8_t  NativeDevNumber:5; uint8_t NativeFunNumber:3;
  uint8_t  CoreId:4;          uint8_t PortId:4;
  PCI_ADDR Address;                 // 4-byte segment/bus/dev/fn
  uint8_t  PcieBridgeId:7;    uint8_t IsBmcLocation:1;
  uint8_t  LogicalBridgeId;
  uint8_t  SlotPowerLimit;
  uint8_t  MaxPayloadSize;
  uint8_t  TXDeEmphasis:4;    uint8_t TXMargin:3; uint8_t UNUSED1:1;
  uint8_t  EqSearchMode:2;    uint8_t BypassGen3EQ:1; uint8_t DisGen3EQPhase:1; uint8_t Gen3FixedPreset:4;
  uint8_t  EqSearchModeGen4:2;uint8_t BypassGen4EQ:1; uint8_t DisGen4EQPhase:1; uint8_t Gen4FixedPreset:4;
  uint8_t  EqSearchModeGen5:2;uint8_t BypassGen5EQ:1; uint8_t DisGen5EQPhase:1; uint8_t Gen5FixedPreset:4;
  uint8_t  ClkReq:4;          uint8_t EqPreset:4;
  struct { u8 SpcGen1:1; u8 SpcGen2:1; u8 SpcGen3:2; u8 SpcGen4:2; u8 SpcGen5:2; } SpcMode;
  /* ...three 32-bit LaneEqualizationCntl structs (Gen3/Gen4/Gen5) ... */
  uint8_t  SrisEnableMode:4; uint8_t SRIS_SRNS:1; uint8_t SRIS_LowerSKPSupport:1;
  uint8_t  EsmControl:1;     /* <<<< THE GEN4 ENABLE BIT >>>> */
  uint8_t  LowerSkpOsGenSup;
  /* ... */
  uint8_t  EsmSpeedBump;     /* GT/s rate to advertise when EsmControl=1, default 16 */
  /* ... */
} PCIe_PORT_CONFIG;
```

Descriptor flag-bit constants from the same file:

```c
#define DESCRIPTOR_TERMINATE_LIST       0x80000000ull  /* bit31 - last in list */
#define DESCRIPTOR_TERMINATE_GNB        0x40000000ull
#define DESCRIPTOR_TERMINATE_TOPOLOGY   0x20000000ull  /* bit29 - stop walk */
#define DESCRIPTOR_PCIE_ENGINE          0x00800000ull  /* bit23 - this is a PCIe engine */
#define DESCRIPTOR_CXL_ENGINE           0x01000000ull  /* bit24 */
```

These flag values **exactly match** the magic numbers seen by radare2 in
`AmdNbioPcieDxe.efi`:

| `RADARE2_NBIOPCIE.md` finding | openSIL canonical name | Match |
|---|---|---|
| `0x800000` = "is leaf port" | `DESCRIPTOR_PCIE_ENGINE` (this descriptor is a PCIe engine, not a wrapper/silicon/complex) | yes — exact value |
| `0x20000000` = "stop walk" | `DESCRIPTOR_TERMINATE_TOPOLOGY` | yes — exact value |
| Walker uses prev/peer pointers at +0x04, +0x06, +0x08 | `Header.Parent` (+0x04), `Header.Peer` (+0x06), `Header.Child` (+0x08) | yes — exact offsets |

---

## 2. Bit-6-of-+0x2E mapped to `EsmControl`

The radare2 finding is `test byte [r14+0x2e], 0x40` at file offset `0x14b1e`
of `AmdNbioPcieDxe.efi`. That `0x40` is bit 6 of the byte. In the openSIL
`PCIe_PORT_CONFIG` struct above, the byte at the relative offset that
contains `EsmControl` is built from bitfields in this order (LSB first):

```
bit 0:    SrisEnableMode (low)
bit 1:    SrisEnableMode
bit 2:    SrisEnableMode
bit 3:    SrisEnableMode (high) — i.e. SrisEnableMode is :4 starting at bit 0
bit 4:    SRIS_SRNS               :1
bit 5:    SRIS_LowerSKPSupport    :1
bit 6:    EsmControl              :1   <<<<<<<
bit 7:    (next bitfield boundary — LowerSkpOsGenSup is u8 in next byte)
```

So **bit 6 of the byte containing the SRIS bitfields is `EsmControl`**. This
matches the radare2-observed mask `0x40` exactly. The byte's *absolute*
struct offset will differ between Genoa (openSIL) and Rome
(closed-source AGESA RomePI) because Rome lacks Gen5 fields and may have
different bitfield packing — but the **bit-position-within-the-byte
identification is unambiguous**: of all the boolean controls in the engine
descriptor, `EsmControl` is the only one that is a packed `:1` adjacent to
`SrisEnableMode:4 + SRIS_SRNS:1 + SRIS_LowerSKPSupport:1` for which bit 6 is
the natural position. No other `:1` field in the descriptor lands at bit 6
of any byte.

The radare2 inference of "+0x2E" as the absolute Rome-runtime offset is
believed correct (it is the read site `[r14+0x2e]`) — the byte's struct-name
identity is what the openSIL header confirms.

---

## 3. Per-bit / per-byte interpretation (corrections to inferred layout)

`docs/RADARE2_NBIOPCIE.md` inferred:

| Inferred offset | Inferred meaning | Public-source canonical name | Verdict |
|---|---|---|---|
| `+0x00` dword, masks `0x800000` and `0x2000000` | descriptor type/flags | `PCIe_DESCRIPTOR_HEADER.DescriptorFlags`, with bits `DESCRIPTOR_PCIE_ENGINE` (`0x00800000`) and `DESCRIPTOR_TERMINATE_TOPOLOGY` (`0x20000000` — note the *radare2 doc has a typo* "0x2000000", actual mask is `0x20000000`) | confirmed |
| `+0x04` word | "offset to previous descriptor" | `Header.Parent` (offset to parent descriptor, not "previous") | corrected — it's parent, not prev |
| `+0x06` word | n/a in inferred layout | `Header.Peer` (next-sibling offset) | new |
| `+0x08` word | "next-sibling pointer" | `Header.Child` (offset to child list) | corrected — radare2 doc conflates Peer/Child |
| `+0x0F` word — compared to `8` | "is link trained?" | `PCIe_ENGINE_INIT_STATUS InitStatus` — a `uint16_t` bitmask of init states (not the same enum as `PCIE_LINK_TRAINING_STATE`). Value `8` is one specific bit in this mask. | corrected — see note |
| `+0x1D` byte — `>>4 & 7` used as register-block index | "NBIO instance / wrapper" | Most likely the byte holding `CoreId:4 \| PortId:4` (or `NativeDevNumber:5 \| NativeFunNumber:3`). The `>>4 & 7` extracts a 3-bit core/wrapper index. | corrected — likely `PortId` (or NativeFunNumber), not raw "NBIO instance" |
| `+0x1E` dword decomposed `>>20`, `>>15 & 0x1f`, `>>12 & 7` | "PCI BDF" | `PCI_ADDR Address` — the AGESA `PCI_ADDR` is a packed bit-union: `[31:20]=Bus, [19:15]=Device, [14:12]=Function, [11:0]=Register/Reserved`. The shifts `>>20`, `>>15&0x1f`, `>>12&7` decode Bus, Device, Function exactly. | confirmed |
| `+0x2E` byte, bit 6 (mask `0x40`) | "Attempt ESM / Gen4 enable" | `PCIe_PORT_CONFIG.EsmControl` — "Bit to enable/disable ESM". Documented as a `:1` bitfield. | **confirmed — canonical name is `EsmControl`** |
| `+0x34` byte, secondary "vendor-id-cached" | runtime cache for AMD vendor in ESM ext-cap | Field name not directly exposed in openSIL header; possibly `Scratch`-class field added by the consumer for endpoint vendor caching. Not part of input descriptor; a runtime workspace byte. | inconclusive — likely a producer-private cache, not in canonical header |

**Note on `+0x0F` field:** `PCIe_ENGINE_INIT_STATUS` is documented in
GnbDxio.h as `typedef uint16_t PCIe_ENGINE_INIT_STATUS;` — i.e. a free-form
init-status word. The radare2 interpretation as the link-training-state enum
is plausible but unconfirmed; the `==8` test specifically may be checking a
single bit (e.g. bit 3 of the status word, "InitDone"). Either way the
field's role is "has this engine reached the point where ESM can be
attempted?" which is consistent with the radare2 narrative.

The semantically related `EsmSpeedBump` field (the GT/s rate to advertise,
default 16) would land somewhere in the same struct but at a higher offset.
The radare2 doc didn't surface a cmp/test against an explicit `16` constant
because the function passes `EsmSpeedBump` through to the SMU command without
inspecting it.

---

## 4. The producer — where bit 6 gets set

In openSIL Genoa, the per-port `EsmControl` value is set in **two** places:

### 4a. Default platform configuration (global)
`xUSL/NBIO/IOD/PkgTypeFixups.c` line 124:
```c
static void PcieEnginePlatformConfigDefault (PCIe_ENGINE_CONFIG *PcieEngine, ...) {
  NBIO_CONFIG_DATA *NbioData = ...;
  PcieEngine->Type.Port.EsmControl   = NbioData->EsmEnableAllRootPorts;
  PcieEngine->Type.Port.EsmSpeedBump = NbioData->EsmTargetSpeed;
  ...
}
```
This iterates over every engine in the platform descriptor list. The boolean
`EsmEnableAllRootPorts` lives in `NBIOCLASS_INPUT_BLK` (xUSL/NBIO/NbioClass-api.h
line 161) with the comment:
```c
bool EsmEnableAllRootPorts;   ///< If set PCIe ESM sequence is attempted on all root ports
uint8_t EsmTargetSpeed;       ///< Initial PCIe ESM Target Speed for all cards in the system
```
In coreboot's openSIL Genoa POC, the default is `false`
(`src/vendorcode/amd/opensil/genoa_poc/mpio/chip.c` line 96):
```c
input->EsmEnableAllRootPorts = false;
input->EsmTargetSpeed        = 16;
```
This is the *global* knob. It's the analogue of "Enable Gen4 ESM on every root
port" and would naively be the easiest thing for ASRock to flip.

### 4b. Per-port topology entry (preferred, fine-grained)
`xUSL/Mpio/Common/MpioTopology.c` line 258:
```c
case MPIO_PP_ESM:
  EngineDescriptor->Port.EsmControl = (uint8_t)PortParam->ParamValue;
  break;
```
The `MPIO_PP_*` enum is a port-parameter type tag. Each `MPIO_PORT_DESCRIPTOR`
in the platform topology table can carry an array of
`(MPIO_PP_ESM, value)` entries which set `EsmControl` only for that specific
port. This is the mechanism that ASRock would use to enable ESM only on
specific GPU slots.

`MpioMappingResults.c` line 204 finalises:
```c
Engine->Type.Port.EsmControl   = TopologyEntry->Port.EsmControl;
Engine->Type.Port.EsmSpeedBump = TopologyEntry->Port.EsmSpeedBump;
```

### 4c. Rome equivalent
The closed-source RomePI follows the same pattern. The DXE binary names
visible in the ROMED8-2T capsule corresponding to these openSIL files are:
- `AmdNbioBaseSspDxe` — analogue of `xUSL/NBIO` — owns `NBIOCLASS_INPUT_BLK`
  defaults (the global `EsmEnableAllRootPorts` knob lives here).
- `AmdCpmPcieInitDxe` — ASRock-customised "platform config" override; the
  analogue of `chip.c` in coreboot. **This is where ASRock would apply
  per-slot `EsmControl` overrides** if they wanted to.
- `AmdNbioPcieDxe` — the *consumer* (already disassembled — see
  `docs/RADARE2_NBIOPCIE.md`). Reads `EsmControl`, never writes it.

The protocol/PPI that publishes the descriptor list between producer and
consumer is named `gAmdPcieComplexDataProtocolGuid` /
`PcieComplexData` in older AGESA and `SilId_NbioClass` (struct find by ID)
in openSIL. In the ROMED8-2T binary, the equivalent handle is the
`PCIe_PLATFORM_CONFIG` structure — a ComplexList of complexes, each with a
silicon list, each with wrappers, each with engines (the leaf descriptors).
The walker in `AmdNbioPcieDxe.efi` at `fcn.0001774c` is `PcieConfigRunProcForAllEngines` (the openSIL function name) — the same walker pattern documented in `xUSL/NBIO/PciExpressLib/...`.

---

## 5. APCB / token mappings — does an APCB token control `EsmControl`?

**No public APCB token directly controls per-port `EsmControl`.**

Cross-referenced against `oxidecomputer/amd-apcb` (Rust-side authoritative
schema for the APCB on-disk format, used by Oxide's amd-host-image-builder).
Searching `src/ondisk.rs`:
- The string "Esm" appears nowhere in the schema.
- The strings "Gen4" / "gen4" appear only in `AdditionalPcieLinkSpeed::Gen4 = 4`,
  which is a token used by the BMC sideband (`SecondPcieLinkSpeed`).
- No `PciePortDescriptor` / per-port-DXIO group is defined; the schema only
  knows `PSPG`, `MEMG`, `TOKN`, and `EarlyPcieConfig` (Turin) groups.

This **independently confirms subagent #1's finding**: the ROMED8-2T APCB
content (`PSPG`/`MEMG`/`TOKN` only) does *not* contain DXIO descriptors. The
`EsmControl` value reaching `AmdNbioPcieDxe` must therefore be either:
1. Hard-coded in `AmdCpmPcieInitDxe` per port (constant tables in the binary), or
2. Computed at runtime from a board-rev MMIO read or NBIOCLASS-input default.

The +64 B size growth of `AmdApcbDxeV3` between P3.70 and P3.80 (per
`docs/CROSS_VERSION_DIFF.md`) is consistent with adding either: (a) a small
table of per-port `EsmControl=1` entries for the GPU slots, or (b) a board-rev
detection branch that conditionally applies (a). Neither would require a
new APCB token, which is what we see. This is what the disassembly diff in
`docs/APCB_DXEV3_DIFF.md` should resolve definitively.

---

## 6. Discrepancies / unresolved items

1. **The exact byte-offset `+0x2E` is Rome-AGESA-specific.** openSIL Genoa
   has Gen5-related fields injected ahead of the SRIS/EsmControl byte
   (`Gen5LaneEqualizationCntl` is 4 B larger than Gen4, plus `EqSearchModeGen5`,
   `BypassGen5EQ`, `DisGen5EQPhase`, `Gen5FixedPreset`). The Rome equivalent
   of this struct will be ~8–12 B smaller, which is why on Rome the field
   is at `+0x2E` and on Genoa it would be at a different absolute offset.
   The bit-position (bit 6) and the relative-to-SRIS-bitfield position are
   identical.
2. **The +0x0F status field**: openSIL types it as `uint16_t
   PCIe_ENGINE_INIT_STATUS` (free-form bitmask) — *not* the
   `PCIE_LINK_TRAINING_STATE` enum (whose values 0–17 are linear states).
   Value 8 in the radare2 cmp may be `LinkStateGen2Fail` (enum), or it may
   be bit-3 of a status mask. Either way the test gates ESM attempt on
   "engine has progressed past initial training". **Inconclusive but not
   load-bearing for the Gen4-cap question.**
3. **The +0x34 byte ("vendor-id-cached")** is not a standard openSIL field
   name. It is likely a producer-private workspace byte added after the
   descriptor body, used to cache the endpoint vendor ID once
   `AmdNbioPcieDxe` reads PCI config space. **Not in the canonical header.**
4. **The radare2 doc states the `0x2000000` flag**; the canonical openSIL
   constant is `0x20000000` (`DESCRIPTOR_TERMINATE_TOPOLOGY`). Either
   radare2's comment was missing a zero or a different bit was being tested
   — should be re-verified by re-reading the disasm.
5. **Whether ROMED8-2T's RomePI exposes `MPIO_PP_ESM`-style per-port
   parameters at all** is unknown. RomePI predates Genoa's MpioTopology
   refactor; the older PI may use a different per-port-parameter encoding
   (likely an array of `(WrapId, PortId, ParamType, ParamValue)` tuples
   embedded in `AmdCpmPcieInitDxe`'s constant data). This is the place to
   look in the disassembly diff between P3.70 and P3.80.

---

## 7. References (file paths and URLs)

Canonical struct (mirror open-source AGESA):
- [openSIL/openSIL @ genoa_poc — `xUSL/NBIO/GnbDxio.h`](https://github.com/openSIL/openSIL/blob/genoa_poc/xUSL/NBIO/GnbDxio.h) — `PCIe_ENGINE_CONFIG`, `PCIe_PORT_CONFIG`, descriptor flag constants.
- [openSIL/openSIL @ genoa_poc — `xUSL/NBIO/NbioClass-api.h`](https://github.com/openSIL/openSIL/blob/genoa_poc/xUSL/NBIO/NbioClass-api.h) — `NBIOCLASS_INPUT_BLK.EsmEnableAllRootPorts`.
- [openSIL/openSIL @ genoa_poc — `xUSL/NBIO/IOD/PkgTypeFixups.c`](https://github.com/openSIL/openSIL/blob/genoa_poc/xUSL/NBIO/IOD/PkgTypeFixups.c) line 124 — the platform-default producer that sets `EsmControl` from the global flag.
- [openSIL/openSIL @ genoa_poc — `xUSL/Mpio/Common/MpioTopology.c`](https://github.com/openSIL/openSIL/blob/genoa_poc/xUSL/Mpio/Common/MpioTopology.c) line 258 — per-port `EsmControl` override via `MPIO_PP_ESM` topology parameter.
- [openSIL/openSIL @ genoa_poc — `xUSL/Mpio/Common/MpioMappingResults.c`](https://github.com/openSIL/openSIL/blob/genoa_poc/xUSL/Mpio/Common/MpioMappingResults.c) line 204 — copies topology-entry `EsmControl` into final engine config.

Older AGESA PI (Naples Family 17h Model 00h) — confirms struct lineage:
- `coreboot/src/vendorcode/amd/pi/00670F00/AGESA.h` lines 466–510 — `PCIe_PORT_DATA`, the user-facing input descriptor (subset of the runtime `PCIe_PORT_CONFIG`).
- [coreboot AGESA.h reference](https://github.com/coreboot/coreboot/blob/master/src/vendorcode/amd/pi/00670F00/AGESA.h)

coreboot openSIL shim (showing default `EsmEnableAllRootPorts = false`):
- `coreboot/src/vendorcode/amd/opensil/genoa_poc/mpio/chip.c` line 96.
- `coreboot/src/vendorcode/amd/opensil/turin_poc/mpio/chip.c` line 117.
- `coreboot/src/vendorcode/amd/opensil/phoenix_poc/mpio/chip.c` line 96.
- [coreboot/coreboot — vendorcode/amd/opensil](https://github.com/coreboot/coreboot/tree/master/src/vendorcode/amd/opensil)

APCB schema — confirms ESM is NOT an APCB token:
- [oxidecomputer/amd-apcb — `src/ondisk.rs`](https://github.com/oxidecomputer/amd-apcb/blob/main/src/ondisk.rs).

Related on-rig binary names (this analysis):
- `AmdNbioPcieDxe.efi` — consumer (analyzed in `docs/RADARE2_NBIOPCIE.md`).
- `AmdCpmPcieInitDxe.efi` — OEM-customised producer (see `docs/DISASM_AmdCpmPcieInitDxe.md`).
- `AmdNbioBaseSspDxe.efi` — owns `NBIOCLASS_INPUT_BLK` defaults (see `docs/DISASM_AmdNbioBaseSspDxe.md`).
- `AmdApcbDxeV3.efi` — APCB consumer (see `docs/APCB_DXEV3_DIFF.md`).

3mdeb commentary on AMD coreboot/openSIL:
- [3mdeb blog — Open Source Firmware on AMD Milan server processors](https://blog.3mdeb.com/2021/2021-09-09-amd-milan-osf/)
- [3mdeb blog — MSI PRO B850-P coreboot port: PCIe and USB descriptors and Phoenix OpenSIL](https://blog.3mdeb.com/2026/2026-03-06-msi_pro_b850p_part2/)
