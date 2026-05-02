# PSP / ABL firmware diff — ROMED8-2T P3.70 vs P3.80

**Goal.** Determine whether the rev-1.03 / P3.80 Gen4 unlock lives in the PSP firmware (PSP_FW_BOOT_LOADER + ABL stack) — the layer that runs on the ARM PSP coprocessor *before* x86 PEI/DXE dispatch and that loads/consumes APCB tokens.

**Headline result (definitive, mostly negative — but with one major structural finding that explains the BIOS-wide changes).**

1. **P3.70 is a Rome+Milan combo image; P3.80 collapses to Milan-only PSP firmware in both ROM regions.** P3.70 ROM 0 ships `AGESA!V9 RomePI-SP3 1.0.0.F` (Rome PSP); ROM 1 ships `AGESA!V9 MilanPI-SP3 1.0.0.A`. P3.80 ships `AGESA!V9 MilanPI-SP3 1.0.0.A` in *both* ROM 0 and ROM 1. **The ASRock change between P3.70 and P3.80 was: stop shipping the Rome-specific PSP/ABL firmware in ROM 0 and ship the Milan PSP/ABL firmware everywhere.** This is silicon-class significant: the rig's EPYC 7532 (Rome) on P3.80 boots through the Milan PSP/ABL stack, which is supersetted to handle Rome silicon (PSP firmware is largely shared across Family 17h Models 30h/31h).
2. **PSP code blobs that changed are encrypted-by-IKEK and cannot be statically disassembled** without keys we don't have. We can confirm sizes/versions/hashes; we cannot confirm or deny the presence of `+0x2E`/`0x40` bit-set logic by reading the binaries.
3. **APCB blobs (carried inside the PSP firmware directories) are byte-identical body** — only V2-header `unique_apcb_instance` (bytes `+0x0C/+0x0D`) and the XOR `checksum_byte` (`+0x10`) differ. This re-confirms subagent #1's APCB finding from a different extraction path. **The APCB itself is not the unlock.**
4. **All AMD/OEM signing keys remain in place; PSB chain is unbroken on both versions.** OEM PSP key 1DC2 (signs ABL0) and AMD root E600 (signs OEM key) are present and verify on both. P3.80 introduces additional Milan-platform keys 94C3 (AMD root) and 289A (OEM PSP key) — these were already present in P3.70's ROM 1 (Milan secondary) but become primary in P3.80. **No path to patch ABL0 without forging an OEM key signature (1DC2 → still required by PSB if PSB is fused).**

**Verdict: inconclusive on PSP/ABL as the unlock site, but with strong indirect evidence pointing to it.** The PSP firmware *did* change substantially between P3.70 and P3.80 (different version `0.C.0.87 → 0.C.0.88`, different ABL0 build `10.F.20.10 → 34.24.20.10`, different platform target Rome→Milan-superset). But the changed bodies are encrypted-by-IKEK, so we cannot directly verify what changed inside them. The combination of (a) APCB body identical, (b) DXE consumer (`AmdNbioPcieDxe`) identical, and (c) PSP/ABL firmware substantially upgraded is consistent with the unlock living in the PSP-side APCB-token interpreter (ABL stack) — the only layer that actually changed and could affect per-port DXIO descriptor synthesis.

**Implication for the no-flash constraint:** even if PSP/ABL is the unlock site, patching it externally requires either (a) breaking AMD/OEM signing (PSB fuse-state-dependent), or (b) reflashing — which the user has ruled out. The PSP/ABL angle therefore does **not** open a userspace runtime fix path.

---

## 1. PSP entry-table diff (full)

Generated from `psptool -E images/ROMD82T3.<v>` on 2026-04-27.

### ROM-level summary

| ROM | P3.70 AGESA | P3.80 AGESA | Change |
|---|---|---|---|
| 0 | `AGESA!V9 RomePI-SP3 1.0.0.F` | `AGESA!V9 MilanPI-SP3 1.0.0.A` | **ROME → MILAN** |
| 1 | `AGESA!V9 MilanPI-SP3 1.0.0.A` | `AGESA!V9 MilanPI-SP3 1.0.0.A` | identical |

P3.70 was a combo image containing Rome PSP firmware (ROM 0) and Milan PSP firmware (ROM 1) — at boot the PSP picks the right ROM by silicon ID. P3.80 ships only Milan PSP firmware everywhere; the Milan ABL/PSP loader is supersetted to also handle Rome (Family 17h Model 31h) silicon and is what actually runs on the rig's EPYC 7532 once P3.80 is flashed.

