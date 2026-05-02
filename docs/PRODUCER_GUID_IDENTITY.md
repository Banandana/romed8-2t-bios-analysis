# Producer-protocol GUID identification

## Headline

**`756DB75C-BB9D-4289-813A-DF2105C4F80E` = `gAmdNbioPcieServicesProtocolGuid`.**

This is AMD's official AGESA / NBIO PCIe topology service protocol. The vtable
contains exactly one method, `PcieGetTopology`, at slot 0 — which matches the
BIOS disassembly in `docs/CALLGRAPH_TRACE.md` (`call [rax]` → vtable[0] →
returns descriptor list head).

## Authoritative citation

Repository: **`tianocore/edk2-platforms`** (current `master`).

| Item | Path | Line |
|------|------|------|
| GUID definition | `Platform/AMD/AgesaModulePkg/AgesaModuleNbioPkg.dec` | 19 |
| Protocol header | `Platform/AMD/AgesaModulePkg/Include/Protocol/AmdNbioPcieServicesProtocol.h` | 1–47 |
| HOB definition  | `Platform/AMD/AgesaModulePkg/Include/Guid/GnbPcieInfoHob.h` | 12–28 |
| Descriptor types | `Platform/AMD/AgesaModulePkg/Include/GnbDxio.h` | 264–367 |
| Reference consumer | `Platform/AMD/TurinBoard/Library/DxePlatformSocLib/DxePlatformSocLib.c` | 295–301 |
| Reference consumer | `Platform/AMD/GenoaBoard/Library/DxePlatformSocLib/DxePlatformSocLib.c` | (same idiom) |

GUID line as written:
```
gAmdNbioPcieServicesProtocolGuid = {0x756db75c, 0xbb9d, 0x4289,
   {0x81, 0x3a, 0xdf, 0x21, 0x5, 0xc4, 0xf8, 0xe}}
```

Note: byte-encoded little-endian as `5C B7 6D 75 9D BB 89 42 81 3A DF 21 05 C4 F8 0E`,
exactly matching the GUID at file offset `0x1c420` in `AmdNbioPcieDxe.efi`.

## Documented protocol signature

```c
typedef struct _DXE_AMD_NBIO_PCIE_SERVICES_PROTOCOL DXE_AMD_NBIO_PCIE_SERVICES_PROTOCOL;

typedef EFI_STATUS (EFIAPI *AMD_NBIO_PCIE_GET_TOPOLOGY_STRUCT)(
  IN  DXE_AMD_NBIO_PCIE_SERVICES_PROTOCOL *This,
  OUT UINT32                              **DebugOptions   // see note below
);

struct _DXE_AMD_NBIO_PCIE_SERVICES_PROTOCOL {
  AMD_NBIO_PCIE_GET_TOPOLOGY_STRUCT PcieGetTopology;   // vtable[0]
};
```

**Important:** the `OUT UINT32**` second-argument type in the AMD header is a
documentation simplification. Per the reference consumer in
`DxePlatformSocLib.c` (Turin/Genoa), the value actually written is a pointer
to a `GNB_PCIE_INFORMATION_DATA_HOB` (cast site at line 301):

```c
PcieServicesProtocol->PcieGetTopology(
    PcieServicesProtocol,
    (UINT32 **)&PciePlatformConfigHobData);   // GNB_PCIE_INFORMATION_DATA_HOB *
Pcie = &(PciePlatformConfigHobData->PciePlatformConfigHob);   // PCIE_PLATFORM_CONFIG
```

The HOB embeds a `PCIE_PLATFORM_CONFIG` structure (per
`GnbPcieInfoHob.h`) which roots a tree of `PCIE_DESCRIPTOR_HEADER`-prefixed
descriptors:

```c
typedef struct {
  UINT32 DescriptorFlags;   // +0x00 — bit 23 (0x00800000) and bit 29 (0x20000000)
                            // are the linked-list semantics observed in the BIOS
  UINT16 Parent;            // +0x04
  UINT16 Peer;              // +0x06
  UINT16 Child;             // +0x08
} PCIE_DESCRIPTOR_HEADER;
```

