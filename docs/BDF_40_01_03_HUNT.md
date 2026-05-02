# Hunt for static DXIO descriptor with BDF `40:01.3` in P3.70

**Date:** 2026-04-27
**Goal:** Locate any static per-port DXIO descriptor table in the BIOS image with an entry for BDF `40:01.3` whose `+0x2E` byte has bit 6 (`0x40`) set. `40:01.3` is the only Gen4-advertising root port on the rig (`LnkCap2: 2.5–16GT/s`); its descriptor must have the ESM/Gen4 flag while the GPU-slot descriptors do not.

**Method:** three-pronged.

1. Whole-image (32 MiB) byte scan for BDF byte permutations.
2. PE32 `.data`/`.rdata` scan in every PE32 module body (and broader `.text` sweep for completeness).
3. Heuristic detection of arrays of structures matching the inferred descriptor layout (`docs/RADARE2_NBIOPCIE.md`).

---

## Prong 1 — whole-image hits

Scanned `images/ROMD82T3.70` (33 554 432 bytes) for six BDF byte permutations.

| Pattern | Label | Hits |
|---|---|---:|
| `40 01 03` | BDF-LE bytes | 4 |
| `03 01 40` | BDF-BE bytes | 1 |
| `40 01 03 00` | BDF-dword LE | 0 |
| `03 01 40 00` | BDF-dword BE | 0 |
| `0B 00 40 00` | encoded BDF (`bus<<16 \| dev<<3 \| fn`) LE | 0 |
| `00 40 00 0B` | encoded BDF BE | 0 |

**Total: 5 hits.**

| File offset | Pattern | Byte at +0x10 | Bit 6 set? | Container (UEFITool tree) |
|---|---|---|---|---|
| `0x00e2b88f` | BDF-LE | `0x4e` | **True** | not in any FFS — between FV `0xdb0028` and FV `0x1037028` (PSP/ABL/padding band) |
| `0x0107c01e` | BDF-LE | `0x07` | False | inside `11 Padding` (Subtype Non-empty — BMC/Aspeed firmware band) |
| `0x011d471e` | BDF-LE | `0x07` | False | inside `11 Padding` (BMC firmware band) — duplicate of 0x0107c01e |
| `0x012c3f64` | BDF-LE | `0x20` | False | inside `11 Padding` (BMC firmware band) |
| `0x0084ab20` | BDF-BE | `0xa8` | False | not in any FFS — top-level image region (looks like crypto/key blob) |

Hex-dump context around each:

- `0xe2b88f`: surrounded by x86-style instruction stream (`33 c0 23 c7 33 46 0c 83 ca ff 8b c8` etc.) — incidental opcode bytes inside compiled code, not a descriptor field. The neighbouring bytes do NOT match descriptor layout (no NBIO byte at `-0x01`, no link-state at `-0x0F`).
- `0x107c01e`, `0x11d471e`: identical 64-byte windows — ARM Thumb-2 instruction stream (`94 f8 38 00 80 07 09 d4 d4 e9`). This is Aspeed AST2500 BMC firmware code. Not descriptor data.
- `0x12c3f64`: ARM Thumb-2 in BMC region (`25 4b 00 eb`). Not descriptor data.
- `0x84ab20`: indistinguishable random bytes (entropy ~uniform across the window) — looks like an encrypted/signed blob (key, certificate, or signed PSP payload).

**No whole-image hit lands inside any AGESA / NBIO / DXIO module.** No hit has the surrounding byte structure expected of a per-port descriptor (NBIO instance, link-state, type/flags dword).

---

## Prong 2 — PE32 `.data` / `.rdata` hunt

Walked all 651 PE32 image sections in `extracted/all/P3.70/img.bin.dump/`. Used `pefile` to identify section layout. Scanned section bytes for the same six BDF patterns.

**Hits in `.data` / `.rdata`: 0.**

For completeness, also scanned `.text`. 22 hits, all in network/UEFI services (`UefiPxeBcDxe`, `PciBus`, `HttpBootDxe`, `TlsDxe`, `Ip4Dxe`, `MnpDxe`, `Bds`, `RfInventory`, `RfSecureBoot`, `RfTlsCertificates`, `AmiRedfishDynExt`, `RedfishHi`, `Udp4Dxe`, `FirmwareConfigDrv`, GUID `EE4E5898-…` = `XhciPei`/similar). None in any AGESA, NBIO, CPM, APCB, or DXIO module. All are incidental opcode/operand byte sequences. Full table in `/tmp/hunt2b_hits.txt`.