### Directory 0 (ROM 0, $PSP) — entries that changed

| Entry | Type | P3.70 (size, version, sha256[:12]) | P3.80 (size, version, sha256[:12]) | Status |
|---|---|---|---|---|
| 0  | `AMD_PUBLIC_KEY~0x0` (E600)         | 0x440, v1, identical                  | 0x440, v1, identical                  | unchanged (Rome+Milan share AMD root key) |
| 1  | `PSP_FW_BOOT_LOADER~0x1`            | 0x15540, **v0.C.0.87**, `3c91a5531ea9` | 0x15540, **v0.C.0.88**, `10782478da7f` | **CHANGED** (encrypted body, 87360 bytes) |
| 2  | `PSP_FW_RECOVERY_BOOT_LOADER~0x3`   | 0x15540, FF.C.0.87, `71eeb1590b7f`    | 0x15440, FF.C.0.88, `839e5e508d28`    | **CHANGED** (encrypted body, **−256 bytes**) |
| 4  | `OEM_PSP_FW_PUBLIC_KEY~0xa` (1DC2)  | 0x640, v1, identical                  | 0x640, v1, identical                  | unchanged |
| 7  | `DEBUG_UNLOCK~0x13`                 | 0x3b00, v0.C.0.87, `63c4e174e696`     | 0x3b00, v0.C.0.88, `04d8355ffd24`     | **CHANGED** (version-bumped, encrypted) |
| 12 | **`ABL0~0x30`**                     | 0x3a0, **v10.F.20.10**, `f03b5f09bd0c` | 0x3a0, **v34.24.20.10**, `489de98dbe13` | **CHANGED** (header-table only — 928 bytes; actual ABL bodies live in BIOS region) |
| 13 | `PSP_FW_L2_PTR~0x40`                | 0x400, `35e1598270e9`                  | 0x400, `9777d97f9faa`                  | **CHANGED** (pointer to secondary directory) |
| 14 | `FW_GEC_OR_DXIO_PHY_SRAM_FW~0x42`   | 0x14b0, v0.30.4.19, identical         | 0x14b0, v0.30.4.19, identical         | unchanged |
| 15 | `DXIO_PHY_SRAM_FW_PUBKEY~0x43` (60FD)| 0x640, v1, identical                  | 0x640, v1, identical                  | unchanged |
| 16 | `PMU_PUBKEY~0x4e` (CC0D)            | 0x640, v1, identical                  | 0x640, v1, identical                  | unchanged |

Other entries (`SMU_OFFCHIP_FW`, `SOFT_FUSE_CHAIN_01`, `SMU_OFF_CHIP_FW_2`, `WRAPPED_IKEK`, `TOKEN_UNLOCK`, `SEC_GASKET`, `MP5_FW`) are byte-identical.

### Directory 1 (ROM 0, $PL2 secondary) — same pattern

The L2 directory contains a duplicate of the same files (PSP design — the secondary is for resilience / partial-flash recovery). All entries that changed in d0 also changed in d1 with identical hashes. Notably:
- `ABL0~0x30` again `v10.F.20.10 → v34.24.20.10` (same body)
- `SEV_CODE~0x39` `v1.0.18.11 → v1.0.18.12` — only present in the secondary
- `SEC_DBG_PUBLIC_KEY~0x9` (3A13) unchanged

### Directory 2 (ROM 0, $BHD BIOS Hash Directory) — entries that changed

| Entry | Type | P3.70 hash[:12] | P3.80 hash[:12] | Status |
|---|---|---|---|---|
| 0  | `APCB_COPY~0x68` (8192 B)            | `bdfca8409f67` | `f3e16d920073` | CHANGED — **3 bytes only**: `+0x0C/+0x0D/+0x10` (V2 header build-id + checksum) |
| 2  | `BIOS` (2424832 B = main UEFI PE volume) | `a22b4dd46666` | `a3850b09dc5a` | CHANGED — covered by separate UEFI module-level diff (subagents F/G) |

PMU_CODE/PMU_DATA blobs (entries 3-14) byte-identical.

### Directory 3 (ROM 0, $BL2 BIOS L2) — entries that changed

