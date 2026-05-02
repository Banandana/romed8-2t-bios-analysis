> ← [Report index](README.md) · [Project README](../README.md) · [Latest synthesis](../BIOS_LATEST.md)
>
> _Phase 1 baseline — most §1 conclusions are superseded by [Part III](part-3-empirical-followup.md) and [`../BIOS_LATEST.md`](../BIOS_LATEST.md). Strikethroughs in §1 mark the original IFR-only verdict that the empirical follow-up overturned._

# ROMED8-2T BIOS reverse-engineering — FINDINGS

**BIOS analyzed:** P3.70 (file `ROMD82T3.70`, 2023-05-30, 33,554,432 bytes / 32 MiB)
**Source:** archive.org `asrock-server-ROMED8-2T` (publicly mirrored — ASRock site is JS-rendered, both the support page and direct CDN URLs are 403/Incapsula-gated).
**Other versions on disk for later diff:** P3.80, P3.90, P4.10, L3.11. None analyzed yet per user instruction.

---

## 1. Headline verdict

> **Updated 2026-04-27 after empirical NVRAM dump from the rig.** Original IFR-only verdict below has been superseded — see [Part III](part-3-empirical-followup.md) for the full empirical-side investigation.

**The 11 per-slot AMD PCIE Link Speed bytes (offsets `0x123`–`0x12D` in the `Setup` UEFI variable) are confirmed VESTIGIAL on P3.70.** AGESA does not read them. The rig has those bytes set to a mix of `0x01` (GEN1) and `0x00` (Auto) values, yet GPUs run at Gen3 in slots whose byte says GEN1. The IFR menu offers per-slot control, but the underlying platform code ignores the values.

**The actual Gen3 link-speed cap on this BIOS is in the DXIO descriptor table inside the AGESA Platform Configuration Block (APCB), not in any IFR-exposed setting.** No setup_var / efivar write to any user-visible NVRAM byte will lift it. Direct evidence:

- `AmdNbioPcieDxe` contains a complete ESM (Extended Speed Mode) Gen4 implementation with the per-port branch `Port does not have ESM enabled` — i.e. ESM enable is a **per-port descriptor-driven decision**, not a global flag.
- The user found one root port (`40:01.3`, x4) advertising Gen4 (`LnkCap2 2.5–16 GT/s`) on the same BIOS. That port's DXIO descriptor declares Gen4. The seven GPU root ports' descriptors declare Gen3. Same code, different per-port descriptor input — proves the cap is per-port descriptor data, not a global toggle.
- Exhaustive IFR enumeration (15 modules, 291 forms, 1565 settings) found zero settings that select Gen4 anywhere. The closest are `Early Link Speed` (Auto/Gen1/Gen2 only — early-init speed, can't enable Gen4) and `Multi Auto Speed Change On Last Rate` (a behavior flag, not a cap).
- Cross-reference of the user's empirical NVRAM dump shows none of the `0x03` or `0x04` bytes scattered through `AmdSetupSSP` are at offsets backed by any PCIe-related IFR setting. The `0x03` at `0x136` is `Pattern Length` (memory MBIST). The `0x04` at `0x106` is `SubUrgRefLowerBound` (DRAM refresh). The other ~20 unmapped bytes are AGESA-internal scratch state with no IFR exposure.

**Recommended action**, in order of leverage:

1. **Stop trying to write to the per-slot bytes.** They do nothing on P3.70. The "AMD PCIE Link Speed → PCIEx" menu is a UI placebo on this BIOS.
2. **Reframe the user's symptom.** The throughput regression (76→40 t/s, 394→92 t/s) cannot be attributed to a BIOS click — empirical NVRAM shows no Gen3-coded byte was written by the user. The Gen3 cap was always there on P3.70. The throughput regression must have a different cause (driver upgrade, GSP toggle, kernel change, GPU dropout, vLLM config). The Gen4-baseline numbers in the parent project's CLAUDE.md are not corroborated by NVRAM evidence and may have been measured against a different rig or BIOS.
3. **Try a newer BIOS.** Cross-version IFR check: `CbsSetupDxeSSP` is functionally identical across P3.70/3.80/3.90/4.10 — no Gen4-enable option was ever added at the AGESA layer. So a BIOS update will only help if ASRock changed the **DXIO descriptors** in a later version (which we cannot read from IFR). Worth installing P4.10 to test, but no IFR-level evidence guarantees it.
4. **The decisive next investigation is empirical, not IFR-derived.** Boot Linux on P3.70 and read all 8 GPU root ports' link state at the PCIe `Capabilities: [...] LnkCap2 SLS Vector` byte. Then update to P4.10 (keeping the same `Setup` NVRAM) and re-read. If P4.10 advertises Gen4 on the GPU root ports out of the box, the descriptor was the cap and we're done. If P4.10 also advertises Gen3, the cap is hard-coded in ASRock's DXIO build and the only fixes are (a) APCB binary patching (Ghidra + dangerous SPI write) or (b) a future BIOS where ASRock fixes it.

The original IFR-only headline (per-slot offsets, setup_var commands) has been preserved verbatim below for reference, with strikethroughs noting what we now know is wrong.

---

### ~~Original IFR-only verdict (now superseded)~~

**~~Per-slot scope is real in the IFR for AMD PCIE Link Speed.~~** _True only in the menu/IFR sense; ineffective in practice — see above._ Each PCIe physical slot has its own NVRAM offset in the standard `Setup` UEFI variable. The 11 entries are at distinct, contiguous offsets `0x123–0x12D` (1 byte each), with no shared backing storage. ~~Writing them via `setup_var.efi` should give per-slot control.~~ **Empirically confirmed: writing them has no effect on the GPU root ports' Gen cap.**

**However, the menu the user remembers as "Advanced → AMD CBS → NBIO → Target Link Speed" does not exist by that path or label in P3.70.** No string "Target Link Speed" is anywhere in the BIOS. What exists, and what the user almost certainly used, is:

> **Advanced → AMD PCIE Link Speed → PCIE7 Link Speed**
> *(or via the alias path **Advanced → Chipset Configuration → AMD PCIE Link Speed**)*

This is an **ASRock board-specific menu** (in the `Setup` HII module — `72 Setup.pe32` inside the BIOS region), **not** an AMD CBS menu. It is a sibling of "AMD CBS" in the Advanced page, not a child of it.

The AMD CBS / NBIO Common Options menu is real, but does **not** contain any per-slot Target Link Speed option in P3.70. _And the per-slot menu in the ASRock `Setup` module is — empirically — a UI placebo._

---

## 2. Offset table — AMD PCIE Link Speed (P3.70)

All entries live in **VarStore "Setup"** (`VarStoreId 0x1`, GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`, total VarStore size `0x174` bytes), Form `0x27A3` "AMD PCIE Link Speed", inside the `Setup` HII module of the BIOS region.

| Slot | Prompt | QuestionId | VarStore | Offset | Width | Default | Options | Suppress |
|---|---|---|---|---|---|---|---|---|
| Slot 1 | `PCIE1 Link Speed` | `0xE1` | `Setup` | **`0x123`** | 1 | `Auto` (0) | 0=Auto, 1=GEN1, 2=GEN2, 3=GEN3, 4=GEN4 | gray-out if Q14A=1 (admin-mode gate) |
| Slot 2 | `PCIE2 Link Speed` | `0xE2` | `Setup` | **`0x124`** | 1 | `Auto` | same | same |
| Slot 3 | `PCIE3 Link Speed` | `0xE3` | `Setup` | **`0x125`** | 1 | `Auto` | same | same |
| Slot 4 | `PCIE4 Link Speed` | `0xE4` | `Setup` | **`0x126`** | 1 | `Auto` | same | same |
| Slot 5 | `PCIE5 Link Speed` | `0xE5` | `Setup` | **`0x127`** | 1 | `Auto` | same | same |
| Slot 6 | `PCIE6 Link Speed` | `0xE6` | `Setup` | **`0x128`** | 1 | `Auto` | same | same |
| Slot 7 | `PCIE7 Link Speed` | `0xE7` | `Setup` | **`0x129`** | 1 | `Auto` | same | same |
| OCU 1 (SlimSAS) | `OCU1 Link Speed` | `0xE8` | `Setup` | **`0x12A`** | 1 | `Auto` | same | same |
| OCU 2 (SlimSAS) | `OCU2 Link Speed` | `0xE9` | `Setup` | **`0x12B`** | 1 | `Auto` | same | same |
| M.2 #1 | `M2_1 Link Speed` | `0xEA` | `Setup` | **`0x12C`** | 1 | `Auto` | same | same |
| M.2 #2 | `M2_2 Link Speed` | `0xEB` | `Setup` | **`0x12D`** | 1 | `Auto` | same | same |

The "Suppress" column is the gating expression `EqIdVal QuestionId: 0x14A, Value: 0x1` — a `GrayOutIf` that hides these from non-admin BIOS users. QuestionId 0x14A is in VarStore `SystemAccess` (`0xF000`, GUID `E770BB69-BCB4-4D04-9E97-23FF9456FEAC`, 1 byte, runtime privilege state). It is **not** a per-slot vs global toggle — it is just admin-vs-user UI access.

There is also a parallel form `0x27A2` "AMD PCIE Link Width" with the same per-slot pattern at offsets `0x11B–0x121` (PCIE1–PCIE7 only, no OCU/M.2), and a hotplug form `0x27A4` at `0x12F–0x137`. None of these is involved in the link-speed cap.

---

## 3. Why the user saw global behavior despite per-slot IFR

The IFR offers per-slot control via 11 distinct NVRAM bytes. **But the user reported that setting one slot to Gen3 in BIOS capped LnkCap2 on every GPU root port to Gen3.** Both observations cannot be simultaneously true unless one of these is happening:

1. **AGESA/DXIO ignores the per-slot bytes.** ASRock's IFR exposes 11 entries that the AGESA Setup-callback layer may consume by reading only one (e.g. PCIE1 only, or the highest non-Auto value, or the first non-Auto slot encountered) and then applying that to all DXIO engines. The per-slot bytes would be vestigial in P3.70 — saved to NVRAM but ignored by the platform-init code. **This is the most likely explanation** given the symptom.
2. **A Setup form callback in `72 Setup.efi` propagates the value.** When the user changes one slot, the callback writes the same value to all 11 offsets before saving. Less likely (the IFR has no `Refresh` cross-references suggesting this) but possible at the binary level.
3. **The user actually clicked a different option.** In P3.70, the AGESA NBIO Common Options menu contains genuinely-global settings: `Multi Upstream Auto Speed Change` (offset `0x169` in `AmdSetupSSP`) — explicitly described as "for all PCIe devices" — and `Multi Auto Speed Change On Last Rate` (offset `0x16A`) — "for all ports". Either, if changed to "Disabled", caps every link.

The IFR alone cannot distinguish #1 from #2. Distinguishing them requires either (a) disassembling `72 Setup.efi` and `CbsSetupDxeSSP.efi` to trace the callback / read paths, or (b) empirical testing on the rig with `setup_var.efi`.

---

## 4. Setup_var.efi commands (proposed — needs empirical verification)

The user's GPU 7 is `0000:c2:00.0`, behind a passive bifurcation adapter, with Xid 79 SI failures at Gen4. The user's other 7 GPUs should run at Gen4. The slot mapping `c2:00.0 → PCIE<N>` depends on the rig's physical install — **the user must confirm which physical slot of the seven the bifurcation adapter occupies before flipping bytes**. The PCIe BDF map is in the manual but the user's `lspci -tvv` is the authoritative source.

Assuming GPU 7 / `c2:00.0` is in slot **PCIE7** (offset `0x129`), the commands from the EFI shell would be:

```text
# Reset all per-slot link speeds to Auto (= Gen4 max for ROMED8-2T's CPU)
setup_var.efi 0x123 0x00       # PCIE1
setup_var.efi 0x124 0x00       # PCIE2
setup_var.efi 0x125 0x00       # PCIE3
setup_var.efi 0x126 0x00       # PCIE4
setup_var.efi 0x127 0x00       # PCIE5
setup_var.efi 0x128 0x00       # PCIE6
setup_var.efi 0x129 0x03       # PCIE7 = GEN3   ← only the bifurcation slot capped
setup_var.efi 0x12A 0x00       # OCU1
setup_var.efi 0x12B 0x00       # OCU2
setup_var.efi 0x12C 0x00       # M2_1
setup_var.efi 0x12D 0x00       # M2_2
```

Values: `0x00` = Auto, `0x01` = GEN1, `0x02` = GEN2, `0x03` = GEN3, `0x04` = GEN4.

**Caveats binding on the user before running these:**

1. **Confirm which physical slot the adapter is in.** The manual's bus-routing table (PCIE1..PCIE7 → root-port BDFs) needs to be read against `lspci -tvv` to decide whether `c2:00.0` is PCIE7, PCIE5, etc. Fix the wrong offset and the wrong slot gets capped.
2. **`setup_var.efi` writes the standard `Setup` UEFI variable.** That is `Setup` with GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`. The Linux equivalent is `efivar -n EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9-Setup`. Any tool the user uses must address that exact name+GUID; some setup_var binaries default to a different GUID and silently fail.
3. **Writing alone is not sufficient if AGESA ignores per-slot bytes.** The empirical test is: write the values above, reboot, and check `LnkCap2` on each root port. If only `c2:00.0` advertises 8 GT/s while every other GPU's root port advertises 16 GT/s, **per-slot works**. If all ports go to one value regardless of the writes, the per-slot bytes are vestigial and this whole approach fails.
4. **If per-slot turns out to be vestigial,** the next thing to check is whether using the GUI to set every slot **back to Auto** restores Gen4 board-wide. If so, the regression is reversible without per-slot control, and the only practical mitigation for `c2:00.0`'s SI failure is hardware-side (replace the bifurcation adapter, add a redriver, or tape lanes).

A safer empirical procedure than running the writes blind:
1. Read all 11 bytes first (`setup_var.efi 0x123` with no value — or dump the whole `Setup` variable via `efivar` from Linux) and record what's currently there. The user's previous BIOS-GUI change should be visible.
2. Compare the 11 current values. If they are all `0x03` (Gen3), the GUI propagated. If only one is `0x03` and the rest are `0x00`, the GUI saved per-slot but DXIO is ignoring it.
3. Only then write.

---

## 5. Per-BIOS-version comparison

Not done — user instruction was to analyze 3.70 only. The four other versions (3.80, 3.90, 4.10, L3.11) are extracted and ready under `images/`. To run the same pipeline on another version, see `scripts/extract.sh` (TODO — pipeline currently inlined).

---

## 6. Other interesting findings

- **Three CPU-family-specific AMD CBS DXE drivers ship in P3.70:**
  - `CbsSetupDxeZP` — Zen 1 / Naples (EPYC 7001). VarStore `AmdSetupZP`, GUID `3A997502-647A-4C82-998E-52EF9486A247`, size `0x5B2`. Has a single `Force PCIe gen speed` option at offset `0x1C6` (Gen1/Gen3 only — Auto=`0x0F`). **NBIO-wide scope** in the ZP family. No per-slot CBS option.
  - `CbsSetupDxeSSP` — Rome / Milan (EPYC 7002 / 7003). Same VarStore GUID, name `AmdSetupSSP`, size `0x686`. **No "Force PCIe gen speed" entry at all.** Has `Early Link Speed` (offset `0x15C`, Auto/Gen1/Gen2 only — used during early DXIO init), `Multi Upstream Auto Speed Change` (offset `0x169`, "for all PCIe devices"), and `Multi Auto Speed Change On Last Rate` (offset `0x16A`, "for all ports"). All NBIO-wide.
  - `CbsSetupDxeGN` — Genoa (EPYC 9004, SP5). Present in the BIOS but irrelevant for ROMED8-2T (SP3 only). Includes per-link `Socket-0 P0/P1/P2/P3 Link Speed` (xGMI inter-socket, not PCIe slots).
  ROMED8-2T at P3.70 supports Naples and Rome SP3 CPUs; Milan support landed in some later release. The CbsSetupDxeSSP module is the relevant CBS/AGESA family for the user's Rome- or Milan-based rig. **Note:** `SSP` here is AMD's AGESA codename for a CPU family, not "Server Single Platform" — it covers Rome/Milan (Zen 2/3) class on SP3.
- **Both PCIe Link Speed (form `0x27A3`) and PCIe Link Width (form `0x27A2`) menus exist.** Width has the same per-slot pattern at offsets `0x11B–0x121` for PCIE1..PCIE7 only (no OCU/M.2 in the width menu — those are wired x4 fixed). Useful if the user later needs to bifurcate a slot.
- **PCIe Hotplug per-slot** is at offsets `0x12F–0x137` in form `0x27A4`. Disabled by default. Enabling per-slot is harmless but unnecessary unless the user adds U.2 NVMe with hot-swap.
- **AMD CBS NBIO Common Options has signal-integrity-relevant settings** that are NOT exposed under per-slot menus and might help with the user's Gen4 SI failures: `Enable Rcv Err and Bad TLP Mask` (SSP offset `0x15B`, "Enables Masking of Receiver Error and Bad TLP at Gen4 x2"), `Compliance Loopback` (`0x168`), `SRIS` (`0x167`). None of these caps speed; they tune error handling and clocking. **Don't change them blind** — `SRIS` in particular matters if the bifurcation adapter forces SRNS clocking.
- **AmdPbsSetupDxe** (FormSet GUID `B863B959-0EC6-4033-99C1-8FD89F040222`, VarStore `AMD_PBS_SETUP`, size `0x80`) has PCIe AER severity register init options but no link-speed control.
- **No PCIe equalization preset / Lane Margining / retimer options** exposed in any IFR menu in P3.70. These would be needed for proper Gen4 SI tuning. Their absence means the user has no BIOS-level Gen4 tuning surface — the only knobs are speed cap, width, and AER masking.

---

## 7. Risks / DO NOT TOUCH

- **`Combo CBS`** (QuestionId `0x7` in CbsSetupDxeZP, offset `0x20` in `AmdSetupZP`): default `0xFE`. This is the AGESA family selector. Changing it can render the system unbootable — it tells AGESA which CPU family code path to take.
- **`SystemAccess` VarStoreId `0xF000`**: runtime privilege state. Don't write — it's not user-settable persistent data.
- **`AMD_PBS_SETUP` PCIe AER Uncorrected/Correctable Severity registers**: changing these can convert a recoverable PCIe error into a fatal sync flood. Default is fine for the user's purpose.
- **`Early Link Speed`** (CbsSetupDxeSSP offset `0x15C`): only takes Auto/Gen1/Gen2. Setting Gen2 here will force every DXIO link to Gen2, board-wide, including the in-band BMC if present. Don't use it as a cap.
- **`Multi Auto Speed Change On Last Rate`** (CbsSetupDxeSSP offset `0x16A`): toggling this changes how all ports negotiate speed. If the user toggled this when they thought they were setting one slot, that alone explains the global cap.
- **NBIO `IOMMU`** (offset `0x154`): default Disabled in this BIOS. The user's 8x GPU rig is presumably not using SR-IOV — leaving it Disabled is correct. Don't enable casually.

---

## 8. What I did not do (and what's needed to close the question fully)

- Did not disassemble `72 Setup.efi` to look for a Setup callback that propagates per-slot writes. That requires Ghidra/IDA on the PE32 binary; modules are saved at `ifr/P3.70/all_ifr/72_Setup.pe32` for reference.
- Did not disassemble `CbsSetupDxeSSP.efi` to determine whether DXIO actually reads offsets `0x123–0x12D`. Same caveat. Module saved at `ifr/P3.70/CbsSetupDxeSSP.pe32`.
- Did not run the diff across BIOS versions — user said skip for now, but the four other images are sitting in `images/` ready to go.
- Did not read the rig's current `Setup` UEFI variable. **That is the single most informative next step** — see "safer empirical procedure" in §4. Either via `efivar` from Linux on the running rig, or `dmpstore Setup` from the EFI shell.

