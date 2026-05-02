# Planned Phase 2 subagent dispatches

These 8 dispatches were drafted on 2026-04-27 to broaden the search after the prime
suspects (`AmdApcbDxeV3`, `CbsSetupDxeSSP`) were eliminated as the Gen4-unlock source.
They were not run on the original analyst machine due to performance constraints;
re-dispatch on the next machine to pick up where the project left off.

**All 8 are independent and parallelizable.** Each writes a reusable script into
`scripts/`, contributes to `scripts/lib/` where appropriate, and produces a findings
document in `docs/`.

## Operating context every subagent needs

Each prompt should start with:
> Read `~/Desktop/romed8/CLAUDE.md`, `~/Desktop/romed8/README.md`, and
> `~/Desktop/romed8/BIOS_LATEST.md` first. This is a git repo at
> `git@github.com:Banandana/romed8-2t-bios-analysis.git`. Your work must be reusable
> — write parameter-driven scripts, not one-shot agent logic. Use the shared library
> at `scripts/lib/` (`versions.py`, `ffs.py`, `pe32.py`). Don't push anything to the
> rig.

## The 8 dispatches

### 1. `module_sweep` — full PE32 hash/size diff across all 5 versions

**Goal:** identify every module that changed between P3.70 and P3.80 (~278 modules in
the active volume; existing `scripts/diff_versions.py` only checks ~30 named ones).

**Deliverable:**
- `scripts/module_sweep.py` — usage `python3 scripts/module_sweep.py [ver_a ver_b]`. Writes a markdown table of all PE32 hashes/sizes per version. With two args: lists only modules that differ, with size deltas.
- Run for P3.70 vs P3.80; output `docs/MODULE_SWEEP_P3.70_vs_P3.80.md`. Highlight modules whose name contains `Pcie`, `Nbio`, `Dxio`, `Cpm`, `Cbs`, `Apcb`, `Oem`, `Asrock`, `Board`, `Platform`, `Strap`, or `BmC`.

### 2. `disasm_diff` — `AmdNbioBaseSspDxe` P3.70 vs P3.80

**Goal:** is this module the producer of bit 6 of byte `+0x2E` in the per-port DXIO descriptor?

**Deliverable:**
- `scripts/disasm_diff.py` (new, reusable). Usage: `python3 scripts/disasm_diff.py <module_name> <ver_a> <ver_b> [-o out.md]`. Outputs hash check, function-listing diff, string diff, bit-set pattern search (for `or byte [reg+0x2E], 0x40` and variants), descriptor-offset references.
- Run for `AmdNbioBaseSspDxe` between P3.70 and P3.80. Output `docs/DISASM_AmdNbioBaseSspDxe.md`.

### 3. PEI: `AmdCpmPcieInitPeim` diff

**Goal:** rev-strap detection most plausibly happens in PEI (early boot, before DXE). `AmdCpm*` is AMD's Common Platform Module — OEM-customizable.

**Deliverable:** Use `scripts/disasm_diff.py` (parallel agent #2 is creating it) to diff `AmdCpmPcieInitPeim` P3.70 vs P3.80. Output `docs/DISASM_AmdCpmPcieInitPeim.md`. Look for: bit-set pattern `or byte [reg+0x2E], 0x40`, MMIO reads to `0xfedXXXXX` / `0xfd0XXXXX` / GPIO ranges, APCB token getter calls, `Gen4` / `ESM` / `Strap` / `Rev` / `Board` / `1.02` / `1.03` strings.

### 4. PEI: `AmdCheckBmcPciePei` diff

**Goal:** the BMC's PCIe path is suggestive — the lone Gen4-capable root port `40:01.3` may be related. Rev-strap detection could live here.

**Deliverable:** Use `scripts/disasm_diff.py` for `AmdCheckBmcPciePei` P3.70 vs P3.80. Output `docs/DISASM_AmdCheckBmcPciePei.md`.

### 5. PEI: `AmdNbioPciePei` diff

**Goal:** PEI sibling of `AmdNbioPcieDxe`. The descriptor list might be initially built here in PEI before DXE consumers see it.

**Deliverable:** Use `scripts/disasm_diff.py` for `AmdNbioPciePei` P3.70 vs P3.80. Output `docs/DISASM_AmdNbioPciePei.md`.

### 6. ASRock OEM-shim hunt

**Goal:** ASRock may ship per-board DXE/PEI modules with names containing `AmdCpmOemInit`, `BoardId`, `Platform`, `Asrock`, `OEM`, etc. If any such module changed between P3.70 and P3.80, it's a strong Gen4-unlock candidate.

**Deliverable:**
- `scripts/oem_shim_hunt.py` — searches the active volume for modules matching the suggestive names; for each, hashes both versions and reports differences.
- Run, write `docs/OEM_SHIM_HUNT.md` with findings + disasm of any suspicious change.

### 7. Bit-pattern global search

**Goal:** since the producer module isn't yet known, search the **entire** P3.70 and P3.80 BIOS images for any `or byte [reg+0x2E], 0x40` pattern (and the more specialized `bts byte [reg+0x2E], 6`). Whichever module contains it is the producer.

**Deliverable:**
- `scripts/find_bit_pattern.py <pattern_hex> [versions...]` — generic byte-pattern hunter. Loads each module's body.bin and searches. With `--mode bit-set`, emits all the common encodings of `or byte [reg+disp8], imm8` for a given (disp, imm) pair.
- Run for `[+0x2E], 0x40` across all versions. Output `docs/BIT_PATTERN_SEARCH.md`. The hits localize the producer.

### 8. BMC 2.08 + P3.80 IPMI flash compatibility (web research)

**Goal:** decisive operational gating for any flash decision. The 45HomeLab thread documented BMC 2.08 + P4.10 IPMI-flash interlock; whether P3.80 has the same problem is unconfirmed.

**Deliverable:** `docs/BMC_COMPAT.md`. Sources: ASRock Forum TID 24737, 45HomeLab forum, ASRock Rack support docs, community Rome / EPYC threads. Determine: does BMC 2.08 + P3.80 IPMI-flash work? If interlock exists, what's the workaround (BMC update first; UEFI shell flash; external SPI programmer)?

---

## After all 8 complete

Synthesize into a final Phase 2 report:
1. **Where is the Gen4 unlock?** (one of items 1–7 should localize it)
2. **What's the gating predicate?** (unconditional vs board-rev MMIO vs APCB-token-driven vs other)
3. **Can BMC 2.08 + P3.80 IPMI-flash safely?** (item 8)
4. **Decision tree for the rig:** flash-yes / flash-with-caveats / flash-no.

Update `BIOS_LATEST.md` with the synthesis. Push to the rig's project tree **only if explicitly authorized** by the user.