**Verdict for prong 2: no PE32 `.data` / `.rdata` anywhere in P3.70 contains the bytes `40 01 03` or `03 01 40` in any orientation. There is no static descriptor table in any PE32 data section that includes BDF `40:01.3`.**

---

## Prong 3 — heuristic descriptor-table detection

Scanned all PE32 `.data` / `.rdata` for arrays of structures with stride ∈ {`0x30`, `0x34`, `0x38`, `0x3C`, `0x40`, `0x44`, `0x48`, `0x50`, `0x58`, `0x60`} satisfying:

- `+0x1D`: NBIO instance ≤ 3
- `+0x1E`: bus in {`0x00`, `0x20`, `0x40`, `0x60`, `0x80`} (Rome IOD bus seeds)
- `+0x1F`: dev ≤ `0x1F`
- `+0x20`: fn ≤ 7
- `+0x2E`: in {`0x00`, `0x40`, `0x80`, `0xC0`, `0x44`, `0x04`, `0xC4`, `0x84`}
- ≥ 4 consecutive entries with **distinct** BDFs (each port unique)

**Candidate arrays found: 2** (both in `200 TlsDxe` `.data`, stride `0x60`, n=4, all BDFs `00:00.x`, all `+0x2E = 0x00`). These are clear false positives — `TlsDxe` is the TLS implementation; the matching bytes are coincidental within a TLS keying / state structure. Full table in `/tmp/hunt3_tighter.txt`.

**Entries with BDF `40:01.3`: 0.**

**Verdict for prong 3: no plausible per-port descriptor array exists in any PE32 data section in P3.70 that includes a `40:01.3` entry — or, in fact, any Rome-style IOD-bus port entry at all.**

---

## Verdict

**Negative on all three prongs.** The static descriptor source for the `40:01.3` Gen4 enable was *not* located in P3.70:

- Whole-image: 5 raw byte-pattern hits, all in non-AGESA regions (BMC firmware, signed blobs, opcode noise). None has bit 6 of byte+`0x10` set in a context resembling a descriptor.
- PE32 `.data`/`.rdata`: 0 hits.
- Heuristic descriptor-array detection: 2 false-positive candidates in `TlsDxe`, neither containing `40:01.3`.

**Implication: the per-port DXIO descriptor table is built at runtime, not stored statically.** This is consistent with the existing key findings:

1. Subagent #1 (`docs/APCB_DECODE.md`): the APCB blob contains only PSPG/MEMG/TOKN — no static DXIO descriptor table.
2. Subagent #5 (`docs/RADARE2_NBIOPCIE.md`): `AmdNbioPcieDxe` reads the descriptor through `r14`, never with a fixed file-image address.
3. The BDF `40:01.3` does not appear as data anywhere in the BIOS image. Whatever sets bit 6 on its descriptor is doing so at runtime, by computing the BDF from the PCIe topology walk (likely in `AmdCpmPcieInitDxe`, `AmdNbioBaseSspDxe`, or `AmdApcbDxeV3`), not by indexing into a baked array.

This redirects the search definitively to runtime synthesizer disassembly. The candidate target remains `AmdApcbDxeV3` (per CLAUDE.md item #1b — `+64 B` size growth between P3.70 and P3.80) — diff that, find the per-port `+0x2E` write, and inspect what condition gates it. The earlier P3.70 baseline disasm of `AmdApcbDxeV3` is in `docs/APCB_DXEV3_DIFF.md` and `docs/APCB_CALLER_FCN13DF4.md`; this hunt confirms the synthesizer does not load the descriptor from a static blob — it constructs it.

---

## Artefacts

- `/tmp/hunt1_hits.txt` — all 5 whole-image hits with `+0x10` byte / bit-6 status.
- `/tmp/hunt2b_hits.txt` — full 22-row PE32 cross-section hit table.
- `/tmp/hunt3_tighter.txt` — 2 false-positive heuristic candidates (TlsDxe).

(Helpers in `/tmp/`, not committed per task constraints.)
