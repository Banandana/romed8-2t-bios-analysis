# APCB decode — ROMED8-2T (Rome SP3, EPYC 7002)

**Goal of this document.** Decode the AMD Platform Configuration Block (APCB) inside each shipped ROMED8-2T BIOS image; locate the per-port DXIO descriptor bytes that determine PCIe Gen-cap; identify the diff between P3.70 and P3.80 that makes Gen4 work on rev-1.03 GPU slots in P3.80; assess PSB signing.

**Headline result (definitive, negative).** **The APCB blobs in P3.70, P3.80, P3.90, and P4.10 are byte-identical bodies.** Only the V2-header `unique_apcb_instance` (bytes 0x0c-0x0d) and `checksum_byte` (byte 0x10) differ between versions — these are an opaque build-ID and the recomputed XOR-sum of the body. Neither encodes per-port speed. **Whatever P3.80 changed to enable Gen4 on rev-1.03 GPU slots, it was NOT in the APCB.** The unlock must live either in `AmdNbioPcieDxe.efi` (which DID change between P3.70 and P3.80 — but only with a hash-renamed identical-size copy; per `CROSS_VERSION_DIFF.md` row 23, P3.70 and P3.80 are listed as `=` so even that's identical), in `CbsSetupDxeSSP` (which DID change between P3.70 and P3.80, 194976 → 195296 bytes), or in a board-rev-strap branch elsewhere. Recommend: pivot to `CbsSetupDxeSSP` static analysis (radare2/Ghidra) as the next step, *not* APCB patching.

The remainder of this document records the decode path, the structures decoded, the empirical diff, and a residual-uncertainty list.

---

## 1. Tool install

```bash
pip install --user --break-system-packages psptool
# Arch's python is externally-managed (PEP 668); --break-system-packages bypasses safely
# Installed: psptool 3.6, prettytable 3.17.0, wcwidth 0.6.0
# CLI: ~/.local/bin/psptool
```

`psptool -h` confirms `-E` (entries), `-X` (extract), `-R` (replace), `-V`. **There is no `--apcb` decoder mode in psptool 3.6** — only PSP firmware directory parsing. APCB body decode required a manual structure walk against the Oxide Computer Rust schema (`oxidecomputer/amd-apcb`, `src/ondisk.rs`) — coreboot's `util/amdfwtool` does NOT contain the APCB v3 schema (only the directory entry types).

The fallback schema source used in this report:
```
curl -sL https://raw.githubusercontent.com/oxidecomputer/amd-apcb/main/src/ondisk.rs
```
This gives V2_HEADER, V3_HEADER_EXT, GROUP_HEADER, ENTRY_HEADER, GroupId enum, all entry IDs, and ~250 PCIe/DXIO/memory/Df/Cbs token IDs.

The custom parser used here is at `/tmp/apcb_parse.py` and `/tmp/apcb_tokens.py` (transient, regenerable from the structures listed in §3 below).

---

## 2. PSP firmware directory listing — P3.70 (summary)

`psptool -E ROMD82T3.70` enumerates two embedded ROMs:

- **ROM 0** — Rome SP3 image (`AGESA!V9 RomePI-SP3 1.0.0.F`), at file offset `0x0`, FET at `0x20000`. Contains directory `$PSP@0x136000` (PSP FW), `$PL2@0x3cb000` (PSP L2), `$BHD@0x246000` (BIOS), `$BL2@0x4cb000` (BIOS L2).
- **ROM 1** — Milan SP3 image (`AGESA!V9 MilanPI-SP3 1.0.0.A`), at file offset `0x1000000`, FET at `0x1020000`. Contains a parallel set of `$PSP/$PL2/$BHD/$BL2` directories. (This BIOS is dual-CPU-family: Rome AND Milan AGESA both present, so the same SPI image will boot a Rome 7xx2 OR a Milan 7xx3 EPYC.)

Both OEM_PSP_FW_PUBLIC_KEY entries (type 0x0a) carry the `1DC2` magic and are `verified(E600), AMD_AND_BIOS_CODE_SIGN`. AMD's root key chain validates the OEM signing key. ABL0 (AGESA BootLoader) and PSP_FW_BOOT_LOADER are also `verified`. SMU/MP5/PMU entries fail signature verification under psptool but pass sha256 — psptool labels them `key_missing(F014)` etc., which is the public ROM behavior (dev/oem keys not present in this image).

### APCB-bearing entries on the Rome side

| Entry | Address | Size | Type | Subprog | Instance |
|---|---|---|---|---|---|
| 0 (in `$BHD`) | `0x247000` | `0x2000` | `APCB_COPY~0x68` | 0x0 | 0x0 |
| 0 (in `$BL2`) | `0x4cc000` | `0x2000` | `APCB_COPY~0x68` | 0x0 | 0x0 |
| 1 (in `$BL2`) | `0x4ce000` | `0x258` | `APCB_COPY~0x68` | 0x0 | 0x8 |
| 2 (in `$BL2`) | `0x4cf000` | `0x2a0` | `APCB_COPY~0x68` | 0x0 | 0x9 |
| 3 (in `$BL2`) | `0x4d0000` | `0x1000` | `APCB~0x60` | 0x0 | 0x0 |
| 4 (in `$BL2`) | `0x4d1000` | `0x1000` | `APCB~0x60` | 0x0 | 0x1 |

The Milan side has the same shape at `0x1189000`, `0x14d9000`, `0x14db000`, `0x14dc000`, `0x14dd000`, `0x14de000`. Total: **12 actual APCB headers** (the previous "14 occurrences" count from `CROSS_VERSION_DIFF.md` was a pure ASCII `APCB` byte-pattern scan; 2 were false-positive matches in unrelated regions).

Note: psptool shows **no signing flags on the APCB/APCB_COPY entries.** They are not in the signed-entity tree at all. The PSP loader applies a body-checksum verification (the `checksum_byte` at offset 0x10 makes the byte sum over `[0..apcb_size)` equal 0 mod 256 — verified, see §5) but no cryptographic signature. **Implication: an APCB body modification is not, in itself, blocked by signing — it just requires a recomputed checksum byte. PSB enforcement, if fused, gates the PSP_FW chain (PSP_FW_BOOT_LOADER, ABL0, etc.), not APCB content.**

---

## 3. APCB v3 binary structure

Decoded from `oxidecomputer/amd-apcb` `src/ondisk.rs`:

```
APCB layout:
  +0x000 V2_HEADER         (32 B)
    +0x00  signature       4B  'APCB'
    +0x04  header_size     2B  0x0080  (== 128 incl V3 ext)
    +0x06  version         2B  0x0030
    +0x08  apcb_size       4B  total bytes incl header
    +0x0C  unique_apcb_inst 4B opaque build/instance ID
    +0x10  checksum_byte   1B  set so sum(body) ≡ 0 (mod 256)
    +0x11  _reserved_1[3]  3B
    +0x14  _reserved_2[3]  12B  (3 × 4B LU32)
  +0x020 V3_HEADER_EXT     (96 B)
    +0x00  signature       4B  'ECB2'
    ... fields designed to look like a fake GROUP_HEADER + ENTRY_HEADER for
        backward-compat with V2-only readers; values at +0x06 = 0x10, +0x08 = 0x12
    +0x58  data_offset     2B  0x0058
    ... ends with 'BCPA' (reverse of APCB) at +0x5C
  +0x080 [GROUP] sequence
GROUP_HEADER (16 B):
  +0x00  signature      4B   e.g. 'PSPG', 'MEMG', 'GNB ', 'DFG ', 'TOKN'
  +0x04  group_id       2B   see GroupId enum below
  +0x06  header_size    2B   0x0010
  +0x08  version        2B   0x0001
  +0x0a  _reserved_     2B
  +0x0c  group_size     4B   incl this header
GroupId enum:
  0x1701 PSP    "PSPG"
  0x1702 CCX
  0x1703 DF     "DFG "
  0x1704 Memory "MEMG"
  0x1705 GNB    "GNB " (DXIO/PCIe — the one we want)
  0x1706 FCH
  0x1707 CBS
  0x1708 OEM
  0x3000 Token  "TOKN"
ENTRY_HEADER (16 B):
  +0x00  group_id (matches outer)
  +0x02  entry_id (eid; entry-type within group)
  +0x04  entry_size (incl this header)
  +0x06  instance_id
  +0x08  context_type (0=Struct, 1=Parameters, 2=Tokens)
  +0x09  context_format (0=Raw, 1=SortAscending)
  +0x0a  unit_size (8 for tokens)
  +0x0b  priority_mask
  +0x0c  key_size + key_pos
  +0x0e  board_instance_mask
Body of a Token entry: array of (key:u32_LE, value:u32_LE) pairs
```

---

## 4. APCB group enumeration — P3.70 main blob @ `0x247000` (size 7168 = 0x1c00)

| Offset | Group | Group ID | Size | Notes |
|---|---|---|---|---|
| `+0x080` | `PSPG` | `0x1701` PSP | 80 | 1 entry |
| `+0x0d0` | `MEMG` | `0x1704` Memory | 4496 | 22 entries (DDR4 RDIMM/UDIMM training, ODT, DataBus, CadBus, post-package-repair, error-out-control) |
| `+0x1260` | `TOKN` | `0x3000` Token | 2464 | 9 entries (5 instance/board-mask variants of token tables: eid 0x0/0x1/0x2/0x4 = `Bool`/`Byte`/`Word`/`Dword` token tables, ×{board=0x0001, board=0x0002, board=0xffff}) |

**No GNB group (0x1705) is present.** **No CBS group (0x1707) is present.** **No DXIO descriptor table is present in this APCB.**

The other 5 APCB blobs on the Rome side:
- `0x4cc000` (size 7168): identical to `0x247000` (it is the L2 backup copy).
- `0x4ce000` and `0x4d0000` (size 600 each, identical to each other): contain `DFG` (DF, group 0x1703) eid 0xcc + a `TOKN` group with sparse entries.
- `0x4cf000` and `0x4d1000` (size 672 each, identical to each other): contain `MEMG` eid 0x5e (memory PSP retention) + a small `TOKN` group.

**Conclusion: across all 6 Rome-side APCBs, no `GNB` (0x1705) group exists. There is no APCB-resident DXIO Engine/Port descriptor table on this BIOS.**

What IS PCIe-relevant in the token tables:
- **Token 0x8723750f = 0x00000002** — `SecondPcieLinkSpeed = Gen2` (per Oxide schema, the `AdditionalPcieLinkSpeed` enum is `Keep=0, Gen1=1, Gen2=2, Gen3=3` — there is no `Gen4` in this enum at all). This token controls a sideband / management PCIe link, not the GPU root ports.
- Tokens like `Third/FourthPcieLinkSpeed` (`0x79633632`, `0x06396763`) are NOT present in the dump.
- No `MaxLinkSpeedCap`, `TargetLinkSpeed`, `EsmEnable`, `LcGen4EnStrap` token IDs found in the Token group (these don't even exist in the Oxide schema's known-token list — they are AGESA C-source defines, not APCB tokens).

This is consistent with the Rome architecture: the **DXIO descriptor table is compiled into AGESA / `AmdNbioPcieDxe.efi` as static data**, not stored in APCB. APCB tokens only override a handful of high-level PCIe knobs (sideband links, reset GPIO selection, SATA mode), not per-port Gen-cap.

---

## 5. P3.70 → P3.80 byte-level diff at all APCB blob offsets

For each of the 6 Rome-side APCB blocks plus the 6 Milan-side APCB blocks, compute byte-by-byte diff between P3.70 and P3.80 across `[0..apcb_size)`:

### Rome side (all 6 blobs)

| Offset | Size | # diff bytes | Diff locations |
|---|---|---|---|
| `0x247000` | 7168 | **3** | `+0x0c`, `+0x0d`, `+0x10` |
| `0x4cc000` | 7168 | **3** | `+0x0c`, `+0x0d`, `+0x10` |
| `0x4ce000` | 600  | **3** | `+0x0c`, `+0x0d`, `+0x10` |
| `0x4cf000` | 672  | **3** | `+0x0c`, `+0x0d`, `+0x10` |
| `0x4d0000` | 600  | **3** | `+0x0c`, `+0x0d`, `+0x10` |
| `0x4d1000` | 672  | **3** | `+0x0c`, `+0x0d`, `+0x10` |

**The only 3 differing bytes per blob are**:
- `+0x0c, +0x0d` = low 2 bytes of `unique_apcb_instance` (V2_HEADER field, opaque build-ID)
- `+0x10` = `checksum_byte` (recomputed because the unique_apcb_instance bytes changed)

Everything from `+0x14` onward — the rest of the V2 reserved block, the entire V3_HEADER_EXT (`+0x20`–`+0x7F`), and the entire group/entry body (`+0x80` to end) — is **byte-identical**.

#### Concrete example — APCB @ `0x247000`

| Offset | P3.70 | P3.80 | Field | Interpretation |
|---|---|---|---|---|
| `+0x0c` | `0x4a` | `0x42` | `unique_apcb_instance[0]` | low byte of build ID (changed) |
| `+0x0d` | `0x24` | `0x22` | `unique_apcb_instance[1]` | next byte of build ID (changed) |
| `+0x0e` | `0x00` | `0x00` | `unique_apcb_instance[2]` | unchanged |
| `+0x0f` | `0x00` | `0x00` | `unique_apcb_instance[3]` | unchanged |
| `+0x10` | `0x56` | `0x60` | `checksum_byte` | recomputed XOR-sum complement |

P3.70 unique_apcb_instance = `0x0000244a` (decimal 9290).
P3.80 unique_apcb_instance = `0x00002242` (decimal 8770).
Both are < 0x10000, look like 16-bit version numbers (P3.70 ≈ 9290, P3.80 ≈ 8770 — note P3.80's is *smaller*, so this is not a monotonic version stamp; possibly a hash-prefix or build-tool sequence number).

#### Cross-check: P3.80 → P3.90 → P4.10

Same exact diff pattern: 3 bytes per blob, all at `+0x0c, +0x0d, +0x10`. APCB body bytes are **identical across P3.70, P3.80, P3.90, and P4.10** for all 6 Rome-side instances. ASRock has not changed APCB content for this CPU socket since at least P3.70 (2023-05-30) through P4.10 (2025-06-05).

### Milan side

Same picture for the small Milan blobs (`0x14db000`, `0x14dc000`, `0x14dd000`, `0x14de000`): identical body bytes across all four BIOSes.

The Milan **main** blob at `0x1189000` / `0x14d9000` (size 6504 → 6564) is the **one exception**: P3.80 → P3.90 changed 4367 body bytes and grew by 60 bytes. P3.70 → P3.80 was identical. P3.90 → P4.10 was identical. This is a **Milan-specific** APCB update that landed in P3.90, irrelevant to a Rome 7402P / 7702 / 7H12 rig.

### Hypothesis: which bytes flip Gen3 → Gen4 in P3.80?

**No bytes in the APCB flip Gen3 → Gen4 between P3.70 and P3.80, because no APCB body bytes change at all.** The Gen4 unlock for rev-1.03 GPU slots — confirmed empirically at the rig — is **not** in the APCB.

The change must therefore be in one of:

1. **`CbsSetupDxeSSP` (PE32)**, which grew from 194976 B (P3.70) to 195296 B (P3.80). New 320 B of code/data. From `CROSS_VERSION_DIFF.md`. Most likely candidate, given that `CbsSetupDxeSSP` is the AGESA Common-Boot-Setup driver responsible for binding NVRAM Setup options to AGESA configuration, and would be the natural place for "if board_rev_strap == 1.03 then enable_gen4_on_gpu_slots" logic.
2. **`Setup` (ASRock board HII)**, which changed (293504 → 293504 B, same size, different hash) between P3.70 and P3.80. Could host the rev-1.03 detection callback.
3. **Some other AGESA module** not listed in the cross-version diff (e.g. an AmdCpm* or AmdPbsSetupDxe), or an embedded data resource within `Setup`.

`AmdNbioPcieDxe` did NOT change between P3.70 and P3.80 (per `CROSS_VERSION_DIFF.md` row 23: `=` between those columns — same 72640 B PE32). So the actual ESM/Gen4 enable code path didn't change; only its inputs. The question is who flipped the input.

`AmdApcbDxeV3` DID change between P3.70 and P3.80 (50848 → 50912 B, +64 B). This is the **runtime APCB consumer driver**, not the APCB blob itself. The driver code grew by 64 bytes. **Possible mechanism: `AmdApcbDxeV3` in P3.80 has new logic that synthesizes/overrides DXIO descriptors at runtime based on a board-rev MMIO read, before passing them to `AmdNbioPcieDxe`.** This would explain why static APCB content unchanged + runtime behavior changed = Gen4 unlock for rev-1.03.

**Recommended next step**: disasm `AmdApcbDxeV3` (P3.70 vs P3.80) and `CbsSetupDxeSSP` (P3.70 vs P3.80), looking for new code paths that read a board strap (likely SMBus EEPROM, GPIO, or SMN MMIO at the board-revision address) and condition DXIO descriptor mutation on it. Combine with `AmdNbioPcieDxe` disasm (see CLAUDE.md item #5).

---

## 6. Per-port descriptors for the 8 GPU root ports

**Cannot be located in this BIOS.** No GNB group (0x1705) is in any APCB blob. The DXIO Engine/Port descriptors that AGESA's `DxioInit` consumes are either:

- Compiled into `AmdNbioPcieDxe.efi` as a static C struct array (AGESA convention on older Naples/Rome platforms); or
- Constructed at runtime by `AmdApcbDxeV3` from a combination of CBS settings + hard-coded ASRock board profile, then passed to `AmdNbioPcieDxe`.

The Oxide `EarlyPcieConfig` entry (Gnb eid 0x1003) is **Turin-only**. Rome/Naples have no equivalent APCB-resident descriptor table.

To retrieve the per-port descriptor for the 8 GPU root ports, the next step is `radare2`/Ghidra disasm of `extracted/all/P3.70/img.bin.dump/.../*AmdNbioPcieDxe*/body.bin`, finding the static descriptor array (look for entries with `start_lane`, `end_lane`, `port_present`, `max_link_speed`, `max_link_width`, `link_aspm`, `hotplug` fields, ~24-32 bytes per port, count ≈ 24 for the four NBIOs × 6 max ports each, or ≈ 11 for the ROMED8-2T's actual slot population).

---

## 7. PSB / PSP signing status

`psptool -E -t ROMD82T3.70` shows the full signed-entity tree:

- **AMD root key (`E600`)** signs the ASRock OEM key (`1DC2`, type `OEM_PSP_FW_PUBLIC_KEY`) with `AMD_AND_BIOS_CODE_SIGN` flag.
- **OEM key (`1DC2`)** signs **ABL0** (AGESA bootloader, type `0x30`, address `0x17f500`) — verified=True.
- AMD root key signs PSP_FW_BOOT_LOADER (`$PS1`, address `0x3cb400`) — verified=True.
- SMU_OFFCHIP_FW, MP5_FW, etc. show `key_missing(F014)` — the dev signing keys aren't in the public image, but AMD's release signing keys would be.
- DEBUG_UNLOCK entry exists (type 0x13, address `0x16a400`) but `key_missing(EA74)` — **no debug unlock token applied in this image** (the image is shipped, not factory-unlocked).
- **TOKEN_UNLOCK region @ `0x16e000`** is all `0xff` bytes — **no token-based debug unlock burned**.
- **SOFT_FUSE_CHAIN_01 @ `0x136060`** has bytes `0b 00 00 00 ff ff ff ff 01 00 00 00 ...` — i.e. soft-fuse byte = 0x01 (a single bit set; AMD soft-fuses are runtime-overridable values that PSP applies on cold boot). The `0x01` bit at byte 8 corresponds to the `soft_fuse(0x1)` annotation psptool produces.

**The APCB and APCB_COPY entries (types 0x60, 0x68) are NOT signed.** They appear in the BHD/BL2 directories without a signature attachment. The PSP integrity-checks them via the `checksum_byte` in the V2 header (an XOR-sum, not a hash). **An APCB body modification with a recomputed checksum will be accepted by the PSP** at integrity-check time. PSB enforcement, if fused on the CPU, gates the *PSP firmware chain* (PSP_FW_BOOT_LOADER → ABL0 → AGESA), not APCB content.

**PSB-fuse status of the rig's CPU cannot be determined from the BIOS image.** It requires reading MSR `0xC0010135` or similar PSP MSRs from the running OS (`rdmsr` from a kernel module, or `psptool --check-fuses` if such option existed — psptool 3.6 does not have it). This is a rig-side check; it is **out of scope for this static analysis** and CLAUDE.md's hard constraint "no rig contact" applies. The constraint also states the user "must not ssh to the rig for this task," so PSB status is recorded as **unknown** here. If at a later date the user runs `cat /sys/firmware/dmi/entries/.../*` or `rdmsr -p 0 0xC0010135` on the rig, PSB-fused state can be derived from the `PSB_STATUS` MSR bits.

**Practical implication:** APCB patching is *technically* viable (no signature). It is moot in this case — there is nothing in the APCB to patch that would lift the GPU-slot Gen3 cap, because the APCB doesn't encode that data on this BIOS. This conclusion holds regardless of PSB fuse state.

---

## 8. What's still unknown / next work

1. **Where in the runtime AGESA code does the rev-1.03 / Gen4 unlock live?**  Strongest leads in priority order:
   - `AmdApcbDxeV3` (changed P3.70→P3.80, +64 B). Disasm and find new function bodies.
   - `CbsSetupDxeSSP` (changed P3.70→P3.80, +320 B). Disasm and find new code.
   - `Setup` ASRock HII module (changed P3.70→P3.80, same size, different hash). Could carry a board-rev callback.
   - Less likely but possible: a board-rev MMIO read added to `AmdNbioPcieDxe` *between* P3.70 and P3.80 by inline patch (the binary hash row in CROSS_VERSION_DIFF says `=`, which means UEFIExtract dump output identical, so this is NOT it — confirmed unchanged).
2. **Where do the 8 GPU root ports' DXIO descriptors actually live?**  Not in APCB. Almost certainly compiled into `AmdNbioPcieDxe.efi` static data. Disasm to find the descriptor array; identify the array's base by xref to the `DxioInit` / `PciePortInit` functions; print 8 entries × ~24-32 B each.
3. **Is PSB fused on the rig CPU?**  Requires rig-side MSR read. Out of scope here per CLAUDE.md no-rig-contact constraint. Recommendation: when the user is at the rig, run `sudo rdmsr -p 0 0xC0010135` (the EPYC Rome PSB status MSR per AMD PPR). Bit 30 = `PSB_STATUS_VALID`, bit 24 = `PSB_FUSED`.
4. **Is the AGESA bootloader (ABL0) consuming the Token group's `SecondPcieLinkSpeed = Gen2` (`0x8723750f = 0x2`) for the BMC sideband or for some GPU slot?**  Static analysis of ABL0 (extracted at `0x17f500`, only 928 B) would clarify — likely it controls only the AST2500 BMC management link, not the GPU slots, but worth confirming.
5. **Cross-vendor APCB comparison**: as called out in CLAUDE.md item #7, decoding the APCB from a Supermicro H12SSL-i / TYAN S8030 / Gigabyte MZ32-AR0 (sibling Rome boards known to do GPUs at Gen4) and comparing GNB-group presence/contents would confirm whether *any* Rome OEM puts DXIO descriptors in APCB. If none do, the descriptor location is an AGESA convention and the fix is purely in `AmdNbioPcieDxe` build flags.

---

## 9. Bottom line — is APCB patching the path to Gen4?

**No.** Three independent findings rule it out:

1. There is no GNB / DXIO descriptor group in any APCB blob on this BIOS (only PSP, Memory, DF, Token).
2. No PCIe-Gen-cap-relevant token in the Token group changes between P3.70 and P3.80, P3.80 and P3.90, P3.90 and P4.10.
3. The 6 Rome-side APCB blob bodies are byte-identical across all 4 versions (P3.70, P3.80, P3.90, P4.10). Only `unique_apcb_instance` and `checksum_byte` differ — fields that don't encode any platform configuration.

The Gen4-unlock-on-rev-1.03 mechanism, empirically observed in P3.80, **must be elsewhere**. The candidate modules with actual byte-content changes between P3.70 and P3.80 are: `CbsSetupDxeSSP`, `CbsSetupDxeZP`, `CbsBaseDxeSSP`, `Setup` (ASRock HII), `AmdApcbDxeV3`. Of these, **`AmdApcbDxeV3` (the runtime APCB consumer)** is the highest-priority disasm target — a new code path that mutates DXIO descriptors before passing them to `AmdNbioPcieDxe`, gated on a board-rev strap, exactly fits the empirical pattern. Second-priority is `CbsSetupDxeSSP` for the same reason at the AGESA-CBS layer.

This invalidates CLAUDE.md's §1.a / §1.b hypothesis ("APCB descriptor field added"). It validates §1.c ("the rev-strap branch is in code, not APCB"). The next-direction roadmap should be reordered:

- **Item #1 (APCB binary parsing)**: ✅ done. Result: APCB is not the unlock site.
- **Item #5 (disassemble `AmdNbioPcieDxe`)**: still relevant for understanding the *consumer* of DXIO descriptors, but its byte-identical state between P3.70 and P3.80 means it's not the *source* of the unlock.
- **NEW Item #5b (disassemble `AmdApcbDxeV3`)**: highest-leverage next step — diff P3.70 vs P3.80 PE32 bodies, find the new 64 B of code, follow xrefs to identify what input it reads (board strap?) and what DXIO descriptor field it writes.
- **NEW Item #5c (disassemble `CbsSetupDxeSSP` diff)**: P3.70→P3.80 added 320 B. Same approach. A board-rev callback registered in this driver could feed the new APCB-consumer logic.

If item #0 (AMD-IOPM-UTIL) does work at runtime, none of this matters and the Gen4 cap is liftable from userspace without flashing. That remains the highest-priority lead per CLAUDE.md.