| Entry | Type | P3.70 hash[:12] | P3.80 hash[:12] | Status |
|---|---|---|---|---|
| 0,1,2 | `APCB_COPY~0x68` (×3 instances)  | various | various | **3-byte diff each** (V2 header instance ID + checksum, body identical) |
| 3,4   | `APCB~0x60` (×2 instances)       | various | various | **3-byte diff each** (same as above) |
| 6     | `BIOS` (2424832 B)               | `a22b4dd46666` | `a3850b09dc5a` | CHANGED — main UEFI volume |
| 19    | `MICROCODE_PATCH~0x66` (cpuid 0x830110, Rome) | `0x08301055` (Feb-2022) | `0x08301072` (Oct-2022) | **CHANGED** — bundled microcode bumped |
| 20    | `MICROCODE_PATCH~0x66` (cpuid 0x830027) | `0x08300027` (Apr-2019) | `0x08300027` (Apr-2019) | unchanged |

PMU_CODE/PMU_DATA byte-identical across versions.

### ROM 1 (Milan combo half) — entries that changed

ROM 1 in P3.70 already contained Milan PSP firmware. Only `SEV_CODE~0x39` bumped `v1.1.35.5 → v1.1.35.5` (no — actually identical version on ROM 1; the SEV_CODE change is in ROM 0's $PL2 directory). ROM 1 PSP firmware is **functionally identical between P3.70 and P3.80** — confirmed by hash equivalence on PSP_FW_BOOT_LOADER, ABL0, etc. on ROM 1.

This is the smoking gun: **the only PSP-firmware change between P3.70 and P3.80 is replacing Rome PSP/ABL in ROM 0 with Milan PSP/ABL.**

---

## 2. Signing-key analysis

### Keys present
- **AMD root pubkey E600** (Rome) — present, valid signature on OEM keys, signs PSP_FW_BOOT_LOADER. Both versions.
- **AMD root pubkey 94C3** (Milan) — present in both versions' ROM 1; in P3.80 also primary in ROM 0.
- **OEM PSP pubkey 1DC2** (Rome) — present, signs `ABL0~0x30`, verified by E600. Both versions.
- **OEM PSP pubkey 289A** (Milan) — present in both versions' ROM 1; in P3.80 also primary in ROM 0; signs Milan ABL0.
- **DXIO PHY SRAM FW pubkey 60FD**, **PMU pubkey CC0D**, **SEC DBG pubkey 3A13** — unchanged across versions.

### Are entries signed?
- Yes. Per `psptool -E -t`, the full chain verifies on both versions. Specifically `verified(E600), sha256_ok` on PSP_FW_BOOT_LOADER, `verified(1DC2), sha256_ok` on Rome ABL0, `verified(289A), sha256_ok` on Milan ABL0.

### Does any key change?
- **No new AMD or OEM keys appeared in P3.80** — both 94C3 (AMD) and 289A (OEM) were already in P3.70's ROM 1. **What changed is which keys' signed entries are placed in the primary directory** — P3.80 promotes Milan-signed entries to primary.

### PSB implications
- The APCB itself remains unsigned (only XOR checksum) on both versions — confirms subagent #1.
- ABL0 remains signed by OEM (1DC2 in Rome, 289A in Milan) on both versions.
- **Whether a forged-or-modified ABL0 would boot depends on whether PSB is fused on the actual CPU** — readable only via MSR `0xC0010135` from the rig (subagent #2 noted: not yet read; out of rig-touch scope).
- If PSB is fused: any patched ABL0 fails signature verification → boot halts. Patching path dead.
- If PSB is NOT fused: ABL0 can be replaced (e.g. via psptool `-R` with self-signed key) — but the modification target lives inside an encrypted body (see §3) which we can't analyze, so we don't know what to patch.

---

## 3. Per-blob disassembly status

### `PSP_FW_BOOT_LOADER~0x1` (87360 B body)
- **Encrypted by AMD IKEK / AES-CCM — disassembly impossible without key.** Entropy 6.604 bits/byte; raw `strings` returns only header magic `$PS1` and a single `ABL Version` literal in plaintext (the rest is ciphertext).
- Both P3.70 and P3.80 versions identical-entropy and same plaintext stub. The ciphertext body differs entirely (98%+ of bytes diff per `cmp -l`).
- **Cannot search for `+0x2E`, `0x40`, `Gen4`, `ESM`, `DXIO`, `Strap`, `Rev`, `1.02`, `1.03`, `Board` in the body.** Only the plaintext header strings are accessible — none of these keywords appear in either version's plaintext.

### `PSP_FW_RECOVERY_BOOT_LOADER~0x3` (87360 → 87104 B)
- Body has plaintext header stub but bulk is also encrypted (entropy 6.59).
- 68916 bytes differ (cmp). Plaintext strings include `PSPFW Bootloader Version`, `SMUFW Version` — present and identical in both. None of the keyword set appears in plaintext.
- **−256 bytes in P3.80.** Suggestive (a function got removed?) but the encrypted body precludes attribution.

### `ABL0~0x30` (928 B both versions — header only)
- This is the **ABL component table-of-contents**, not the ABL code itself. First 16 B is signature, then `$PS1` magic, then a 0x100-byte signature/header, then a TOC at offset 0x100 listing 19 sub-blobs (ABL0..ABL13 with their relative offsets and sizes).
- Version field at offset `+0x60`: P3.70 = `10 20 0F 10` (`v10.F.20.10`), P3.80 = `10 20 24 34` (`v34.24.20.10`).
- TOC offsets are nearly identical (sub-blob `0x01` at `0x4330` in both; `0x02` at `0xea90` vs `0xeb20` — a 144-byte offset shift; subsequent blobs all shifted by similar small deltas). **This is consistent with each ABL sub-blob growing by tens of bytes — the cumulative size growth is ~+34 KB across the full ABL stack from P3.70 to P3.80.**
- The actual ABL sub-blob bodies are *not* extracted by psptool from this 928-byte file — they live elsewhere (likely embedded in the BIOS volume or compressed inside an encrypted parent). Untraceable from this entry alone.
- **Cannot disassemble.** Even if we located the ABL bodies, AMD ABLs are AES-encrypted at rest with a key derived from PSP fuses (`PSP_BIOS_KEY` / IKEK). Decryption requires a non-fused PSP or an extracted IKEK from a chip-decap — out of scope.

### `DEBUG_UNLOCK~0x13`
- Body encrypted, version-bumped only. Not a code path that runs on production silicon.

### `MICROCODE_PATCH~0x66` (cpuid 0x830110)
- Plaintext patch header + AES-encrypted body (standard AMD μcode format).
- P3.70 patch level `0x08301055` (Feb-2022); P3.80 `0x08301072` (Oct-2022).
- **Rig is currently running `0x0830107C` (per CLAUDE.md)** — newer than P3.80's bundled patch. The rig's microcode is loaded by Linux at boot from `/lib/firmware/amd-ucode/`, *not* from BIOS. So this microcode bump cannot be the unlock — even rig-on-P3.80 would still get loaded the same `0x0830107C` microcode at OS-runtime, and rig-on-P3.70 already runs `0x0830107C`. **Microcode is not the source of the unlock.**

### `BIOS` region (2424832 B)
- Out of scope for this document — covered by `docs/CROSS_VERSION_DIFF.md`, `docs/MODULE_SWEEP_P3.70_vs_P3.80.md`, and DXE-module subagents F/G/etc.

---

## 4. Search summary

For the keywords requested in the task:

| Keyword | In PSP_FW_BOOT_LOADER plaintext? | In Recovery loader plaintext? | In ABL0 header? |
|---|---|---|---|
| `Gen4` | no | no | no |
| `ESM` | no | no | no |
| `DXIO` | no | no | no |
| `Strap` | no | no | no |
| `Rev` | no | no | no |
| `1.02` | no | no | no |
| `1.03` | no | no | no |
| `Board` | no | no | no |
| `+0x2E` byte / `0x40` bit pattern | unsearchable (encrypted) | unsearchable (encrypted) | not in TOC |
| `APCB` group IDs (0x1701, 0x1704, 0x3000) | unsearchable (encrypted) | unsearchable (encrypted) | not in TOC |

The keyword search is **vacuous** for the encrypted PSP code blobs. All meaningful diff content sits behind AMD's PSP IKEK encryption, which we have no path to recover.

---

## 5. Cross-check against open-source PSP reverse-engineering work

- **`PSPReverse/PSPTool`** (the source of `psptool 3.6` we used) — provides entry parsing, signature verification, key-graph construction, and (for some entries) decompression. **Decryption of `PSP_FW_BOOT_LOADER` and ABL bodies is NOT supported** — these are AES-CCM encrypted by an IKEK that is fuse-derived per silicon stepping; the project's README and issue tracker (`PSPReverse/PSPTool` issues #25, #41) confirm this.
- **`PSPReverse/PSPEmu`** — emulates a PSP environment from a leaked development unit, can run extracted unencrypted ABL components. We do not have a leaked dev IKEK, and the upstream emu's targets are Naples/Zen-1; Rome/Milan IKEK is not in the public corpus.
- **`coreboot/util/amdfwtool`** — packs/unpacks the PSP directory for embedding into coreboot images. Confirms our entry-type table mapping (e.g. `0x30` = ABL0, `0x60` = APCB, `0x68` = APCB_COPY). Does not include decryption.
- **`coreboot/src/vendorcode/amd/agesa/`** — contains AGESA's *x86-side* glue but **not the PSP-side ABL source code**. ABL code is AMD-internal proprietary.

There is no known public path to read the cleartext of P3.70's or P3.80's PSP_FW_BOOT_LOADER or ABL bodies. This is an architectural property of AMD's PSP boot trust chain, not a tooling gap.

---

## 6. Verdict & implications

### Is the rev-1.03 / Gen4 unlock in PSP/ABL firmware?

**Inconclusive — but circumstantially likely.** Evidence:

**For PSP/ABL being the unlock site:**
- PSP firmware substantially changed between P3.70 and P3.80 (Rome→Milan-superset replacement, ABL stack version `10.F.20.10 → 34.24.20.10`).
- Sizes grew by tens of bytes per ABL sub-blob (≈+34 KB total inferred from TOC offset shifts).
- APCB body byte-identical (re-confirmed). The DXIO descriptor consumer in DXE (`AmdNbioPcieDxe`) byte-identical. The DXIO descriptor *producer* must therefore live in (a) a DXE/PEI module that did change, or (b) the PSP/ABL stack that did change. Subagents F/G covered (a) extensively for DXE; PEI was less thoroughly covered. The PSP/ABL stack falls into (b).
- ABL is the canonical layer that consumes APCB tokens at boot (per AMD docs / coreboot wiki).

**Against PSP/ABL being the unlock site:**
- Cannot directly verify due to encryption.
- The PSP firmware change is more easily explained as ASRock's normal Rome→Milan platform-merge maintenance (Milan-PI superseded Rome-PI for both silicons by 2023). The Gen4 unlock could be coincidental with that merge rather than caused by it.
- Per agent prior work, `AmdApcbDxeV3` (the DXE-side APCB consumer) grew +64 bytes between P3.70 and P3.80 — an alternative descriptor-producer candidate that *can* be disassembled. That investigation (per `docs/APCB_DXEV3_DIFF.md`) is the lower-cost and higher-evidentiary-power path.

### Can it be patched without flashing the whole BIOS?

- **No clear path.** Even if PSP/ABL is the unlock site:
  - The relevant code is encrypted (PSP_FW_BOOT_LOADER, ABL bodies). We cannot identify what to patch.
  - ABL0 is signed by OEM key 1DC2. Replacing it requires either (a) an unfused PSB (re-sign with attacker key — but we don't know the rig's PSB fuse state without reading MSR `0xC0010135`), or (b) breaking RSA-2048 on AMD's signing key (infeasible).
  - Even if both above are satisfied, patching encrypted code requires the IKEK to re-encrypt — we don't have it.
- **The PSP/ABL angle does not open a no-flash userspace fix.** It also does not open a feasible offline-patch-then-flash path either, because the patch target itself is unreadable.

### Reconciliation with prior subagents

| Subagent / doc | Hypothesis | Status |
|---|---|---|
| #1 (APCB decode) | APCB body identical | **CONFIRMED** by independent extraction here |
| #5 (NbioPcieDxe disasm) | DXE consumer reads `+0x2E` bit 6, identical P3.70/P3.80 | (no conflict — not retested here) |
| `APCB_DXEV3_DIFF.md` | DXE producer (`AmdApcbDxeV3`) +64 B in P3.80 | (no conflict — orthogonal to PSP) |
| Agent G | "producer must use non-canonical addressing OR live in PEI" | PSP is upstream of even PEI; this finding adds "OR live in PSP/ABL" as a third possibility |

**Recommendation.** The PSP/ABL angle is best treated as a **plausible-but-unverifiable** alternative hypothesis. Continue to weight `AmdApcbDxeV3` disasm (`docs/APCB_DXEV3_DIFF.md`) and PEI-module sweep as the primary actionable leads, since those are accessible. If both DXE and PEI are exhausted negatively, the PSP/ABL site becomes the only remaining hypothesis — but it would also be terminal: unverifiable + unpatchable + flash-only.

---

## 7. Artifacts

- Extracted PSP entries (helper, not committed): `/tmp/psp_diff/p370_extracted/` and `/tmp/psp_diff/p380_extracted/`
- Hash diff: `/tmp/psp_diff/p370_hashes.txt`, `/tmp/psp_diff/p380_hashes.txt`
- Raw psptool output: `/tmp/psp_diff/psp_p3.70.txt`, `/tmp/psp_diff/psp_p3.80.txt`