The bit-flags `0x00800000` (leaf) and `0x20000000` (stop walk) match
`docs/CALLGRAPH_TRACE.md` Step 3 perfectly.

## What the +0x2E bit-6 field is (Genoa/Turin reference)

Per `GnbDxio.h` line 364, in **modern** AGESA (Genoa/Turin) the `PCIE_PORT_CONFIG`
runtime descriptor includes an explicit:

```c
UINT8 EsmControl : 1;      ///< Bit to enable/disable ESM
```

ESM = Extended Speed Mode = Gen4/Gen5 enable. The Rome (SSP) descriptor
layout in P3.70 has the same semantic field at byte `+0x2E`, bit 6 — confirmed
by subagent #5's disassembly of `PcieAttemptEsmIfEnabled`. The header file we
have is for Genoa/Turin but the AMD AGESA NBIO subsystem reuses this descriptor
shape across families with offset variations; the protocol GUID has been
**stable from Naples through Turin**.

Adjacent fields in `PCIE_PORT_CONFIG` of relevance (Genoa layout, similar in Rome):
- `TargetLinkSpeed : 3` — Target Link Speed (1=Gen1 … 5=Gen5)
- `SetGen4FixedPreset : 1`, `Gen4FixedPreset : 4`
- `EsmSpeedBump`, `EsmUsTxPreset : 4`, `EsmDsTxPreset : 4`
- `CcixControl : 1` (the comment "Bit to enable/disable ESM" on line 302 is
  copy-paste error in the upstream header; semantically it's CCIX, not ESM)

## Known consumers (cross-referenced with this BIOS)

From `docs/CALLGRAPH_TRACE.md` step 5, all of these `LocateProtocol` the GUID:

| BIOS module | Role |
|-------------|------|
| `AmdNbioPcieDxe`     | reads bit 6 / +0x2E to gate `PcieAttemptEsmIfEnabled` |
| `AmdNbioBaseSspDxe`  | walks descriptors → `NbioBaseSetHwInitLock` on SMN straps |
| `AmdNbioBaseGnDxe`   | Genoa equivalent (idle on Rome) |
| `AmdNbioAlibDxe`     | builds ACPI _DSM PCIe data (ALIB) |
| `AmdNbioAlibZpDxe`   | Zeppelin-family ALIB variant |
| `AmdNbioIOMMUDxe`    | IOMMU init from topology |
| `ApicInfoDataDxe`    | builds APIC routing |
| `SmuV11Dxe`/`SmuV11DxeGN` | SMU V11 PCIe service |

Reference upstream consumer (publicly documented):
- `Platform/AMD/{Turin,Genoa}Board/Library/DxePlatformSocLib/DxePlatformSocLib.c`
  uses it for IOAPIC enumeration (walks the GnbHandle tree).

## Producer — what the upstream code reveals

**The GUID dec file does not list a producer in `edk2-platforms`.** The producer
of this protocol is closed-source AGESA binary code that AMD ships pre-built
to OEMs as part of the AGESA module release. `edk2-platforms` only contains
the public-facing protocol definitions and consumers; the AGESA NBIO PEI/DXE
binaries that *install* this protocol are not in the open tree.

That said, the conventional naming pattern within AGESA NBIO modules is:
- `AmdNbioPciePei` / `AmdNbioPcieDxe` — public family
- `AmdNbio<arch>Pei` / `AmdNbio<arch>Dxe` — per-family variant
   - SSP = Stoney/Rome (Family 17h Models 30h–3Fh)
   - GN  = Genoa (Family 19h Models 10h–1Fh)
   - ZP  = Zeppelin (Naples) — see `AmdNbioAlibZpDxe`

The AGESA NBIO design pattern is for a **PEI module to construct the
`GNB_PCIE_INFORMATION_DATA_HOB`** during platform init (consuming APCB tokens +
DXIO descriptor inputs), then a **DXE module to install
`gAmdNbioPcieServicesProtocolGuid`** with a `PcieGetTopology` implementation
that simply returns the HOB pointer.

For Rome, given module naming on this BIOS:
- The HOB is **almost certainly built in PEI** by `AmdNbioPciePei` (or its
  Rome/SSP-specific shim).
- The DXE protocol installer is most likely a small auto-generated
  service-stub module that we have not yet identified — possibly fused into
  the entry stub of `AmdNbioBaseSspDxe`, or a separate
  `AmdNbioPcieServicesDxe` / `AmdCpmPcieServicesDxe`-style FFS.

## Cross-reference with this project's prior findings

1. **`docs/CALLGRAPH_TRACE.md`** — the protocol named here matches the
   "producer-protocol GUID" investigated. The vtable's single method
   `PcieGetTopology` is exactly the `call [rax]` (vtable[0]) seen in the
   disassembly.
2. **Subagent #1 (`docs/APCB_DECODE.md`)** — confirmed the per-port
   descriptors are NOT in APCB. The header file confirms why: descriptors
   are in a runtime HOB built in PEI from APCB tokens, not in any APCB group.
3. **Subagent #5 (`docs/RADARE2_NBIOPCIE.md`)** — bit 6 of `+0x2E` matches
   the documented `EsmControl : 1` field semantically. The Rome-era
   descriptor layout is offset-shifted from the Genoa layout but conceptually
   identical.
4. **Subagent #1b (`docs/APCB_DXEV3_DIFF.md` and `docs/PEI_PRODUCER_SWEEP.md`)** —
   those investigations on `AmdApcbDxeV3` and PEI-volume sweeps are looking
   for the right thing: the **PEI HOB-builder** for the topology HOB. Per
   the upstream pattern, the producer is in PEI, not DXE.

## Implications for the next-step plan

1. **The `+64 B` growth in `AmdApcbDxeV3` P3.70 → P3.80** (per
   `docs/APCB_DXEV3_DIFF.md`) is consistent with a code addition that
   modifies `EsmControl` bits during HOB construction — `AmdApcbDxeV3` is
   plausibly the consumer of APCB tokens that contributes data to the
   `GNB_PCIE_INFORMATION_DATA_HOB` builder.
2. **Highest-leverage targets to disassemble next:**
   - The PEI HOB-builder (likely `AmdNbioPciePei` or `AmdCpmPciePei` —
     check for `BuildGuidHob` with `gGnbPcieHobInfoGuid` =
     `0x03EB1D90-CE14-40D8-A6BA-103A8D7BD32D`).
   - The DXE protocol-installer (search any DXE FFS for
     `InstallProtocolInterface` with `gAmdNbioPcieServicesProtocolGuid`).
3. **Both `gGnbPcieHobInfoGuid` (0x03EB1D90-CE14-40D8-A6BA-103A8D7BD32D) and
   `gAmdNbioPcieServicesProtocolGuid` (0x756DB75C-BB9D-4289-813A-DF2105C4F80E)
   should be searched as byte patterns** across the entire P3.70 + P3.80
   image (PEI + DXE) — the HOB GUID hits will localize the producer.

## Appendix — useful adjacent GUIDs from `AgesaModuleNbioPkg.dec` and friends

From `Platform/AMD/AgesaModulePkg/`:

| GUID | Name | Purpose |
|------|------|---------|
| `756DB75C-BB9D-4289-813A-DF2105C4F80E` | `gAmdNbioPcieServicesProtocolGuid` | **this protocol** — DXE PCIe topology service |
| `03EB1D90-CE14-40D8-A6BA-103A8D7BD32D` | `gGnbPcieHobInfoGuid` | the HOB GUID returned via `PcieGetTopology` |

The HOB GUID is the **primary pivot** for finding the PEI producer: any
`BuildGuidHob` call with this GUID is the topology-HOB builder, and any
modification of the HOB after construction (e.g. setting `EsmControl` bits) is
the bit-6 setter we're hunting for.
