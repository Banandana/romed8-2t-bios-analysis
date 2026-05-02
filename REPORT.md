# ROMED8-2T BIOS reverse-engineering — FINDINGS

**BIOS analyzed:** P3.70 (file `ROMD82T3.70`, 2023-05-30, 33,554,432 bytes / 32 MiB)
**Source:** archive.org `asrock-server-ROMED8-2T` (publicly mirrored — ASRock site is JS-rendered, both the support page and direct CDN URLs are 403/Incapsula-gated).
**Other versions on disk for later diff:** P3.80, P3.90, P4.10, L3.11. None analyzed yet per user instruction.

---

## 1. Headline verdict

> **Updated 2026-04-27 after empirical NVRAM dump from the rig.** Original IFR-only verdict below has been superseded — see Part III for the full empirical-side investigation.

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


---
---

---

# Part III — Empirical follow-up (added 2026-04-27 after rig NVRAM dump)

The rig was queried for runtime PCIe state and live NVRAM contents. Findings contradicted the IFR-only conclusions of Parts I–II in places and produced a sharper picture of where the Gen3 cap actually comes from. This Part III documents what changed and answers the six specific drilldown questions raised in the handoff.

## Empirical context (summary)

- ROMED8-2T, EPYC SP3, BIOS **P3.70**, BMC 2.08, board mfg 2025-08-29 → ~certainly hw rev 1.03 (rules out rev-strap-Gen3 theory).
- 8× RTX 3090 across PCIE1–6 + GPU 7 (`0000:c2:00.0`) behind a passive bifurcation card (almost certainly slot PCIE7).
- Driver `nvidia` 595.58.03 (proprietary), GSP firmware **disabled** (`NVreg_EnableGpuFirmware=0`), `pcie_aspm=off`, kernel 6.19.12-arch1-1.
- `lspci -vv`: all 8 GPU root ports report `LnkCap2: Supported Link Speeds: 2.5–8GT/s` — root port itself is Gen3-capped.
- One non-slot root port (`40:01.3`, x4) reports `LnkCap2: 2.5–16GT/s` — proving Gen4 root-port advertisement IS achievable on this CPU/BIOS, just not for the GPU root ports.
- GPU side `LnkCap2: 2.5–16GT/s` — devices are Gen4-capable; host caps to Gen3.
- All 11 per-slot bytes at `Setup:0x123`–`0x12D` are at `0x00`/`0x01`. **None at `0x03`.** Slots set to GEN1 (e.g. `0x129 = 0x01` for PCIE7) still host Gen3-running GPUs → those bytes are observed-vestigial in P3.70.

Throughput observation (Qwen3.5-122B-A10B AWQ, TP=8, vLLM v0.19.0): single-stream 40 tok/s, concurrent ×16 92 tok/s aggregate. Parent project's CLAUDE.md previously recorded 76 / 394 t/s — those numbers may always have been measured at Gen3 (no Gen4-confirmed baseline exists). Treat the regression as not corroborated by BIOS evidence.

---

## Q1 — Decode of `0x169` and `0x16A` in `AmdSetupSSP`

Both options live in form `0x7004` "NBIO Common Options" inside the `CbsSetupDxeSSP` FormSet (FormSet GUID `7A6A3896-4AF0-45E5-BA63-89357FBD6D63`, VarStore `AmdSetupSSP`, GUID `3A997502-647A-4C82-998E-52EF9486A247`, size `0x686`).

### `0x169` — **Multi Upstream Auto Speed Change** (QuestionId `0xFB`)

| Value | Option | Default? |
|------:|--------|---------|
| `0x00` | Disabled | |
| `0x01` | Enabled | |
| `0x0F` | Auto | **default** |

Help text (verbatim): *"Defines the setting of this feature for all PCIe devices. 'Auto' uses the DXIO default setting of 0 for Gen1 and 1 for Gen2/3."*

- `0x0F` is AGESA's "Auto / DXIO decides" sentinel, not "uninitialized". The byte is at its DefaultId 0 default. AMI's "Optimized Defaults" would write `0x0F`.
- This option **does not target a Gen**. It controls whether the *speed-change feature* itself runs during link training, with the DXIO default behavior split between Gen1 and Gen2/3 ports. Setting it Disabled would PREVENT any speed change above the initial training rate — i.e. force everything to Gen1 if Gen1 was the start rate. That's the opposite of "force Gen4".
- Conclusion: **not a Gen-cap source.** The rig's `0x0F` value is AGESA-default and correct.

### `0x16A` — **Multi Auto Speed Change On Last Rate** (QuestionId `0xFC`)

| Value | Option | Default? |
|------:|--------|---------|
| `0x00` | Disabled — use highest data rate ever advertised | |
| `0x01` | Enabled — use last data rate advertised | |
| `0xFF` | Auto | **default** |

Help text (verbatim): *"Force PCIe link training speed to last advertised for all ports. Disabled = Use highest data rate ever advertised. Enabled = Use last data rate advertised."*

- `0xFF` is AGESA's "Auto" sentinel, default. Rig is at default.
- Controls retrain-after-recovery behavior. Not a target-rate setting; cannot raise a Gen3-capped port to Gen4.
- Conclusion: **not a Gen-cap source.** Default is correct.

### Why neither would lift Gen3 to Gen4

Both options are **behavior modifiers around an already-trained link's max speed**, not target-speed selectors. There is no IFR-exposed `OneOf` anywhere in P3.70 with options including "Gen4" for general PCIe ports. The closest phrase is in `CbsSetupDxeSSP` Help text: `Enable Rcv Err and Bad TLP Mask` says *"Enables Masking of Receiver Error and Bad TLP at Gen4 x2"* — that's an error-handling tweak that **assumes** Gen4 is happening, not a Gen4-enable.

The rig's bytes for both are at AGESA defaults. **Changing them is not the path.**

---

## Q2 — The actual link-speed-cap source for AGESA SSP

There is **no IFR-exposed cap source.** This is a substantive finding, not a "haven't found it yet."

Searches performed across P3.70:

- **Every `OneOf Prompt` / `Numeric Prompt` / `CheckBox` matching** any of: `Speed`, `PCIe`/`Pcie`, `Gen[1-9]`, `DXIO`/`Dxio`, `PHY`, `Equali[sz]`, `Margin`, `Force`, `Target`, `Cap`, `Override`, `Max.*Link`, `Link.*Max`, `ESM`, `Extended Speed`. Files searched: `CbsSetupDxeSSP.txt`, `CbsSetupDxeZP.txt`, `CbsSetupDxeGN.txt`, `72_Setup.txt` (entire ASRock board form set), `52_AmdPbsSetupDxe.txt`, `75_ServerMgmtSetup.txt`, `89_PciDynamicSetup.txt`, `91_PciOutOfResourceSetupPage.txt`, `110_EventLogsSetupPage.txt`. Total IFR coverage: **15 modules, 291 forms, 1565 settings.**
- Result: **zero settings whose option enum includes Gen4.**
- Closest non-vestigial settings:
  - `CbsSetupDxeSSP:0x15C` `Early Link Speed` — Auto/Gen1/Gen2 only (intentionally limited to early-init speeds).
  - `Setup:0xC6` `PCIe Link Training Type` (1-Step / 2-Step) — not a cap.
  - `Setup:0xC7` `PCIe Compliance Mode` — not a cap.
  - The 11 per-slot Setup:0x123–0x12D entries — vestigial.

Cross-version sanity check: extracting and grepping `CbsSetupDxeSSP` from P3.80 / P3.90 / P4.10 produces identical SSP IFR — same VarStore size (`0x686`), same option counts, no new Gen4 setting introduced in any later release. ASRock has not added an IFR-level Gen4-enable across the four BIOS versions we checked.

### Where the cap actually lives

Strings in the BIOS image and the `AmdNbioPcieDxe` PE32 module reveal:

```
maxLinkSpeedCap - %d
targetLinkSpeed = %d
DxioPortMapping enter
%a Setting ESM rates to PCIE_LC_SPEED_CNTL.LC_GEN4_EN_STRAP=1 register
%a Speed change to ESM gen4 was successful!
%a Port does not have ESM enabled                  ← per-port branch
%a ESM Training FAILED for this root port
```

`AmdNbioPcieDxe` contains a **complete ESM (Extended Speed Mode = Gen4) implementation**. ESM is enabled / disabled **per port**, decided from the **DXIO descriptor table** that AGESA receives at init. The descriptor table lives in the **APCB (AMD Platform Configuration Block)** binary blob in the BIOS region — specifically referenced by `AmdApcbDxeV3` (50,848-byte PE32 module) and `AmdApcbSmmV3` (724 strings). The APCB is a binary structure, not IFR.

ASRock generates the APCB (and its DXIO descriptors) at BIOS-build time. For ROMED8-2T P3.70:

- 7× GPU root ports → DXIO descriptor declares **Gen3 max** (probably for SI conservatism on a x16-slot riser-friendly board).
- At least one non-slot root port (`40:01.3`, x4) → descriptor declares **Gen4 max**. (Likely a chipset/USB-uplink/internal device.)

The `Port does not have ESM enabled` branch in `AmdNbioPcieDxe` runs for the GPU root ports. The seven Gen4-capable GPUs negotiate down to whatever max their root port advertises — which is Gen3.

**This is a deliberate or oversight platform-policy decision baked into ASRock's APCB. There is no NVRAM byte that overrides it.**

---

## Q3 — Per-slot callback propagation check

The IFR previously identified `72_Setup.pe32` as the ASRock-specific HII module containing the per-slot menu (form `0x27A3`). Empirical NVRAM data already settled the question — the per-slot bytes hold a mix of `0x00`/`0x01` and have no observed effect — but for completeness:

### Strings on `72_Setup.pe32`

`strings -n 6 72_Setup.pe32 | grep -i …` for any of `linkspeed`, `pciespeed`, `propag`, `broadcast`, `callback`, `each.?slot`, `all.?slot`, `pcie.?gen`, `gen[1-5]…` returns **only the literal string `AMICallback`** (the standard AMI variable-broadcasting framework symbol, not a per-slot propagation hint). No developer naming leaked through. **No evidence of a callback that propagates one slot's value to all 11 offsets.** Combined with the empirical observation that the per-slot bytes hold *different* values (some `0x00`, some `0x01`), there is no propagation — they are independent NVRAM bytes that the upper-layer setup code writes correctly. They simply have no consumer.

### Refresh / Variable-Definition references in IFR

The only `Refresh*` token in the IFR is the unrelated `RefreshAttribRegistry` setting (re-evaluates HII attribute conditions next boot). No `RefreshGuid` / `RefreshId` chain on the per-slot offsets. Each setting is an independent OneOf with its own QuestionId/VarOffset. UI behavior is not "all share one value."

**Conclusion:** The per-slot menu correctly *writes* 11 distinct bytes. The bytes simply aren't read by AGESA. Hypothesis #1 from §3 of Part I — "AGESA ignores per-slot bytes, IFR is vestigial" — is now empirically confirmed. Hypothesis #2 (callback propagation) is ruled out.

---

## Q4 — IFR cross-reference of every `0x03` / `0x04` byte in the empirical `AmdSetupSSP` dump

Mapped each empirical byte against the SSP IFR (`AmdSetupSSP` VarStore, total size `0x686`, 447 IFR-mapped settings):

### `0x03` bytes — IFR mapping

| Offset | IFR-backed setting | Width | Default? | Conclusion |
|--------|--------------------|------:|----------|------------|
| `0x002` | (no IFR backing) | – | – | AGESA-internal scratch |
| `0x026` | (no IFR backing) | – | – | AGESA-internal |
| `0x02E` | (no IFR backing) | – | – | AGESA-internal |
| `0x032` | (no IFR backing) | – | – | AGESA-internal |
| `0x0A8`–`0x0AA` | (no IFR backing) | – | – | AGESA-internal |
| `0x0B0`–`0x0B3` | (no IFR backing) | – | – | AGESA-internal |
| `0x0B6`–`0x0B7` | (no IFR backing) | – | – | AGESA-internal |
| `0x0BE` | (no IFR backing) | – | – | AGESA-internal |
| `0x0CA`–`0x0CB` | (no IFR backing) | – | – | AGESA-internal |
| `0x0EB` | (no IFR backing) | – | – | AGESA-internal |
| `0x0ED` | (no IFR backing) | – | – | AGESA-internal |
| **`0x136`** | **`Pattern Length`** (Numeric, range 3–12) | 8-bit | – | **Memory MBIST. `0x03` = 3-cycle pattern. Decoy — not PCIe.** |
| `0x14E` | (no IFR backing) | – | – | AGESA-internal |
| `0x1BA` | (no IFR backing) | – | – | AGESA-internal |
| `0x1CC` | (no IFR backing) | – | – | AGESA-internal |

### `0x04` bytes — IFR mapping

| Offset | IFR-backed setting | Width | Default? | Conclusion |
|--------|--------------------|------:|----------|------------|
| **`0x106`** | **`SubUrgRefLowerBound`** (Numeric, range 1–6) | 8-bit | default `4` | **DRAM refresh threshold. `0x04` = the AGESA default. Decoy — not PCIe.** |
| `0x1BC` | (no IFR backing) | – | – | AGESA-internal |
| `0x1CE` | (no IFR backing) | – | – | AGESA-internal |

### Conclusion of Q4

**No `0x03` or `0x04` byte in the empirical `AmdSetupSSP` dump corresponds to an IFR-exposed PCIe link-speed setting.** The two that ARE IFR-backed (`0x106`, `0x136`) are unrelated DRAM/MBIST options at their AGESA defaults. The remaining ~20 bytes are AGESA-internal scratch / state — they have no IFR mapping because AGESA writes them from internal logic, not from user-settable IFR controls. Their presence/value reflects AGESA's runtime decisions, not BIOS user choices.

**This rules out Q6 hypothesis (b)** — there is no settable IFR-backed offset that holds `0x03` and acts as a Gen3 cap. **The user's BIOS interaction did not write any setting whose value (or default-fallback) currently reads `0x03`.**

---

## Q5 — VarStore enumeration in P3.70 IFR

Every IFR-backed VarStore declared anywhere in the 15 IFR-bearing modules:

| VarStore name | GUID | Size | Backing module(s) | Contains PCIe link-speed control? |
|---------------|------|------|-------------------|-----------------------------------|
| `Setup` | `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9` | `0x174` (372 B) | `72_Setup`, `110_EventLogsSetupPage`, `75_ServerMgmtSetup` (read-only) | **Yes — vestigial:** per-slot AMD PCIE Link Speed at `0x123`–`0x12D`. Empirically ignored by AGESA. |
| `AmdSetupZP` | `3A997502-647A-4C82-998E-52EF9486A247` | `0x5B2` (1458 B) | `CbsSetupDxeZP` (Naples / Zen 1) | Has `Force PCIe gen speed` at `0x1C6` (Gen1/Gen3 only) — **NBIO-wide**, not per-slot. ZP family is unused for Rome/Milan rigs. |
| `AmdSetupSSP` | `3A997502-647A-4C82-998E-52EF9486A247` | `0x686` (1670 B) | `CbsSetupDxeSSP` (Rome / Milan / Zen 2/3) | **No Gen4-enable.** Has `Early Link Speed` (Auto/Gen1/Gen2 only), `Multi Upstream Auto Speed Change`, `Multi Auto Speed Change On Last Rate`. None caps or releases Gen4. |
| `AmdSetup` (GN) | `3A997502-647A-4C82-998E-52EF9486A247` | `0x6CB` (1739 B) | `CbsSetupDxeGN` (Genoa SP5 — irrelevant for SP3 board) | Per-link Socket-0 P0/P1/P2/P3 link speeds, but those are xGMI inter-socket links, not PCIe slots, and not used on this single-socket SP3 board. |
| `AMD_PBS_SETUP` | `A339D746-F678-49B3-9FC7-54CE0F9DF226` | `0x80` (128 B) | `52_AmdPbsSetupDxe` | No. PCIe AER severity registers + DRAM `Skip interval`. |
| `ServerSetup` | `01239999-FC0E-4B6E-9E79-D54D5DB6CD20` | `0x2FB` (763 B) | `75_ServerMgmtSetup` | No. BMC/IPMI/server-mgmt config. |
| `HideBondingInfo` | `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9` | `0x1` | `75_ServerMgmtSetup` | No. UI flag. |
| `LanEnableInfo` | `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9` | `0x10` (16 B) | `75_ServerMgmtSetup` | No. NIC enable flags. |
| `AsrBackupBmcMacSetup` | `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9` | `0x1` | `75_ServerMgmtSetup` | No. |
| `AMITSESetup` | `C811FA38-42C8-4579-A9BB-60E94EDDFB34` | `0x41` (65 B) | `72_Setup` | No. AMI Setup engine state. |
| `Setup` (alt) | `80E1202E-2697-4264-9CC9-80762C3E5863` | `0x7` | `100_ReFlash` | No. Different GUID — only used by the BIOS recovery/reflash module. |
| `Setup2` | `80E1202E-2697-4264-9CC9-80762C3E5863` | `0x1` | `100_ReFlash` | No. |
| `IP4_CONFIG2_IFR_NVDATA` | `9B942747-…` | `0x260` | `203_Ip4Dxe` | No. Network. |
| `IP6_CONFIG_IFR_NVDATA` | `02EEA107-…` | `0x638` | `206_Ip6Dxe` | No. Network. |
| `HTTP_BOOT_CONFIG_IFR_NVDATA` | `4D20583A-…` | `0x296` | `197_HttpBootDxe` | No. |
| `PCI_COMMON` | `ACA9F304-21E2-4852-9875-7FF4881D67A5` | `0x8` | `89_PciDynamicSetup` | No. PCI subsystem nav, not PCIe link-rate. |
| `ErrorManager`, `RefreshAttribRegistry`, `BootManager`, `PlatformLang`, etc. | various | small | various | No. UI / runtime state. |

Note re: user's list — the runtime `efivar` enumeration also showed `UsbSupport (ec87d643)` and `SecureBootSetup (7b59104a)`. Neither has IFR backing in the modules we extracted (likely backed by the EDK2 `SecureBootConfigDxe` and a USB control driver respectively, neither of which appeared in the IFR-bearing module set). Neither is a candidate for PCIe Gen control.

**Q5 summary:** Of all 16 IFR-backed VarStores, exactly two contain anything resembling a PCIe link-speed control: `Setup` (vestigial per-slot bytes), and `AmdSetupSSP` (NBIO behavior flags, no Gen4 selection). No hidden VarStore with a Gen4 enable was discovered.

---

## Q6 — Did the user's BIOS interaction matter?

**Synthesis of the empirical evidence:**

- The user clicked something in the BIOS GUI under the "AMD PCIE Link Speed" menu (or possibly "AMD CBS → NBIO Common Options"; user recollection is approximate).
- The empirical NVRAM dump shows **no byte set to `0x03` (GEN3) anywhere** that has IFR-backed PCIe-link-speed semantics.
- The 11 vestigial per-slot bytes hold a curious pattern: PCIE1 / PCIE2 / PCIE7 / OCU1 / OCU2 / M2_1 are at `0x01` (GEN1), and PCIE3 / PCIE4 / PCIE5 / PCIE6 / M2_2 are at `0x00` (Auto). That asymmetric pattern is not "all Auto" (manufacturing default) and is not "single-slot edited" — it's something else. Possibilities:
  - The user clicked through several slots, intending Gen3, but the GUI saved Gen1 (`0x01`) instead because of a stuck-key or wrap-around behavior in the BIOS UI. (Unlikely but possible.)
  - The user previously edited those slots to Gen1 deliberately, possibly during an earlier troubleshooting session that wasn't documented in the parent project's CLAUDE.md.
  - "Optimized Defaults" was loaded at some point and overwrote whatever the user had set; the asymmetric pattern is the "Optimized Defaults" content for these bytes (which would imply the AMI default-store has a non-uniform default for these per-slot offsets — atypical but possible).
- **Regardless of which is true, the per-slot bytes are vestigial — the GPU root ports' Gen3 cap is not driven by them.** The user's click changed values that AGESA does not consume.

**Therefore:** the user's BIOS interaction was a **no-op with respect to PCIe Gen** on this board/BIOS combination. The Gen3 cap is the BIOS's intrinsic default for the GPU root ports on P3.70 — set in ASRock's APCB / DXIO descriptors at build time. Restoring the per-slot bytes to all-Auto will not lift it. Setting them all to GEN4 will not lift it. The cap is not in the NVRAM-writable surface at all.

The throughput regression the user observed (76→40 t/s, 394→92 t/s) is most plausibly explained by something other than a BIOS Gen-cap flip — driver upgrade, GPU dropout, GSP-firmware change, vLLM version, kernel scheduler regression, etc. None of those is in scope for this BIOS report; flagging that the BIOS evidence does **not** support a "user clicked Gen3 in BIOS and capped everything" narrative. The cap was almost certainly **always** Gen3 on this BIOS for these slots, and the previously-recorded "Gen4 baseline" numbers in the parent project's CLAUDE.md were never on this rig at this BIOS version (or were never actually at Gen4).

---

## Updated §4 — proposed write actions

**No `setup_var.efi` write will lift the Gen3 cap on P3.70.** The IFR-only proposal in Part I §4 (writing per-slot bytes `0x123`–`0x12D`) is moot — empirically confirmed vestigial. There is no other IFR-backed setting whose modification would re-enable Gen4 on the GPU root ports.

**The remaining options, ranked by leverage and risk:**

1. **Try newer BIOS for a different DXIO descriptor.** Test in this order: P4.10 (newest public, on disk), then L3.11 (older sibling, on disk), then beg ASRock support for L4.11 (private). Boot, dump LnkCap2 on each GPU root port. If any non-P3.70 BIOS exposes Gen4 on the GPU root ports out-of-the-box, ship that BIOS. **Lowest risk, highest possible value.** All four images are already on disk under `images/`.
2. **If no BIOS version works:** confirm-then-fix the failing GPU 7 link at the hardware layer. The bifurcation adapter is the prime suspect. Replace with a known-good adapter or a redriver-equipped adapter, OR move GPU 7 to a slot fed directly by CPU lanes without bifurcation, OR cap GPU 7 at Gen3 at the *driver* layer with `nvidia-smi -lgc` / `pci=pcie_bus_perf` / a downstream port `LnkCtl2` write from `setpci`. The driver/sysfs path **does** work for capping per-port — it bypasses BIOS entirely. We've not investigated that path here; it's an avenue worth pursuing if the BIOS path is dead.
3. **APCB binary patching.** The DXIO descriptors live in a binary structure inside the BIOS image. Locating, decoding, and patching them is a Ghidra-grade undertaking with real risk of bricking the board (SPI write of an invalid APCB causes no-POST). **Do not attempt unless options 1 and 2 are exhausted, and only with an external SPI flasher and a known-good backup BIOS image.** The `AmdApcbDxeV3` module's strings (`Write back APCB to SPI`, `APCB SPI Entry too small`) confirm the runtime path; offline patching would target the on-disk APCB FFS file.
4. **Empirically test whether `40:01.3`'s Gen4 capability extends.** The user observed one root port at Gen4 (`40:01.3`, x4). Identifying which physical interface that port serves — and whether any GPU could be moved onto its lane group — is a small investigation that could yield an immediate workaround. Run `lspci -tvv` and trace `40:01.3` to its endpoint.

---

## Updated §6 — additional findings from the empirical drilldown

- **`AmdApcbDxeV3`** (volume 7, FFS index 43, 50,848 B) is the runtime APCB driver. It implements `GetApcbShadowCopy`, `AmdPspWriteBackApcbShadowCopy`, and a SMM/DXE mutex protocol for APCB modification. APCB modifications go through this driver — strings include `Ready to write APCB shadow copy @ 0x%x back to: Entry 0x%x, Binary Instance %d`. This is **the legal kernel-side path** for runtime APCB updates if a future Linux APCB-tweak driver were written. Currently no public tool uses it.
- **`AmdNbioPcieDxe`** (volume 20, FFS index 37, ~70 KB PE32) contains the full ESM/Gen4 implementation. Notable strings: `SetVg20EsmEnableViaMmio`, `Hit bit ESM GO bit for VG20`, `Polling until LcCntl7.Field.LC_ESM_PLL_INIT_DONE = 1`. The code is fully Gen4-capable; whether any given port reaches that path is decided by the per-port descriptor.
- **`AmdCheckBmcPciePei`** (volume 21, PEI module) is a boot-time check for the BMC's PCIe link state. Unrelated to GPU links but a useful reference for how AGESA checks per-port state.
- The single Gen4 root port the user observed (`40:01.3`) likely terminates at one of: the AST2500 BMC bridge, the ROMED8-2T's onboard X550 NICs, or a chipset-internal device. Its DXIO descriptor is wired Gen4 because its endpoint is Gen4-trustworthy and its PCB trace is short. This proves "Gen4 works on this CPU+BIOS" — the cap is a per-port descriptor decision, not a chipset/CPU limit.

---

## Highest-leverage next action

**Flash P4.10 and re-read `LnkCap2` on every GPU root port. Total elapsed: ~10 min.**

Why this ranks highest:
- The BIOS image is already on disk (`images/ROMD82T4.10`).
- P4.10 is the newest public BIOS; if ASRock ever changed the DXIO descriptors for the GPU slots, it's most likely there.
- The user's `Setup` NVRAM survives BIOS updates by default (settings don't get nuked unless ASRock ships a new VarStore layout — which our SSP-IFR cross-version check showed they didn't), so the empirical state can be compared cleanly.
- If P4.10 advertises Gen4 on the GPU root ports → done, ship that BIOS.
- If P4.10 still caps at Gen3 → the cap is hard-baked in ASRock's DXIO build across all public BIOS versions. At that point the BIOS path is exhausted and the only remaining options are (a) hardware change to GPU 7's link or (b) sysfs/setpci downgrade applied per-port from userspace. Document and move on.

Pre-flash checklist (rig-side, not in this report's scope but worth flagging): **back up the current SPI flash via `flashrom -r`** before flashing P4.10, so we have a known-good rollback. ASRock Rack's BIOS rollback policy on this board is unclear; some EPYC boards have monotonic-version-only flashing once an L-series build is installed, and we don't know if that applies here.

# Part II — Complete BIOS Setting Reference (P3.70)

_The remainder of this document is a machine-readable enumeration of every BIOS setup setting in P3.70. It is generated from the raw IFR via `scripts/ifr_to_reference.py`. Use it as a lookup table when correlating menu paths with NVRAM offsets, or when an LLM needs ground-truth for any setting on this board._

_Generated content begins below._

This is the complete enumeration of every BIOS setup setting in P3.70, extracted from the IFR (Internal Forms Representation) of every UEFI module that defines a HII Forms package. Organized hierarchically as Module → FormSet → Form → Setting, with full metadata: NVRAM VarStore + byte offset, size, allowed values/options, defaults, and the SuppressIf / GrayOutIf conditions that gate each setting.

**Summary:** 15 modules, 291 forms, 1565 settings.

**How to read a setting block:**
- `0xNNN` (e.g. `0xe1`) is the QuestionId — a stable per-FormSet identifier.
- `VarStore 0xN` is the NVRAM variable that backs the setting (look up its name + GUID in the module's VarStore table).
- `offset 0xNNN` is the byte offset inside that variable. This is what you feed to `setup_var.efi` from the EFI shell, or to `efivar` from Linux.
- Options like `0x3 = GEN3` mean writing the byte value `0x03` selects the GEN3 option.
- `conditions: GrayOutIf(Qabc=0x1)` means the setting is grayed in the GUI when the referenced QuestionId equals 0x1. The NVRAM byte is still writable directly — gray-out is a UI policy, not a write protection.

---
## Module: `100_ReFlash.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `80E1202E-2697-4264-9CC9-80762C3E5863`
- FormSet title: **Select Storage Device**
- FormSet help: Can't add string

### VarStores
- `0x1` **Setup** — GUID `80E1202E-2697-4264-9CC9-80762C3E5863`, size `0x7`
- `0x2` **Setup2** — GUID `80E1202E-2697-4264-9CC9-80762C3E5863`, size `0x1`
- `0xf000` **SystemAccess** — GUID `E770BB69-BCB4-4D04-9E97-23FF9456FEAC`, size `0x1`
- `0xf002` **AMICallback** — GUID `9CF0F18E-7C7D-49DE-B5AA-BBBAD6B21007`, size `0x2`

### Forms

#### Form `0x1` — Select Storage Device

_Navigation (children):_
- → `0x1` **InvalidId**
  - Can't add string
- → `0x1` **InvalidId**
  - Can't add string
- → `0x1` **InvalidId**
  - Can't add string
- → `0x2` **InvalidId**
  - InvalidId

_Settings:_

##### `0x1` — **(unnamed)** (CheckBox)
> InvalidId
- VarStore `0x1` · offset `0x3` · 8-bit
- options: `0` = Disabled, `1` = Enabled

##### `0x2` — **InvalidId** (CheckBox)
> InvalidId
- VarStore `0x1` · offset `0x4` · 8-bit
- options: `0` = Disabled, `1` = Enabled

#### Form `0x2` — InvalidId

_Settings:_

##### `0x3` — **(unnamed)** (Numeric)
- VarStore `0xf002` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

##### `0x4` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x1` · 8-bit · range `0x0`..`0xff`

##### `0x5` — **(unnamed)** (Numeric)
- VarStore `0xf000` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x6` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x6` · 8-bit · range `0x0`..`0xff`

##### `0x7` — **(unnamed)** (Numeric)
- VarStore `0x2` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x8` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x0` · 8-bit · range `0x0`..`0xff`

## Module: `100_ReFlash.pe32.0.1.en-US.uefi.ifr.txt`
- FormSet GUID: `80E1202E-2697-4264-9CC9-80762C3E5863`
- FormSet title: **Recovery**

### VarStores
- `0x1` **Setup** — GUID `80E1202E-2697-4264-9CC9-80762C3E5863`, size `0x7`
- `0x2` **Setup2** — GUID `80E1202E-2697-4264-9CC9-80762C3E5863`, size `0x1`
- `0xf000` **SystemAccess** — GUID `E770BB69-BCB4-4D04-9E97-23FF9456FEAC`, size `0x1`
- `0xf002` **AMICallback** — GUID `9CF0F18E-7C7D-49DE-B5AA-BBBAD6B21007`, size `0x2`

### Forms

#### Form `0x1` — Recovery

_Navigation (children):_
- → `0x1` **Select Image file**
- → `0x1` **Update Image**
- → `0x1` **Yes, I'm sure**
- → `0x2` **Proceed with flash update**
  - Select this to start flash update

_Settings:_

##### `0x1` — **Reset NVRAM** (CheckBox)
> Set this option to reset NVRAM to default values
- VarStore `0x1` · offset `0x3` · 8-bit
- options: `0` = Disabled, `1` = Enabled

##### `0x2` — **Boot Block Update** (CheckBox)
> Set this option to update boot block area of the firmware
- VarStore `0x1` · offset `0x4` · 8-bit
- options: `0` = Disabled, `1` = Enabled

#### Form `0x2` — Flashing...

_Settings:_

##### `0x3` — **(unnamed)** (Numeric)
- VarStore `0xf002` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

##### `0x4` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x1` · 8-bit · range `0x0`..`0xff`

##### `0x5` — **(unnamed)** (Numeric)
- VarStore `0xf000` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x6` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x6` · 8-bit · range `0x0`..`0xff`

##### `0x7` — **(unnamed)** (Numeric)
- VarStore `0x2` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x8` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x0` · 8-bit · range `0x0`..`0xff`

## Module: `110_EventLogsSetupPage.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `8BEB8C19-3FEC-4FAB-A378-C903E890FCAE`
- FormSet title: **Event Logs**

### VarStores
- `0x1` **Setup** — GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`, size `0x174`
- `0x2` **ErrorManager** — GUID `ADDEBF82-A560-46B9-A280-78C6AB61AEDA`, size `0x4`
- `0xf000` **SystemAccess** — GUID `E770BB69-BCB4-4D04-9E97-23FF9456FEAC`, size `0x1`

### Forms

#### Form `0x2710` — Event Logs

_Navigation (children):_
- → `0x2712` **Change Smbios Event Log Settings**
  - Press <Enter> to change the Smbios Event Log configuration.
- → `0x2713` **View Smbios Event Log**
  - Press <Enter> to view the Smbios Event Log records.

#### Form `0x2712` — Change Settings

_Settings:_

##### `0x2` — **Smbios Event Log** (OneOf)
> Change this to enable or disable all features of Smbios Event Logging during boot.
- VarStore `0x1` · offset `0xcb` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled
- conditions: GrayOutIf(Q0xc=0x1)

##### `0x3` — **Erase Event Log** (OneOf)
> Choose options for erasing Smbios Event Log.  Erasing is done prior to any logging activation during reset.
- VarStore `0x1` · offset `0xcd` · 8-bit · range `0x0`..`0x2`
- options: `0` = No, `1` = Yes, Next reset, `2` = Yes, Every reset
- conditions: SuppressIf(Q0x2=0x0); GrayOutIf(Q0xc=0x1)

##### `0x4` — **When Log is Full** (OneOf)
> Choose options for reactions to a full Smbios Event Log.
- VarStore `0x1` · offset `0xcc` · 8-bit · range `0x0`..`0x1`
- options: `0` = Do Nothing, `1` = Erase Immediately
- conditions: SuppressIf(Q0x2=0x0); GrayOutIf(Q0xc=0x1)

##### `0x5` — **Log System Boot Event** (OneOf)
> Choose option to enable/disable logging of System boot event
- VarStore `0x1` · offset `0xce` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled
- conditions: SuppressIf(Q0x2=0x0); GrayOutIf(Q0xc=0x1)

##### `0x6` — **MECI** (Numeric)
> Mutiple Event Count Increment:  The number of occurrences of a duplicate event that must pass before the multiple-event counter of log entry is updated.The value ranges from 1 to 255.
- VarStore `0x1` · offset `0xd1` · 8-bit · range `0x1`..`0xff` · default `1`
- conditions: SuppressIf(Q0x2=0x0); GrayOutIf(Q0xc=0x1)

##### `0x7` — **METW** (Numeric)
> Mutiple Event Time Window:  The number of minutes which must pass between duplicate log entries which utilize a multiple-event counter. The value ranges from 0 to 99 minutes.
- VarStore `0x1` · offset `0xd0` · 8-bit · range `0x0`..`0x63` · default `60`
- conditions: SuppressIf(Q0x2=0x0)

##### `0x8` — **Log EFI Status Code** (OneOf)
> Enable or disable the logging of EFI Status Codes as OEM reserved type E0 (if not already converted to legacy).
- VarStore `0x1` · offset `0xcf` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled
- conditions: SuppressIf(Q0x2=0x0); GrayOutIf(Q0xc=0x1)

##### `0x9` — **Convert EFI Status Codes to Standard Smbios Type** (OneOf)
> Enable or disable the converting of EFI Status Codes to Standard Smbios Types (Not all may be translated).
- VarStore `0x1` · offset `0xd2` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled
- conditions: SuppressIf(Q0x2=0x0); GrayOutIf(Q0xc=0x1); SuppressIf(Q0x8=0x0)

#### Form `0x2713` — View Smbios Event Log

_Navigation (children):_
- → `0x2713` ****

_Settings:_

##### `0xb` — **(unnamed)** (Numeric)
- VarStore `0x2` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

##### `0xc` — **(unnamed)** (Numeric)
- VarStore `0xf000` · offset `0x0` · 8-bit · range `0x0`..`0xff`

## Module: `118_SataDevInfo.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `5D9265F7-E3EC-4BE1-A995-85D860A5A42E`
- FormSet title: **SATA Configuration**
- FormSet help: SATA Devices Information.

### Forms

#### Form `0x1` — SATA Configuration

## Module: `197_HttpBootDxe.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `4D20583A-7765-4E7A-8A67-DCDE74EE3EC5`
- FormSet title: **HTTP Boot Configuration**
- FormSet help: Configure HTTP Boot parameters.

### VarStores
- `0x1` **HTTP_BOOT_CONFIG_IFR_NVDATA** — GUID `4D20583A-7765-4E7A-8A67-DCDE74EE3EC5`, size `0x296`

### Forms

#### Form `0x1` — HTTP Boot Configuration

_Settings:_

##### `0x2` — **Internet Protocol** (OneOf)
> Select the version of Internet Protocol.
- VarStore `0x1` · offset `0x0` · 8-bit · range `0x0`..`0x1`
- options: `0` = IPv4 (default), `1` = IPv6

## Module: `203_Ip4Dxe.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `9B942747-154E-4D29-A436-BF7100C8B53B`
- FormSet title: **IPv4 Network Configuration**
- FormSet help: Configure network parameters.

### VarStores
- `0x1` **IP4_CONFIG2_IFR_NVDATA** — GUID `9B942747-154E-4D29-A436-BF7100C8B53B`, size `0x260`

### Forms

#### Form `0x1` — (untitled)

_Settings:_

##### `0x100` — **Configured** (CheckBox)
> Indicate whether network address configured successfully or not.
- VarStore `0x1` · offset `0x0` · 8-bit
- options: `0` = Disabled, `1` = Enabled

##### `0x101` — **Enable DHCP** (CheckBox)
> Enable DHCP
- VarStore `0x1` · offset `0x1` · 8-bit
- options: `0` = Disabled, `1` = Enabled
- conditions: SuppressIf(Q0x100=0x0)

## Module: `206_Ip6Dxe.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `02EEA107-98DB-400E-9830-460A1542D799`
- FormSet title: **IPv6 Network Configuration**
- FormSet help: Configure IPv6 network parameters.

### VarStores
- `0x1` **IP6_CONFIG_IFR_NVDATA** — GUID `02EEA107-98DB-400E-9830-460A1542D799`, size `0x638`

### Forms

#### Form `0x3` — IPv6 Current Setting

_Navigation (children):_
- → `0x1` **Enter Configuration Menu**
  - Press ENTER to enter configuration menu for IPv6 configuration.

#### Form `0x1` — IPv6 Current Setting

_Navigation (children):_
- → `0x2` **Advanced Configuration**
  - Configure the interface manually. IP address, gateway address, and DNS server address can be configured.

_Settings:_

##### `0x1` — **DAD Transmit Count** (Numeric)
> The number of consecutive Neighbor Solicitation messages sent while performing Duplicate Address Detection on a tentative address. A value of zero indicates that Duplicate Address Detection is not performed.
- VarStore `0x1` · offset `0x8` · 32-bit · range `0x0`..`0xa`

##### `0x2` — **Policy** (OneOf)
> automatic or manual
- VarStore `0x1` · offset `0x4` · 32-bit · range `0x0`..`0x1`
- options: `0` = automatic (default), `1` = manual

#### Form `0x2` — Advanced Configuration

## Module: `50_CbsSetupDxeGN.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `B04535E3-3004-4946-9EB7-149428983053`
- FormSet title: **AMD CBS**
- FormSet help: AMD CBS Setup Page

### VarStores
- `0x5000` **AmdSetup** — GUID `3A997502-647A-4C82-998E-52EF9486A247`, size `0x6cb`

### Forms

#### Form `0x7000` — AMD CBS

_Navigation (children):_
- → `0x7001` **CPU Common Options**
  - CPU Common Options
- → `0x7002` **DF Common Options**
  - DF Common Options
- → `0x7003` **UMC Common Options**
  - UMC Common Options
- → `0x7004` **NBIO Common Options**
  - NBIO Common Options
- → `0x7005` **FCH Common Options**
  - FCH Common Options
- → `0x7006` **NTB Common Options**
  - NTB Common Options
- → `0x7007` **Soc Miscellaneous Control**
  - Soc Miscellaneous Control
- → `0x7008` **Workload Tuning**
  - Workload Tuning

_Settings:_

##### `0x9` — **Combo CBS** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x20` · 8-bit · range `0x0`..`0xff` · default `254`

#### Form `0x7001` — CPU Common Options

_Navigation (children):_
- → `0x7009` **Performance**
  - Performance
- → `0x700a` **Prefetcher settings**
  - Prefetcher settings
- → `0x700b` **Core Watchdog**
  - Core Watchdog

_Settings:_

##### `0xd` — **RedirectForReturnDis** (OneOf)
> From a workaround for GCC/C000005 issue for XV Core on CZ A0, setting MSRC001_1029 Decode Configuration (DE_CFG) bit 14 [DecfgNoRdrctForReturns] to 1
- VarStore `0x5000` · offset `0x21` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = 1, `0` = 0

##### `0xe` — **Platform First Error Handling** (OneOf)
> Enable/disable PFEH, cloak individual banks, and mask deferred error interrupts from each bank.
- VarStore `0x5000` · offset `0x22` · 8-bit · range `0x0`..`0x3`
- options: `1` = Enabled, `0` = Disabled, `3` = Auto (default)

##### `0xf` — **Core Performance Boost** (OneOf)
> Disable CPB
- VarStore `0x5000` · offset `0x23` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Auto (default)

##### `0x10` — **Global C-state Control** (OneOf)
> Controls IO based C-state generation and DF C-states.
- VarStore `0x5000` · offset `0x24` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x11` — **Power Supply Idle Control** (OneOf)
> Power Supply Idle Control.
- VarStore `0x5000` · offset `0x25` · 8-bit · range `0x0`..`0xf`
- options: `1` = Low Current Idle, `0` = Typical Current Idle, `15` = Auto (default)

##### `0x700c` — **SEV ASID Count** (OneOf)
> This fields specifies the maximum valid ASID, which affects the maximum system physical address space. 16TB of physical address space is available for systems that support 253 ASIDs, while 8TB of physical address space is available for systems that support 509 ASIDs.
- VarStore `0x5000` · offset `0x26` · 8-bit · range `0x0`..`0x3`
- options: `0` = 253 ASIDs, `1` = 509 ASIDs, `3` = Auto (default)

##### `0x12` — **SEV-ES ASID Space Limit Control** (OneOf)
> Customize SEV-ES ASID space limit
- VarStore `0x5000` · offset `0x27` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x700d` — **SEV-ES ASID Space Limit** (Numeric)
> SEV VMs using ASIDs below the SEV-ES ASID Space Limit must enable the SEV-ES feature. ASIDs from SEV-ES ASID Space Limit to (SEV ASID Count + 1) can only be used with SEV VMs. If this field is set to (SEV ASID Count + 1), all ASIDs are forced to be SEV-ES ASIDs. Hence, the valid values for this field is 1 - (SEV ASID Count + 1)
- VarStore `0x5000` · offset `0x28` · 32-bit · range `0x1`..`0x1fe` · default `1`

##### `0x13` — **SEV Control** (OneOf)
> Can be used to disable SEV. To re-enable SEV, a POWER CYCLE is needed after selecting the 'Enable' option.
- VarStore `0x5000` · offset `0x2c` · 8-bit · range `0x0`..`0x1`
- options: `0` = Enable (default), `1` = Disable

##### `0x14` — **Streaming Stores Control** (OneOf)
> Enables or disables the streaming stores functionality
- VarStore `0x5000` · offset `0x2d` · 8-bit · range `0x0`..`0xff`
- options: `1` = Disabled, `0` = Enabled, `255` = Auto (default)

##### `0x15` — **Local APIC Mode** (OneOf)
> Select local APIC mode: Compatability, xAPIC or x2APIC
- VarStore `0x5000` · offset `0x2e` · 8-bit · range `0x0`..`0xff`
- options: `0` = Compatibility, `1` = xAPIC, `2` = x2APIC, `255` = Auto (default)

##### `0x16` — **ACPI _CST C1 Declaration** (OneOf)
> Determines whether or not to declare the C1 state to the OS.
- VarStore `0x5000` · offset `0x2f` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x17` — **MCA error thresh enable** (OneOf)
> Enable MCA error thresholding.
- VarStore `0x5000` · offset `0x30` · 8-bit · range `0x0`..`0xff`
- options: `0` = False, `1` = True, `255` = Auto (default)

##### `0x18` — **MCA error thresh count** (Numeric)
> Effective error threshold count = 4095(0xFFF) - <this value> (e.g. the default value of 0xFF5 results in a threshold of 10).
- VarStore `0x5000` · offset `0x31` · 16-bit · range `0x1`..`0xfff` · default `4085`

##### `0x19` — **SMU and PSP Debug Mode** (OneOf)
> When this option is enabled, specific uncorrected errors detected by the PSP FW or SMU FW will hang and not reset the system
- VarStore `0x5000` · offset `0x33` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x1b` — **PPIN Opt-in** (OneOf)
> Turn on PPIN feature
- VarStore `0x5000` · offset `0x35` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0x1c` — **SNP Memory (RMP Table) Coverage** (OneOf)
> Enabled = ENTIRE system memory is covered.
- VarStore `0x5000` · offset `0x36` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `2` = Custom, `255` = Auto (default)

##### `0x1d` — **Amount of Memory to Cover** (Numeric)
> Specify MB of System Memory to be covered in Hex.
- VarStore `0x5000` · offset `0x37` · 32-bit · range `0x10`..`0x100000` · default `16`

##### `0x1e` — **SMEE** (OneOf)
> Control secure memory encryption enable
- VarStore `0x5000` · offset `0x3b` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x1f` — **Action on BIST Failure** (OneOf)
> Action to take when a CCD BIST failure is detected.
- VarStore `0x5000` · offset `0x3c` · 8-bit · range `0x0`..`0xff`
- options: `0` = Do nothing, `1` = Down-CCD, `255` = Auto (default)

##### `0x20` — **Fast Short REP MOVSB (FSRM)** (OneOf)
> Can be disabled for analysis purposes as long as OS supports it.
- VarStore `0x5000` · offset `0x3d` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0x21` — **Enhanced REP MOVSB/STOSB (ERMSB)** (OneOf)
> Can be disabled for analysis purposes as long as OS supports it.
- VarStore `0x5000` · offset `0x3e` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0x22` — **REP-MOV/STOS Streaming** (OneOf)
> Allow REP-MOVS/STOS to use non-caching streaming stores for large sizes
- VarStore `0x5000` · offset `0x3f` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default), `1` = Enabled

##### `0x700e` — **3D V-Cache** (OneOf)
> Override of X3D technology
- VarStore `0x5000` · offset `0x40` · 8-bit · range `0x0`..`0xf`
- options: `15` = Auto (default), `0` = Disabled, `1` = 1 stack, `2` = 2 stack, `4` = 4 stack

##### `0x23` — **IBS hardware workaround** (OneOf)
> Set if using IBS execution sampling without software workaround for erratum 1,285. May impact performance.
- VarStore `0x5000` · offset `0x41` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Enabled

#### Form `0x7009` — Performance

_Navigation (children):_
- → `0x7012` **DownCore Bitmap**
  - DownCore Bitmap
- → `0x7013` **Custom Core Pstates**
  - Custom Core Pstates
- → `0x7014` **CCD/Core/Thread Enablement**
  - CCD/Core/Thread Enablement

_Settings:_

##### `0x7011` — **OC Mode** (OneOf)
> Can be used to modify the number of core/CCD.
- VarStore `0x5000` · offset `0x42` · 8-bit · range `0x0`..`0x5`
- options: `0` = Normal Operation (default), `5` = Customized

##### `0x27` — **SMT Control** (OneOf)
> Can be used to disable symmetric multithreading. To re-enable SMT, a POWER CYCLE is needed after selecting the 'Enable' option. Select 'Auto' base on BIOS PCD (PcdAmdSmtMode) default setting. WARNING - S3 is NOT SUPPORTED on systems where SMT is disabled.
- VarStore `0x5000` · offset `0x43` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7012` — DownCore Bitmap

_Settings:_

##### `0x28` — **CCD 0 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x44` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x29` — **CCD 3 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x45` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x2a` — **CCD 1 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x46` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x2b` — **CCD 4 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x47` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x2c` — **CCD 2 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x48` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x2d` — **CCD 5 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x49` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x2e` — **CCD 6 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x4a` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x2f` — **CCD 7 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x4b` · 8-bit · range `0x0`..`0xff` · default `0`

#### Form `0x7013` — Custom Core Pstates

_Navigation (children):_
- → `0x7009` **Decline**
  - Decline
- → `0x7016` **Accept**
  - Accept

#### Form `0x7015` — Decline

#### Form `0x7016` — Accept

_Settings:_

##### `0x7018` — **Pstate0 Freq (MHz)** (Numeric)
> Specifies core frequency (MHz)
- VarStore `0x5000` · offset `0x4f` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x32` — **P0 Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x53` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x33` — **P0 Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x57` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7019` — **Pstate0 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x5b` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x701a` — **Pstate0 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x5c` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x701b` — **Pstate0 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x5d` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x701d` — **Pstate1 Freq (MHz)** (Numeric)
> Specifies core frequency (MHz)
- VarStore `0x5000` · offset `0x5f` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x34` — **P1 Frequency (MHz)** (Numeric)
> Set frequency (Mhz). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0x63` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x35` — **P1 Voltage (uV)** (Numeric)
> Set Voltage (uV). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0x67` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x701e` — **Pstate1 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x6b` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x701f` — **Pstate1 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x6c` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7020` — **Pstate1 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x6d` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x7022` — **Pstate2 Freq (MHz)** (Numeric)
> Specifies core frequency (MHz)
- VarStore `0x5000` · offset `0x6f` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x36` — **P2 Frequency (MHz)** (Numeric)
> Set frequency (Mhz). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0x73` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x37` — **P2 Voltage (uV)** (Numeric)
> Set Voltage (uV). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0x77` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7023` — **Pstate2 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x7b` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7024` — **Pstate2 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x7c` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7025` — **Pstate2 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x7d` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x38` — **P3 Frequency (MHz)** (Numeric)
> Set frequency (Mhz). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0x7f` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x39` — **P3 Voltage (uV)** (Numeric)
> Set Voltage (uV). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0x83` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7027` — **Pstate3 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x87` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7028` — **Pstate3 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x88` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7029` — **Pstate3 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x89` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x3a` — **P4 Frequency (MHz)** (Numeric)
> Set frequency (Mhz). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0x8b` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x3b` — **P4 Voltage (uV)** (Numeric)
> Set Voltage (uV). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0x8f` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x702b` — **Pstate4 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x93` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x702c` — **Pstate4 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x94` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x702d` — **Pstate4 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x95` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x3c` — **P5 Frequency (MHz)** (Numeric)
> Set frequency (Mhz). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0x97` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x3d` — **P5 Voltage (uV)** (Numeric)
> Set Voltage (uV). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0x9b` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x702f` — **Pstate5 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x9f` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7030` — **Pstate5 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0xa0` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7031` — **Pstate5 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0xa1` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x3e` — **P6 Frequency (MHz)** (Numeric)
> Set frequency (Mhz). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0xa3` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x3f` — **P6 Voltage (uV)** (Numeric)
> Set Voltage (uV). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0xa7` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7033` — **Pstate6 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0xab` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7034` — **Pstate6 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0xac` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7035` — **Pstate6 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0xad` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x40` — **P7 Frequency (MHz)** (Numeric)
> Set frequency (Mhz). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0xaf` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x41` — **P7 Voltage (uV)** (Numeric)
> Set Voltage (uV). Range: 0-0xffffffff
- VarStore `0x5000` · offset `0xb3` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7037` — **Pstate7 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0xb7` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7038` — **Pstate7 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0xb8` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7039` — **Pstate7 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0xb9` · 8-bit · range `0x0`..`0xff` · default `255`

#### Form `0x7014` — CCD/Core/Thread Enablement

_Settings:_

##### `0x42` — **CCD Control** (OneOf)
> Sets the number of CCDs to be used. Once this option has been used to remove any CCDs, a POWER CYCLE is required in order for future selections to take effect.
- VarStore `0x5000` · offset `0xba` · 8-bit · range `0x0`..`0x6`
- options: `0` = Auto (default), `2` = 2 CCDs, `3` = 3 CCDs, `4` = 4 CCDs, `6` = 6 CCDs

##### `0x43` — **Core control** (OneOf)
> Sets the number of cores to be used. Once this option has been used to remove any cores, a POWER CYCLE is required in order for future selections to take effect.
- VarStore `0x5000` · offset `0xbb` · 8-bit · range `0x0`..`0xa`
- options: `0` = Auto (default), `1` = ONE (1 + 0), `3` = TWO (2 + 0), `4` = THREE (3 + 0), `6` = FOUR (4 + 0), `8` = FIVE (5 + 0), `9` = SIX (6 + 0), `10` = SEVEN (7 + 0)

#### Form `0x700a` — Prefetcher settings

_Settings:_

##### `0x44` — **L1 Stream HW Prefetcher** (OneOf)
> Option to Enable | Disable L1 Stream HW Prefetcher
- VarStore `0x5000` · offset `0xbc` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x45` — **L1 Stride Prefetcher** (OneOf)
> Uses memory access history of individual instructions to fetch additional lines when each access is a constant distance from the previous.
- VarStore `0x5000` · offset `0xbd` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x46` — **L1 Region Prefetcher** (OneOf)
> Uses memory access history to fetch additional lines when the data access for a given instruction tends to be followed by other data accesses.
- VarStore `0x5000` · offset `0xbe` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x47` — **L2 Stream HW Prefetcher** (OneOf)
> Option to Enable | Disable L2 Stream HW Prefetcher
- VarStore `0x5000` · offset `0xbf` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x48` — **L2 Up/Down Prefetcher** (OneOf)
> Uses memory access history to determine whether to fetch the next or previous line for all memory accesses.
- VarStore `0x5000` · offset `0xc0` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

#### Form `0x700b` — Core Watchdog

_Settings:_

##### `0x703a` — **Core Watchdog Timer Enable** (OneOf)
> Enable or disable CPU Watchdog Timer
- VarStore `0x5000` · offset `0xc1` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x49` — **Core Watchdog Timer Interval** (OneOf)
> No help string
- VarStore `0x5000` · offset `0xc2` · 16-bit · range `0x0`..`0xffff`
- options: `2304` = 21.461s, `2048` = 10.730s, `0` = 5.364s, `256` = 2.681s, `512` = 1.340s, `768` = 669.41ms, `1024` = 334.05ms, `1280` = 166.37ms, `1536` = 82.53ms, `1792` = 40.61ms, `2305` = 20.970ms, `2049` = 10.484ms, `1` = 5.241ms, `257` = 2.620ms, `513` = 1.309ms, `769` = 654.08us, `1025` = 326.4us, `1281` = 162.56us, `1537` = 80.64us, `1793` = 39.68us, `65535` = Auto (default)

##### `0x4a` — **Core Watchdog Timer Severity** (OneOf)
> Specify the CPU watch dog timer severity (MSRC001_0074[CpuWdTmrCfgSeverity]).
- VarStore `0x5000` · offset `0xc4` · 8-bit · range `0x0`..`0xff`
- options: `0` = No Error, `1` = Transparent, `2` = Corrected, `3` = Deferred, `4` = Uncorrected, `5` = Fatal, `255` = Auto (default)

#### Form `0x7002` — DF Common Options

_Navigation (children):_
- → `0x703b` **Scrubber**
  - Scrubber
- → `0x703c` **Memory Addressing**
  - Memory Addressing
- → `0x703d` **ACPI**
  - ACPI
- → `0x703e` **Link**
  - Link

_Settings:_

##### `0x4f` — **Disable DF to external IP SyncFloodPropagation** (OneOf)
> Disable SyncFlood to UMC & downstream slaves.
- VarStore `0x5000` · offset `0xc5` · 8-bit · range `0x0`..`0xff`
- options: `1` = Sync flood disabled, `0` = Sync flood enabled, `255` = Auto (default)

##### `0x50` — **Disable DF sync flood propagation** (OneOf)
> Control DF::PIEConfig[DisSyncFloodProp]
- VarStore `0x5000` · offset `0xc6` · 8-bit · range `0x0`..`0xff`
- options: `1` = Sync flood disabled, `0` = Sync flood enabled, `255` = Auto (default)

##### `0x52` — **CC6 memory region encryption** (OneOf)
> Control whether or not the CC6 save/restore memory is encrypted
- VarStore `0x5000` · offset `0xc8` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x53` — **System probe filter** (OneOf)
> Controls whether or not the probe filter is enabled. Has no effect on parts where the probe filter is fuse disabled.
- VarStore `0x5000` · offset `0xc9` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x54` — **Memory Clear** (OneOf)
> When this feature is disabled, BIOS does not implement MemClear after memory training (only if non-ECC DIMMs are used).
- VarStore `0x5000` · offset `0xca` · 8-bit · range `0x0`..`0x3`
- options: `0` = Enabled, `1` = Disabled, `3` = Auto (default)

##### `0x55` — **PSP error injection support** (OneOf)
> 'True' enables error injection.
- VarStore `0x5000` · offset `0xcb` · 8-bit · range `0x0`..`0x1`
- options: `0` = False (default), `1` = True

#### Form `0x703b` — Scrubber

_Settings:_

##### `0x56` — **DRAM scrub time** (OneOf)
> Provide a value that is the number of hours to scrub memory.
- VarStore `0x5000` · offset `0xcc` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = 1 hour, `4` = 4 hours, `8` = 8 hours, `16` = 16 hours, `24` = 24 hours, `48` = 48 hours, `255` = Auto (default)

##### `0x57` — **Poison scrubber control** (OneOf)
> Control DF::RedirScrubCtrl[RedirScrubMode[1]]
- VarStore `0x5000` · offset `0xcd` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x58` — **Redirect scrubber control** (OneOf)
> Control DF::RedirScrubCtrl[RedirScrubMode[0]]
- VarStore `0x5000` · offset `0xce` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x59` — **Redirect scrubber limit** (OneOf)
> Control DF::RedirScrubCtrl[RedirScrubReqLmt]
- VarStore `0x5000` · offset `0xcf` · 8-bit · range `0x0`..`0xff`
- options: `1` = 2, `2` = 4, `3` = 8, `0` = Infinite, `255` = Auto (default)

##### `0x5a` — **Periodic Directory Rinse** (OneOf)
> Control Periodic Directory Rinse Mode.
- VarStore `0x5000` · offset `0xd0` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

#### Form `0x703c` — Memory Addressing

_Settings:_

##### `0x703f` — **NUMA nodes per socket** (OneOf)
> Specifies the number of desired NUMA nodes per socket.  Zero will attempt to interleave the two sockets together.
- VarStore `0x5000` · offset `0xd1` · 8-bit · range `0x0`..`0x7`
- options: `0` = NPS0, `1` = NPS1, `2` = NPS2, `3` = NPS4, `7` = Auto (default)

##### `0x5b` — **Memory interleaving** (OneOf)
> Allows for disabling memory interleaving.  Note that NUMA nodes per socket will be honored regardless of this setting.
- VarStore `0x5000` · offset `0xd2` · 8-bit · range `0x0`..`0x7`
- options: `0` = Disabled, `7` = Auto (default)

##### `0x7042` — **Memory interleaving size** (OneOf)
> Controls the memory interleaving size. The valid values are AUTO, 256 bytes, 512 bytes, 1 Kbytes, 2 Kbytes and 4 Kbytes. This determines the starting address of the interleave (bit 8, 9, 10, 11 or 12).
- VarStore `0x5000` · offset `0xd3` · 8-bit · range `0x0`..`0x7`
- options: `0` = 256 Bytes, `1` = 512 Bytes, `2` = 1 KB, `3` = 2 KB, `4` = 4 KB, `7` = Auto (default)

##### `0x5c` — **1TB remap** (OneOf)
> Attempt to remap DRAM out of the space just below the 1TB boundary.  The ability to remap depends on DRAM configuration, NPS, and interleaving selection, and may not always be possible.
- VarStore `0x5000` · offset `0xd4` · 8-bit · range `0x0`..`0xff`
- options: `0` = Do not remap, `1` = Attempt to remap, `255` = Auto (default)

##### `0x5d` — **DRAM map inversion** (OneOf)
> Inverting the map will cause the highest memory channels to get assigned the lowest addresses in the system.
- VarStore `0x5000` · offset `0xd5` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x5e` — **Location of private memory regions** (OneOf)
> Controls whether or not the private memory regions (PSP, SMU and CC6) are at the top of DRAM, at the top of 1st DRAM pair or distributed. Note that distributed requires memory on all dies. Note that it will always be at the top of DRAM if some dies don't have memory regardless of this option's setting.
- VarStore `0x5000` · offset `0xd6` · 8-bit · range `0x0`..`0xff`
- options: `0` = Distributed, `1` = Consolidated, `2` = Consolidated to 1st DRAM pair, `255` = Auto (default)

#### Form `0x703d` — ACPI

_Settings:_

##### `0x60` — **ACPI SLIT Distance Control** (OneOf)
> Determines how the SLIT distances are declared.
- VarStore `0x5000` · offset `0xd8` · 8-bit · range `0x0`..`0xff`
- options: `0` = Manual, `255` = Auto (default)

##### `0x61` — **ACPI SLIT remote relative distance** (OneOf)
> Set the remote socket distance for 2P systems as near (2.8) or far (3.2).
- VarStore `0x5000` · offset `0xd9` · 8-bit · range `0x0`..`0xff`
- options: `0` = Near, `1` = Far, `255` = Auto (default)

##### `0x62` — **ACPI SLIT virtual distance** (Numeric)
> Specify the distance between two virtual domains (see L3 Cache as NUMA Domain) in the same physical domain.
- VarStore `0x5000` · offset `0xda` · 8-bit · range `0xa`..`0xff` · default `11`

##### `0x63` — **ACPI SLIT same socket distance** (Numeric)
> Specify the distance to other physical domains within the same socket.
- VarStore `0x5000` · offset `0xdb` · 8-bit · range `0xa`..`0xff` · default `12`

##### `0x64` — **ACPI SLIT remote socket distance** (Numeric)
> Specify the distance to domains on the remote socket.
- VarStore `0x5000` · offset `0xdc` · 8-bit · range `0xa`..`0xff` · default `32`

##### `0x65` — **ACPI SLIT local SLink distance** (Numeric)
> Specify the distance to an SLink domain on the same socket.
- VarStore `0x5000` · offset `0xdd` · 8-bit · range `0xa`..`0xff` · default `50`

##### `0x66` — **ACPI SLIT remote SLink distance** (Numeric)
> Specify the distance to an SLink domain on the other socket.
- VarStore `0x5000` · offset `0xde` · 8-bit · range `0xa`..`0xff` · default `60`

##### `0x67` — **ACPI SLIT local inter-SLink distance** (Numeric)
> Specify the distance between two SLink domains on the same socket.
- VarStore `0x5000` · offset `0xdf` · 8-bit · range `0xa`..`0xff` · default `255`

##### `0x68` — **ACPI SLIT remote inter-SLink distance** (Numeric)
> Specify the distance between two SLink domains, each on a different socket.
- VarStore `0x5000` · offset `0xe0` · 8-bit · range `0xa`..`0xff` · default `255`

#### Form `0x703e` — Link

_Settings:_

##### `0x69` — **GMI encryption control** (OneOf)
> Control GMI link encryption
- VarStore `0x5000` · offset `0xe1` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x6a` — **xGMI encryption control** (OneOf)
> Control xGMI link encryption
- VarStore `0x5000` · offset `0xe2` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x6b` — **CAKE CRC perf bounds Control** (OneOf)
> Customize the amount of performance loss that is acceptable to enable CRC protection
- VarStore `0x5000` · offset `0xe3` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x6c` — **CAKE CRC perf bounds** (Numeric)
> Specify the amount of performance loss that is acceptable to enable CRC protection.  Units are in 0.00001%, Range: disabled (0) - 10% (1000000).
- VarStore `0x5000` · offset `0xe4` · 32-bit · range `0x0`..`0xf4240` · default `100`

##### `0x6d` — **xGMI Link Configuration** (OneOf)
> Configures the number of xGMI2 links used on a multi-socket system.
- VarStore `0x5000` · offset `0xe8` · 8-bit · range `0x0`..`0x3`
- options: `3` = Auto (default), `0` = 2 xGMI Links, `1` = 3 xGMI Links, `2` = 4 xGMI Links

##### `0x6e` — **4-link xGMI max speed** (OneOf)
> Max speed for 4-link xGMI
- VarStore `0x5000` · offset `0xe9` · 8-bit · range `0x0`..`0xff`
- options: `0` = 6.4Gbps, `1` = 7.467Gbps, `2` = 8.533Gbps, `3` = 9.6Gbps, `4` = 10.667Gbps, `5` = 11Gbps, `6` = 12Gbps, `7` = 13Gbps, `8` = 14Gbps, `9` = 15Gbps, `10` = 16Gbps, `11` = 17Gbps, `12` = 18Gbps, `13` = 19Gbps, `14` = 20Gbps, `15` = 21Gbps, `16` = 22Gbps, `17` = 23Gbps, `18` = 24Gbps, `19` = 25Gbps, `255` = Auto (default)

##### `0x6f` — **3-link xGMI max speed** (OneOf)
> Max speed for 3-link xGMI
- VarStore `0x5000` · offset `0xea` · 8-bit · range `0x0`..`0xff`
- options: `0` = 6.4Gbps, `1` = 7.467Gbps, `2` = 8.533Gbps, `3` = 9.6Gbps, `4` = 10.667Gbps, `5` = 11Gbps, `6` = 12Gbps, `7` = 13Gbps, `8` = 14Gbps, `9` = 15Gbps, `10` = 16Gbps, `11` = 17Gbps, `12` = 18Gbps, `13` = 19Gbps, `14` = 20Gbps, `15` = 21Gbps, `16` = 22Gbps, `17` = 23Gbps, `18` = 24Gbps, `19` = 25Gbps, `255` = Auto (default)

##### `0x70` — **xGMI TXEQ Mode** (OneOf)
> Select XGMI TXEQ/RX vetting Mode
- VarStore `0x5000` · offset `0xeb` · 8-bit · range `0x0`..`0xf`
- options: `0` = TXEQ_Disabled, `1` = TXEQ_Lane, `2` = TXEQ_Link, `3` = TXEQ_RX_Vet, `15` = Auto (default)

##### `0x71` — **xGMI 18GACOFC** (OneOf)
> xGMI 18GACOFC control
- VarStore `0x5000` · offset `0xec` · 8-bit · range `0x0`..`0xf`
- options: `15` = Auto (default), `1` = Enable, `0` = Disable

#### Form `0x7003` — UMC Common Options

_Navigation (children):_
- → `0x7045` **DDR4 Common Options**
  - DDR4 Common Options
- → `0x7046` **DRAM Memory Mapping**
  - DRAM Memory Mapping
- → `0x7047` **NVDIMM**
  - NVDIMM
- → `0x7048` **Memory MBIST**
  - Memory MBIST

#### Form `0x7045` — DDR4 Common Options

_Navigation (children):_
- → `0x7049` **DRAM Timing Configuration**
  - DRAM Timing Configuration
- → `0x704a` **DRAM Controller Configuration**
  - DRAM Controller Configuration
- → `0x704b` **CAD Bus Configuration**
  - CAD Bus Configuration
- → `0x704c` **Data Bus Configuration**
  - Data Bus Configuration
- → `0x704d` **Common RAS**
  - Common RAS
- → `0x704e` **Security**
  - Security
- → `0x704f` **Phy Configuration**
  - Phy Configuration

_Settings:_

##### `0x7d` — **Disable tCCD = 5 read command spacing** (OneOf)
> No help string
- VarStore `0x5000` · offset `0xed` · 8-bit · range `0x0`..`0x1`
- options: `0` = No, `1` = Yes (default)

#### Form `0x7049` — DRAM Timing Configuration

_Navigation (children):_
- → `0x7045` **Decline**
  - Decline
- → `0x7051` **Accept**
  - Accept

#### Form `0x7050` — Decline

#### Form `0x7051` — Accept

_Settings:_

##### `0x80` — **Overclock** (OneOf)
> Memory Overclock Settings
- VarStore `0x5000` · offset `0xf0` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Enabled

##### `0x81` — **Memory Clock Speed** (OneOf)
> Specifies the memory clock frequency.
- VarStore `0x5000` · offset `0xf1` · 8-bit · range `0x6`..`0xff`
- options: `255` = Auto (default), `24` = 800MHz, `28` = 933MHz, `32` = 1067MHz, `36` = 1200MHz, `40` = 1333MHz, `44` = 1467MHz, `48` = 1600MHz, `49` = 1633MHz, `50` = 1667MHz, `51` = 1700MHz, `52` = 1733MHz, `53` = 1767MHz, `54` = 1800MHz, `6` = 400MHz

##### `0x82` — **Tcl** (OneOf)
> Specifies the CAS latency.
- VarStore `0x5000` · offset `0xf2` · 8-bit · range `0x8`..`0xff`
- options: `255` = Auto (default), `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk, `28` = 1Ch Clk, `29` = 1Dh Clk, `30` = 1Eh Clk, `31` = 1Fh Clk, `32` = 20h Clk, `33` = 21h Clk

##### `0x83` — **Trcdrd** (OneOf)
> Specifies the RAS# Active to CAS# Read Delay Time.
- VarStore `0x5000` · offset `0xf3` · 8-bit · range `0x8`..`0xff`
- options: `255` = Auto (default), `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk

##### `0x84` — **Trcdwr** (OneOf)
> Specifies the RAS# Active to CAS# Write Delay Time.
- VarStore `0x5000` · offset `0xf4` · 8-bit · range `0x8`..`0xff`
- options: `255` = Auto (default), `8` = 8 Clk, `9` = 9 Clk, `10` = 0A Clk, `11` = 0B Clk, `12` = 0C Clk, `13` = 0D Clk, `14` = 0E Clk, `15` = 0F Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk

##### `0x85` — **Trp** (OneOf)
> Specifies Row Precharge Delay Time.
- VarStore `0x5000` · offset `0xf5` · 8-bit · range `0x8`..`0xff`
- options: `255` = Auto (default), `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk

##### `0x86` — **Tras** (OneOf)
> Specifies the Active to Precharge Delay Time.
- VarStore `0x5000` · offset `0xf6` · 8-bit · range `0x15`..`0xff`
- options: `255` = Auto (default), `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk, `28` = 1Ch Clk, `29` = 1Dh Clk, `30` = 1Eh Clk, `31` = 1Fh Clk, `32` = 20h Clk, `33` = 21h Clk, `34` = 22h Clk, `35` = 23h Clk, `36` = 24h Clk, `37` = 25h Clk, `38` = 26h Clk, `39` = 27h Clk, `40` = 28h Clk, `41` = 29h Clk, `42` = 2Ah Clk, `43` = 2Bh Clk, `44` = 2Ch Clk, `45` = 2Dh Clk, `46` = 2Eh Clk, `47` = 2Fh Clk, `48` = 30h Clk, `49` = 31h Clk, `50` = 32h Clk, `51` = 33h Clk, `52` = 34h Clk, `53` = 35h Clk, `54` = 36h Clk, `55` = 37h Clk, `56` = 38h Clk, `57` = 39h Clk, `58` = 3Ah Clk

##### `0x87` — **Trc Ctrl** (OneOf)
> Specify Trc
- VarStore `0x5000` · offset `0xf7` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x88` — **Trc** (Numeric)
> Specifies Active to Active/Refresh Delay Time. Valid values 87h-1Dh.
- VarStore `0x5000` · offset `0xf8` · 8-bit · range `0x1d`..`0x87` · default `57`

##### `0x89` — **TrrdS** (OneOf)
> Specifies the Activate to Activate Delay Time, different bank group (tRRD_S)
- VarStore `0x5000` · offset `0xf9` · 8-bit · range `0x4`..`0xff`
- options: `255` = Auto (default), `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk

##### `0x8a` — **TrrdL** (OneOf)
> Specifies the Activate to Activate Delay Time, same bank group (tRRD_L)
- VarStore `0x5000` · offset `0xfa` · 8-bit · range `0x4`..`0xff`
- options: `255` = Auto (default), `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk

##### `0x8b` — **Tfaw Ctrl** (OneOf)
> Specify Tfaw
- VarStore `0x5000` · offset `0xfb` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x8c` — **Tfaw** (Numeric)
> Specifies the Four Activate Window Time. Valid values 36h-6h.
- VarStore `0x5000` · offset `0xfc` · 8-bit · range `0x6`..`0x36` · default `26`

##### `0x8d` — **TwtrS** (OneOf)
> Specifies the Minimum Write to Read Time, different bank group
- VarStore `0x5000` · offset `0xfd` · 8-bit · range `0x2`..`0xff`
- options: `255` = Auto (default), `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk

##### `0x8e` — **TwtrL** (OneOf)
> Specifies the Minimum Write to Read Time, same bank group
- VarStore `0x5000` · offset `0xfe` · 8-bit · range `0x2`..`0xff`
- options: `255` = Auto (default), `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk

##### `0x8f` — **Twr Ctrl** (OneOf)
> Specify Twr
- VarStore `0x5000` · offset `0xff` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x90` — **Twr** (Numeric)
> Specifies the Minimum Write Recovery Time. Valid value 51h-Ah
- VarStore `0x5000` · offset `0x100` · 8-bit · range `0xa`..`0x51` · default `18`

##### `0x91` — **Trcpage Ctrl** (OneOf)
> Specify Trcpage
- VarStore `0x5000` · offset `0x101` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x92` — **Trcpage** (Numeric)
> SDRAM Optional Features (tMAW, MAC). Valid value 3FFh - 0h
- VarStore `0x5000` · offset `0x102` · 16-bit · range `0x0`..`0x3ff` · default `0`

##### `0x93` — **TrdrdScL Ctrl** (OneOf)
> Specify TrdrdScL
- VarStore `0x5000` · offset `0x104` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x94` — **TrdrdScL** (Numeric)
> Specifies the CAS to CAS Delay Time, same bank group. Valid values Fh-1h
- VarStore `0x5000` · offset `0x105` · 8-bit · range `0x1`..`0xf` · default `3`

##### `0x95` — **TwrwrScL Ctrl** (OneOf)
> Specify TwrwrScL
- VarStore `0x5000` · offset `0x106` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x96` — **TwrwrScL** (Numeric)
> Specifies the CAS to CAS Delay Time, same bank group. Valid values 3Fh-1h
- VarStore `0x5000` · offset `0x107` · 8-bit · range `0x1`..`0x3f` · default `3`

##### `0x97` — **Trfc Ctrl** (OneOf)
> Specify Trfc
- VarStore `0x5000` · offset `0x108` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x98` — **Trfc** (Numeric)
> Specifies the Refresh Recovery Delay Time (tRFC1). Valid values 3DEh-3Ch
- VarStore `0x5000` · offset `0x109` · 16-bit · range `0x3c`..`0x3de` · default `312`

##### `0x99` — **Trfc2 Ctrl** (OneOf)
> Specify Trfc2
- VarStore `0x5000` · offset `0x10b` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x9a` — **Trfc2** (Numeric)
> Specifies the Refresh Recovery Delay Time (tRFC2).  Valid values 3DEh-3Ch
- VarStore `0x5000` · offset `0x10c` · 16-bit · range `0x3c`..`0x3de` · default `192`

##### `0x9b` — **Trfc4 Ctrl** (OneOf)
> Specify Trfc4
- VarStore `0x5000` · offset `0x10e` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x9c` — **Trfc4** (Numeric)
> Specifies the Refresh Recovery Delay Time (tRFC4). Valid values 3DEh-3Ch
- VarStore `0x5000` · offset `0x10f` · 16-bit · range `0x3c`..`0x3de` · default `132`

##### `0x9d` — **Tcwl** (OneOf)
> Specifies the CAS Write Latency
- VarStore `0x5000` · offset `0x111` · 8-bit · range `0x9`..`0xff`
- options: `255` = Auto (default), `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `14` = 0Eh Clk, `16` = 10h Clk, `18` = 12h Clk, `20` = 14h Clk

##### `0x9e` — **Trtp** (OneOf)
> Specifies the Read CAS# to Precharge Delay Time.
- VarStore `0x5000` · offset `0x112` · 8-bit · range `0x5`..`0xff`
- options: `255` = Auto (default), `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk

##### `0x9f` — **Tcke** (OneOf)
> Specifies the CKE minimum high and low pulse width in memory clock cycles.
- VarStore `0x5000` · offset `0x113` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk, `28` = 1Ch Clk, `29` = 1Dh Clk, `30` = 1Eh Clk, `31` = 1Fh Clk

##### `0xa0` — **Trdwr** (OneOf)
> Specifies the Read to Write turnaround timing.
- VarStore `0x5000` · offset `0x114` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk, `28` = 1Ch Clk, `29` = 1Dh Clk, `30` = 1Eh Clk, `31` = 1Fh Clk

##### `0xa1` — **Twrrd** (OneOf)
> Specifies the Write to Read turnaround timing.
- VarStore `0x5000` · offset `0x115` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk

##### `0xa2` — **TwrwrSc** (OneOf)
> Specifies the Write to Write turnaround timing in the same chipselect.
- VarStore `0x5000` · offset `0x116` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk

##### `0xa3` — **TwrwrSd** (OneOf)
> Specifies the Write to Write turnaround timing in the same DIMM.
- VarStore `0x5000` · offset `0x117` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk

##### `0xa4` — **TwrwrDd** (OneOf)
> Specifies the Write to Write turnaround timing in a different DIMM.
- VarStore `0x5000` · offset `0x118` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk

##### `0xa5` — **TrdrdSc** (OneOf)
> Specifies the Read to Read turnaround timing in the same chipselect.
- VarStore `0x5000` · offset `0x119` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk

##### `0xa6` — **TrdrdSd** (OneOf)
> Specifies the Read to Read turnaround timing in the same DIMM.
- VarStore `0x5000` · offset `0x11a` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk

##### `0xa7` — **TrdrdDd** (OneOf)
> Specifies the Read to Read turnaround timing in a different DIMM.
- VarStore `0x5000` · offset `0x11b` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk

##### `0xa8` — **ProcODT** (OneOf)
> Specifies the Processor ODT
- VarStore `0x5000` · offset `0x11c` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = High Impedance, `1` = 480 ohm, `2` = 240 ohm, `3` = 160 ohm, `8` = 120 ohm, `9` = 96 ohm, `10` = 80 ohm, `11` = 68.6 ohm, `24` = 60 ohm, `25` = 53.3 ohm, `26` = 48 ohm, `27` = 43.6 ohm, `56` = 40 ohm, `57` = 36.9 ohm, `58` = 34.3 ohm, `59` = 32 ohm, `62` = 30 ohm, `63` = 28.2 ohm

#### Form `0x704a` — DRAM Controller Configuration

_Navigation (children):_
- → `0x7052` **DRAM Power Options**
  - DRAM Power Options

_Settings:_

##### `0xaa` — **Cmd2T** (OneOf)
> Select between 1T and 2T mode on ADDR/CMD
- VarStore `0x5000` · offset `0x11d` · 8-bit · range `0x0`..`0xff`
- options: `0` = 1T, `1` = 2T, `255` = Auto (default)

##### `0xab` — **Gear Down Mode** (OneOf)
> Enable or Disable Gear Down Mode
- VarStore `0x5000` · offset `0x11e` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

#### Form `0x7052` — DRAM Power Options

_Settings:_

##### `0xac` — **Power Down Enable** (OneOf)
> Enable or disable DDR power down mode
- VarStore `0x5000` · offset `0x11f` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0xad` — **Power Down Entry Delay** (Numeric)
> Specify value at UMC::CH::DramTiming17 [19:8] PwrDownDly
- VarStore `0x5000` · offset `0x120` · 16-bit · range `0x0`..`0xfff` · default `3000`

##### `0xb1` — **DRAM Refresh Rate** (OneOf)
> DRAM refresh rate
- VarStore `0x5000` · offset `0x125` · 8-bit · range `0x0`..`0x1`
- options: `0` = 7.8 usec (default), `1` = 3.9 usec

#### Form `0x704b` — CAD Bus Configuration

_Settings:_

##### `0xb3` — **CAD Bus Timing User Controls** (OneOf)
> Setup time on CAD bus signals to Auto or Manual
- VarStore `0x5000` · offset `0x127` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Manual

##### `0xb4` — **AddrCmdSetup** (Numeric)
> Setup time on CAD bus signals. Valid values 3Fh-0h.
- VarStore `0x5000` · offset `0x128` · 8-bit · range `0x0`..`0x3f` · default `0`

##### `0xb5` — **CsOdtSetup** (Numeric)
> Setup time on CAD bus signals. Valid values 3Fh-0h.
- VarStore `0x5000` · offset `0x129` · 8-bit · range `0x0`..`0x3f` · default `0`

##### `0xb6` — **CkeSetup** (Numeric)
> Setup time on CAD bus signals. Valid values 3Fh-0h.
- VarStore `0x5000` · offset `0x12a` · 8-bit · range `0x0`..`0x3f` · default `0`

##### `0xb7` — **CAD Bus Drive Strength User Controls** (OneOf)
> Drive Strength on CAD bus signals to Auto or Manual
- VarStore `0x5000` · offset `0x12b` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Manual

##### `0xb8` — **ClkDrvStren** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x12c` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 120.0 Ohm, `1` = 60.0 Ohm, `3` = 40.0 Ohm, `7` = 30.0 Ohm, `15` = 24.0 Ohm, `31` = 20.0 Ohm

##### `0xb9` — **AddrCmdDrvStren** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x12d` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 120.0 Ohm, `1` = 60.0 Ohm, `3` = 40.0 Ohm, `7` = 30.0 Ohm, `15` = 24.0 Ohm, `31` = 20.0 Ohm

##### `0xba` — **CsOdtDrvStren** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x12e` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 120.0 Ohm, `1` = 60.0 Ohm, `3` = 40.0 Ohm, `7` = 30.0 Ohm, `15` = 24.0 Ohm, `31` = 20.0 Ohm

##### `0xbb` — **CkeDrvStren** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x12f` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 120.0 Ohm, `1` = 60.0 Ohm, `3` = 40.0 Ohm, `7` = 30.0 Ohm, `15` = 24.0 Ohm, `31` = 20.0 Ohm

#### Form `0x704c` — Data Bus Configuration

_Settings:_

##### `0xbc` — **Data Bus Configuration User Controls** (OneOf)
> Specify the mode for drive strength to Auto or Manual
- VarStore `0x5000` · offset `0x130` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Manual

##### `0xbd` — **RttNom** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x131` · 8-bit · range `0x0`..`0xff`
- options: `0` = Rtt_Nom Disable, `1` = RZQ/4, `2` = RZQ/2, `3` = RZQ/6, `4` = RZQ/1, `5` = RZQ/5, `6` = RZQ/3, `7` = RZQ/7, `255` = Auto (default)

##### `0xbe` — **RttWr** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x132` · 8-bit · range `0x0`..`0xff`
- options: `0` = Dynamic ODT Off, `1` = RZQ/2, `2` = RZQ/1, `3` = Hi-Z, `4` = RZQ/3, `255` = Auto (default)

##### `0xbf` — **RttPark** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x133` · 8-bit · range `0x0`..`0xff`
- options: `0` = Rtt_PARK Disable, `1` = RZQ/4, `2` = RZQ/2, `3` = RZQ/6, `4` = RZQ/1, `5` = RZQ/5, `6` = RZQ/3, `7` = RZQ/7, `255` = Auto (default)

#### Form `0x704d` — Common RAS

_Navigation (children):_
- → `0x7053` **ECC Configuration**
  - ECC Configuration

_Settings:_

##### `0xc0` — **Data Poisoning** (OneOf)
> Enable/disable data poisoning: UMC_CH::EccCtrl[UcFatalEn] is functional only when UMC_CH::EccCtrl[WrEccEn] is enabled.
- VarStore `0x5000` · offset `0x134` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0xc2` — **RCD Parity** (OneOf)
> Enable or Disable RCD parity
- VarStore `0x5000` · offset `0x136` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = Disabled, `1` = Enabled

##### `0xc3` — **DRAM Address Command Parity Retry** (OneOf)
> UMC_CH::RecCtrl[RecEn][0] and UMC_CH::RecCtrl[MaxParRply]
- VarStore `0x5000` · offset `0x137` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = Disabled, `1` = Enabled

##### `0xc4` — **Max Parity Error Replay** (Numeric)
> Value in hex, 1, 2 or 3 is invalid
- VarStore `0x5000` · offset `0x138` · 8-bit · range `0x0`..`0x3f` · default `8`

##### `0xc5` — **Write CRC Enable** (OneOf)
> Enable write CRC generation. UMC::CH::BeqCtrl1[WrCrcEn]
- VarStore `0x5000` · offset `0x139` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = Disabled, `1` = Enabled

##### `0xc6` — **DRAM Write CRC Enable and Retry Limit** (OneOf)
> UMC_CH::RecCtrl[RecEn][1] and UMC_CH::RecCtrl[MaxCrcRply]
- VarStore `0x5000` · offset `0x13a` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = Disabled, `1` = Enabled

##### `0xc7` — **Max Write CRC Error Replay** (Numeric)
> Value in hex, 1, 2 or 3 is invalid
- VarStore `0x5000` · offset `0x13b` · 8-bit · range `0x0`..`0x3f` · default `8`

##### `0xc8` — **Disable Memory Error Injection** (OneOf)
> True: UMC::CH::MiscCfg[DisErrInj]=1
- VarStore `0x5000` · offset `0x13c` · 8-bit · range `0x0`..`0x1`
- options: `0` = False, `1` = True (default)

#### Form `0x7053` — ECC Configuration

_Settings:_

##### `0xca` — **DRAM ECC Symbol Size** (OneOf)
> DRAM ECC Symbol Size (x4/x8/x16) - UMC_CH::EccCtrl[EccSymbolSize16, EccSymbolSize]
- VarStore `0x5000` · offset `0x13d` · 8-bit · range `0x0`..`0xff`
- options: `0` = x4, `1` = x8, `2` = x16, `255` = Auto (default)

##### `0xcb` — **DRAM ECC Enable** (OneOf)
> Use this option to enable / disable DRAM ECC. Auto will set ECC to enable.
- VarStore `0x5000` · offset `0x13e` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0xcc` — **DRAM UECC Retry** (OneOf)
> Use this option to enable / disable DRAM UECC Retry.
- VarStore `0x5000` · offset `0x13f` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = Enabled, `0` = Disabled

#### Form `0x704e` — Security

_Settings:_

##### `0x7054` — **TSME** (OneOf)
> Transparent SME: AddrTweakEn = 1; ForceEncrEn =0; DataEncrEn = 1
- VarStore `0x5000` · offset `0x140` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0x7055` — **Data Scramble** (OneOf)
> Data scrambling: DataScrambleEn
- VarStore `0x5000` · offset `0x141` · 8-bit · range `0x0`..`0xff`
- options: `1` = Enabled, `0` = Disabled, `255` = Auto (default)

#### Form `0x704f` — Phy Configuration

_Navigation (children):_
- → `0x7056` **PMU Training**
  - PMU Training

#### Form `0x7056` — PMU Training

_Settings:_

##### `0xce` — **DFE Read Training** (OneOf)
> Perform 2D Read Training with DFE on.
- VarStore `0x5000` · offset `0x142` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disable, `1` = Enable, `255` = Auto (default)

##### `0xcf` — **FFE Write Training** (OneOf)
> Perform 2D WriteTraining with FFE on.
- VarStore `0x5000` · offset `0x143` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disable, `1` = Enable, `255` = Auto (default)

##### `0xd0` — **PMU Pattern Bits Control** (OneOf)
> Customize PMU pattern bits
- VarStore `0x5000` · offset `0x144` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0xd1` — **PMU Pattern Bits** (Numeric)
> PMU pattern bits range: 0-0xA
- VarStore `0x5000` · offset `0x145` · 8-bit · range `0x0`..`0xa` · default `0`

##### `0xd2` — **MR6VrefDQ Control** (OneOf)
> Customize voltage reference [VrefDQ] for DDR4
- VarStore `0x5000` · offset `0x146` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Manual

##### `0xd3` — **MR6VrefDQ** (Numeric)
> Set voltage reference [VrefDQ] for DDR4. The range is 0-0x7f
- VarStore `0x5000` · offset `0x147` · 8-bit · range `0x0`..`0x7f` · default `0`

##### `0xd4` — **CPU Vref Training Seed Control** (OneOf)
> Customize CPU Vref training seed
- VarStore `0x5000` · offset `0x148` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Manual

##### `0xd5` — **CPU Vref Training Seed** (Numeric)
> CPU Vref training seed range: 0-0xff
- VarStore `0x5000` · offset `0x149` · 8-bit · range `0x0`..`0xff` · default `0`

#### Form `0x7046` — DRAM Memory Mapping

_Settings:_

##### `0xd6` — **Chipselect Interleaving** (OneOf)
> Interleave memory blocks across the DRAM chip selects for node 0.
- VarStore `0x5000` · offset `0x14a` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `255` = Auto (default)

##### `0xd9` — **Address Hash Bank 2 ColXor** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x14d` · 16-bit · range `0x0`..`0x1fff` · default `1016`

##### `0xda` — **Address Hash Bank** (OneOf)
> Enable or disable bank address hashing
- VarStore `0x5000` · offset `0x14f` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0xdb` — **Address Hash CS** (OneOf)
> Enable or disable CS address hashing
- VarStore `0x5000` · offset `0x150` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = Enabled, `0` = Disabled

##### `0xdc` — **Address Hash Rm** (OneOf)
> Enable or disable RM address hashing
- VarStore `0x5000` · offset `0x151` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = Enabled, `0` = Disabled

##### `0xdd` — **SPD Read Optimization** (OneOf)
> Enable or disable SPD Read Optimization, Enabled - SPD reads are skipped for Reserved fields and most of upper 256 Bytes, Disabled - read all 512 SPD Bytes
- VarStore `0x5000` · offset `0x152` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = Enabled, `0` = Disabled

#### Form `0x7047` — NVDIMM

_Settings:_

##### `0xde` — **Disable NVDIMM-N Feature** (OneOf)
> Disable NVDIMM-N feature for memory margin tool
- VarStore `0x5000` · offset `0x153` · 8-bit · range `0x0`..`0x1`
- options: `0` = No (default), `1` = Yes

#### Form `0x7048` — Memory MBIST

_Navigation (children):_
- → `0x7057` **Data Eye**
  - Data Eye

_Settings:_

##### `0xdf` — **MBIST Enable** (OneOf)
> Enable or disable Memory MBIST
- VarStore `0x5000` · offset `0x154` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default), `1` = Enabled

##### `0xe0` — **MBIST Test Mode** (OneOf)
> Select MBIST Test Mode -Interface Mode (Tests Single and Multiple CS transactions and Basic Connectivity) or Data Eye Mode (Measures Voltage vs. Timing)
- VarStore `0x5000` · offset `0x155` · 8-bit · range `0x0`..`0xff`
- options: `0` = Interface Mode, `1` = Data Eye Mode, `2` = Both, `255` = Auto (default)

##### `0xe1` — **MBIST Aggressors** (OneOf)
> Enable or disable MBIST Aggressor test
- VarStore `0x5000` · offset `0x156` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0xe2` — **MBIST Per Bit Slave Die Reporting** (OneOf)
> Reports 2D Data Eye Results in ABL Log for each DQ, Chipselect, and Channel
- VarStore `0x5000` · offset `0x157` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0xe6` — **Mem BIST Test Select** (OneOf)
> Select the vendor specific tests to use with BIOS memory healing BIST
- VarStore `0x5000` · offset `0x15a` · 8-bit · range `0x0`..`0x2`
- options: `0` = Vendor Tests Enabled (default), `1` = Vendor Tests Disabled, `2` = All Tests - All Vendors

##### `0xe8` — **Mem BIST Post Package Repair Type** (OneOf)
> For DRAM errors found in the BIOS memory BIST select the repair type, soft, hard or test only and do not attempt to repair.
- VarStore `0x5000` · offset `0x15c` · 8-bit · range `0x0`..`0x2`
- options: `0` = Soft Repair (default), `1` = Hard Repair, `2` = No Repairs - Test only

##### `0xe9` — **Specific Vendor Test Option 1** (Numeric)
> Reserved option for vendor specific Memory Healing BIST settings.
- VarStore `0x5000` · offset `0x15d` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0xea` — **Specific Vendor Test Option 2** (Numeric)
> Reserved option for vendor specific Memory Healing BIST settings.
- VarStore `0x5000` · offset `0x161` · 32-bit · range `0x0`..`0xffffffff` · default `0`

#### Form `0x7057` — Data Eye

_Settings:_

##### `0xeb` — **Pattern Select** (OneOf)
> Select pattern
- VarStore `0x5000` · offset `0x165` · 8-bit · range `0x0`..`0x2`
- options: `0` = PRBS (default), `1` = SSO, `2` = Both

##### `0xec` — **Pattern Length** (Numeric)
> This token helps to determine the pattern length. The possible options are N=3...12
- VarStore `0x5000` · offset `0x166` · 8-bit · range `0x3`..`0xc` · default `3`

##### `0xed` — **Aggressor Channel** (OneOf)
> This helps read the aggressors channels. If it is enabled, you can read from one or more than one aggressor channel. The default is set to disabled.
- VarStore `0x5000` · offset `0x167` · 8-bit · range `0x0`..`0x7`
- options: `0` = Disabled, `1` = 1 Aggressor Channel (default), `3` = 3 Aggressor Channels, `7` = 7 Aggressor Channels

##### `0xef` — **Aggressor Static Lane Select Upper 32 bits** (Numeric)
> Static Lane Select for Upper 32 bits. The bit mask represents the bits to be read
- VarStore `0x5000` · offset `0x169` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0xf0` — **Aggressor Static Lane Select Lower 32 Bits** (Numeric)
> Static Lane Select for Lower 32 bits. The bit mask represents the bits to be read
- VarStore `0x5000` · offset `0x16d` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0xf1` — **Aggressor Static Lane Select ECC** (Numeric)
> Static Lane Select for ECC Lanes. The bit mask represents the bits to be read
- VarStore `0x5000` · offset `0x171` · 8-bit · range `0x0`..`0xa` · default `0`

##### `0xf2` — **Aggressor Static Lane Value** (Numeric)
> TBD
- VarStore `0x5000` · offset `0x172` · 8-bit · range `0x0`..`0xa` · default `0`

##### `0xf3` — **Target Static Lane Control** (OneOf)
> Enable or disable target static lane
- VarStore `0x5000` · offset `0x173` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default), `1` = Enabled

##### `0xf4` — **Target Static Lane Select Upper 32 bit** (Numeric)
> Static Lane Select for Upper 32 bit. The bit mask represents the bits to be read. Range: 0-0xFFFFFFFF
- VarStore `0x5000` · offset `0x174` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0xf5` — **Target Static Lane Select Lower 32 Bits** (Numeric)
> Static Lane Select for Lower 32 bit. The bit mask represents the bits to be read. Range 0-0xA
- VarStore `0x5000` · offset `0x178` · 32-bit · range `0x0`..`0xa` · default `0`

##### `0xf6` — **Target Static Lane Select ECC** (Numeric)
> Static Lane Select for ECC. The bit mask represents the bits to be read. Range 0-0xA
- VarStore `0x5000` · offset `0x17c` · 8-bit · range `0x0`..`0xa` · default `0`

##### `0xf7` — **Target Static Lane Value** (Numeric)
> Static Lane value. Range 0-0xA
- VarStore `0x5000` · offset `0x17d` · 8-bit · range `0x0`..`0xa` · default `0`

##### `0xf8` — **Data Eye Type** (OneOf)
> This options determines which results are expected to be captured for Data Eye. Supported options are 1D Voltage Sweep, 1D Timing Sweep, 2D Full Data Eye and Worst Case Margin only.
- VarStore `0x5000` · offset `0x17e` · 8-bit · range `0x0`..`0x3`
- options: `0` = 1D Voltage Sweep, `1` = 1D Timing Sweep, `2` = 2D Full Data Eye, `3` = Worst Case Margin Only (default)

##### `0xf9` — **Worst Case Margin Granularity** (OneOf)
> Select per Chip or per Nibble
- VarStore `0x5000` · offset `0x17f` · 8-bit · range `0x0`..`0x1`
- options: `0` = Per Chip Select (default), `1` = Per Nibble

##### `0xfa` — **Read Voltage Sweep Step Size** (OneOf)
> This option determines the step size for Read Data Eye voltage sweep, Supported options are 1,2 and 4
- VarStore `0x5000` · offset `0x180` · 8-bit · range `0x1`..`0x4`
- options: `1` = 1 (default), `2` = 2, `4` = 4

##### `0xfb` — **Read Timing Sweep Step Size** (OneOf)
> This options supports step size for Read Data Eye. Supported options are 1, 2 and 4
- VarStore `0x5000` · offset `0x181` · 8-bit · range `0x1`..`0x4`
- options: `1` = 1 (default), `2` = 2, `4` = 4

##### `0xfc` — **Write Voltage Sweep Step Size** (OneOf)
> This option determines the step size for write Data Eye voltage sweep, Supported options are 1,2 and 4
- VarStore `0x5000` · offset `0x182` · 8-bit · range `0x1`..`0x4`
- options: `1` = 1 (default), `2` = 2, `4` = 4

##### `0xfd` — **Write Timing Sweep Step Size** (OneOf)
> This options supports step size for write Data Eye. Supported options are 1, 2 and 4
- VarStore `0x5000` · offset `0x183` · 8-bit · range `0x1`..`0x4`
- options: `1` = 1 (default), `2` = 2, `4` = 4

#### Form `0x7004` — NBIO Common Options

_Navigation (children):_
- → `0x7058` **XFR Enhancement**
  - XFR Enhancement
- → `0x7059` **SMU Common Options**
  - SMU Common Options
- → `0x705a` **NBIO RAS Common Options**
  - NBIO RAS Common Options
- → `0x705c` **HIDDEN DYNAMIC INFO**
  - HIDDEN DYNAMIC INFO

_Settings:_

##### `0xfe` — **IOMMU** (OneOf)
> Enable/Disable IOMMU
- VarStore `0x5000` · offset `0x184` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xff` — **DMAr Support** (OneOf)
> Enable DMAr system protection during POST.
- VarStore `0x5000` · offset `0x185` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x100` — **DRTM Virtual Device Support** (OneOf)
> Enable DRTM ACPI virtual device.
- VarStore `0x5000` · offset `0x186` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x103` — **ACS Enable** (OneOf)
> AER must be enabled for ACS enable to work
- VarStore `0x5000` · offset `0x188` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x104` — **PCIe ARI Support** (OneOf)
> Enables Alternative Routing-ID Interpretation
- VarStore `0x5000` · offset `0x189` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disable, `1` = Enable, `15` = Auto (default)

##### `0x105` — **PCIe ARI Enumeration** (OneOf)
> ARI Forwarding Enable for each downstream port
- VarStore `0x5000` · offset `0x18a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disable, `1` = Enable, `15` = Auto (default)

##### `0x107` — **HD Audio Enable** (OneOf)
> Control HD audio enable or disable
- VarStore `0x5000` · offset `0x18c` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enable, `0` = Disabled, `15` = Auto (default)

##### `0x10a` — **Enable AER Cap** (OneOf)
> Enables Advanced Error Reporting Capability
- VarStore `0x5000` · offset `0x18d` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enable, `0` = Disabled, `15` = Auto (default)

##### `0x10b` — **Early Link Speed** (OneOf)
> Set Early Link Speed
- VarStore `0x5000` · offset `0x18e` · 8-bit · range `0x0`..`0x2`
- options: `0` = Auto (default), `1` = Gen1, `2` = Gen2

##### `0x10c` — **Hot Plug Handling mode** (OneOf)
> Control the Hot Plug Handling mode
- VarStore `0x5000` · offset `0x18f` · 8-bit · range `0x1`..`0xf`
- options: `1` = OS First, `3` = Firmware First, `15` = Auto (default)

##### `0x10d` — **Presence Detect Select mode** (OneOf)
> Control the Presence Detect Select mode
- VarStore `0x5000` · offset `0x190` · 8-bit · range `0x0`..`0xf`
- options: `0` = OR, `1` = AND, `15` = Auto (default)

##### `0x10f` — **Enhanced Preferred IO Mode** (OneOf)
> Enabling the Enhanced Preferred I/O mode assures an LCLK value for best performance. (Note: Setting 'LCLK Freq Control' on the same Root Complex which the Preferred IO Bus belongs to, to anything other than 'Auto' will override the Enhanced Preferred IO Mode.)
- VarStore `0x5000` · offset `0x194` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disable, `1` = Enable, `15` = Auto (default)

##### `0x110` — **Data Link Feature Cap** (OneOf)
> Data Link Feature Capability
- VarStore `0x5000` · offset `0x195` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x111` — **Data Link Feature Exchange** (OneOf)
> Data Link Feature Exchange
- VarStore `0x5000` · offset `0x196` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x113` — **SEV-SNP Support** (OneOf)
> Enable or Disable SEV-SNP Support
- VarStore `0x5000` · offset `0x198` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disable (default), `1` = Enable

##### `0x114` — **SRIS** (OneOf)
> SRIS
- VarStore `0x5000` · offset `0x199` · 8-bit · range `0x0`..`0xf`
- options: `15` = Auto (default), `0` = Disable, `1` = Enable

##### `0x115` — **Compliance Loopback** (OneOf)
> Compliance Loopback Test
- VarStore `0x5000` · offset `0x19a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disable, `1` = Enable, `15` = Auto (default)

##### `0x116` — **Multi Upstream Auto Speed Change** (OneOf)
> Defines the setting of this feature for all PCIe devices.  'Auto' uses the DXIO default setting of 0 for Gen1 and 1 for Gen2/3
- VarStore `0x5000` · offset `0x19b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x118` — **RTM Margining Support** (OneOf)
> RTM Margining Support
- VarStore `0x5000` · offset `0x19d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disable, `1` = Enable, `15` = Auto (default)

#### Form `0x7058` — XFR Enhancement

_Navigation (children):_
- → `0x7004` **Declined**
  - Declined
- → `0x705e` **Accepted**
  - Accepted

_Settings:_

##### `0x11c` — **FCLK Frequency** (OneOf)
> Specifies the FCLK frequency.
- VarStore `0x5000` · offset `0x1a0` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 667MHz, `1` = 800MHz, `2` = 933MHz, `3` = 1067MHz, `4` = 1200MHz, `5` = 1333MHz, `6` = 1367MHz, `7` = 1400MHz, `8` = 1433MHz, `9` = 1467MHz, `10` = 1500MHz, `11` = 1533MHz, `12` = 1567MHz, `13` = 1600MHz, `14` = 1633MHz, `15` = 1667MHz, `16` = 1700MHz, `17` = 1733MHz, `18` = 1767MHz, `19` = 1800MHz, `20` = 1833MHz, `21` = 1867MHz, `22` = 1900MHz, `23` = 1933MHz, `24` = 1967MHz, `25` = 2000MHz, `26` = 2033MHz, `27` = 2067MHz, `28` = 2100MHz, `29` = 2133MHz, `30` = 2167MHz, `31` = 2200MHz, `32` = 2233MHz, `33` = 2267MHz, `34` = 2300MHz, `35` = 2333MHz, `36` = 2367MHz, `37` = 2400MHz, `38` = 2433MHz, `39` = 2467MHz, `40` = 2500MHz, `41` = 2550MHz, `42` = 2600MHz, `43` = 2650MHz, `44` = 2700MHz, `45` = 2750MHz, `46` = 2800MHz, `47` = 2850MHz, `48` = 2900MHz, `49` = 2950MHz, `50` = 3000MHz

##### `0x11d` — **MEMCLK Frequency** (OneOf)
> Specifies the MEMCLK frequency.
- VarStore `0x5000` · offset `0x1a1` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 667MHz, `1` = 800MHz, `2` = 933MHz, `3` = 1067MHz, `4` = 1200MHz, `5` = 1333MHz, `6` = 1367MHz, `7` = 1400MHz, `8` = 1433MHz, `9` = 1467MHz, `10` = 1500MHz, `11` = 1533MHz, `12` = 1567MHz, `13` = 1600MHz, `14` = 1633MHz, `15` = 1667MHz, `16` = 1700MHz, `17` = 1733MHz, `18` = 1767MHz, `19` = 1800MHz, `20` = 1833MHz, `21` = 1867MHz, `22` = 1900MHz, `23` = 1933MHz, `24` = 1967MHz, `25` = 2000MHz, `26` = 2033MHz, `27` = 2067MHz, `28` = 2100MHz, `29` = 2133MHz, `30` = 2167MHz, `31` = 2200MHz, `32` = 2233MHz, `33` = 2267MHz, `34` = 2300MHz, `35` = 2333MHz, `36` = 2367MHz, `37` = 2400MHz, `38` = 2433MHz, `39` = 2467MHz, `40` = 2500MHz

##### `0x120` — **VDDP Voltage Control** (OneOf)
> Manual = User can set customized VDDP voltage
- VarStore `0x5000` · offset `0x1a4` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x121` — **VDDP Voltage** (Numeric)
> VDDP is a voltage for the DDR4 bus signaling ('PHY'), and it is derived from your DRAM Voltage ('VDDIO_Mem'). As a result, VDDP (input in mV) can approach but not exceed your DRAM Voltage.
- VarStore `0x5000` · offset `0x1a5` · 16-bit · range `0x0`..`0x7ff` · default `0`

##### `0x122` — **VDDG Voltage Control** (OneOf)
> Manual = User can set customized VDDG voltage
- VarStore `0x5000` · offset `0x1a7` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x123` — **VDDG Voltage** (Numeric)
> VDDG represents voltage for the data portion of the Infinity Fabric. It is derived from the CPU SoC/Uncore Voltage (VDD_SOC). VDDG (input in mV) can approach but not exceed VDD_SOC.
- VarStore `0x5000` · offset `0x1a8` · 16-bit · range `0x0`..`0x7ff` · default `0`

##### `0x124` — **SoC/Uncore OC Mode** (OneOf)
> Forces CPU SoC/uncore components (e.g. Infinity Fabric, memory, and integrated graphics) to run at their maximum specified frequency at all times. May improve performance at the expense of idle power savings.
- VarStore `0x5000` · offset `0x1aa` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = Enabled, `0` = Disabled

##### `0x125` — **LN2 Mode** (OneOf)
> Send a message to SMU to help with cold boot and operating under LN2 conditions for GMI2.
- VarStore `0x5000` · offset `0x1ab` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = Enabled, `0` = Disabled

#### Form `0x705d` — Declined

#### Form `0x705e` — Accepted

_Settings:_

##### `0x127` — **PPT Limit** (Numeric)
> PPT Limit [W], Board Socket Power capability, adjustable up to motherboard programed PPT limit.
- VarStore `0x5000` · offset `0x1ad` · 32-bit · range `0x0`..`0xffff` · default `0`

##### `0x128` — **TDC Limit** (Numeric)
> TDC Limit [A], Board thermally constrained current delivery capability, adjustable up to motherboard programed board TDC limit.
- VarStore `0x5000` · offset `0x1b1` · 32-bit · range `0x0`..`0xffff` · default `0`

##### `0x129` — **EDC Limit** (Numeric)
> EDC Limit [A], Board electrically constrained current delivery capability, adjustable up to motherboard programed board EDC limit.
- VarStore `0x5000` · offset `0x1b5` · 32-bit · range `0x0`..`0xffff` · default `0`

##### `0x12b` — **customized Precision Boost Overdrive Scalar** (OneOf)
> Precision Boost Overdrive increases the maximum boost voltage used (runs above parts specified maximum) and the amount of time spent at that voltage. The larger the value entered the larger the boost voltage used and the longer that voltage will be maintained.
- VarStore `0x5000` · offset `0x1ba` · 32-bit · range `0x64`..`0x3e8`
- options: `100` = 1X, `200` = 2X (default), `300` = 3X, `400` = 4X, `500` = 5X, `600` = 6X, `700` = 7X, `800` = 8X, `900` = 9X, `1000` = 10X

#### Form `0x7059` — SMU Common Options

_Navigation (children):_
- → `0x705f` **Fan Control**
  - Fan Control
- → `0x7066` **LCLK Frequency Control**
  - LCLK Frequency Control

_Settings:_

##### `0x7060` — **cTDP** (Numeric)
> cTDP [W] 0 = Invalid value.
- VarStore `0x5000` · offset `0x1c1` · 32-bit · range `0x0`..`0x18f` · default `0`

##### `0x132` — **Package Power Limit** (Numeric)
> Package Power Limit (PPT) [W]
- VarStore `0x5000` · offset `0x1c7` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x139` — **Fixed SOC Pstate** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1d2` · 8-bit · range `0x0`..`0xf`
- options: `0` = P0, `1` = P1, `2` = P2, `3` = P3, `15` = Auto (default)

##### `0x7062` — **CPPC** (OneOf)
> FEATURE_CPPC_MASK
- VarStore `0x5000` · offset `0x1d3` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x7063` — **HSMP Support** (OneOf)
> Select HSMP support enable or disable
- VarStore `0x5000` · offset `0x1d4` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x7064` — **Diagnostic Mode** (OneOf)
> Select Diag mode enable or disable
- VarStore `0x5000` · offset `0x1d5` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x7065` — **DLWM Support** (OneOf)
> Select DLWM support enable or disable
- VarStore `0x5000` · offset `0x1d6` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x13b` — **BoostFmax** (Numeric)
> Specify the boost Fmax frequency limit to apply to all cores (MHz)
- VarStore `0x5000` · offset `0x1d8` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x13c` — **EDC Current Tracking** (OneOf)
> The generation a correctable MCE when the telemetry current value is over the set threshold defined by EDC Current Tracking Current Threshold.
- VarStore `0x5000` · offset `0x1dc` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disable (default), `1` = Enable

##### `0x13d` — **EDC Tracking Current Threshold** (Numeric)
> The current threshold in AMPs for EDC Current Tracking feature
- VarStore `0x5000` · offset `0x1dd` · 16-bit · range `0x0`..`0xffff` · default `0`

##### `0x13e` — **EDC Tracking Report Interval** (Numeric)
> Reporting interval. Every nth observed excursion results in SMU logging a correctable MCE
- VarStore `0x5000` · offset `0x1df` · 16-bit · range `0x0`..`0xffff` · default `1`

##### `0x141` — **DF PState FClk Limit** (OneOf)
> Selects the fixed PState when DF PState Mode Select is Override
- VarStore `0x5000` · offset `0x1e2` · 8-bit · range `0x0`..`0xff`
- options: `0` = 1600 MHz, `1` = 1467 MHz, `2` = 1333 MHz, `3` = 1200 MHz, `4` = 1067 MHz, `5` = 933 MHz, `6` = 800 MHz, `255` = Auto (default)

##### `0x143` — **EDC** (Numeric)
> VDDCR_CPU EDC Limit [A]
- VarStore `0x5000` · offset `0x1e4` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x144` — **EDC Platform Limit** (Numeric)
> EDC Platform Limit [W]
- VarStore `0x5000` · offset `0x1e8` · 32-bit · range `0x0`..`0xffffffff` · default `0`

#### Form `0x705f` — Fan Control

_Settings:_

##### `0x146` — **Low Temperature** (Numeric)
> Low Temperature ['C]
- VarStore `0x5000` · offset `0x1ed` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x147` — **Medium Temperature** (Numeric)
> Medium Temperature ['C]
- VarStore `0x5000` · offset `0x1ee` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x148` — **High Temperature** (Numeric)
> High Temperature ['C]
- VarStore `0x5000` · offset `0x1ef` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x149` — **Critical Temperature** (Numeric)
> Critical Temperature ['C]
- VarStore `0x5000` · offset `0x1f0` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x14a` — **Low Pwm** (Numeric)
> Low Pwm [0-100]
- VarStore `0x5000` · offset `0x1f1` · 8-bit · range `0x0`..`0x64` · default `0`

##### `0x14b` — **Medium Pwm** (Numeric)
> Medium Pwm [0-100]
- VarStore `0x5000` · offset `0x1f2` · 8-bit · range `0x0`..`0x64` · default `0`

##### `0x14c` — **High Pwm** (Numeric)
> High Pwm [0-100]
- VarStore `0x5000` · offset `0x1f3` · 8-bit · range `0x0`..`0x64` · default `0`

##### `0x14d` — **Temperature Hysteresis** (Numeric)
> Temperature Hysteresis ['C]
- VarStore `0x5000` · offset `0x1f4` · 8-bit · range `0x0`..`0xff` · default `0`

#### Form `0x7066` — LCLK Frequency Control

_Settings:_

##### `0x7067` — **Root Complex 0x00 LCLK Frequency** (OneOf)
> Set Root Complex LCLK Frequency (Bus range 0x00-0x1F). Auto = Dynamic Frequency Control(Enhanced PIO setting will be in effect). 593Mhz = Set LCLK Frequency at 593MHz (Overrides Enhanced PIO setting).
- VarStore `0x5000` · offset `0x1f7` · 8-bit · range `0x2`..`0xf`
- options: `15` = Auto (default), `2` = 593Mhz

##### `0x7068` — **Root Complex 0x20 LCLK Frequency** (OneOf)
> Set Root Complex LCLK Frequency (Bus range 0x20-0x3F). Auto = Dynamic Frequency Control(Enhanced PIO setting will be in effect). 593Mhz = Set LCLK Frequency at 593MHz (Overrides Enhanced PIO setting).
- VarStore `0x5000` · offset `0x1f8` · 8-bit · range `0x2`..`0xf`
- options: `15` = Auto (default), `2` = 593Mhz

##### `0x7069` — **Root Complex 0x40 LCLK Frequency** (OneOf)
> Set Root Complex LCLK Frequency (Bus range 0x40-0x5F). Auto = Dynamic Frequency Control(Enhanced PIO setting will be in effect). 593Mhz = Set LCLK Frequency at 593MHz (Overrides Enhanced PIO setting).
- VarStore `0x5000` · offset `0x1f9` · 8-bit · range `0x2`..`0xf`
- options: `15` = Auto (default), `2` = 593Mhz

##### `0x706a` — **Root Complex 0x60 LCLK Frequency** (OneOf)
> Set Root Complex LCLK Frequency (Bus range 0x60-0x7F). Auto = Dynamic Frequency Control(Enhanced PIO setting will be in effect). 593Mhz = Set LCLK Frequency at 593MHz (Overrides Enhanced PIO setting).
- VarStore `0x5000` · offset `0x1fa` · 8-bit · range `0x2`..`0xf`
- options: `15` = Auto (default), `2` = 593Mhz

##### `0x706b` — **Root Complex 0x80 LCLK Frequency** (OneOf)
> Set Root Complex LCLK Frequency (Bus range 0x80-0x9F). Auto = Dynamic Frequency Control(Enhanced PIO setting will be in effect). 593Mhz = Set LCLK Frequency at 593MHz (Overrides Enhanced PIO setting).
- VarStore `0x5000` · offset `0x1fb` · 8-bit · range `0x2`..`0xf`
- options: `15` = Auto (default), `2` = 593Mhz

##### `0x706c` — **Root Complex 0xA0 LCLK Frequency** (OneOf)
> Set Root Complex LCLK Frequency (Bus range 0xA0-0xBF). Auto = Dynamic Frequency Control(Enhanced PIO setting will be in effect). 593Mhz = Set LCLK Frequency at 593MHz (Overrides Enhanced PIO setting).
- VarStore `0x5000` · offset `0x1fc` · 8-bit · range `0x2`..`0xf`
- options: `15` = Auto (default), `2` = 593Mhz

##### `0x706d` — **Root Complex 0xC0 LCLK Frequency** (OneOf)
> Set Root Complex LCLK Frequency (Bus range 0xC0-0xDF). Auto = Dynamic Frequency Control(Enhanced PIO setting will be in effect). 593Mhz = Set LCLK Frequency at 593MHz (Overrides Enhanced PIO setting).
- VarStore `0x5000` · offset `0x1fd` · 8-bit · range `0x2`..`0xf`
- options: `15` = Auto (default), `2` = 593Mhz

##### `0x706e` — **Root Complex 0xE0 LCLK Frequency** (OneOf)
> Set Root Complex LCLK Frequency (Bus range 0xE0-0xFF). Auto = Dynamic Frequency Control(Enhanced PIO setting will be in effect). 593Mhz = Set LCLK Frequency at 593MHz (Overrides Enhanced PIO setting).
- VarStore `0x5000` · offset `0x1fe` · 8-bit · range `0x2`..`0xf`
- options: `15` = Auto (default), `2` = 593Mhz

#### Form `0x705a` — NBIO RAS Common Options

_Settings:_

##### `0x150` — **NBIO RAS Control** (OneOf)
> (0) Disabled, (1) MCA, (2) Legacy
- VarStore `0x5000` · offset `0x1ff` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = MCA, `2` = Legacy, `15` = Auto (default)

##### `0x151` — **Egress Poison Severity High** (Numeric)
> Each bit set to 1 enables HIGH severity on the associated IOHC egress port. A bit of 0 indicates LOW severity.
- VarStore `0x5000` · offset `0x200` · 32-bit · range `0x0`..`0xffffffff` · default `196625`

##### `0x152` — **Egress Poison Severity Low** (Numeric)
> Each bit set to 1 enables HIGH severity on the associated IOHC egress port. A bit of 0 indicates LOW severity.
- VarStore `0x5000` · offset `0x204` · 32-bit · range `0x0`..`0xffffffff` · default `4`

##### `0x153` — **NBIO SyncFlood Generation** (OneOf)
> This value may be used to mask SyncFlood caused by NBIO RAS options.  When set to TRUE SyncFlood from NBIO is masked.  When set to FALSE NBIO is capable of generating SyncFlood.
- VarStore `0x5000` · offset `0x208` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x154` — **NBIO SyncFlood Reporting** (OneOf)
> This value may be used to enable SyncFlood reporting to APML.  When set to TRUE SyncFlood will be reported to APML.  When set to FALSE that reporting well be disabled
- VarStore `0x5000` · offset `0x209` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x155` — **Egress Poison Mask High** (Numeric)
> These set the enable mask for masking of errors logged in EGRESS_POISON_STATUS. For each bit set to 1, errors are masked.  For each bit set to 0, errors trigger response actions.
- VarStore `0x5000` · offset `0x20a` · 32-bit · range `0x0`..`0xffffffff` · default `4294770687`

##### `0x156` — **Egress Poison Mask Low** (Numeric)
> These set the enable mask for masking of errors logged in EGRESS_POISON_STATUS. For each bit set to 1, errors are masked.  For each bit set to 0, errors trigger response actions.
- VarStore `0x5000` · offset `0x20e` · 32-bit · range `0x0`..`0xffffffff` · default `4294967291`

##### `0x157` — **Uncorrected Converted to Poison Enable Mask High** (Numeric)
> These set the enable mask for masking of uncorrectable parity errors on internal arrays.  For each bit set to 1, a system fatal error event is triggered for UCP errors on arrays associated with that egress port.  For each bit set to 0, errors are masked.
- VarStore `0x5000` · offset `0x212` · 32-bit · range `0x0`..`0xffffffff` · default `196608`

##### `0x158` — **Uncorrected Converted to Poison Enable Mask Low** (Numeric)
> These set the enable mask for masking of uncorrectable parity errors on internal arrays.  For each bit set to 1, a system fatal error event is triggered for UCP errors on arrays associated with that egress port.  For each bit set to 0, errors are masked.
- VarStore `0x5000` · offset `0x216` · 32-bit · range `0x0`..`0xffffffff` · default `4`

##### `0x159` — **System Hub Watchdog Timer** (Numeric)
> This value specifies the timer interval of the SYSHUB Watchdog timer in miliseconds
- VarStore `0x5000` · offset `0x21a` · 32-bit · range `0x0`..`0xffff` · default `2600`

##### `0x15a` — **SLINK Read Response OK** (OneOf)
> This value specifies whether SLINK read response errors are converted to an Okay response.  When this value is set to TRUE, read response errors are converted to Okay responses with data of all FFs.  When set to FALSE read response errors are not converted.
- VarStore `0x5000` · offset `0x21e` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled (default)

##### `0x15b` — **SLINK Read Response Error Handling** (OneOf)
> This value specifies whether SLINK write response errors are converted to an Okay response.  When this value is set to 0, write response errors will be logged in the MCA.  When set to 1, write response errors will trigger an MCOMMIT error. When this value is set to 2, write response errors are converted to Okay responses.
- VarStore `0x5000` · offset `0x21f` · 8-bit · range `0x0`..`0x2`
- options: `2` = Enabled, `1` = Trigger MCOMMIT Error, `0` = Log Errors in MCA (default)

##### `0x15c` — **Log Poison Data from SLINK** (OneOf)
> This value specifies whether poison data propagated from SLINK will generate a deferred error.  When set to TRUE, deferred errors are enabled.  When set to FALSE, errors are not generated.
- VarStore `0x5000` · offset `0x220` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled (default)

##### `0x15d` — **PCIe Aer Reporting Mechanism** (OneOf)
> This value selects the method of reporting AER errors from PCI Express.  A value of 1 allows OS First handling of the errors through generation of a system control interrupt (SCI).  A value of 2 provides for Firmware First handling of errors through generation of a system management interrupt (SMI).
- VarStore `0x5000` · offset `0x221` · 8-bit · range `0x1`..`0xf`
- options: `2` = Firmware First, `1` = OS First, `15` = Auto (default)

##### `0x15e` — **Edpc Control** (OneOf)
> (0) Disabled; (1) Enabled; (3) Auto
- VarStore `0x5000` · offset `0x222` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x15f` — **NBIO Poison Consumption** (OneOf)
> NBIO Poison Consumption
- VarStore `0x5000` · offset `0x223` · 8-bit · range `0x0`..`0x2`
- options: `0` = Auto (default), `1` = Enabled, `2` = Disabled

#### Form `0x705c` — HIDDEN DYNAMIC INFO

_Settings:_

##### `0x161` — **Number of Sockets** (Numeric)
> Hidden option. The info that reference from other NBIO CBS options
- VarStore `0x5000` · offset `0x225` · 8-bit · range `0x0`..`0xff` · default `1`

##### `0x162` — **EPIO Setting Override** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x226` · 8-bit · range `0x0`..`0x1`
- options: `0` = False (default), `1` = True

#### Form `0x7005` — FCH Common Options

_Navigation (children):_
- → `0x706f` **SATA Configuration Options**
  - SATA Configuration Options
- → `0x7070` **USB Configuration Options**
  - USB Configuration Options
- → `0x7071` **SD Dump Options**
  - SD Dump Options
- → `0x7072` **Ac Power Loss Options**
  - Ac Power Loss Options
- → `0x7073` **I2C Configuration Options**
  - I2C Configuration Options
- → `0x7074` **Uart Configuration Options**
  - Uart Configuration Options
- → `0x7075` **FCH RAS Options**
  - FCH RAS Options
- → `0x7076` **Miscellaneous Options**
  - Miscellaneous Options

#### Form `0x706f` — SATA Configuration Options

_Navigation (children):_
- → `0x7078` **SATA Controller options**
  - SATA Controller options

_Settings:_

##### `0x7077` — **SATA Enable** (OneOf)
> Disable or enable OnChip SATA controller
- VarStore `0x5000` · offset `0x227` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x16b` — **SATA Mode** (OneOf)
> Select OnChip SATA Type
- VarStore `0x5000` · offset `0x228` · 8-bit · range `0x2`..`0xf`
- options: `2` = AHCI (default), `5` = AHCI as ID 0x7904, `15` = Auto

##### `0x16c` — **Sata RAS Support** (OneOf)
> Disable or enable Sata RAS Support
- VarStore `0x5000` · offset `0x229` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x16d` — **Sata Disabled AHCI Prefetch Function** (OneOf)
> Disable or enable Sata Disabled AHCI Prefetch Function
- VarStore `0x5000` · offset `0x22a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x16e` — **Aggresive SATA Device Sleep Port 0** (OneOf)
> Enable or disable aggresive SATA device sleep on port 0
- VarStore `0x5000` · offset `0x22b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x16f` — **DevSleep0 Port Number** (Numeric)
> DEVSLP port 0
- VarStore `0x5000` · offset `0x22c` · 8-bit · range `0x0`..`0x7` · default `0`

##### `0x170` — **Aggresive SATA Device Sleep Port 1** (OneOf)
> Enable or disable aggresive SATA device sleep on port 1
- VarStore `0x5000` · offset `0x22d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x171` — **DevSleep1 Port Number** (Numeric)
> DEVSLP port 1
- VarStore `0x5000` · offset `0x22e` · 8-bit · range `0x0`..`0x7` · default `0`

#### Form `0x7078` — SATA Controller options

_Navigation (children):_
- → `0x7079` **SATA Controller Enable**
  - SATA Controller Enable
- → `0x707a` **SATA Controller eSATA**
  - SATA Controller eSATA
- → `0x707b` **SATA Controller DevSlp**
  - SATA Controller DevSlp
- → `0x707c` **SATA Controller SGPIO**
  - SATA Controller SGPIO

#### Form `0x7079` — SATA Controller Enable

#### Form `0x707a` — SATA Controller eSATA

_Navigation (children):_
- → `0x707d` **Sata0 eSATA**
  - Sata0 eSATA
- → `0x707e` **Sata1 eSATA**
  - Sata1 eSATA
- → `0x707f` **Sata2 eSATA**
  - Sata2 eSATA
- → `0x7080` **Sata3 eSATA**
  - Sata3 eSATA
- → `0x7081` **Sata4 eSATA**
  - Sata4 eSATA
- → `0x7082` **Sata5 eSATA**
  - Sata5 eSATA
- → `0x7083` **Sata6 eSATA**
  - Sata6 eSATA
- → `0x7084` **Sata7 eSATA**
  - Sata7 eSATA

#### Form `0x707d` — Sata0 eSATA

_Settings:_

##### `0x187` — **Sata0 eSATA Port0** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x237` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x188` — **Sata0 eSATA Port1** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x238` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x189` — **Sata0 eSATA Port2** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x239` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x18a` — **Sata0 eSATA Port3** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x23a` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x18b` — **Sata0 eSATA Port4** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x23b` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x18c` — **Sata0 eSATA Port5** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x23c` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x18d` — **Sata0 eSATA Port6** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x23d` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x18e` — **Sata0 eSATA Port7** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x23e` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

#### Form `0x707e` — Sata1 eSATA

_Settings:_

##### `0x18f` — **Sata1 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x23f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x190` — **Sata1 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x240` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x191` — **Sata1 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x241` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x192` — **Sata1 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x242` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x193` — **Sata1 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x243` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x194` — **Sata1 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x244` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x195` — **Sata1 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x245` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x196` — **Sata1 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x246` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x707f` — Sata2 eSATA

_Settings:_

##### `0x197` — **Sata2 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x247` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x198` — **Sata2 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x248` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x199` — **Sata2 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x249` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x19a` — **Sata2 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x24a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x19b` — **Sata2 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x24b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x19c` — **Sata2 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x24c` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x19d` — **Sata2 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x24d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x19e` — **Sata2 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x24e` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7080` — Sata3 eSATA

_Settings:_

##### `0x19f` — **Sata3 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x24f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a0` — **Sata3 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x250` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a1` — **Sata3 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x251` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a2` — **Sata3 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x252` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a3` — **Sata3 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x253` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a4` — **Sata3 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x254` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a5` — **Sata3 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x255` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a6` — **Sata3 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x256` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7081` — Sata4 eSATA

_Settings:_

##### `0x1a7` — **Sata4 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x257` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a8` — **Sata4 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x258` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a9` — **Sata4 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x259` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1aa` — **Sata4 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x25a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1ab` — **Sata4 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x25b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1ac` — **Sata4 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x25c` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1ad` — **Sata4 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x25d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1ae` — **Sata4 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x25e` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7082` — Sata5 eSATA

_Settings:_

##### `0x1af` — **Sata5 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x25f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b0` — **Sata5 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x260` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b1` — **Sata5 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x261` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b2` — **Sata5 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x262` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b3` — **Sata5 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x263` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b4` — **Sata5 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x264` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b5` — **Sata5 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x265` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b6` — **Sata5 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x266` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7083` — Sata6 eSATA

_Settings:_

##### `0x1b7` — **Sata6 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x267` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b8` — **Sata6 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x268` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b9` — **Sata6 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x269` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1ba` — **Sata6 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x26a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1bb` — **Sata6 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x26b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1bc` — **Sata6 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x26c` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1bd` — **Sata6 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x26d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1be` — **Sata6 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x26e` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7084` — Sata7 eSATA

_Settings:_

##### `0x1bf` — **Sata7 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x26f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1c0` — **Sata7 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x270` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1c1` — **Sata7 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x271` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1c2` — **Sata7 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x272` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1c3` — **Sata7 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x273` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1c4` — **Sata7 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x274` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1c5` — **Sata7 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x275` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1c6` — **Sata7 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x276` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x707b` — SATA Controller DevSlp

_Navigation (children):_
- → `0x7085` **Socket1 DevSlp**
  - Socket1 DevSlp

#### Form `0x7085` — Socket1 DevSlp

_Settings:_

##### `0x1c8` — **Socket1 DevSlp0 Enable** (OneOf)
> Only Sata0 on each IOD/socket support DevSlp.
- VarStore `0x5000` · offset `0x277` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1c9` — **DevSleep0 Port Number** (Numeric)
> DEVSLP port 0
- VarStore `0x5000` · offset `0x278` · 8-bit · range `0x0`..`0x7` · default `0`

##### `0x1ca` — **Socket1 DevSlp1 Enable** (OneOf)
> Only Sata0 on each IOD/socket support DevSlp.
- VarStore `0x5000` · offset `0x279` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1cb` — **DevSleep1 Port Number** (Numeric)
> DEVSLP port 1
- VarStore `0x5000` · offset `0x27a` · 8-bit · range `0x0`..`0x7` · default `1`

#### Form `0x707c` — SATA Controller SGPIO

_Settings:_

##### `0x1cc` — **Sata0 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata0
- VarStore `0x5000` · offset `0x27b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1cd` — **Sata1 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata1
- VarStore `0x5000` · offset `0x27c` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto

##### `0x1ce` — **Sata2 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata2
- VarStore `0x5000` · offset `0x27d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1cf` — **Sata3 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata3
- VarStore `0x5000` · offset `0x27e` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1d0` — **Sata4 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata4 (Socket1)
- VarStore `0x5000` · offset `0x27f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1d1` — **Sata5 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata5 (Socket1)
- VarStore `0x5000` · offset `0x280` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1d2` — **Sata6 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata6 (Socket1)
- VarStore `0x5000` · offset `0x281` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1d3` — **Sata7 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata7 (Socket1)
- VarStore `0x5000` · offset `0x282` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7070` — USB Configuration Options

_Navigation (children):_
- → `0x7086` **MCM USB enable**
  - MCM USB enable

_Settings:_

##### `0x1d4` — **XHCI Controller0 enable** (OneOf)
> Enable or disable USB3 controller.
- VarStore `0x5000` · offset `0x283` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x1d5` — **XHCI Controller1 enable** (OneOf)
> Enable or disable USB3 controller.
- VarStore `0x5000` · offset `0x284` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x1d6` — **USB ecc SMI Enable** (OneOf)
> Enable or disable USB ecc SMI
- VarStore `0x5000` · offset `0x285` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enable, `0` = Off, `15` = Auto (default)

#### Form `0x7086` — MCM USB enable

_Settings:_

##### `0x1d8` — **XHCI2 enable (Socket1)** (OneOf)
> Enable or disable USB3 controller.
- VarStore `0x5000` · offset `0x286` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x1d9` — **XHCI3 enable (Socket1)** (OneOf)
> Enable or disable USB3 controller.
- VarStore `0x5000` · offset `0x287` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

#### Form `0x7071` — SD Dump Options

_Settings:_

##### `0x1da` — **SD Configuration Mode** (OneOf)
> Select SD Mode
- VarStore `0x5000` · offset `0x288` · 8-bit · range `0x0`..`0x6`
- options: `0` = SD Dump disabled (default), `6` = SD Dump enabled

#### Form `0x7072` — Ac Power Loss Options

_Settings:_

##### `0x1db` — **Ac Loss Control** (OneOf)
> Select Ac Loss Control Method
- VarStore `0x5000` · offset `0x289` · 8-bit · range `0x0`..`0xf`
- options: `0` = Always Off, `1` = Always On (default), `2` = Reserved, `3` = Previous, `15` = Auto

#### Form `0x7073` — I2C Configuration Options

_Settings:_

##### `0x1dc` — **I2C 0 Enable** (OneOf)
> Enable or disable I2C 0
- VarStore `0x5000` · offset `0x28a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1dd` — **I2C 1 Enable** (OneOf)
> Enable or disable I2C 1
- VarStore `0x5000` · offset `0x28b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1de` — **I2C 2 Enable** (OneOf)
> Enable or disable I2C 2
- VarStore `0x5000` · offset `0x28c` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1df` — **I2C 3 Enable** (OneOf)
> Enable or disable I2C 3
- VarStore `0x5000` · offset `0x28d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1e0` — **I2C 4 Enable** (OneOf)
> Enable or disable I2C 4
- VarStore `0x5000` · offset `0x28e` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1e1` — **I2C 5 Enable** (OneOf)
> Enable or disable I2C 5
- VarStore `0x5000` · offset `0x28f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7074` — Uart Configuration Options

_Settings:_

##### `0x1e2` — **Uart 0 Enable** (OneOf)
> Uart 0 has no HW FC if Uart 2 is enabled
- VarStore `0x5000` · offset `0x290` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1e3` — **Uart 0 Legacy Options** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x291` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = 0x2E8, `2` = 0x2F8, `3` = 0x3E8, `4` = 0x3F8, `15` = Auto (default)

##### `0x1e4` — **Uart 1 Enable** (OneOf)
> Uart 1 has no HW FC if Uart 3 is enabled
- VarStore `0x5000` · offset `0x292` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1e5` — **Uart 1 Legacy Options** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x293` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = 0x2E8, `2` = 0x2F8, `3` = 0x3E8, `4` = 0x3F8, `15` = Auto (default)

##### `0x1e6` — **Uart 2 Enable (no HW FC)** (OneOf)
> Uart 2 has no HW FC if Uart 0 is enabled
- VarStore `0x5000` · offset `0x294` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1e7` — **Uart 2 Legacy Options** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x295` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = 0x2E8, `2` = 0x2F8, `3` = 0x3E8, `4` = 0x3F8, `15` = Auto (default)

##### `0x1e8` — **Uart 3 Enable (no HW FC)** (OneOf)
> Uart 3 has no HW FC if Uart 1 is enabled
- VarStore `0x5000` · offset `0x296` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1e9` — **Uart 3 Legacy Options** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x297` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = 0x2E8, `2` = 0x2F8, `3` = 0x3E8, `4` = 0x3F8, `15` = Auto (default)

#### Form `0x7075` — FCH RAS Options

_Settings:_

##### `0x1ea` — **ALink RAS Support** (OneOf)
> Enable ALink RAS Support
- VarStore `0x5000` · offset `0x298` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7076` — Miscellaneous Options

#### Form `0x7006` — NTB Common Options

_Settings:_

##### `0x1ed` — **Socket-0 P0 NTB Enable** (OneOf)
> Enable NTB on Socket-0 P0 Link
- VarStore `0x5000` · offset `0x29b` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Enable

##### `0x1ee` — **Socket-0 P0 Start Lane** (Numeric)
> NTB Start Lane on Socket-0 P0 Link
- VarStore `0x5000` · offset `0x29c` · 8-bit · range `0x0`..`0xf` · default `0`

##### `0x1ef` — **Socket-0 P0 End Lane** (Numeric)
> NTB End Lane on Socket-0 P0 Link
- VarStore `0x5000` · offset `0x29d` · 8-bit · range `0x0`..`0xf` · default `15`

##### `0x1f0` — **Socket-0 P0 Link Speed** (OneOf)
> Link Speed for Socket-0 P0 Link
- VarStore `0x5000` · offset `0x29e` · 8-bit · range `0x1`..`0xf`
- options: `15` = Auto (default), `1` = Gen 1, `2` = Gen 2, `3` = Gen 3, `4` = Gen 4

##### `0x1f1` — **Socket-0 P0 NTB Mode** (OneOf)
> NTB Mode for Socket-0 P0 Link
- VarStore `0x5000` · offset `0x29f` · 8-bit · range `0x0`..`0xf`
- options: `15` = Auto (default), `0` = NTB Disabled, `1` = NTB Primary, `2` = NTB Secondary

##### `0x1f2` — **Socket-0 P1 NTB Enable** (OneOf)
> Enable NTB on Socket-0 P1 Link
- VarStore `0x5000` · offset `0x2a0` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Enable

##### `0x1f3` — **Socket-0 P1 Start Lane** (Numeric)
> NTB Start Lane on Socket-0 P1 Link
- VarStore `0x5000` · offset `0x2a1` · 8-bit · range `0x20`..`0x2f` · default `32`

##### `0x1f4` — **Socket-0 P1 End Lane** (Numeric)
> NTB End Lane on Socket-0 P1 Link
- VarStore `0x5000` · offset `0x2a2` · 8-bit · range `0x20`..`0x2f` · default `47`

##### `0x1f5` — **Socket-0 P1 Link Speed** (OneOf)
> Link Speed for Socket-0 P1 Link
- VarStore `0x5000` · offset `0x2a3` · 8-bit · range `0x1`..`0xf`
- options: `15` = Auto (default), `1` = Gen 1, `2` = Gen 2, `3` = Gen 3, `4` = Gen 4

##### `0x1f6` — **Socket-0 P1 NTB Mode** (OneOf)
> NTB Mode for Socket-0 P1 Link
- VarStore `0x5000` · offset `0x2a4` · 8-bit · range `0x0`..`0xf`
- options: `15` = Auto (default), `0` = NTB Disabled, `1` = NTB Primary, `2` = NTB Secondary

##### `0x1f7` — **Socket-0 P2 NTB Enable** (OneOf)
> Enable NTB on Socket-0 P2 Link
- VarStore `0x5000` · offset `0x2a5` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Enable

##### `0x1f8` — **Socket-0 P2 Start Lane** (Numeric)
> NTB Start Lane on Socket-0 P2 Link
- VarStore `0x5000` · offset `0x2a6` · 8-bit · range `0x50`..`0x5f` · default `80`

##### `0x1f9` — **Socket-0 P2 End Lane** (Numeric)
> NTB End Lane on Socket-0 P2 Link
- VarStore `0x5000` · offset `0x2a7` · 8-bit · range `0x50`..`0x5f` · default `95`

##### `0x1fa` — **Socket-0 P2 Link Speed** (OneOf)
> Link Speed for Socket-0 P2 Link
- VarStore `0x5000` · offset `0x2a8` · 8-bit · range `0x1`..`0xf`
- options: `15` = Auto (default), `1` = Gen 1, `2` = Gen 2, `3` = Gen 3, `4` = Gen 4

##### `0x1fb` — **Socket-0 P2 NTB Mode** (OneOf)
> NTB Mode for Socket-0 P2 Link
- VarStore `0x5000` · offset `0x2a9` · 8-bit · range `0x0`..`0xf`
- options: `15` = Auto (default), `0` = NTB Disabled, `1` = NTB Primary, `2` = NTB Secondary

##### `0x1fc` — **Socket-0 P3 NTB Enable** (OneOf)
> Enable NTB on Socket-0 P3 Link
- VarStore `0x5000` · offset `0x2aa` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Enable

##### `0x1fd` — **Socket-0 P3 Start Lane** (Numeric)
> NTB Start Lane on Socket-0 P3 Link
- VarStore `0x5000` · offset `0x2ab` · 8-bit · range `0x70`..`0x7f` · default `112`

##### `0x1fe` — **Socket-0 P3 End Lane** (Numeric)
> NTB End Lane on Socket-0 P3 Link
- VarStore `0x5000` · offset `0x2ac` · 8-bit · range `0x70`..`0x7f` · default `127`

##### `0x1ff` — **Socket-0 P3 Link Speed** (OneOf)
> Link Speed for Socket-0 P3 Link
- VarStore `0x5000` · offset `0x2ad` · 8-bit · range `0x1`..`0xf`
- options: `15` = Auto (default), `1` = Gen 1, `2` = Gen 2, `3` = Gen 3, `4` = Gen 4

##### `0x200` — **Socket-0 P3 NTB Mode** (OneOf)
> NTB Mode for Socket-0 P3 Link
- VarStore `0x5000` · offset `0x2ae` · 8-bit · range `0x0`..`0xf`
- options: `15` = Auto (default), `0` = NTB Disabled, `1` = NTB Primary, `2` = NTB Secondary

#### Form `0x7007` — Soc Miscellaneous Control

#### Form `0x7008` — Workload Tuning

_Settings:_

##### `0x205` — **Workload Profile** (OneOf)
> Select the profile for different workloads.
- VarStore `0x5000` · offset `0x2c9` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = CPU Intensive, `2` = Java Throughput, `3` = Java Latency, `4` = Power Efficiency, `5` = Memory Throughput Intensive, `6` = Storage IO Intensive, `7` = NIC Throughput Intensive, `8` = NIC Latency Sensitive, `9` = Accelerator Throughput, `10` = VMware vSphere Optimized, `11` = Linux KVM Optimized, `12` = Container Optimized, `13` = RDBMS Optimized, `14` = Big Data Analytics Optimized, `15` = IOT Gateway, `16` = HPC Optimized, `17` = OpenStack NFV, `18` = OpenStack for RealTime Kernel, `255` = Auto (default)

##### `0x206` — **Performance Tracing** (OneOf)
> Enable to allow capturing performance traces.
- VarStore `0x5000` · offset `0x2ca` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

## Module: `52_AmdPbsSetupDxe.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `B863B959-0EC6-4033-99C1-8FD89F040222`
- FormSet title: **AMD PBS**
- FormSet help: AMD PBS Setup Page

### VarStores
- `0x1` **AMD_PBS_SETUP** — GUID `A339D746-F678-49B3-9FC7-54CE0F9DF226`, size `0x80`
- `0xf000` **SystemAccess** — GUID `E770BB69-BCB4-4D04-9E97-23FF9456FEAC`, size `0x1`

### Forms

#### Form `0xb` — AMD PBS Option

_Navigation (children):_
- → `0xc` **RAS**
  - AMD CPM RAS related settings

_Settings:_

##### `0x2` — **SPI Locking** (OneOf)
> Enable/ disable SPI Locking for protect ROM part
- VarStore `0x1` · offset `0x9` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled 
- conditions: GrayOutIf(Q0x1f=0x1)

##### `0x3` — **iLA TraceMemoryEn** (OneOf)
> Reserved 1M bytes MMIO space on 1M boundary when iLA TraceMemoryEn enabled
- VarStore `0x1` · offset `0x2f` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default), `1` = Enabled 

##### `0x4` — **SRIS mode debug** (OneOf)
> Control SRIS mode debug
- VarStore `0x1` · offset `0x31` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled , `15` = Auto (default, mfg)

##### `0x5` — **Skip interval** (OneOf)
> Appears in the order of SRNS (Gen2 & below); SRIS (Gen2 & below); SRNS (Gen3 & above); SRIS (Gen3 & above). It is ok to enable REFCLK Spread Spectrum for this feature.
- VarStore `0x1` · offset `0x32` · 8-bit · range `0x0`..`0x3`
- options: `0` = 1506; 144; 6050; 640 (default, mfg), `1` = 1538; 154; 6068; 656, `2` = 1358; 128; 6032; 624, `3` = 1180; 112; 5996; 608

##### `0x6` — **LOWER_SKP_OS_GEN_SUPPORT** (OneOf)
> Control LOWER_SKP_OS_GEN_SUPPORT
- VarStore `0x1` · offset `0x33` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled (default, mfg), `1` = Gen1, `3` = Gen2, `7` = Gen3, `15` = Gen4

##### `0x7` — **LOWER_SKP_OS_RCV_SUPPORT** (OneOf)
> Control LOWER_SKP_OS_RCV_SUPPORT
- VarStore `0x1` · offset `0x34` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled (default, mfg), `1` = Gen1, `3` = Gen2, `7` = Gen3, `15` = Gen4

##### `0x8` — **SRIS Autodetect** (OneOf)
> Control SRIS Autodetect
- VarStore `0x1` · offset `0x35` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled , `15` = Auto (default, mfg)

##### `0x9` — **SKP Interval Selection Mode** (OneOf)
> Controls the SKP ordered set interval selection method
- VarStore `0x1` · offset `0x36` · 8-bit · range `0x0`..`0x2`
- options: `0` = SKP ordered set Interval Lock Mode, `1` = Dynamic SKP ordered set Interval Mode (default, mfg), `2` = Far End Nominal Empty Mode

##### `0xa` — **Autodetect Factor** (OneOf)
> Controls the Autodetection factor
- VarStore `0x1` · offset `0x37` · 8-bit · range `0x0`..`0x3`
- options: `0` = 1x (default, mfg), `1` = 0.95x, `2` = 0.9x, `3` = 0.85x

#### Form `0xc` — RAS

_Settings:_

##### `0xb` — **RAS Periodic SMI Control** (OneOf)
> Enable/ disable Periodic SMI for polling [MCA Threshold] error
- VarStore `0x1` · offset `0x0` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled  (default, mfg)
- conditions: GrayOutIf(Q0x1f=0x1)

##### `0xc` — **SMI Threshold** (Numeric)
> The [SMI Threshold] limits the number of [MCA Threshold and Deferred Error SMI source] per a Unit time (Defined by [SMI Scale]). (Default: 5 dec interrupts)
- VarStore `0x1` · offset `0x1` · 32-bit · range `0x0`..`0xffff` · default `5`
- conditions: SuppressIf(Q0xb=0x0)

##### `0xd` — **SMI Scale** (Numeric)
> The [SMI Scale] defines the time scale. (Default: 1000 dec)
- VarStore `0x1` · offset `0x5` · 32-bit · range `0x0`..`0x7fff` · default `1000`

##### `0xe` — **SMI Scale Unit** (OneOf)
> The [SMI Scale Unit] defines the unit of time scale. (Default: ms)
- VarStore `0x1` · offset `0xa` · 8-bit · range `0x0`..`0x2`
- options: `0` = millisecond (default, mfg), `1` = second, `2` = minute

##### `0xf` — **SMI Period** (Numeric)
> The [SMI Period] defines the polling interval (Default: 1000 dec, Maximum: 32767 dec, 0: Disable, Unit: ms)
- VarStore `0x1` · offset `0xb` · 32-bit · range `0x0`..`0x7fff` · default `1000`

##### `0x10` — **GHES Notify Type** (OneOf)
> Notification type for deferred/corrected errors
- VarStore `0x1` · offset `0xf` · 8-bit · range `0x0`..`0x1`
- options: `0` = Polled (default, mfg), `1` = SCI
- conditions: GrayOutIf(Q0x1f=0x1)

##### `0x11` — **GHES UnCorr Notify Type** (OneOf)
> Notification type for uncorrected errors
- VarStore `0x1` · offset `0x2c` · 8-bit · range `0x0`..`0x1`
- options: `0` = Polled, `1` = NMI (default, mfg)

##### `0x12` — **PCIe GHES Notify Type** (OneOf)
> Notification type for PCIe corrected errors
- VarStore `0x1` · offset `0x10` · 8-bit · range `0x0`..`0x1`
- options: `0` = Polled (default, mfg), `1` = SCI

##### `0x13` — **PCIe UnCorr GHES Notify Type** (OneOf)
> Notification type for PCIe uncorrected errors
- VarStore `0x1` · offset `0x2d` · 8-bit · range `0x0`..`0x1`
- options: `0` = Polled, `1` = NMI (default, mfg)

##### `0x14` — **PCIe Root Port Corr Err Mask Reg** (Numeric)
> Initialize the PCIe AER Corrected Error Mask register of Root Port
- VarStore `0x1` · offset `0x11` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x15` — **PCIe Root Port UnCorr Err Mask Reg** (Numeric)
> Initialize the PCIe AER Uncorrected Error Mask register of Root Port
- VarStore `0x1` · offset `0x15` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x16` — **Pcie Root Port UnCorr Error Sev Reg** (Numeric)
> Initialize the PCIe AER Uncorrected Error Severity registers of Root Port
- VarStore `0x1` · offset `0x19` · 32-bit · range `0x0`..`0xffffffff` · default `133128240`

##### `0x17` — **PCIe Device Corr Err Mask Reg** (Numeric)
> Initialize the PCIe AER Corrected Error Mask register of PCIe Device
- VarStore `0x1` · offset `0x1d` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x18` — **PCIe Device UnCorr Err Mask Reg** (Numeric)
> Initialize the PCIe AER Uncorrected Error Mask register of PCIe Device
- VarStore `0x1` · offset `0x21` · 32-bit · range `0x0`..`0xffffffff` · default `1048576`

##### `0x19` — **Pcie Device UnCorr Error Sev Reg** (Numeric)
> Initialize the PCIe AER Uncorrected Error Severity registers of PCIe Device
- VarStore `0x1` · offset `0x25` · 32-bit · range `0x0`..`0xffffffff` · default `133128240`

##### `0x1a` — **CCIX GHES Deferred Err Notify Type** (OneOf)
> Notification type for CCIX deferred error
- VarStore `0x1` · offset `0x29` · 8-bit · range `0x0`..`0x1`
- options: `0` = Polled (default, mfg), `1` = SCI

##### `0x1b` — **CCIX GHES Corrected Err Notify Type** (OneOf)
> Notification type for CCIX Corrected error
- VarStore `0x1` · offset `0x2a` · 8-bit · range `0x0`..`0x1`
- options: `0` = Polled (default, mfg), `1` = SCI

##### `0x1c` — **DDR4 DRAM Hard Post Package Repair** (OneOf)
> This feature allows spare DRAM rows to replace malfunctioning rows via an in-field repair mechanism
- VarStore `0x1` · offset `0x2b` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled 

##### `0x1d` — **HEST DMC Structure Support** (OneOf)
> HEST DMC(Deferred Machine Check) Structure Support
- VarStore `0x1` · offset `0x2e` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled 

##### `0x1e` — **RAS EINJ Mode** (OneOf)
> BIOS: Send APEI EINJ actions to PSP via CPM EINJ SMI callback; PSP: Send APEI EINJ actions to PSP via PSP Mailbox
- VarStore `0x1` · offset `0x30` · 8-bit · range `0x0`..`0x1`
- options: `0` = BIOS, `1` = PSP (default, mfg)

##### `0x1f` — **(unnamed)** (Numeric)
- VarStore `0xf000` · offset `0x0` · 8-bit · range `0x0`..`0xff`

## Module: `72_Setup.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `7B59104A-C00D-4158-87FF-F04D6396A915`
- FormSet title: **Setup**
- FormSet help: Setup

### VarStores
- `0x1` **Setup** — GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`, size `0x174`
- `0x2` **TcgNvmeVar** — GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`, size `0x1`
- `0x3` **PNP0501_0_VV** — GUID `560BF58A-1E0D-4D7E-953F-2980A261E031`, size `0x9`
- `0x4` **PNP0501_0_NV** — GUID `560BF58A-1E0D-4D7E-953F-2980A261E031`, size `0x3`
- `0x5` **PNP0501_1_VV** — GUID `560BF58A-1E0D-4D7E-953F-2980A261E031`, size `0x9`
- `0x6` **PNP0501_1_NV** — GUID `560BF58A-1E0D-4D7E-953F-2980A261E031`, size `0x3`
- `0x7` **PNP0501_2_VV** — GUID `560BF58A-1E0D-4D7E-953F-2980A261E031`, size `0x9`
- `0x8` **PNP0501_2_NV** — GUID `560BF58A-1E0D-4D7E-953F-2980A261E031`, size `0x3`
- `0x9` **PNP0501_3_VV** — GUID `560BF58A-1E0D-4D7E-953F-2980A261E031`, size `0x9`
- `0xa` **PNP0501_3_NV** — GUID `560BF58A-1E0D-4D7E-953F-2980A261E031`, size `0x3`
- `0xb` **RefreshAttribRegistry** — GUID `8E31482A-72EA-4E08-AE30-232472BE3DD9`, size `0x1`
- `0xc` **TerminalPortsEnableVar** — GUID `279B9A61-F654-49E3-A252-A0B76B7C3865`, size `0x3`
- `0xd` **SetupCpuFeatures** — GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`, size `0x7`
- `0xe` **DriverManager** — GUID `C0B4FB05-15E5-4588-9FE9-B3D39C067715`, size `0x2`
- `0xf` **DriverOrder** — GUID `8BE4DF61-93CA-11D2-AA0D-00E098032B8C`, size `0x2`
- `0x10` **SioSetupData** — GUID `6B0CC1BC-910F-411E-B6CB-0E314D0BB8C1`, size `0x1`
- `0x11` **UsbMassDevNum** — GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`, size `0x2`
- `0x12` **UsbMassDevValid** — GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`, size `0x20`
- `0x13` **UsbControllerNum** — GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`, size `0x4`
- `0x14` **UsbSupport** — GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`, size `0x31`
- `0x15` **NetworkStackVar** — GUID `D1405D16-7AFC-4695-BB12-41459D3695A2`, size `0x8`
- `0x16` **HDDSecConfig** — GUID `3DD0DE67-02D7-4129-914A-9F377CC34B0D`, size `0x356`
- `0x17` **NvmeDriverManager** — GUID `C9456C5D-6CA5-4B5B-B1B2-C75C905BB90F`, size `0x21`
- `0x18` **SecureBootSetup** — GUID `7B59104A-C00D-4158-87FF-F04D6396A915`, size `0x7`
- `0x19` **SecureVarPresent** — GUID `7B59104A-C00D-4158-87FF-F04D6396A915`, size `0x6`
- `0x1a` **VendorKeys** — GUID `8BE4DF61-93CA-11D2-AA0D-00E098032B8C`, size `0x1`
- `0x1b` **SetupMode** — GUID `8BE4DF61-93CA-11D2-AA0D-00E098032B8C`, size `0x1`
- `0x1c` **SecureBoot** — GUID `8BE4DF61-93CA-11D2-AA0D-00E098032B8C`, size `0x1`
- `0x1d` **AuditMode** — GUID `8BE4DF61-93CA-11D2-AA0D-00E098032B8C`, size `0x1`
- `0x1e` **DeployedMode** — GUID `8BE4DF61-93CA-11D2-AA0D-00E098032B8C`, size `0x1`
- `0x1f` **ChasisIDVarControl** — GUID `A57AEAE9-A95A-4F1B-9FA7-D2C4F910C2E7`, size `0x1`
- `0x20` **FruDataVarControl** — GUID `2CB1647B-601B-42D8-8451-7DC23365B796`, size `0x1`
- `0x21` **IPMIHWMonitor** — GUID `165DD4A8-EDB4-489C-A8F0-8F83CDC5D002`, size `0x1`
- `0x22` **LanControl** — GUID `749EF5EB-23B2-43C3-9E29-F9F9F381C4CF`, size `0x4`
- `0x23` **DynamicPageCount** — GUID `B63BF800-F267-4F55-9217-E97FB3B69846`, size `0x2`
- `0x24` **DriverHlthEnable** — GUID `0885F288-418C-4BE1-A6AF-8BAD61DA08FE`, size `0x2`
- `0x25` **DriverHealthCount** — GUID `7459A7D4-6533-4480-BBA7-79E25A4443C9`, size `0x2`
- `0x26` **DrvHealthCtrlCnt** — GUID `58279C2D-FB19-466E-B42E-CD437016DC25`, size `0x2`
- `0xf000` **SystemAccess** — GUID `E770BB69-BCB4-4D04-9E97-23FF9456FEAC`, size `0x1`
- `0xf002` **AMICallback** — GUID `9CF0F18E-7C7D-49DE-B5AA-BBBAD6B21007`, size `0x2`
- `0xf003` **BootManager** — GUID `B4909CF3-7B93-4751-9BD8-5BA8220B9BB2`, size `0x2`
- `0xf005` **Timeout** — GUID `8BE4DF61-93CA-11D2-AA0D-00E098032B8C`, size `0x2`
- `0xf006` **BootOrder** — GUID `8BE4DF61-93CA-11D2-AA0D-00E098032B8C`, size `0x2`
- `0xf007` **LegacyDev** — GUID `A56074DB-65FE-45F7-BD21-2D2BDD8E9652`, size `0x2`
- `0xf008` **LegacyDevOrder** — GUID `A56074DB-65FE-45F7-BD21-2D2BDD8E9652`, size `0x2`
- `0xf009` **PlatformLang** — GUID `8BE4DF61-93CA-11D2-AA0D-00E098032B8C`, size `0x2`
- `0xf00a` **PlatformLangCodes** — GUID `8BE4DF61-93CA-11D2-AA0D-00E098032B8C`, size `0x2`
- `0xf00b` **Shell** — GUID `C57AD6B7-0515-40A8-9D21-551652854E37`, size `0x2`
- `0xf00d` **AddBootOption** — GUID `19D96D3F-6A6A-47D2-B195-7B2432DA3BE2`, size `0x11c`
- `0xf00e` **DelBootOption** — GUID `F6C73719-F34C-479C-B32F-277FCBBCFE4F`, size `0x2`
- `0xf013` **AMITSESetup** — GUID `C811FA38-42C8-4579-A9BB-60E94EDDFB34`, size `0x41`
- `0xf014` **BootNowCount** — GUID `052E6EB0-F240-42C5-8309-45874545C6B4`, size `0x2`
- `0xf016` **LegacyGroup** — GUID `A56074DB-65FE-45F7-BD21-2D2BDD8E9652`, size `0x2`

### Forms

#### Form `0x2710` — Setup

_Navigation (children):_
- → `0x2711` **Main**
- → `0x2712` **Advanced**
- → `0x2713` **Chipset**
- → `0x2714` **Security**
- → `0x2715` **Boot**
- → `0x2716` **Exit**

#### Form `0x2711` — Main

_Navigation (children):_
- → `0x27bc` **Main**
  - Main

_Settings:_

##### `0x7` — **System Language** (OneOf)
> Choose the system default language
- VarStore `0xf009` · offset `0x0` · 16-bit · range `0x0`..`0x1`
- options: `0` = , `1` = 
- conditions: SuppressIf(Q0x1d6=0xffff)

#### Form `0x27bc` — Main

#### Form `0x2712` — Advanced

_Navigation (children):_
- → `0x2719` **Trusted Computing**
  - Trusted Computing Settings
- → `0x271a` **Trusted Computing**
  - Trusted Computing Settings
- → `0x2718` **Trusted Computing**
  - Trusted Computing Settings
- → `0x271b` **PSP Firmware Versions**
  - PSP Firmware Versions
- → `0x271c` **Advanced**
  - Advanced
- → `0x271f` **ACPI Configuration**
  - Configure ACPI Settings
- → `0x2722` **Redfish Host Interface Settings**
  - Redfish Host Interface Parameters.
- → `0x2729` **CRB Board**
  - CRB Board Parameters
- → `0xb` **AMD PBS** (external FormSet `B863B959-0EC6-4033-99C1-8FD89F040222`)
  - AMD PBS Setup Page
- → `0x7000` **AMD CBS** (external FormSet `B04535E3-3004-4946-9EB7-149428983053`)
  - AMD CBS Setup Page
- → `0x2733` **AST2500 Super IO Configuration**
  - System Super IO Chip Parameters.
- → `0x273a` **Serial Port Console Redirection**
  - Serial Port Console Redirection
- → `0x274c` **CPU Configuration**
  - CPU Configuration Parameters
- → `0x2755` **Debug Port Table Configuration**
  - Enable or Disable DBGP and DBG2 Tables
- → `0x2757` **SIO Common Setting**
  - SIO Common Setting
- → `0x1` **PCI Subsystem Settings** (external FormSet `ACA9F304-21E2-4852-9875-7FF4881D67A5`)
  - PCI Subsystem Settings
- → `0x275c` **USB Configuration**
  - USB Configuration Parameters
- → `0x275f` **Network Stack Configuration**
  - Network Stack Settings
- → `0x2761` **CSM Configuration**
  - CSM configuration: Enable/Disable, Option ROM execution settings, etc.
- → `0x277c` **NVMe Configuration**
  - NVMe Device Options Settings
- → `0x1` **SATA Configuration** (external FormSet `5D9265F7-E3EC-4BE1-A995-85D860A5A42E`)
  - SATA Devices Information.
- → `0x27a2` **AMD PCIE Link Width**
  - AMD PCIE Link Width
- → `0x27a3` **AMD PCIE Link Speed**
  - AMD PCIE Link Speed
- → `0x27a4` **AMD PCIE Hotplug**
  - AMD PCIE Hotplug
- → `0x27bd` **ACPI Configuration**
  - Configure ACPI Settings
- → `0x27cf` **USB Configuration**
  - Configure the USB support.
- → `0x27d1` **H/W Monitor**
  - H/W Monitor
- → `0x2712` ****
- → `0x27d9` **Driver Health**
  - Provides Health Status for the Drivers/Controllers

#### Form `0x2718` — Trusted Computing

_Settings:_

##### `0x29` — **  Security Device Support** (OneOf)
> Enables or Disables BIOS support for security device. O.S. will not show Security Device. TCG EFI protocol and INT1A interface will not be available.
- VarStore `0x1` · offset `0x6` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x2a` — **  Disable Block Sid** (OneOf)
> Override to allow SID authentication in TCG Storage device
- VarStore `0x1` · offset `0x21` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled (default, mfg)
- conditions: SuppressIf(Q0x1cd=0x0)

#### Form `0x2719` — Trusted Computing

_Settings:_

##### `0x2b` — **  Security Device Support** (OneOf)
> Enables or Disables BIOS support for security device. O.S. will not show Security Device. TCG EFI protocol and INT1A interface will not be available.
- VarStore `0x1` · offset `0x6` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: SuppressIf(Q0x1d2=0x0); GrayOutIf(Q0x14a=0x1)

##### `0x2c` — **  TPM State** (OneOf)
> Enable/Disable Security Device. NOTE: Your Computer will reboot during restart in order to change State of the Device.
- VarStore `0x1` · offset `0x1` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x2d` — **Pending operation** (OneOf)
> Schedule an Operation for the Security Device. NOTE: Your Computer will reboot during restart in order to change State of Security Device.
- VarStore `0x1` · offset `0x2` · 8-bit · range `0x0`..`0x5`
- options: `0` = None (default, mfg), `5` = TPM Clear

##### `0x2e` — **  Security Device Support** (OneOf)
> Enables or Disables BIOS support for security device. O.S. will not show Security Device. TCG EFI protocol and INT1A interface will not be available.
- VarStore `0x1` · offset `0x6` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: SuppressIf(Q0x1d1=0x0); GrayOutIf(Q0x14a=0x1)

##### `0x2f` — **  TCM State** (OneOf)
> Enable/Disable Security Device. NOTE: Your Computer will reboot during restart in order to change State of the Device.
- VarStore `0x1` · offset `0x1` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x30` — **Pending operation** (OneOf)
> Schedule an Operation for the Security Device. NOTE: Your Computer will reboot during restart in order to change State of Security Device.
- VarStore `0x1` · offset `0x2` · 8-bit · range `0x0`..`0x5`
- options: `0` = None (default, mfg), `5` = TPM Clear

##### `0x31` — **  Device Select** (OneOf)
> TPM 1.2 will restrict support to TPM 1.2 devices, TPM 2.0 will restrict support to TPM 2.0 devices, Auto will support both with the default set to TPM 2.0 devices if not found, TPM 1.2 devices will be enumerated
- VarStore `0x1` · offset `0x13` · 8-bit · range `0x0`..`0x2`
- options: `0` = TPM 1.2, `1` = TPM 2.0, `2` = Auto (default, mfg)

#### Form `0x271a` — Trusted Computing

_Settings:_

##### `0x32` — **  Security Device Support** (OneOf)
> Enables or Disables BIOS support for security device. O.S. will not show Security Device. TCG EFI protocol and INT1A interface will not be available.
- VarStore `0x1` · offset `0x6` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x33` — **  SHA-1 PCR Bank** (OneOf)
> Enable or Disable SHA-1 PCR Bank
- VarStore `0x1` · offset `0x1a` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled
- conditions: GrayOutIf(Q0x3c=0x1); SuppressIf(Q0x32=0x0)

##### `0x34` — **  SHA256 PCR Bank** (OneOf)
> Enable or Disable SHA256 PCR Bank
- VarStore `0x1` · offset `0x1b` · 8-bit · range `0x0`..`0x2`
- options: `0` = Disabled, `2` = Enabled
- conditions: GrayOutIf(Q0x3c=0x1)

##### `0x35` — **  SHA384 PCR Bank** (OneOf)
> Enable or Disable SHA384 PCR Bank
- VarStore `0x1` · offset `0x1c` · 8-bit · range `0x0`..`0x4`
- options: `0` = Disabled, `4` = Enabled

##### `0x36` — **  SHA512 PCR Bank** (OneOf)
> Enable or Disable SHA512 PCR Bank
- VarStore `0x1` · offset `0x1d` · 8-bit · range `0x0`..`0x8`
- options: `0` = Disabled, `8` = Enabled

##### `0x37` — **  SM3_256 PCR Bank** (OneOf)
> Enable or Disable SM3_256 PCR Bank
- VarStore `0x1` · offset `0x1e` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled

##### `0x38` — **  Pending operation** (OneOf)
> Schedule an Operation for the Security Device. NOTE: Your Computer will reboot during restart in order to change State of Security Device.
- VarStore `0x1` · offset `0x2` · 8-bit · range `0x0`..`0x1`
- options: `0` = None (default, mfg), `1` = TPM Clear
- conditions: SuppressIf(Q0x32=0x0)

##### `0x39` — **  Platform Hierarchy** (OneOf)
> Enable or Disable Platform Hierarchy
- VarStore `0x1` · offset `0xf` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)

##### `0x3a` — **  Storage Hierarchy** (OneOf)
> Enable or Disable Storage Hierarchy
- VarStore `0x1` · offset `0x10` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)

##### `0x3b` — **  Endorsement Hierarchy** (OneOf)
> Enable or Disable Endorsement Hierarchy
- VarStore `0x1` · offset `0x11` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)

##### `0x3d` — **  Physical Presence Spec Version** (OneOf)
> Select to Tell O.S. to support PPI Spec Version 1.2 or 1.3. Note some HCK tests might not support 1.3.
- VarStore `0x1` · offset `0x20` · 8-bit · range `0x0`..`0x1`
- options: `0` = 1.2, `1` = 1.3 (default, mfg)

##### `0x3e` — **  TPM 2.0 InterfaceType** (OneOf)
> Select the Communication Interface to TPM 20 Device.
- VarStore `0x1` · offset `0x12` · 8-bit · range `0x0`..`0x1`
- options: `0` = CRB (default, mfg), `1` = TIS
- conditions: SuppressIf(Q0x32=0x0)

##### `0x3f` — **  Device Select** (OneOf)
> TPM 1.2 will restrict support to TPM 1.2 devices, TPM 2.0 will restrict support to TPM 2.0 devices, Auto will support both with the default set to TPM 2.0 devices if not found, TPM 1.2 devices will be enumerated
- VarStore `0x1` · offset `0x13` · 8-bit · range `0x0`..`0x2`
- options: `0` = TPM 1.2, `1` = TPM 2.0, `2` = Auto (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1); SuppressIf(Q0x32=0x0)

##### `0x40` — **  Disable Block Sid** (OneOf)
> Override to allow SID authentication in TCG Storage device
- VarStore `0x1` · offset `0x21` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled (default, mfg)
- conditions: SuppressIf(Q0x1cd=0x0)

#### Form `0x271b` — PSP Firmware Versions

#### Form `0x271c` — Advanced

_Navigation (children):_
- → `0x271d` **CPU Configuration**
  - CPU Configuration Parameters
- → `0x271e` **Chipset Configuration**
  - Configure Chipset Settings.
- → `0x27be` **Storage Configuration**
  - Configure storage devices.
- → `0x277c` **NVMe Configuration**
  - NVMe Device Options Settings
- → `0x27bd` **ACPI Configuration**
  - Configure ACPI Settings
- → `0x27cf` **USB Configuration**
  - Configure the USB support.
- → `0x2733` **Super IO Configuration**
  - Configure Super IO Settings.
- → `0x273a` **Serial Port Console Redirection**
  - Serial Port Console Redirection
- → `0x27d1` **H/W Monitor**
  - Monitor hardware status
- → `0x1` **PCI Subsystem Settings** (external FormSet `ACA9F304-21E2-4852-9875-7FF4881D67A5`)
  - PCI Subsystem Settings
- → `0x7000` **AMD CBS** (external FormSet `B04535E3-3004-4946-9EB7-149428983053`)
  - AMD CBS Setup Page
- → `0xb` **AMD PBS** (external FormSet `B863B959-0EC6-4033-99C1-8FD89F040222`)
  - AMD PBS Setup Page
- → `0x271b` **PSP Firmware Versions**
  - PSP Firmware Versions
- → `0x2719` **Trusted Computing**
  - Trusted Computing Settings
- → `0x271a` **Trusted Computing**
  - Trusted Computing Settings
- → `0x2718` **Trusted Computing**
  - Trusted Computing Settings
- → `0x275f` **Network Stack Configuration**
  - Network Stack Settings
- → `0x2712` ****
- → `0x271c` **Instant Flash**
  - Save UEFI files in your USB storage device and run Instant Flash to update your UEFI. Please note that your USB storage device must be FAT32/16/12 file system.

#### Form `0x271d` — CPU Configuration

_Navigation (children):_
- → `0x274d` **Node 0 Information**
  - View Memory Information related to Node 0

_Settings:_

##### `0x53` — **SVM Mode** (OneOf)
> Enable/disable CPU Virtualization
- VarStore `0x1` · offset `0xf8` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x271e` — Chipset Configuration

_Navigation (children):_
- → `0x27a4` **AMD PCIE Hotplug**
  - AMD PCIE Hotplug
- → `0x27a2` **AMD PCIE Link Width**
  - AMD PCIE Link Width
- → `0x27a3` **AMD PCIE Link Speed**
  - AMD PCIE Link Speed

_Settings:_

##### `0x55` — **Primary Graphics Adapter** (OneOf)
> Select a primary VGA.
- VarStore `0x1` · offset `0x16c` · 8-bit · range `0x0`..`0x1`
- options: `0` = Onboard VGA, `1` = PCI Express (default, mfg)
- conditions: SuppressIf(Q0x2760=0x0); GrayOutIf(Q0x14a=0x1)

##### `0x56` — **Onboard VGA** (OneOf)
> To Enable or Disable Onboard VGA
- VarStore `0x1` · offset `0x16b` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x57` — **SPI/LPC TPM switch** (OneOf)
> To select. 0 - LPC TPM. 1 - SPI TPM
- VarStore `0x1` · offset `0x16d` · 8-bit · range `0x0`..`0x1`
- options: `1` = LPC TPM (default, mfg), `0` = SPI TPM

##### `0x58` — **Onboard LAN1** (OneOf)
> To Enable or Disable Onboard LAN
- VarStore `0x1` · offset `0x15a` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x59` — **Onboard LAN2** (OneOf)
> To Enable or Disable Onboard LAN
- VarStore `0x1` · offset `0x15b` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)

##### `0x5a` — **Onboard LAN** (OneOf)
> To Enable or Disable Onboard LAN
- VarStore `0x1` · offset `0x15c` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)

##### `0x5e` — **PCIE1 ASPM Support** (OneOf)
> Configure the ASPM of PCIE1
- VarStore `0x1` · offset `0x15d` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled (default, mfg), `1` = ASPM L0s, `2` = ASPM L1, `3` = ASPM L0sL1

##### `0x5f` — **PCIE2 ASPM Support** (OneOf)
> Configure the ASPM of PCIE2
- VarStore `0x1` · offset `0x15e` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled (default, mfg), `1` = ASPM L0s, `2` = ASPM L1, `3` = ASPM L0sL1

##### `0x60` — **PCIE3 ASPM Support** (OneOf)
> Configure the ASPM of PCIE3
- VarStore `0x1` · offset `0x15f` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled (default, mfg), `1` = ASPM L0s, `2` = ASPM L1, `3` = ASPM L0sL1

##### `0x61` — **PCIE4 ASPM Support** (OneOf)
> Configure the ASPM of PCIE4
- VarStore `0x1` · offset `0x160` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled (default, mfg), `1` = ASPM L0s, `2` = ASPM L1, `3` = ASPM L0sL1

##### `0x62` — **PCIE5 ASPM Support** (OneOf)
> Configure the ASPM of PCIE5
- VarStore `0x1` · offset `0x161` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled (default, mfg), `1` = ASPM L0s, `2` = ASPM L1, `3` = ASPM L0sL1

##### `0x63` — **PCIE6 ASPM Support** (OneOf)
> Configure the ASPM of PCIE6
- VarStore `0x1` · offset `0x162` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled (default, mfg), `1` = ASPM L0s, `2` = ASPM L1, `3` = ASPM L0sL1

##### `0x64` — **PCIE7 ASPM Support** (OneOf)
> Configure the ASPM of PCIE7
- VarStore `0x1` · offset `0x163` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled (default, mfg), `1` = ASPM L0s, `2` = ASPM L1, `3` = ASPM L0sL1

##### `0x65` — **OCU1 ASPM Support** (OneOf)
> Configure the ASPM of OCU1
- VarStore `0x1` · offset `0x165` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled (default, mfg), `1` = ASPM L0s, `2` = ASPM L1, `3` = ASPM L0sL1

##### `0x66` — **OCU2 ASPM Support** (OneOf)
> Configure the ASPM of OCU2
- VarStore `0x1` · offset `0x166` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled (default, mfg), `1` = ASPM L0s, `2` = ASPM L1, `3` = ASPM L0sL1

##### `0x67` — **Onboard Debug Port LED** (OneOf)
> Enable/disable the onboard Dr. Debug LED.
- VarStore `0x1` · offset `0x171` · 8-bit · range `0x0`..`0x2`
- options: `0` = Off, `1` = On, `2` = Auto (default, mfg)

##### `0x68` — **Restore AC Power Loss** (OneOf)
> Select the power state after a power failure. If [Power Off] is selected, the power will remain off when the power recovers. If [Power On] is selected, the system will start to boot up when the power recovers.
- VarStore `0x1` · offset `0x119` · 8-bit · range `0x0`..`0x3`
- options: `0` = Power Off, `1` = Last State, `2` = Power On, `3` = No change (default, mfg)

#### Form `0x271f` — ACPI Configuration

_Settings:_

##### `0x69` — **Enable ACPI Auto Configuration** (CheckBox)
> Enables or Disables BIOS ACPI Auto Configuration.
- VarStore `0x1` · offset `0x23` · 8-bit
- options: `0` = Disabled, `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x2722` — Redfish Host Interface Settings

_Settings:_

##### `0x6a` — **Redfish** (OneOf)
> Enable/Disable AMI Redfish
- VarStore `0x1` · offset `0x29` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled

##### `0x6b` — **Authentication mode** (OneOf)
> Select authentication mode
- VarStore `0x1` · offset `0x6a` · 8-bit · range `0x0`..`0x0`
- options: `0` = Authentication None (default, mfg)

##### `0x6c` — **IP Port** (Numeric)
> Enter IP Port
- VarStore `0x1` · offset `0xab` · 16-bit · range `0x0`..`0xffff` · default `65535`

##### `0x6d` — **Vlan ID** (Numeric)
> Enter Vlan ID
- VarStore `0x1` · offset `0xad` · 32-bit · range `0x0`..`0xffffffff` · default `0`

#### Form `0x2729` — CRB Board

_Settings:_

##### `0x6e` — **OnBrd/Ext VGA Select** (OneOf)
> Select between onboard or external VGA support.
- VarStore `0x1` · offset `0xc9` · 8-bit · range `0x0`..`0x2`
- options: `0` = Auto (default, mfg), `1` = Onboard, `2` = External
- conditions: SuppressIf(Q0x136=0x1)

##### `0x6f` — **VGA Slot** (Numeric)
> For external VGA, select VGA on which slot to be enabled.
- VarStore `0x1` · offset `0xca` · 8-bit · range `0x1`..`0x8` · default `1`

#### Form `0x2733` — AST2500 Super IO Configuration

_Navigation (children):_
- → `0x2734` **Serial Port 1 Configuration**
  - Set Parameters of COM1
- → `0x2735` **SOL Configuration**
  - Set Parameters of SOL

#### Form `0x2734` — Serial Port 1 Configuration

_Settings:_

##### `0x72` — **Serial Port** (CheckBox)
> Enable or Disable Serial Port (COM)
- VarStore `0x4` · offset `0x0` · 8-bit
- options: `0` = Disabled, `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x73` — **Change Settings** (OneOf)
> Select an optimal settings for Super IO Device
- VarStore `0x4` · offset `0x1` · 8-bit · range `0x1`..`0x4`
- options: `1` = 3F8h/IRQ4, `4` = 3E8h/IRQ4
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x2735` — SOL Configuration

_Settings:_

##### `0x74` — **SOL Port** (CheckBox)
> Enable or Disable SOL Port
- VarStore `0x6` · offset `0x0` · 8-bit
- options: `0` = Disabled, `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x75` — **Change Settings** (OneOf)
> Select an optimal settings for Super IO Device
- VarStore `0x6` · offset `0x1` · 8-bit · range `0x1`..`0x5`
- options: `1` = 2F8h/IRQ3, `5` = 2E8h/IRQ3
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x273a` — Serial Port Console Redirection

_Navigation (children):_
- → `0x273d` **Console Redirection Settings**
  - The settings specify how the host computer and the remote computer (which the user is using) will exchange data. Both computers should have the same or compatible settings.
- → `0x273e` **Console Redirection Settings**
  - The settings specify how the host computer and the remote computer (which the user is using) will exchange data. Both computers should have the same or compatible settings.
- → `0x273c` **Legacy Console Redirection Settings**
  - Legacy Console Redirection Settings
- → `0x273b` **Console Redirection Settings**
  - The settings specify how the host computer and the remote computer (which the user is using) will exchange data. Both computers should have the same or compatible settings.

_Settings:_

##### `0x76` — **Console Redirection** (CheckBox)
> Console Redirection Enable or Disable.
- VarStore `0x1` · offset `0xdd` · 8-bit
- options: `0` = Disabled, `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x78` — **Console Redirection** (CheckBox)
> Console Redirection Enable or Disable.
- VarStore `0x1` · offset `0xde` · 8-bit
- options: `0` = Disabled, `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x7b` — **Console Redirection EMS** (CheckBox)
> Console Redirection Enable or Disable.
- VarStore `0x1` · offset `0xeb` · 8-bit
- options: `0` = Disabled, `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x273b` — Console Redirection Settings

_Settings:_

##### `0x7d` — **Out-of-Band Mgmt Port** (OneOf)
> Microsoft Windows Emergency Management Services (EMS) allows for remote management of a Windows Server OS through a serial port.
- VarStore `0x1` · offset `0xec` · 8-bit · range `0x0`..`0x1`
- options: `0` = COM1 (default, mfg), `1` = SOL
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x7e` — **Terminal Type EMS** (OneOf)
> VT-UTF8 is the preferred terminal type for out-of-band management. The next best choice is VT100+ and then VT100. See above, in Console Redirection Settings page, for more Help with Terminal Type/Emulation.
- VarStore `0x1` · offset `0xed` · 8-bit · range `0x0`..`0x3`
- options: `0` = VT100, `1` = VT100Plus, `2` = VT-UTF8, `3` = ANSI
- conditions: GrayOutIf(Q0x7b=0x0)

##### `0x7f` — **Bits per second EMS** (OneOf)
> Selects serial port transmission speed. The speed must be matched on the other side. Long or noisy lines may require lower speeds.
- VarStore `0x1` · offset `0xee` · 8-bit · range `0x3`..`0x7`
- options: `3` = 9600, `4` = 19200, `6` = 57600, `7` = 115200
- conditions: GrayOutIf(Q0x7b=0x0)

##### `0x80` — **Flow Control EMS** (OneOf)
> Flow control can prevent data loss from buffer overflow. When sending data, if the receiving buffers are full, a 'stop' signal can be sent to stop the data flow. Once the buffers are empty, a 'start' signal can be sent to re-start the flow. Hardware flow control uses two wires to send start/stop signals.
- VarStore `0x1` · offset `0xef` · 8-bit · range `0x0`..`0x2`
- options: `0` = None, `1` = Hardware RTS/CTS, `2` = Software Xon/Xoff
- conditions: GrayOutIf(Q0x7b=0x0)

#### Form `0x273c` — Legacy Console Redirection Settings

_Settings:_

##### `0x81` — **Redirection COM Port** (OneOf)
> Select a COM port to display redirection of Legacy OS and Legacy OPROM Messages
- VarStore `0x1` · offset `0xf3` · 8-bit · range `0x0`..`0x1`
- options: `0` = COM1 (default, mfg), `1` = SOL
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x82` — **Resolution** (OneOf)
> On Legacy OS, the Number of Rows and Columns supported redirection
- VarStore `0x1` · offset `0xe7` · 8-bit · range `0x0`..`0x1`
- options: `0` = 80x24, `1` = 80x25

##### `0x83` — **Redirect After POST** (OneOf)
> When Bootloader is selected, then Legacy Console Redirection is disabled before booting to legacy OS. When Always Enable is selected, then Legacy Console Redirection is enabled for legacy OS. Default setting for this option is set to Always Enable.
- VarStore `0x1` · offset `0xea` · 8-bit · range `0x0`..`0x1`
- options: `0` = Always Enable, `1` = BootLoader

#### Form `0x273d` — COM1

_Settings:_

##### `0x84` — **Terminal Type** (OneOf)
> Emulation: ANSI: Extended ASCII char set. VT100: ASCII char set. VT100Plus: Extends VT100 to support color, function keys, etc. VT-UTF8: Uses UTF8 encoding to map Unicode chars onto 1 or more bytes.
- VarStore `0x1` · offset `0xdf` · 8-bit · range `0x0`..`0x3`
- options: `0` = VT100, `1` = VT100Plus, `2` = VT-UTF8, `3` = ANSI
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x85` — **Bits per second** (OneOf)
> Selects serial port transmission speed. The speed must be matched on the other side. Long or noisy lines may require lower speeds.
- VarStore `0x1` · offset `0xd3` · 8-bit · range `0x3`..`0x7`
- options: `3` = 9600, `4` = 19200, `5` = 38400, `6` = 57600, `7` = 115200

##### `0x86` — **Data Bits** (OneOf)
> Data Bits
- VarStore `0x1` · offset `0xd5` · 8-bit · range `0x7`..`0x8`
- options: `7` = 7, `8` = 8

##### `0x87` — **Parity** (OneOf)
> A parity bit can be sent with the data bits to detect some transmission errors. Even: parity bit is 0 if the num of 1's in the data bits is even. Odd: parity bit is 0 if num of 1's in the data bits is odd.  Mark: parity bit is always 1. Space: Parity bit is always 0. Mark and Space Parity do not allow for error detection. They can be used as an additional data bit.
- VarStore `0x1` · offset `0xd7` · 8-bit · range `0x1`..`0x5`
- options: `1` = None, `2` = Even, `3` = Odd, `4` = Mark, `5` = Space

##### `0x88` — **Stop Bits** (OneOf)
> Stop bits indicate the end of a serial data packet. (A start bit indicates the beginning). The standard setting is 1 stop bit. Communication with slow devices may require more than 1 stop bit.
- VarStore `0x1` · offset `0xd9` · 8-bit · range `0x1`..`0x3`
- options: `1` = 1, `3` = 2

##### `0x89` — **Flow Control** (OneOf)
> Flow control can prevent data loss from buffer overflow. When sending data, if the receiving buffers are full, a 'stop' signal can be sent to stop the data flow. Once the buffers are empty, a 'start' signal can be sent to re-start the flow. Hardware flow control uses two wires to send start/stop signals.
- VarStore `0x1` · offset `0xdb` · 8-bit · range `0x0`..`0x1`
- options: `0` = None, `1` = Hardware RTS/CTS

##### `0x8a` — **VT-UTF8 Combo Key Support** (CheckBox)
> Enable VT-UTF8 Combination Key Support for ANSI/VT100 terminals
- VarStore `0x1` · offset `0xe1` · 8-bit
- options: `0` = Disabled, `1` = Enabled

##### `0x8b` — **Recorder Mode** (CheckBox)
> With this mode enabled only text will be sent. This is to capture Terminal data.
- VarStore `0x1` · offset `0xe3` · 8-bit
- options: `0` = Disabled, `1` = Enabled

##### `0x8c` — **Resolution 100x31** (CheckBox)
> Enables or disables extended terminal resolution
- VarStore `0x1` · offset `0xe5` · 8-bit
- options: `0` = Disabled, `1` = Enabled

##### `0x8d` — **Putty KeyPad** (OneOf)
> Select FunctionKey and KeyPad on Putty.
- VarStore `0x1` · offset `0xe8` · 8-bit · range `0x1`..`0x20`
- options: `1` = VT100, `2` = LINUX, `4` = XTERMR6, `8` = SCO, `16` = ESCN, `32` = VT400

#### Form `0x273e` — SOL

_Settings:_

##### `0x8e` — **Terminal Type** (OneOf)
> Emulation: ANSI: Extended ASCII char set. VT100: ASCII char set. VT100Plus: Extends VT100 to support color, function keys, etc. VT-UTF8: Uses UTF8 encoding to map Unicode chars onto 1 or more bytes.
- VarStore `0x1` · offset `0xe0` · 8-bit · range `0x0`..`0x3`
- options: `0` = VT100, `1` = VT100Plus, `2` = VT-UTF8, `3` = ANSI
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x8f` — **Bits per second** (OneOf)
> Selects serial port transmission speed. The speed must be matched on the other side. Long or noisy lines may require lower speeds.
- VarStore `0x1` · offset `0xd4` · 8-bit · range `0x3`..`0x7`
- options: `3` = 9600, `4` = 19200, `5` = 38400, `6` = 57600, `7` = 115200

##### `0x90` — **Data Bits** (OneOf)
> Data Bits
- VarStore `0x1` · offset `0xd6` · 8-bit · range `0x7`..`0x8`
- options: `7` = 7, `8` = 8

##### `0x91` — **Parity** (OneOf)
> A parity bit can be sent with the data bits to detect some transmission errors. Even: parity bit is 0 if the num of 1's in the data bits is even. Odd: parity bit is 0 if num of 1's in the data bits is odd.  Mark: parity bit is always 1. Space: Parity bit is always 0. Mark and Space Parity do not allow for error detection. They can be used as an additional data bit.
- VarStore `0x1` · offset `0xd8` · 8-bit · range `0x1`..`0x5`
- options: `1` = None, `2` = Even, `3` = Odd, `4` = Mark, `5` = Space

##### `0x92` — **Stop Bits** (OneOf)
> Stop bits indicate the end of a serial data packet. (A start bit indicates the beginning). The standard setting is 1 stop bit. Communication with slow devices may require more than 1 stop bit.
- VarStore `0x1` · offset `0xda` · 8-bit · range `0x1`..`0x3`
- options: `1` = 1, `3` = 2

##### `0x93` — **Flow Control** (OneOf)
> Flow control can prevent data loss from buffer overflow. When sending data, if the receiving buffers are full, a 'stop' signal can be sent to stop the data flow. Once the buffers are empty, a 'start' signal can be sent to re-start the flow. Hardware flow control uses two wires to send start/stop signals.
- VarStore `0x1` · offset `0xdc` · 8-bit · range `0x0`..`0x1`
- options: `0` = None, `1` = Hardware RTS/CTS

##### `0x94` — **VT-UTF8 Combo Key Support** (CheckBox)
> Enable VT-UTF8 Combination Key Support for ANSI/VT100 terminals
- VarStore `0x1` · offset `0xe2` · 8-bit
- options: `0` = Disabled, `1` = Enabled

##### `0x95` — **Recorder Mode** (CheckBox)
> With this mode enabled only text will be sent. This is to capture Terminal data.
- VarStore `0x1` · offset `0xe4` · 8-bit
- options: `0` = Disabled, `1` = Enabled

##### `0x96` — **Resolution 100x31** (CheckBox)
> Enables or disables extended terminal resolution
- VarStore `0x1` · offset `0xe6` · 8-bit
- options: `0` = Disabled, `1` = Enabled

##### `0x97` — **Putty KeyPad** (OneOf)
> Select FunctionKey and KeyPad on Putty.
- VarStore `0x1` · offset `0xe9` · 8-bit · range `0x1`..`0x20`
- options: `1` = VT100, `2` = LINUX, `4` = XTERMR6, `8` = SCO, `16` = ESCN, `32` = VT400

#### Form `0x274c` — CPU Configuration

_Navigation (children):_
- → `0x274d` **Node 0 Information**
  - View Memory Information related to Node 0
- → `0x274e` **Node 1 Information**
  - View Memory Information related to Node 1

_Settings:_

##### `0x98` — **SVM Mode** (OneOf)
> Enable/disable CPU Virtualization
- VarStore `0x1` · offset `0xf8` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)

#### Form `0x274d` — Node 0 Information

#### Form `0x274e` — Node 1 Information

#### Form `0x2755` — Debug Port Table

_Settings:_

##### `0x9b` — **Debug Port Table** (OneOf)
> Debug Port Table
- VarStore `0x1` · offset `0x104` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled

##### `0x9c` — **Debug Port Table 2** (OneOf)
> Debug Port Table 2
- VarStore `0x1` · offset `0x105` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled

#### Form `0x2757` — SIO Common Setting

_Settings:_

##### `0x9d` — **Lock Legacy Resources** (CheckBox)
> Enables or Disables Lock of Legacy Resources
- VarStore `0x10` · offset `0x0` · 8-bit
- options: `0` = Disabled, `1` = Enabled

#### Form `0x275c` — USB Configuration

_Settings:_

##### `0x9e` — **USB Support** (OneOf)
> USB Support Parameters
- VarStore `0x14` · offset `0x0` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x9f` — **Legacy USB Support** (OneOf)
> Enables Legacy USB support. AUTO option disables legacy support if no USB devices are connected. DISABLE option will keep USB devices available only for EFI applications.
- VarStore `0x14` · offset `0x1` · 8-bit · range `0x0`..`0x1`
- options: `0` = Enabled (default, mfg), `1` = UEFI Setup Only
- conditions: SuppressIf(Q0x9e=0x0); GrayOutIf(Q0x14a=0x1)

##### `0xa0` — **USB 2.0 Controller Mode** (OneOf)
> Configures the USB 2.0 controller in HiSpeed (480Mbps) or FullSpeed (12Mbps).
- VarStore `0x14` · offset `0x2e` · 8-bit · range `0x0`..`0x1`
- options: `1` = HiSpeed (default, mfg), `0` = FullSpeed
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xa1` — **Legacy USB 3.0 Support** (OneOf)
> Enable or disable Legacy OS Support for USB 3.0 devices.
- VarStore `0x14` · offset `0x2a` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled (default, mfg), `0` = Disabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xa2` — **XHCI Hand-off** (OneOf)
> This is a workaround for OSes without XHCI hand-off support. The XHCI ownership change should be claimed by XHCI driver.
- VarStore `0x14` · offset `0x2b` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xa3` — **EHCI Hand-off** (OneOf)
> This is a workaround for OSes without EHCI hand-off support. The EHCI ownership change should be claimed by EHCI driver.
- VarStore `0x14` · offset `0x2` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xa4` — **USB Mass Storage Driver Support** (OneOf)
> Enable/Disable USB Mass Storage Driver Support.
- VarStore `0x14` · offset `0x2f` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: SuppressIf(Q0x9e=0x0)

##### `0xa5` — **Port 60/64 Emulation** (OneOf)
> Enables I/O port 60h/64h emulation support. This should be enabled for the complete USB keyboard legacy support for non-USB aware OSes.
- VarStore `0x14` · offset `0x7` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled
- conditions: SuppressIf(Q0x9e=0x0); GrayOutIf(Q0x14a=0x1)

##### `0xa6` — **USB transfer time-out** (OneOf)
> The time-out value for Control, Bulk, and Interrupt transfers.
- VarStore `0x14` · offset `0x9` · 8-bit · range `0x1`..`0x14`
- options: `1` = 1 sec, `5` = 5 sec, `10` = 10 sec, `20` = 20 sec (default, mfg)
- conditions: SuppressIf(Q0x9e=0x0)

##### `0xa7` — **Device reset time-out** (OneOf)
> USB mass storage device Start Unit command time-out.
- VarStore `0x14` · offset `0x8` · 8-bit · range `0x0`..`0x3`
- options: `0` = 10 sec, `1` = 20 sec (default, mfg), `2` = 30 sec, `3` = 40 sec
- conditions: SuppressIf(Q0x9e=0x0)

##### `0xa8` — **Device power-up delay** (OneOf)
> Maximum time the device will take before it properly reports itself to the Host Controller. 'Auto' uses default value: for a Root port it is 100 ms, for a Hub port the delay is taken from Hub descriptor.
- VarStore `0x14` · offset `0x2c` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default, mfg), `1` = Manual

##### `0xa9` — **Device power-up delay in seconds** (Numeric)
> Delay range is 1..40 seconds, in one second increments
- VarStore `0x14` · offset `0x2d` · 8-bit · range `0x1`..`0x28` · default `5`
- conditions: SuppressIf(Q0xa8=0x0)

##### `0xaa` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0xa` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xab` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0xb` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xac` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0xc` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xad` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0xd` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xae` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0xe` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xaf` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0xf` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xb0` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x10` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xb1` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x11` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xb2` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x12` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xb3` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x13` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xb4` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x14` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xb5` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x15` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xb6` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x16` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xb7` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x17` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xb8` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x18` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xb9` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x19` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xba` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x1a` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xbb` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x1b` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xbc` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x1c` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xbd` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x1d` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xbe` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x1e` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xbf` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x1f` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xc0` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x20` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xc1` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x21` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xc2` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x22` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xc3` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x23` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xc4` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x24` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xc5` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x25` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xc6` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x26` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xc7` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x27` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xc8` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x28` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

##### `0xc9` — **N/A** (OneOf)
> Mass storage device emulation type. 'AUTO' enumerates devices according to their media format. Optical drives are emulated as 'CDROM', drives with no media will be emulated according to a drive type.
- VarStore `0x14` · offset `0x29` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `1` = Floppy, `2` = Forced FDD, `3` = Hard Disk, `4` = CD-ROM

#### Form `0x275f` — Network Stack Configuration

_Settings:_

##### `0xca` — **Network Stack** (OneOf)
> Enable/Disable UEFI Network Stack
- VarStore `0x15` · offset `0x0` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xcb` — **IPv4 PXE Support** (OneOf)
> Enable/Disable IPv4 PXE boot support. If disabled, IPv4 PXE boot support will not be available.
- VarStore `0x15` · offset `0x1` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled
- conditions: SuppressIf(Q0xca=0x0); GrayOutIf(Q0x14a=0x1)

##### `0xcc` — **IPv4 HTTP Support** (OneOf)
> Enable/Disable IPv4 HTTP boot support. If disabled, IPv4 HTTP boot support will not be available.
- VarStore `0x15` · offset `0x6` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled
- conditions: SuppressIf(Q0xca=0x0)

##### `0xcd` — **IPv6 PXE Support** (OneOf)
> Enable/Disable IPv6 PXE boot support. If disabled, IPv6 PXE boot support will not be available.
- VarStore `0x15` · offset `0x2` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled
- conditions: SuppressIf(Q0xca=0x0); GrayOutIf(Q0x14a=0x1)

##### `0xce` — **IPv6 HTTP Support** (OneOf)
> Enable/Disable IPv6 HTTP boot support. If disabled, IPv6 HTTP boot support will not be available.
- VarStore `0x15` · offset `0x7` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled
- conditions: SuppressIf(Q0xca=0x0)

##### `0xcf` — **PXE boot wait time** (Numeric)
> Wait time in seconds to press ESC key to abort the PXE boot. Use either +/- or numeric keys to set the value.
- VarStore `0x15` · offset `0x4` · 8-bit · range `0x0`..`0x5` · default `0`
- conditions: SuppressIf(Q0xca=0x0); GrayOutIf(Q0x14a=0x1)

##### `0xd0` — **Media detect count** (Numeric)
> Number of times the presence of media will be checked. Use either +/- or numeric keys to set the value.
- VarStore `0x15` · offset `0x5` · 8-bit · range `0x1`..`0x32` · default `1`
- conditions: SuppressIf(Q0xca=0x0); GrayOutIf(Q0x14a=0x1)

#### Form `0x2761` — CSM Configuration

_Settings:_

##### `0xd1` — **GateA20 Active** (OneOf)
> UPON REQUEST - GA20 can be disabled using BIOS services. ALWAYS - do not allow disabling GA20; this option is useful when any RT code is executed above 1MB.
- VarStore `0x1` · offset `0x10b` · 8-bit · range `0x0`..`0x1`
- options: `0` = Upon Request (default, mfg), `1` = Always

##### `0xd2` — **  AddOn ROM Display** (OneOf)
> Set display mode for Option ROM
- VarStore `0x1` · offset `0x107` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled (default, mfg), `0` = Disabled

##### `0xd3` — **INT19 Trap Response** (OneOf)
> BIOS reaction on INT19 trapping by Option ROM: IMMEDIATE - execute the trap right away; POSTPONED - execute the trap during legacy boot.
- VarStore `0x1` · offset `0x108` · 8-bit · range `0x0`..`0x1`
- options: `1` = Immediate (default, mfg), `0` = Postponed

##### `0xd4` — **HDD Connection Order** (OneOf)
> Some OS require HDD handles to be adjusted, i.e. OS is installed on drive 80h.
- VarStore `0x1` · offset `0x10a` · 8-bit · range `0x0`..`0x1`
- options: `0` = Adjust (default, mfg), `1` = Keep
- conditions: SuppressIf(Q0x12d=0x2)

##### `0xd5` — **Boot option filter** (OneOf)
> This option controls Legacy/UEFI ROMs priority
- VarStore `0x1` · offset `0x10c` · 8-bit · range `0x0`..`0x2`
- options: `0` = UEFI and Legacy, `1` = Legacy only, `2` = UEFI only

##### `0xd6` — **Launch PXE OpROM Policy** (OneOf)
> Select UEFI only to run those that support UEFI option ROM only. Select Legacy only to run those that support legacy option ROM only. Select Do not launch to not execute both legacy and UEFI option ROM.
- VarStore `0x1` · offset `0x10d` · 8-bit · range `0x0`..`0x2`
- options: `0` = Do not launch, `1` = UEFI only, `2` = Legacy only

##### `0xd7` — **Launch Storage OpROM Policy** (OneOf)
> Select UEFI only to run those that support UEFI option ROM only. Select Legacy only to run those that support legacy option ROM only. Select Do not launch to not execute both legacy and UEFI option ROM.
- VarStore `0x1` · offset `0x10e` · 8-bit · range `0x0`..`0x2`
- options: `0` = Do not launch, `1` = UEFI only, `2` = Legacy only

##### `0xd8` — **Launch Video OpROM Policy** (OneOf)
> Select UEFI only to run those that support UEFI option ROM only. Select Legacy only to run those that support legacy option ROM only. Select Do not launch to not execute both legacy and UEFI option ROM.
- VarStore `0x1` · offset `0x10f` · 8-bit · range `0x0`..`0x2`
- options: `0` = Do not launch, `1` = UEFI only, `2` = Legacy only

##### `0xd9` — **Other PCI device ROM priority** (OneOf)
> For PCI devices other than Network, Mass storage or Video defines which OpROM to launch
- VarStore `0x1` · offset `0x110` · 8-bit · range `0x0`..`0x2`
- options: `0` = Do not launch, `1` = UEFI only (default, mfg), `2` = Legacy only

#### Form `0x277c` — NVMe Configuration

#### Form `0x27a2` — AMD PCIE Link Width

_Settings:_

##### `0xda` — **PCIE1 Link Width** (OneOf)
> AMD PCIE Link Width
- VarStore `0x1` · offset `0x11b` · 8-bit · range `0x0`..`0x4`
- options: `0` = x16 (default, mfg), `1` = x8x8, `2` = x8x4x4, `3` = x4x4x8, `4` = x4x4x4x4
- conditions: GrayOutIf(Q0x14a=0x1); GrayOutIf(Q0x14a=0x1)

##### `0xdb` — **PCIE2/M2_1 Link Width** (OneOf)
> AMD PCIE Link Width
- VarStore `0x1` · offset `0x11c` · 8-bit · range `0x0`..`0x4`
- options: `0` = x16 (default, mfg), `1` = x8x8, `2` = x8x4x4, `3` = x4x4x8, `4` = x4x4x4x4
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xdc` — **PCIE3 Link Width** (OneOf)
> AMD PCIE Link Width
- VarStore `0x1` · offset `0x11d` · 8-bit · range `0x0`..`0x4`
- options: `0` = x16 (default, mfg), `1` = x8x8, `2` = x8x4x4, `3` = x4x4x8, `4` = x4x4x4x4
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xdd` — **PCIE4 Link Width** (OneOf)
> AMD PCIE Link Width
- VarStore `0x1` · offset `0x11e` · 8-bit · range `0x0`..`0x4`
- options: `0` = x16 (default, mfg), `1` = x8x8, `2` = x8x4x4, `3` = x4x4x8, `4` = x4x4x4x4
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xde` — **PCIE5 Link Width** (OneOf)
> AMD PCIE Link Width
- VarStore `0x1` · offset `0x11f` · 8-bit · range `0x0`..`0x4`
- options: `0` = x16 (default, mfg), `1` = x8x8, `2` = x8x4x4, `3` = x4x4x8, `4` = x4x4x4x4
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xdf` — **PCIE6 Link Width** (OneOf)
> AMD PCIE Link Width
- VarStore `0x1` · offset `0x120` · 8-bit · range `0x0`..`0x4`
- options: `0` = x16 (default, mfg), `1` = x8x8, `2` = x8x4x4, `3` = x4x4x8, `4` = x4x4x4x4
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xe0` — **PCIE7 Link Width** (OneOf)
> AMD PCIE Link Width
- VarStore `0x1` · offset `0x121` · 8-bit · range `0x0`..`0x4`
- options: `0` = x16 (default, mfg), `1` = x8x8, `2` = x8x4x4, `3` = x4x4x8, `4` = x4x4x4x4
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x27a3` — AMD PCIE Link Speed

_Settings:_

##### `0xe1` — **PCIE1 Link Speed** (OneOf)
> AMD PCIE Link Speed
- VarStore `0x1` · offset `0x123` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `4` = GEN4, `3` = GEN3, `2` = GEN2, `1` = GEN1
- conditions: GrayOutIf(Q0x14a=0x1); GrayOutIf(Q0x14a=0x1)

##### `0xe2` — **PCIE2 Link Speed** (OneOf)
> AMD PCIE Link Speed
- VarStore `0x1` · offset `0x124` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `4` = GEN4, `3` = GEN3, `2` = GEN2, `1` = GEN1
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xe3` — **PCIE3 Link Speed** (OneOf)
> AMD PCIE Link Speed
- VarStore `0x1` · offset `0x125` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `4` = GEN4, `3` = GEN3, `2` = GEN2, `1` = GEN1
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xe4` — **PCIE4 Link Speed** (OneOf)
> AMD PCIE Link Speed
- VarStore `0x1` · offset `0x126` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `4` = GEN4, `3` = GEN3, `2` = GEN2, `1` = GEN1
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xe5` — **PCIE5 Link Speed** (OneOf)
> AMD PCIE Link Speed
- VarStore `0x1` · offset `0x127` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `4` = GEN4, `3` = GEN3, `2` = GEN2, `1` = GEN1
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xe6` — **PCIE6 Link Speed** (OneOf)
> AMD PCIE Link Speed
- VarStore `0x1` · offset `0x128` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `4` = GEN4, `3` = GEN3, `2` = GEN2, `1` = GEN1
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xe7` — **PCIE7 Link Speed** (OneOf)
> AMD PCIE Link Speed
- VarStore `0x1` · offset `0x129` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `4` = GEN4, `3` = GEN3, `2` = GEN2, `1` = GEN1
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xe8` — **OCU1 Link Speed** (OneOf)
> AMD PCIE Link Speed
- VarStore `0x1` · offset `0x12a` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `4` = GEN4, `3` = GEN3, `2` = GEN2, `1` = GEN1
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xe9` — **OCU2 Link Speed** (OneOf)
> AMD PCIE Link Speed
- VarStore `0x1` · offset `0x12b` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `4` = GEN4, `3` = GEN3, `2` = GEN2, `1` = GEN1
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xea` — **M2_1 Link Speed** (OneOf)
> AMD PCIE Link Speed
- VarStore `0x1` · offset `0x12c` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `4` = GEN4, `3` = GEN3, `2` = GEN2, `1` = GEN1
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xeb` — **M2_2 Link Speed** (OneOf)
> AMD PCIE Link Speed
- VarStore `0x1` · offset `0x12d` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default, mfg), `4` = GEN4, `3` = GEN3, `2` = GEN2, `1` = GEN1
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x27a4` — AMD PCIE Hotplug

_Settings:_

##### `0xec` — **PCIE1 HotPlug** (OneOf)
> AMD PCIE Hotplug
- VarStore `0x1` · offset `0x12f` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1); GrayOutIf(Q0x14a=0x1)

##### `0xed` — **PCIE2 HotPlug** (OneOf)
> AMD PCIE Hotplug
- VarStore `0x1` · offset `0x130` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xee` — **PCIE3 HotPlug** (OneOf)
> AMD PCIE Hotplug
- VarStore `0x1` · offset `0x131` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xef` — **PCIE4 HotPlug** (OneOf)
> AMD PCIE Hotplug
- VarStore `0x1` · offset `0x132` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xf0` — **PCIE5 HotPlug** (OneOf)
> AMD PCIE Hotplug
- VarStore `0x1` · offset `0x133` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xf1` — **PCIE6 HotPlug** (OneOf)
> AMD PCIE Hotplug
- VarStore `0x1` · offset `0x134` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xf2` — **PCIE7 HotPlug** (OneOf)
> AMD PCIE Hotplug
- VarStore `0x1` · offset `0x135` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xf3` — **OCU1 HotPlug** (OneOf)
> AMD PCIE Hotplug
- VarStore `0x1` · offset `0x136` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xf4` — **OCU2 HotPlug** (OneOf)
> AMD PCIE Hotplug
- VarStore `0x1` · offset `0x137` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x27bd` — ACPI Configuration

_Settings:_

##### `0xf5` — **PCIE Devices Power On** (OneOf)
> Allow the system to be waked up by a PCIE device and enable wake on LAN.
- VarStore `0x1` · offset `0x111` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xf6` — **Ring-In Power On** (OneOf)
> Allow the system to be waked up by onboard COM port modem Ring-In signals.
- VarStore `0x1` · offset `0x113` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xf7` — **RTC Alarm Power On** (OneOf)
> Allow the system to be waked up by the real time clock alarm. Set it to By OS to let it be handled by your operating system.
- VarStore `0x1` · offset `0x114` · 8-bit · range `0x0`..`0x2`
- options: `0` = Disabled, `1` = Enabled, `2` = By OS (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xf8` — **  RTC Alarm Date** (OneOf)
> Set Date of RTC power on feature.
- VarStore `0x1` · offset `0x115` · 8-bit · range `0x0`..`0x1f`
- options: `0` = Every Day (default, mfg), `1` = 1, `2` = 2, `3` = 3, `4` = 4, `5` = 5, `6` = 6, `7` = 7, `8` = 8, `9` = 9, `10` = 10, `11` = 11, `12` = 12, `13` = 13, `14` = 14, `15` = 15, `16` = 16, `17` = 17, `18` = 18, `19` = 19, `20` = 20, `21` = 21, `22` = 22, `23` = 23, `24` = 24, `25` = 25, `26` = 26, `27` = 27, `28` = 28, `29` = 29, `30` = 30, `31` = 31
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0xf9` — **  RTC Alarm Hour** (OneOf)
> Set Hour of RTC power on feature.
- VarStore `0x1` · offset `0x116` · 8-bit · range `0x0`..`0x17`
- options: `0` = 0 (default, mfg), `1` = 1, `2` = 2, `3` = 3, `4` = 4, `5` = 5, `6` = 6, `7` = 7, `8` = 8, `9` = 9, `10` = 10, `11` = 11, `12` = 12, `13` = 13, `14` = 14, `15` = 15, `16` = 16, `17` = 17, `18` = 18, `19` = 19, `20` = 20, `21` = 21, `22` = 22, `23` = 23

##### `0xfa` — **  RTC Alarm Minute** (OneOf)
> Set Minute of RTC power on feature.
- VarStore `0x1` · offset `0x117` · 8-bit · range `0x0`..`0x3b`
- options: `0` = 0 (default, mfg), `1` = 1, `2` = 2, `3` = 3, `4` = 4, `5` = 5, `6` = 6, `7` = 7, `8` = 8, `9` = 9, `10` = 10, `11` = 11, `12` = 12, `13` = 13, `14` = 14, `15` = 15, `16` = 16, `17` = 17, `18` = 18, `19` = 19, `20` = 20, `21` = 21, `22` = 22, `23` = 23, `24` = 24, `25` = 25, `26` = 26, `27` = 27, `28` = 28, `29` = 29, `30` = 30, `31` = 31, `32` = 32, `33` = 33, `34` = 34, `35` = 35, `36` = 36, `37` = 37, `38` = 38, `39` = 39, `40` = 40, `41` = 41, `42` = 42, `43` = 43, `44` = 44, `45` = 45, `46` = 46, `47` = 47, `48` = 48, `49` = 49, `50` = 50, `51` = 51, `52` = 52, `53` = 53, `54` = 54, `55` = 55, `56` = 56, `57` = 57, `58` = 58, `59` = 59

##### `0xfb` — **  RTC Alarm Second** (OneOf)
> Set Second of RTC power on feature.
- VarStore `0x1` · offset `0x118` · 8-bit · range `0x0`..`0x3b`
- options: `0` = 0 (default, mfg), `1` = 1, `2` = 2, `3` = 3, `4` = 4, `5` = 5, `6` = 6, `7` = 7, `8` = 8, `9` = 9, `10` = 10, `11` = 11, `12` = 12, `13` = 13, `14` = 14, `15` = 15, `16` = 16, `17` = 17, `18` = 18, `19` = 19, `20` = 20, `21` = 21, `22` = 22, `23` = 23, `24` = 24, `25` = 25, `26` = 26, `27` = 27, `28` = 28, `29` = 29, `30` = 30, `31` = 31, `32` = 32, `33` = 33, `34` = 34, `35` = 35, `36` = 36, `37` = 37, `38` = 38, `39` = 39, `40` = 40, `41` = 41, `42` = 42, `43` = 43, `44` = 44, `45` = 45, `46` = 46, `47` = 47, `48` = 48, `49` = 49, `50` = 50, `51` = 51, `52` = 52, `53` = 53, `54` = 54, `55` = 55, `56` = 56, `57` = 57, `58` = 58, `59` = 59

#### Form `0x27be` — Storage Configuration

_Navigation (children):_
- → `0x27bf` **%s**
- → `0x27c0` **%s**
- → `0x27c1` **%s**
- → `0x27c2` **%s**
- → `0x27c3` **%s**
- → `0x27c4` **%s**
- → `0x27c5` **%s**
- → `0x27c6` **%s**
- → `0x27ca` **%s**
- → `0x27cb` **%s**

_Settings:_

##### `0xfc` — **SATA Hot Plug** (OneOf)
> SATA Hot Plug
- VarStore `0x1` · offset `0x16e` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x27bf` — %s

#### Form `0x27c0` — %s

#### Form `0x27c1` — %s

#### Form `0x27c2` — %s

#### Form `0x27c3` — %s

#### Form `0x27c4` — %s

#### Form `0x27c5` — %s

#### Form `0x27c6` — %s

#### Form `0x27ca` — %s

#### Form `0x27cb` — %s

#### Form `0x27cf` — USB Configuration

_Settings:_

##### `0x107` — **Legacy USB Support** (OneOf)
> Enables Legacy USB support. AUTO option disables legacy support if no USB devices are connected. DISABLE option will keep USB devices available only for EFI applications.
- VarStore `0x14` · offset `0x1` · 8-bit · range `0x0`..`0x1`
- options: `0` = Enabled (default, mfg), `1` = UEFI Setup Only
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x27d1` — H/W Monitor

_Settings:_

##### `0x108` — **Watch Dog Timer** (OneOf)
> Watch Dog Timer
- VarStore `0x1` · offset `0x157` · 8-bit · range `0x0`..`0x2`
- options: `0` = Auto (default), `1` = Reset, `2` = NMI
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x27d9` — Driver Health

_Navigation (children):_
- → `0x27da` ****
  - Provides Health Status for the Drivers/Controllers

#### Form `0x27da` — Driver Health

_Navigation (children):_
- → `0x27da` ****
  - Provides Health Status for the Drivers/Controllers

#### Form `0x2713` — Chipset

_Navigation (children):_
- → `0x2723` **South Bridge**
  - South Bridge Parameters
- → `0x2750` **North Bridge**
  - North Bridge Parameters

_Settings:_

##### `0x10b` — **PCIe Link Training Type** (OneOf)
> PCIe Link training in 1 or 2 steps.
- VarStore `0x1` · offset `0xc6` · 8-bit · range `0x0`..`0x1`
- options: `0` = 1 Step (default, mfg), `1` = 2 Step

##### `0x10c` — **PCIe Compliance Mode** (OneOf)
> PCIe Link Compliance Mode.
- VarStore `0x1` · offset `0xc7` · 8-bit · range `0x0`..`0x1`
- options: `0` = Off (default, mfg), `1` = On

#### Form `0x2723` — South Bridge

_Navigation (children):_
- → `0x2725` **SB Debug Configuration**
  - Options For SB Debug Features

#### Form `0x2725` — SB Debug Configuration

_Navigation (children):_
- → `0x2726` **SB SATA DEBUG Configuration**
  - Options For SATA  DEBUG Configuration
- → `0x2727` **SB FUSION DEBUG Configuration**
  - Options For SB FUSION DEBUG Configuration
- → `0x2728` **SB MISC DEBUG Configuration**
  - Options For SB DEBUG Configuration

#### Form `0x2726` — SB SATA DEBUG Configuration

_Settings:_

##### `0x113` — **Aggressive Link PM Capability** (OneOf)
> Indicates Whether Host Bus Adapter (HBA) Can Support Auto-Generating Link Requests To The Partial Or Slumber States When There Are No Commands To Process
- VarStore `0x1` · offset `0xb1` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x114` — **Port Multiplier Capability** (OneOf)
> Indicates Whether Host Bus Adapter (HBA) Can Support A Port Multiplier
- VarStore `0x1` · offset `0xb2` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x115` — **SATA Ports Auto Clock Control** (OneOf)
> EnableDisable SATA Ports Auto Clock Control
- VarStore `0x1` · offset `0xb3` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x116` — **SATA Partial State Capability** (OneOf)
> Indicates Whether SATA Host Bus Adapter (HBA) Can Support Transitions To The Partial State
- VarStore `0x1` · offset `0xb4` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x117` — **SATA FIS Based Switching** (OneOf)
> Indicates Whether SATA Host Bus Adapter (HBA) Can Support Port Multiplier FIS-Based Switching
- VarStore `0x1` · offset `0xb5` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x118` — **SATA Command Completion Coalescing Support** (OneOf)
> Indicates Whether SATA Host Bus Adapter (HBA) Can Support Command Completion Coalescing
- VarStore `0x1` · offset `0xb6` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x119` — **SATA Slumber State Capability** (OneOf)
> Indicates Whether SATA Host Bus Adapter (HBA) Can Support Transitions To The Slumber State
- VarStore `0x1` · offset `0xb7` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x11a` — **SATA Target Support 8 Devices** (OneOf)
> Indicates Whether SATA Target Support 8 Devices Function
- VarStore `0x1` · offset `0xb8` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x11b` — **Generic Mode** (OneOf)
> Sata Disable Generic Mode
- VarStore `0x1` · offset `0xb9` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x11c` — **SATA AHCI Enclosure** (OneOf)
> SATA AHCI Enclosure Management
- VarStore `0x1` · offset `0xba` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x11d` — **SATA SGPIO 0** (OneOf)
> Enable/Disable SATA Serial General Purpose Input/Output (SGPIO) 0
- VarStore `0x1` · offset `0xbb` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x2727` — SB FUSION DEBUG Configuration

_Settings:_

##### `0x11e` — **TimerTick Tracking** (OneOf)
- VarStore `0x1` · offset `0xbc` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x11f` — **Clock Interrupt Tag** (OneOf)
- VarStore `0x1` · offset `0xbd` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x2728` — SB MISC DEBUG Configuration

_Settings:_

##### `0x120` — **SB Clock Spread Spectrum** (OneOf)
> Enable/Disable CG1_PLL Spread Spectrum
- VarStore `0x1` · offset `0xbe` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x121` — **HPET In SB** (OneOf)
> HPET Function Switch
- VarStore `0x1` · offset `0xbf` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x122` — **MsiDis in HPET** (OneOf)
> Expose MSI capability in HPET Capbility register
- VarStore `0x1` · offset `0xc0` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x2750` — North Bridge

_Navigation (children):_
- → `0x2751` **Socket 0 Information**
  - View Information related to Socket 0
- → `0x2752` **Socket 1 Information**
  - View Information related to Socket 1

#### Form `0x2751` — Socket 0 Information

#### Form `0x2752` — Socket 1 Information

#### Form `0x2753` — Memory Configuration

_Settings:_

##### `0x274f` — **Memory Clock** (OneOf)
> This Option Allows User to select different Memory Clock. Default value is 800Mhz.
- VarStore `0x1` · offset `0x101` · 8-bit · range `0x0`..`0x5`
- options: `0` = Auto (default, mfg), `1` = 1333MHz, `2` = 1600MHz, `3` = 1866MHz, `4` = 2133MHz, `5` = 2400MHz

#### Form `0x2714` — Security

_Navigation (children):_
- → `0x2775` **1st HDD Security:**
  - HDD Security Configuration for selected drive
- → `0x2776` **2nd HDD Security:**
  - HDD Security Configuration for selected drive
- → `0x2777` **3rd HDD Security:**
  - HDD Security Configuration for selected drive
- → `0x2778` **4th HDD Security:**
  - HDD Security Configuration for selected drive
- → `0x2779` **5th HDD Security:**
  - HDD Security Configuration for selected drive
- → `0x277a` **6th HDD Security:**
  - HDD Security Configuration for selected drive
- → `0x27d4` **Security**
  - Security

#### Form `0x2775` — HDD Security Configuration:

#### Form `0x2776` — HDD Security Configuration:

#### Form `0x2777` — HDD Security Configuration:

#### Form `0x2778` — HDD Security Configuration:

#### Form `0x2779` — HDD Security Configuration:

#### Form `0x277a` — HDD Security Configuration:

#### Form `0x2784` — Secure Boot

_Settings:_

##### `0x2785` — **Secure Boot** (OneOf)
> Enable to support Windows 8 Secure Boot.
- VarStore `0x18` · offset `0x0` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x278b` — Key Management

_Navigation (children):_
- → `0x278b` **Install default Secure Boot keys**
  - Please install default secure boot keys if it's the first time you use secure boot.
- → `0x278b` **Clear Secure Boot keys**
  - Force System to Setup Mode - clear all Secure Boot Variables. Change takes effect after reboot
- → `0x278b` **Export Secure Boot variables**
  - Copy NVRAM content of Secure Boot variables to files in a root folder on a file system device
- → `0x278b` **Remove 'UEFI CA' from DB**
  - Device Guard ready system must not list 'Microsoft UEFI CA' Certificate in Authorized Signature database (db)
- → `0x278b` **Restore DB defaults**
  - Restore DB variable to factory defaults

_Settings:_

##### `0x278c` — **Factory Key Provision** (OneOf)
> Install factory default Secure Boot keys after the platform reset and while the System is in Setup mode
- VarStore `0x18` · offset `0x2` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled (default, mfg)

#### Form `0x27d4` — Security

_Navigation (children):_
- → `0x2784` **Secure Boot**
  - Secure Boot configuration

_Settings:_

##### `0x126` — **Supervisor Password** (Password)
> Set or change the password for the administrator account. Only the administrator has authority to change the settings in the UEFI Setup Utility. Leave it blank and press enter to remove the password.
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x127` — **User Password** (Password)
> Set or change the password for the user account. Users are unable to change the settings in the UEFI Setup Utility. Leave it blank and press enter to remove the password.
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x2715` — Boot

_Navigation (children):_
- → `0x27d2` **Boot**
  - Boot

_Settings:_

##### `0x129` — **Boot Option #%d** (OneOf)
> Sets the system boot order
- VarStore `0xf006` · offset `0x0` · 16-bit · range `0x0`..`0x1`
- options: `0` = , `1` = 

##### `0x12a` — **Driver Option #%d** (OneOf)
> Sets the system driver order
- VarStore `0xf` · offset `0x0` · 16-bit · range `0x0`..`0x1`
- options: `0` =  (default, mfg), `1` = 

#### Form `0x27d2` — Boot

_Navigation (children):_
- → `0x27d3` **CSM(Compatibility Support Module)**
  - OpROM execution, boot options filter, etc.

_Settings:_

##### `0x12c` — **Boot Option #%d** (OneOf)
> Sets the system boot order
- VarStore `0xf006` · offset `0x0` · 16-bit · range `0x0`..`0x1`
- options: `0` =  (default), `1` = 

##### `0x12d` — **Boot option filter** (OneOf)
> This option controls Legacy/UEFI ROMs priority
- VarStore `0x1` · offset `0x10c` · 8-bit · range `0x0`..`0x2`
- options: `0` = UEFI and Legacy, `1` = Legacy only, `2` = UEFI only
- conditions: SuppressIf(Q0x2760=0x0)

##### `0x12e` — **Setup Prompt Timeout** (Numeric)
> Configure the number of seconds to wait for the UEFI setup utility.
- VarStore `0xf005` · offset `0x0` · 16-bit · range `0x0`..`0xffff` · default `1`
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x12f` — **Bootup Num-Lock** (OneOf)
> Select whether Num Lock should be turned on or off when the system boots up.
- VarStore `0x1` · offset `0x0` · 8-bit · range `0x0`..`0x1`
- options: `1` = On (default), `0` = Off
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x130` — **Boot Beep** (OneOf)
> Select whether the Boot Beep should be turned on or off when the system boots up. Please note that a buzzer is needed.
- VarStore `0x1` · offset `0x172` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x131` — **Full Screen Logo** (CheckBox)
> Enable to display the boot logo or disable to show normal POST messages.
- VarStore `0xf013` · offset `0x40` · 8-bit
- options: `0` = Disabled, `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x132` — **  AddOn ROM Display** (OneOf)
> Set display mode for Option ROM
- VarStore `0x1` · offset `0x107` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled (default, mfg), `0` = Disabled
- conditions: GrayOutIf(Q0x14a=0x1)

#### Form `0x27d3` — CSM(Compatibility Support Module)

_Settings:_

##### `0x2760` — **CSM** (OneOf)
> Enable to launch the Compatibility Support Module. If you are using Windows 8 64-bit UEFI and all of your devices support UEFI, you may also disable CSM for faster boot speed.
- VarStore `0x1` · offset `0x106` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x134` — **Launch PXE OpROM Policy** (OneOf)
> Select UEFI only to run those that support UEFI option ROM only. Select Legacy only to run those that support legacy option ROM only. Select Do not launch to not execute both legacy and UEFI option ROM.
- VarStore `0x1` · offset `0x10d` · 8-bit · range `0x0`..`0x2`
- options: `0` = Do not launch, `1` = UEFI only, `2` = Legacy only
- conditions: GrayOutIf(Q0x14a=0x1)

##### `0x135` — **Launch Storage OpROM Policy** (OneOf)
> Select UEFI only to run those that support UEFI option ROM only. Select Legacy only to run those that support legacy option ROM only. Select Do not launch to not execute both legacy and UEFI option ROM.
- VarStore `0x1` · offset `0x10e` · 8-bit · range `0x0`..`0x2`
- options: `0` = Do not launch, `1` = UEFI only, `2` = Legacy only

##### `0x136` — **Launch Video OpROM Policy** (OneOf)
> Select UEFI only to run those that support UEFI option ROM only. Select Legacy only to run those that support legacy option ROM only. Select Do not launch to not execute both legacy and UEFI option ROM.
- VarStore `0x1` · offset `0x10f` · 8-bit · range `0x0`..`0x2`
- options: `0` = Do not launch, `1` = UEFI only, `2` = Legacy only

#### Form `0x2716` — Exit

_Navigation (children):_
- → `0x2716` **Save Changes and Reset**
  - Reset the system after saving the changes.
- → `0x2716` **Discard Changes and Reset**
  - Reset system setup without saving any changes.
- → `0x2716` **Save Changes**
  - Save Changes done so far to any of the setup options.
- → `0x2716` **Save as User Defaults**
  - Save the changes done so far as User Defaults.
- → `0x2716` **Restore User Defaults**
  - Restore the User Defaults to all the setup options.
- → `0x2716` ****
- → `0x27d6` **Exit**
  - Exit

_Settings:_

##### `0x141` — **Refresh attribute registry** (OneOf)
> Refreshes the attribute registry in next boot. This will be helpful for complex condition evaluation
- VarStore `0xb` · offset `0x0` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled

#### Form `0x27d6` — Exit

_Navigation (children):_
- → `0x27d6` **Save Changes**
  - Save Changes done so far to any of the setup options.
- → `0x27d6` ****

_Settings:_

##### `0x149` — **(unnamed)** (Numeric)
- VarStore `0xf003` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

##### `0x14a` — **(unnamed)** (Numeric)
- VarStore `0xf000` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x14b` — **(unnamed)** (Numeric)
- VarStore `0xf002` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

##### `0x14c` — **(unnamed)** (Numeric)
- VarStore `0xe` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

##### `0x14d` — **(unnamed)** (Numeric)
- VarStore `0x19` · offset `0x3` · 8-bit · range `0x0`..`0xff`

##### `0x14e` — **(unnamed)** (Numeric)
- VarStore `0x19` · offset `0x2` · 8-bit · range `0x0`..`0xff`

##### `0x14f` — **(unnamed)** (Numeric)
- VarStore `0x19` · offset `0x1` · 8-bit · range `0x0`..`0xff`

##### `0x150` — **(unnamed)** (Numeric)
- VarStore `0x19` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x151` — **(unnamed)** (Numeric)
- VarStore `0x19` · offset `0x4` · 8-bit · range `0x0`..`0xff`

##### `0x152` — **(unnamed)** (Numeric)
- VarStore `0x19` · offset `0x5` · 8-bit · range `0x0`..`0xff`

##### `0x153` — **(unnamed)** (Numeric)
- VarStore `0x1a` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x154` — **(unnamed)** (Numeric)
- VarStore `0x1c` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x155` — **(unnamed)** (Numeric)
- VarStore `0x1b` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x156` — **(unnamed)** (Numeric)
- VarStore `0x1d` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x157` — **(unnamed)** (Numeric)
- VarStore `0x1e` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x158` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

##### `0x159` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x30` · 16-bit · range `0x0`..`0xffff`

##### `0x15a` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x48` · 16-bit · range `0x0`..`0xffff`

##### `0x15b` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x3c` · 16-bit · range `0x0`..`0xffff`

##### `0x15c` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x24` · 16-bit · range `0x0`..`0xffff`

##### `0x15d` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x18` · 16-bit · range `0x0`..`0xffff`

##### `0x15e` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0xc` · 16-bit · range `0x0`..`0xffff`

##### `0x15f` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x2e` · 16-bit · range `0x0`..`0xffff`

##### `0x160` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x46` · 16-bit · range `0x0`..`0xffff`

##### `0x161` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x3a` · 16-bit · range `0x0`..`0xffff`

##### `0x162` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x22` · 16-bit · range `0x0`..`0xffff`

##### `0x163` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x16` · 16-bit · range `0x0`..`0xffff`

##### `0x164` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0xa` · 16-bit · range `0x0`..`0xffff`

##### `0x165` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x2c` · 16-bit · range `0x0`..`0xffff`

##### `0x166` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x44` · 16-bit · range `0x0`..`0xffff`

##### `0x167` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x38` · 16-bit · range `0x0`..`0xffff`

##### `0x168` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x20` · 16-bit · range `0x0`..`0xffff`

##### `0x169` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x14` · 16-bit · range `0x0`..`0xffff`

##### `0x16a` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x8` · 16-bit · range `0x0`..`0xffff`

##### `0x16b` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x2a` · 16-bit · range `0x0`..`0xffff`

##### `0x16c` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x42` · 16-bit · range `0x0`..`0xffff`

##### `0x16d` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x36` · 16-bit · range `0x0`..`0xffff`

##### `0x16e` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x1e` · 16-bit · range `0x0`..`0xffff`

##### `0x16f` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x12` · 16-bit · range `0x0`..`0xffff`

##### `0x170` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x6` · 16-bit · range `0x0`..`0xffff`

##### `0x171` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x28` · 16-bit · range `0x0`..`0xffff`

##### `0x172` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x40` · 16-bit · range `0x0`..`0xffff`

##### `0x173` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x34` · 16-bit · range `0x0`..`0xffff`

##### `0x174` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x1c` · 16-bit · range `0x0`..`0xffff`

##### `0x175` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x10` · 16-bit · range `0x0`..`0xffff`

##### `0x176` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x4` · 16-bit · range `0x0`..`0xffff`

##### `0x177` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x26` · 16-bit · range `0x0`..`0xffff`

##### `0x178` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x3e` · 16-bit · range `0x0`..`0xffff`

##### `0x179` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x32` · 16-bit · range `0x0`..`0xffff`

##### `0x17a` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x1a` · 16-bit · range `0x0`..`0xffff`

##### `0x17b` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0xe` · 16-bit · range `0x0`..`0xffff`

##### `0x17c` — **(unnamed)** (Numeric)
- VarStore `0x16` · offset `0x2` · 16-bit · range `0x0`..`0xffff`

##### `0x17d` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0xfe` · 8-bit · range `0x0`..`0xff`

##### `0x17e` — **(unnamed)** (Numeric)
- VarStore `0x26` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

##### `0x17f` — **(unnamed)** (Numeric)
- VarStore `0x25` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

##### `0x180` — **(unnamed)** (Numeric)
- VarStore `0x21` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x181` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x16a` · 8-bit · range `0x0`..`0xff`

##### `0x182` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x1f` · 8-bit · range `0x0`..`0xff`

##### `0x183` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x1e` · 8-bit · range `0x0`..`0xff`

##### `0x184` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x1d` · 8-bit · range `0x0`..`0xff`

##### `0x185` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x1c` · 8-bit · range `0x0`..`0xff`

##### `0x186` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x1b` · 8-bit · range `0x0`..`0xff`

##### `0x187` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x1a` · 8-bit · range `0x0`..`0xff`

##### `0x188` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x19` · 8-bit · range `0x0`..`0xff`

##### `0x189` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x18` · 8-bit · range `0x0`..`0xff`

##### `0x18a` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x17` · 8-bit · range `0x0`..`0xff`

##### `0x18b` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x16` · 8-bit · range `0x0`..`0xff`

##### `0x18c` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x15` · 8-bit · range `0x0`..`0xff`

##### `0x18d` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x14` · 8-bit · range `0x0`..`0xff`

##### `0x18e` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x13` · 8-bit · range `0x0`..`0xff`

##### `0x18f` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x12` · 8-bit · range `0x0`..`0xff`

##### `0x190` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x11` · 8-bit · range `0x0`..`0xff`

##### `0x191` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x10` · 8-bit · range `0x0`..`0xff`

##### `0x192` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0xf` · 8-bit · range `0x0`..`0xff`

##### `0x193` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0xe` · 8-bit · range `0x0`..`0xff`

##### `0x194` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0xd` · 8-bit · range `0x0`..`0xff`

##### `0x195` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0xc` · 8-bit · range `0x0`..`0xff`

##### `0x196` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0xb` · 8-bit · range `0x0`..`0xff`

##### `0x197` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0xa` · 8-bit · range `0x0`..`0xff`

##### `0x198` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x9` · 8-bit · range `0x0`..`0xff`

##### `0x199` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x8` · 8-bit · range `0x0`..`0xff`

##### `0x19a` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x7` · 8-bit · range `0x0`..`0xff`

##### `0x19b` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x6` · 8-bit · range `0x0`..`0xff`

##### `0x19c` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x5` · 8-bit · range `0x0`..`0xff`

##### `0x19d` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x4` · 8-bit · range `0x0`..`0xff`

##### `0x19e` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x3` · 8-bit · range `0x0`..`0xff`

##### `0x19f` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x2` · 8-bit · range `0x0`..`0xff`

##### `0x1a0` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x1` · 8-bit · range `0x0`..`0xff`

##### `0x1a1` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x1a2` — **(unnamed)** (Numeric)
- VarStore `0x17` · offset `0x20` · 8-bit · range `0x0`..`0xff`

##### `0x1a3` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x1f` · 8-bit · range `0x0`..`0xff`

##### `0x1a4` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x1e` · 8-bit · range `0x0`..`0xff`

##### `0x1a5` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x1d` · 8-bit · range `0x0`..`0xff`

##### `0x1a6` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x1c` · 8-bit · range `0x0`..`0xff`

##### `0x1a7` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x1b` · 8-bit · range `0x0`..`0xff`

##### `0x1a8` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x1a` · 8-bit · range `0x0`..`0xff`

##### `0x1a9` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x19` · 8-bit · range `0x0`..`0xff`

##### `0x1aa` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x18` · 8-bit · range `0x0`..`0xff`

##### `0x1ab` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x17` · 8-bit · range `0x0`..`0xff`

##### `0x1ac` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x16` · 8-bit · range `0x0`..`0xff`

##### `0x1ad` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x15` · 8-bit · range `0x0`..`0xff`

##### `0x1ae` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x14` · 8-bit · range `0x0`..`0xff`

##### `0x1af` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x13` · 8-bit · range `0x0`..`0xff`

##### `0x1b0` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x12` · 8-bit · range `0x0`..`0xff`

##### `0x1b1` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x11` · 8-bit · range `0x0`..`0xff`

##### `0x1b2` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x10` · 8-bit · range `0x0`..`0xff`

##### `0x1b3` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0xf` · 8-bit · range `0x0`..`0xff`

##### `0x1b4` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0xe` · 8-bit · range `0x0`..`0xff`

##### `0x1b5` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0xd` · 8-bit · range `0x0`..`0xff`

##### `0x1b6` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0xc` · 8-bit · range `0x0`..`0xff`

##### `0x1b7` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0xb` · 8-bit · range `0x0`..`0xff`

##### `0x1b8` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0xa` · 8-bit · range `0x0`..`0xff`

##### `0x1b9` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x9` · 8-bit · range `0x0`..`0xff`

##### `0x1ba` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x8` · 8-bit · range `0x0`..`0xff`

##### `0x1bb` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x7` · 8-bit · range `0x0`..`0xff`

##### `0x1bc` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x6` · 8-bit · range `0x0`..`0xff`

##### `0x1bd` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x5` · 8-bit · range `0x0`..`0xff`

##### `0x1be` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x4` · 8-bit · range `0x0`..`0xff`

##### `0x1bf` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x3` · 8-bit · range `0x0`..`0xff`

##### `0x1c0` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x2` · 8-bit · range `0x0`..`0xff`

##### `0x1c1` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x1` · 8-bit · range `0x0`..`0xff`

##### `0x1c2` — **(unnamed)** (Numeric)
- VarStore `0x12` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x1c3` — **(unnamed)** (Numeric)
- VarStore `0x11` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x1c4` — **(unnamed)** (Numeric)
- VarStore `0x13` · offset `0x3` · 8-bit · range `0x0`..`0xff`

##### `0x1c5` — **(unnamed)** (Numeric)
- VarStore `0x13` · offset `0x2` · 8-bit · range `0x0`..`0xff`

##### `0x1c6` — **(unnamed)** (Numeric)
- VarStore `0x13` · offset `0x1` · 8-bit · range `0x0`..`0xff`

##### `0x1c7` — **(unnamed)** (Numeric)
- VarStore `0x13` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x1c8` — **(unnamed)** (Numeric)
- VarStore `0x22` · offset `0x3` · 8-bit · range `0x0`..`0xff`

##### `0x1c9` — **(unnamed)** (Numeric)
- VarStore `0x23` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

##### `0x1ca` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x9` · 8-bit · range `0x0`..`0xff`

##### `0x1cb` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0xd` · 8-bit · range `0x0`..`0xff`

##### `0x1cc` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0xb` · 8-bit · range `0x0`..`0xff`

##### `0x1cd` — **(unnamed)** (Numeric)
- VarStore `0x2` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x1ce` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x19` · 8-bit · range `0x0`..`0xff`

##### `0x1cf` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x18` · 8-bit · range `0x0`..`0xff`

##### `0x1d0` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x17` · 8-bit · range `0x0`..`0xff`

##### `0x1d1` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x8` · 8-bit · range `0x0`..`0xff`

##### `0x1d2` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x7` · 8-bit · range `0x0`..`0xff`

##### `0x1d3` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x4` · 8-bit · range `0x0`..`0xff`

##### `0x1d4` — **(unnamed)** (Numeric)
- VarStore `0x24` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

##### `0x1d5` — **(unnamed)** (Numeric)
- VarStore `0x20` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x1d6` — **(unnamed)** (Numeric)
- VarStore `0xf00a` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

## Module: `75_ServerMgmtSetup.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `01239999-FC0E-4B6E-9E79-D54D5DB6CD20`
- FormSet title: **Server Mgmt**
- FormSet help: Press <Enter> to view or change the Server management configuration.

### VarStores
- `0x1` **ServerSetup** — GUID `01239999-FC0E-4B6E-9E79-D54D5DB6CD20`, size `0x2fb`
- `0x2` **HideBondingInfo** — GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`, size `0x1`
- `0x3` **LanEnableInfo** — GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`, size `0x10`
- `0x4` **ErrorManager** — GUID `ADDEBF82-A560-46B9-A280-78C6AB61AEDA`, size `0x4`
- `0x5` **AsrBackupBmcMacSetup** — GUID `EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9`, size `0x1`
- `0xf000` **SystemAccess** — GUID `E770BB69-BCB4-4D04-9E97-23FF9456FEAC`, size `0x1`

### Forms

#### Form `0x2711` — Server Mgmt

_Navigation (children):_
- → `0x2718` **BMC Network Configuration**
  - Configure BMC network parameters
- → `0x2772` **System Event Log**
  - Press <Enter> to change the SEL event log configuration.
- → `0x2774` **Bmc self test log**
  - logs the report returned by BMC self test command
- → `0x2776` **View System Event Log**
  - Press <Enter> to view the System Event Log Records.
- → `0x2786` **BMC User Settings**
  - Press <Enter> to Add, Delete and Set Privilege level for users.
- → `0x278e` **BMC Mac Backup Tool**
  - If your BMC Mac is broken, restore it from the backup
- → `0x2791` **BMC Tools**
  - BMC Tools

_Settings:_

##### `0x1` — **BMC Support** (OneOf)
> Enable/Disable interfaces to communicate with BMC
- VarStore `0x1` · offset `0x0` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled

##### `0x2` — **IPMI Interface Type** (OneOf)
> Type of Interface to communicate BMC from HOST
- VarStore `0x1` · offset `0x16` · 8-bit · range `0x1`..`0x8`
- options: `1` = Kcs Interface, `3` = Bt Interface, `4` = Ssif Interface, `5` = Ipmb Interface, `6` = Usb Interface, `7` = Oem1 Interface, `8` = Oem2 Interface

##### `0x3` — **Wait For BMC** (OneOf)
> Wait For BMC response for specified time out. BMC starts at the same time when BIOS starts during AC power ON. It takes around 90 seconds to initialize Host to BMC interfaces.
- VarStore `0x1` · offset `0x1` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled
- conditions: GrayOutIf(Q0x22=0x1)

##### `0x4` — **FRB-2 Timer** (OneOf)
> Enable or Disable FRB-2 timer(POST timer)
- VarStore `0x1` · offset `0x21f` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled
- conditions: SuppressIf(Q0x1=0x0); GrayOutIf(Q0x22=0x1)

##### `0x5` — **FRB-2 Timer timeout** (Numeric)
> Enter value Between 1 to 30 min for FRB-2 Timer Expiration
- VarStore `0x1` · offset `0x220` · 8-bit · range `0x1`..`0x1e` · default `6`
- conditions: SuppressIf(Q0x1=0x0)

##### `0x6` — **FRB-2 Timer Policy** (OneOf)
> Configure how the system should respond if the FRB-2 Timer expires. Not available if FRB-2 Timer is disabled.
- VarStore `0x1` · offset `0x221` · 8-bit · range `0x0`..`0x3`
- options: `0` = Do Nothing, `1` = Reset, `2` = Power Down, `3` = Power Cycle
- conditions: SuppressIf(Q0x1=0x0)

##### `0x7` — **OS Watchdog Timer** (OneOf)
> If enabled, starts a BIOS timer which can only be shut off by Management Software after the OS loads.  Helps determine that the OS successfully loaded or follows the OS Boot Watchdog Timer policy.
- VarStore `0x1` · offset `0x222` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled
- conditions: SuppressIf(Q0x1=0x0); GrayOutIf(Q0x22=0x1)

##### `0x8` — **OS Wtd Timer Timeout** (Numeric)
> Enter the value Between 1 to 30 min for OS Boot Watchdog Timer Expiration. Not available if OS Boot Watchdog Timer is disabled.
- VarStore `0x1` · offset `0x223` · 8-bit · range `0x1`..`0x1e` · default `10`
- conditions: SuppressIf(Q0x1=0x0)

##### `0x9` — **OS Wtd Timer Policy** (OneOf)
> Configure how the system should respond if the OS Boot Watchdog Timer expires. Not available if OS Boot Watchdog Timer is disabled.
- VarStore `0x1` · offset `0x224` · 8-bit · range `0x0`..`0x3`
- options: `0` = Do Nothing, `1` = Reset, `2` = Power Down, `3` = Power Cycle
- conditions: SuppressIf(Q0x1=0x0)

##### `0xa` — **Serial Mux** (OneOf)
> Press <Enter> to enable or disable Serial Mux configuration.
- VarStore `0x1` · offset `0x22d` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled
- conditions: SuppressIf(Q0x1=0x0); GrayOutIf(Q0x22=0x1)

#### Form `0x2718` — BMC Network Configuration

_Navigation (children):_
- → `0x2718` **Bonding Setting**
  - Enable/Disable bonding, if you want to enable bonding please enable all Lan channel first
- → `0x2718` **eth2 enable setting**
  - BMC LAN enable setting
- → `0x2718` **eth0 enable setting**
  - BMC LAN enable setting
- → `0x2718` **eth1 enable setting**
  - BMC LAN enable setting

_Settings:_

##### `0xd` — **Configuration address source** (OneOf)
> Static/DHCP IP address
- VarStore `0x1` · offset `0x19` · 8-bit · range `0x1`..`0x2`
- options: `1` = Static, `2` = DHCP (default, mfg)
- conditions: SuppressIf(Q0x2724=0x2); GrayOutIf(Q0x22=0x1)

##### `0xe` — **VLAN** (OneOf)
> Enabled/Disabled Virtual Local Area Network.
- VarStore `0x1` · offset `0x217` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled

##### `0x11` — **Configuration address source** (OneOf)
> Static/DHCP IP address
- VarStore `0x1` · offset `0x1a` · 8-bit · range `0x1`..`0x2`
- options: `1` = Static, `2` = DHCP (default, mfg)
- conditions: SuppressIf(Q0x2725=0x2); GrayOutIf(Q0x22=0x1)

##### `0x12` — **VLAN** (OneOf)
> Enabled/Disabled Virtual Local Area Network.
- VarStore `0x1` · offset `0x218` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default, mfg), `1` = Enabled

##### `0x2750` — **IPV6 Support** (OneOf)
> Enable or Disable LAN IPV6 Support
- VarStore `0x1` · offset `0xcf` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled
- conditions: GrayOutIf(Q0x22=0x1)

##### `0x15` — **Manual setting IPMI LAN(IPV6)** (OneOf)
> Select to configure LAN channel parameters statically or dynamically(by BIOS or BMC). Unspecified option will not modify any BMC network parameters during BIOS phase
- VarStore `0x1` · offset `0x175` · 8-bit · range `0x0`..`0x2`
- options: `0` = No Change, `1` = Static, `2` = DHCP
- conditions: SuppressIf(Q0x2750=0x0); GrayOutIf(Q0x22=0x1)

##### `0x16` — **Prefix Length** (Numeric)
> Change the prefix length
- VarStore `0x1` · offset `0xd1` · 8-bit · range `0x0`..`0x80` · default `0`

##### `0x2751` — **IPV6 Support** (OneOf)
> Enable or Disable LAN IPV6 Support
- VarStore `0x1` · offset `0xd0` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled
- conditions: GrayOutIf(Q0x22=0x1)

##### `0x17` — **Manual setting IPMI LAN(IPV6)** (OneOf)
> Select to configure LAN channel parameters statically or dynamically(by BIOS or BMC). Unspecified option will not modify any BMC network parameters during BIOS phase
- VarStore `0x1` · offset `0x176` · 8-bit · range `0x0`..`0x2`
- options: `0` = No Change, `1` = Static, `2` = DHCP
- conditions: SuppressIf(Q0x2751=0x0); GrayOutIf(Q0x22=0x1)

##### `0x18` — **Prefix Length** (Numeric)
> Change the prefix length
- VarStore `0x1` · offset `0xd2` · 8-bit · range `0x0`..`0x80` · default `0`

#### Form `0x2772` — System Event Log

_Settings:_

##### `0x19` — **SEL Components** (OneOf)
> Change this to enable or disable event logging for error/progress codes during boot.
- VarStore `0x1` · offset `0x225` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled
- conditions: GrayOutIf(Q0x22=0x1)

##### `0x1a` — **Erase SEL** (OneOf)
> Choose options for erasing SEL.
- VarStore `0x1` · offset `0x226` · 8-bit · range `0x0`..`0x2`
- options: `0` = No, `1` = Yes, On next reset, `2` = Yes, On every reset

##### `0x1b` — **When SEL is Full** (OneOf)
> Choose options for reactions to a full SEL.
- VarStore `0x1` · offset `0x227` · 8-bit · range `0x0`..`0x1`
- options: `0` = Do Nothing, `1` = Erase Immediately

##### `0x1c` — **Log EFI Status Codes** (OneOf)
> Disable the logging of EFI Status Codes or log only error code or only progress code or both.
- VarStore `0x1` · offset `0x228` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Both, `2` = Error code, `3` = Progress code

##### `0x1d` — **PCIe Device Degrade ELog Support** (OneOf)
> Enable/Disable PCIe Device Degrade Error Logging Support
- VarStore `0x1` · offset `0x2f9` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Enabled

#### Form `0x2774` — Bmc self test log

_Settings:_

##### `0x1e` — **Erase Log** (OneOf)
> Erase Log Options
- VarStore `0x1` · offset `0x22b` · 8-bit · range `0x0`..`0x1`
- options: `1` = Yes, On every reset, `0` = No

##### `0x1f` — **When log is full** (OneOf)
> Select the action to be taken when log is full
- VarStore `0x1` · offset `0x22c` · 8-bit · range `0x0`..`0x1`
- options: `1` = Clear Log, `0` = Do not log any more

#### Form `0x2776` — View System Event Log

_Navigation (children):_
- → `0x2776` **View remaining System Event Log**
  - Press <Enter> to view the remaining System Event Log Records.
- → `0x2776` ****

#### Form `0x2786` — BMC User Settings

_Navigation (children):_
- → `0x278a` **Add User**
  - Press <Enter> to Add a User.
- → `0x278b` **Delete User**
  - Press <Enter> to Delete a User.
- → `0x278c` **Change User Settings**
  - Press <Enter> to Change User Settings.

#### Form `0x278a` — BMC Add User Details

_Settings:_

##### `0x2779` — **User Password** (Password)
> Enter BMC User Password
- conditions: GrayOutIf(Q0x2c=0x0)

##### `0x277a` — **User Access** (OneOf)
> Enable/Disable the BMC User's Access.
- VarStore `0x1` · offset `0x2eb` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enable, `0` = Disable
- conditions: GrayOutIf(Q0x2b=0x0)

##### `0x277b` — **Channel No** (Numeric)
> Enter BMC Channel Number
- VarStore `0x1` · offset `0x2e9` · 8-bit · range `0x0`..`0xf` · default `0`

##### `0x277c` — **User Privilege Limit** (OneOf)
> Enter BMC User Privilege Limit for Selected Channel
- VarStore `0x1` · offset `0x2ea` · 8-bit · range `0x1`..`0xf`
- options: `15` = No Access, `1` = Callback, `2` = User, `3` = Operator, `4` = Administrator, `5` = OEM Proprietary
- conditions: GrayOutIf(Q0x2a=0x0)

#### Form `0x278b` — BMC Delete User Details

#### Form `0x278c` — BMC Change User Settings

_Settings:_

##### `0x2783` — **Change User Password** (Password)
> Enter New Password to change.
- conditions: GrayOutIf(Q0x25=0x0)

##### `0x2784` — **User Access** (OneOf)
> Enable/Disable the BMC User's Access.
- VarStore `0x1` · offset `0x2f0` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enable, `0` = Disable

##### `0x2781` — **Channel No** (Numeric)
> Enter BMC Channel Number
- VarStore `0x1` · offset `0x2f1` · 8-bit · range `0x0`..`0xf` · default `0`

##### `0x2782` — **User Privilege Limit** (OneOf)
> Enter BMC User Privilege Limit for Selected Channel
- VarStore `0x1` · offset `0x2f2` · 8-bit · range `0x1`..`0xf`
- options: `15` = No Access, `1` = Callback, `2` = User, `3` = Operator, `4` = Administrator, `5` = OEM Proprietary
- conditions: GrayOutIf(Q0x24=0x0)

#### Form `0x278e` — BMC Mac Backup Tool

_Navigation (children):_
- → `0x278e` **Restore BMC Mac from backup**
  - If your BMC Mac is broken, restore it from the backup

#### Form `0x2791` — BMC Tools

_Navigation (children):_
- → `0x2791` **Load BMC Default Settings**
  - Load BMC Default Settings

_Settings:_

##### `0x21` — **KCS control** (OneOf)
> Select the KSC interface state after POST end. If [Enabled] is selected, the BMC will remain KCS interface after POST stage. If [Disabled] is selected, the BMC will disable KCS interface after POST stage
- VarStore `0x1` · offset `0x2fa` · 8-bit · range `0x0`..`0x2`
- options: `0` = Disabled, `1` = Enabled, `2` = No change (default, mfg)
- conditions: SuppressIf(Q0x1=0x0); GrayOutIf(Q0x22=0x1)

##### `0x22` — **(unnamed)** (Numeric)
- VarStore `0xf000` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x23` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x2f8` · 8-bit · range `0x0`..`0xff`

##### `0x24` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x2f3` · 8-bit · range `0x0`..`0xff`

##### `0x25` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x2f6` · 8-bit · range `0x0`..`0xff`

##### `0x26` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x2f5` · 8-bit · range `0x0`..`0xff`

##### `0x27` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x2f4` · 8-bit · range `0x0`..`0xff`

##### `0x28` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x2ef` · 8-bit · range `0x0`..`0xff`

##### `0x29` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x2f7` · 8-bit · range `0x0`..`0xff`

##### `0x2a` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x2ee` · 8-bit · range `0x0`..`0xff`

##### `0x2b` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x2ec` · 8-bit · range `0x0`..`0xff`

##### `0x2c` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x2ed` · 8-bit · range `0x0`..`0xff`

##### `0x2d` — **(unnamed)** (Numeric)
- VarStore `0x4` · offset `0x0` · 16-bit · range `0x0`..`0xffff`

##### `0x2e` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x22e` · 8-bit · range `0x0`..`0xff`

##### `0x2f` — **(unnamed)** (Numeric)
- VarStore `0x3` · offset `0x1` · 8-bit · range `0x0`..`0xff`

##### `0x30` — **(unnamed)** (Numeric)
- VarStore `0x2` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x31` — **(unnamed)** (Numeric)
- VarStore `0x3` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x32` — **(unnamed)** (Numeric)
- VarStore `0x5` · offset `0x0` · 8-bit · range `0x0`..`0xff`

##### `0x33` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x15` · 8-bit · range `0x0`..`0xff`

##### `0x34` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x14` · 8-bit · range `0x0`..`0xff`

##### `0x35` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x13` · 8-bit · range `0x0`..`0xff`

##### `0x36` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x12` · 8-bit · range `0x0`..`0xff`

##### `0x37` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x11` · 8-bit · range `0x0`..`0xff`

##### `0x38` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0x10` · 8-bit · range `0x0`..`0xff`

##### `0x39` — **(unnamed)** (Numeric)
- VarStore `0x1` · offset `0xe` · 8-bit · range `0x0`..`0xff`

## Module: `89_PciDynamicSetup.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `ACA9F304-21E2-4852-9875-7FF4881D67A5`
- FormSet title: **PCI Subsystem Settings**

### VarStores
- `0xcccc` **PCI_COMMON** — GUID `ACA9F304-21E2-4852-9875-7FF4881D67A5`, size `0x8`

### Forms

#### Form `0x1` — PCI Subsystem Settings

_Settings:_

##### `0x7006` — **Above 4G Decoding** (CheckBox)
> Globally Enables or Disables 64bit capable Devices to be Decoded in Above 4G Address Space (Only if System Supports 64 bit PCI Decoding).
- VarStore `0xcccc` · offset `0x3` · 8-bit
- options: `0` = Disabled, `1` = Enabled

##### `0x7007` — **SR-IOV Support** (CheckBox)
> If system has SR-IOV capable PCIe Devices, this option Enables or Disables Single Root IO Virtualization Support.
- VarStore `0xcccc` · offset `0x5` · 8-bit
- options: `0` = Disabled, `1` = Enabled

##### `0x7008` — **Hot-Plug Support** (CheckBox)
> Globally Enables or Disables Hot-Plug support for the entire System. If System has Hot-Plug capable Slots and this option set to Enabled, it provides a Setup screen for selecting PCI resource padding for Hot-Plug.
- VarStore `0xcccc` · offset `0x2` · 8-bit
- options: `0` = Disabled, `1` = Enabled

##### `0x702b` — **Re-Size BAR Support** (CheckBox)
> If system has Resizable BAR capable PCIe Devices, this option Enables or Disables Resizable BAR Support.
- VarStore `0xcccc` · offset `0x4` · 8-bit
- options: `0` = Disabled, `1` = Enabled

#### Form `0x2` — PCI Device Settings

#### Form `0x3` — PCI Express GEN 1 Settings

#### Form `0x4` — PCI Express GEN 2 Settings

#### Form `0x5` — PCI Hot-Plug Settings

## Module: `91_PciOutOfResourceSetupPage.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `932D37B0-0D4A-11E0-81E0-0800200C9A66`
- FormSet title: **!!!! PCI Resource ERROR !!!!**

### Forms

#### Form `0x1` — !!!! PCI Resource ERROR !!!!

## Module: `CbsSetupDxeSSP.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `7A6A3896-4AF0-45E5-BA63-89357FBD6D63`
- FormSet title: **AMD CBS**
- FormSet help: AMD CBS Setup Page

### VarStores
- `0x5000` **AmdSetupSSP** — GUID `3A997502-647A-4C82-998E-52EF9486A247`, size `0x686`

### Forms

#### Form `0x7000` — AMD CBS

_Navigation (children):_
- → `0x7001` **CPU Common Options**
  - CPU Common Options
- → `0x7002` **DF Common Options**
  - DF Common Options
- → `0x7003` **UMC Common Options**
  - UMC Common Options
- → `0x7004` **NBIO Common Options**
  - NBIO Common Options
- → `0x7005` **FCH Common Options**
  - FCH Common Options
- → `0x7007` **NTB Common Options**
  - NTB Common Options
- → `0x7008` **Soc Miscellaneous Control**
  - Soc Miscellaneous Control

_Settings:_

##### `0x8` — **Combo CBS** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x20` · 8-bit · range `0x0`..`0xff` · default `254`

#### Form `0x7001` — CPU Common Options

_Navigation (children):_
- → `0x7009` **Performance**
  - Performance
- → `0x700a` **Prefetcher settings**
  - Prefetcher settings
- → `0x700b` **Core Watchdog**
  - Core Watchdog

_Settings:_

##### `0xc` — **RedirectForReturnDis** (OneOf)
> From a workaround for GCC/C000005 issue for XV Core on CZ A0, setting MSRC001_1029 Decode Configuration (DE_CFG) bit 14 [DecfgNoRdrctForReturns] to 1
- VarStore `0x5000` · offset `0x21` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = 1, `0` = 0

##### `0xd` — **Platform First Error Handling** (OneOf)
> Enable/disable PFEH, cloak individual banks, and mask deferred error interrupts from each bank.
- VarStore `0x5000` · offset `0x22` · 8-bit · range `0x0`..`0x3`
- options: `1` = Enabled (default), `0` = Disabled, `3` = Auto

##### `0xe` — **Core Performance Boost** (OneOf)
> Disable CPB
- VarStore `0x5000` · offset `0x23` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Auto (default)

##### `0xf` — **Global C-state Control** (OneOf)
> Controls IO based C-state generation and DF C-states.
- VarStore `0x5000` · offset `0x24` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x10` — **Power Supply Idle Control** (OneOf)
> Power Supply Idle Control.
- VarStore `0x5000` · offset `0x25` · 8-bit · range `0x0`..`0xf`
- options: `1` = Low Current Idle, `0` = Typical Current Idle, `15` = Auto (default)

##### `0x700c` — **SEV ASID Count** (OneOf)
> This fields specifies the maximum valid ASID, which affects the maximum system physical address space. 16TB of physical address space is available for systems that support 253 ASIDs, while 8TB of physical address space is available for systems that support 509 ASIDs.
- VarStore `0x5000` · offset `0x26` · 8-bit · range `0x0`..`0x3`
- options: `0` = 253 ASIDs, `1` = 509 ASIDs, `3` = Auto (default)

##### `0x11` — **SEV-ES ASID Space Limit Control** (OneOf)
> Customize SEV-ES ASID space limit
- VarStore `0x5000` · offset `0x27` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x700d` — **SEV-ES ASID Space Limit** (Numeric)
> SEV VMs using ASIDs below the SEV-ES ASID Space Limit must enable the SEV-ES feature. ASIDs from SEV-ES ASID Space Limit to (SEV ASID Count + 1) can only be used with SEV VMs. If this field is set to (SEV ASID Count + 1), all ASIDs are forced to be SEV-ES ASIDs. Hence, the valid values for this field is 1 - (SEV ASID Count + 1)
- VarStore `0x5000` · offset `0x28` · 32-bit · range `0x1`..`0x1fe` · default `1`
- conditions: SuppressIf(Q0x11=0x0)

##### `0x12` — **Streaming Stores Control** (OneOf)
> Enables or disables the streaming stores functionality
- VarStore `0x5000` · offset `0x2c` · 8-bit · range `0x0`..`0xff`
- options: `1` = Disabled, `0` = Enabled, `255` = Auto (default)

##### `0x13` — **Local APIC Mode** (OneOf)
> Select local APIC mode: Compatibility, xAPIC or x2APIC
- VarStore `0x5000` · offset `0x2d` · 8-bit · range `0x0`..`0xff`
- options: `0` = xAPIC, `1` = x2APIC, `255` = Auto (default)

##### `0x14` — **ACPI _CST C1 Declaration** (OneOf)
> Determines whether or not to declare the C1 state to the OS.
- VarStore `0x5000` · offset `0x2e` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x15` — **MCA error thresh enable** (OneOf)
> Enable MCA error thresholding.
- VarStore `0x5000` · offset `0x2f` · 8-bit · range `0x0`..`0xff`
- options: `0` = False, `1` = True, `255` = Auto (default)

##### `0x16` — **MCA error thresh count** (Numeric)
> Effective error threshold count = 4095(0xFFF) - <this value> (e.g. the default value of 0xFF5 results in a threshold of 10).
- VarStore `0x5000` · offset `0x30` · 16-bit · range `0x1`..`0xfff` · default `4085`

##### `0x17` — **SMU and PSP Debug Mode** (OneOf)
> When this option is enabled, specific uncorrected errors detected by the PSP FW or SMU FW will hang and not reset the system
- VarStore `0x5000` · offset `0x32` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x19` — **PPIN Opt-in** (OneOf)
> Turn on PPIN feature
- VarStore `0x5000` · offset `0x34` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0x1a` — **RdRand** (OneOf)
> Disable RdRand instruction
- VarStore `0x5000` · offset `0x35` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = Enabled, `0` = Disabled

#### Form `0x7009` — Performance

_Navigation (children):_
- → `0x700f` **Custom Core Pstates**
  - Custom Core Pstates
- → `0x7010` **CCD/Core/Thread Enablement**
  - CCD/Core/Thread Enablement

_Settings:_

##### `0x700e` — **OC Mode** (OneOf)
> Can be used to modify the number of core/CCD.
- VarStore `0x5000` · offset `0x36` · 8-bit · range `0x0`..`0x5`
- options: `0` = Normal Operation (default), `1` = OC1, `2` = OC2, `3` = OC3, `5` = Customized

#### Form `0x700f` — Custom Core Pstates

_Navigation (children):_
- → `0x7011` **Decline**
  - Decline
- → `0x7012` **Accept**
  - Accept

#### Form `0x7011` — Decline

#### Form `0x7012` — Accept

_Settings:_

##### `0x1f` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x3a` · 32-bit · range `0x0`..`0xffffffff` · default `0`
- conditions: SuppressIf(Q0x7013=0x2)

##### `0x20` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x3e` · 32-bit · range `0x0`..`0xffffffff` · default `0`
- conditions: SuppressIf(Q0x7013=0x2)

##### `0x7014` — **Pstate0 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x42` · 8-bit · range `0x10`..`0xff` · default `16`
- conditions: SuppressIf(Q0x7013=0x2)

##### `0x7015` — **Pstate0 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x43` · 8-bit · range `0x8`..`0x30` · default `8`
- conditions: SuppressIf(Q0x7013=0x2)

##### `0x7016` — **Pstate0 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x44` · 8-bit · range `0x0`..`0xff` · default `255`
- conditions: SuppressIf(Q0x7013=0x2)

##### `0x21` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x46` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x22` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x4a` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7018` — **Pstate1 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x4e` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7019` — **Pstate1 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x4f` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x701a` — **Pstate1 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x50` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x23` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x52` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x24` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x56` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x701c` — **Pstate2 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x5a` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x701d` — **Pstate2 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x5b` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x701e` — **Pstate2 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x5c` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x25` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x5e` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x26` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x62` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7020` — **Pstate3 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x66` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7021` — **Pstate3 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x67` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7022` — **Pstate3 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x68` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x27` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x6a` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x28` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x6e` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7024` — **Pstate4 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x72` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7025` — **Pstate4 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x73` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7026` — **Pstate4 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x74` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x29` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x76` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x2a` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x7a` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7028` — **Pstate5 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x7e` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7029` — **Pstate5 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x7f` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x702a` — **Pstate5 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x80` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x2b` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x82` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x2c` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x86` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x702c` — **Pstate6 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x8a` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x702d` — **Pstate6 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x8b` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x702e` — **Pstate6 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x8c` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x2d` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x8e` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x2e` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x92` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7030` — **Pstate7 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x96` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7031` — **Pstate7 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x97` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7032` — **Pstate7 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x98` · 8-bit · range `0x0`..`0xff` · default `255`

#### Form `0x7010` — CCD/Core/Thread Enablement

_Navigation (children):_
- → `0x7033` **Decline**
  - Decline
- → `0x7034` **Accept**
  - Accept

#### Form `0x7033` — Decline

#### Form `0x7034` — Accept

_Navigation (children):_
- → `0x7035` **DownCore Bitmap**
  - DownCore Bitmap

_Settings:_

##### `0x31` — **CCD Control** (OneOf)
> Sets the number of CCDs to be used. Once this option has been used to remove any CCDs, a POWER CYCLE is required in order for future selections to take effect.
- VarStore `0x5000` · offset `0x9a` · 8-bit · range `0x0`..`0x6`
- options: `0` = Auto (default), `2` = 2 CCDs, `3` = 3 CCDs, `4` = 4 CCDs, `6` = 6 CCDs

##### `0x32` — **CCD Control** (OneOf)
> Sets the number of CCDs to be used. Once this option has been used to remove any CCDs, a POWER CYCLE is required in order for future selections to take effect.
- VarStore `0x5000` · offset `0x9b` · 8-bit · range `0x0`..`0x4`
- options: `0` = Auto (default), `1` = 1 CCD, `2` = 2 CCDs, `3` = 3 CCDs, `4` = 4 CCDs

##### `0x33` — **CCD Control** (OneOf)
> Sets the number of CCDs to be used. Once this option has been used to remove any CCDs, a POWER CYCLE is required in order for future selections to take effect.
- VarStore `0x5000` · offset `0x9c` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = 1 CCD

##### `0x34` — **Core control** (OneOf)
> Sets the number of cores to be used. Once this option has been used to remove any cores, a POWER CYCLE is required in order for future selections to take effect.
- VarStore `0x5000` · offset `0x9d` · 8-bit · range `0x0`..`0x7`
- options: `0` = Auto (default), `2` = TWO (1 + 1), `3` = TWO (2 + 0), `4` = THREE (3 + 0), `5` = FOUR (2 + 2), `6` = FOUR (4 + 0), `7` = SIX (3 + 3)

##### `0x35` — **Core control** (OneOf)
> Sets the number of cores to be used. Once this option has been used to remove any cores, a POWER CYCLE is required in order for future selections to take effect.
- VarStore `0x5000` · offset `0x9e` · 8-bit · range `0x0`..`0x7`
- options: `0` = Auto (default), `2` = TWO (1 + 1), `5` = FOUR (2 + 2), `7` = SIX (3 + 3)

##### `0x36` — **SMT Control** (OneOf)
> Can be used to disable symmetric multithreading. To re-enable SMT, a POWER CYCLE is needed after selecting the 'Auto' option. WARNING - S3 is NOT SUPPORTED on systems where SMT is disabled.
- VarStore `0x5000` · offset `0x9f` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Auto (default)

#### Form `0x7035` — DownCore Bitmap

_Settings:_

##### `0x38` — **CCD 0 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0xa0` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x39` — **CCD 3 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0xa1` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x3a` — **CCD 1 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0xa2` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x3b` — **CCD 4 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0xa3` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x3c` — **CCD 2 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0xa4` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x3d` — **CCD 5 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0xa5` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x3e` — **CCD 6 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0xa6` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x3f` — **CCD 7 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0xa7` · 8-bit · range `0x0`..`0xff` · default `0`

#### Form `0x700a` — Prefetcher settings

_Settings:_

##### `0x40` — **L1 Stream HW Prefetcher** (OneOf)
> Option to Enable | Disable L1 Stream HW Prefetcher
- VarStore `0x5000` · offset `0xa8` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x41` — **L2 Stream HW Prefetcher** (OneOf)
> Option to Enable | Disable L2 Stream HW Prefetcher
- VarStore `0x5000` · offset `0xa9` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

#### Form `0x700b` — Core Watchdog

_Settings:_

##### `0x7036` — **Core Watchdog Timer Enable** (OneOf)
> Enable or disable CPU Watchdog Timer
- VarStore `0x5000` · offset `0xaa` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x42` — **Core Watchdog Timer Interval** (OneOf)
> CPU Watchdog Timer Interval
- VarStore `0x5000` · offset `0xab` · 16-bit · range `0x0`..`0xffff`
- options: `2304` = 21.461s, `2048` = 10.730s, `0` = 5.364s, `256` = 2.681s, `512` = 1.340s, `768` = 669.41ms, `1024` = 334.05ms, `1280` = 166.37ms, `1536` = 82.53ms, `1792` = 40.61ms, `2305` = 20.970ms, `2049` = 10.484ms, `1` = 5.241ms, `257` = 2.620ms, `513` = 1.309ms, `769` = 654.08us, `1025` = 326.4us, `1281` = 162.56us, `1537` = 80.64us, `1793` = 39.68us, `65535` = Auto (default)

##### `0x43` — **Core Watchdog Timer Severity** (OneOf)
> Specify the CPU watch dog timer severity (MSRC001_0074[CpuWdTmrCfgSeverity]).
- VarStore `0x5000` · offset `0xad` · 8-bit · range `0x0`..`0xff`
- options: `0` = No Error, `1` = Transparent, `2` = Corrected, `3` = Deferred, `4` = Uncorrected, `5` = Fatal, `255` = Auto (default)

#### Form `0x7002` — DF Common Options

_Navigation (children):_
- → `0x7037` **Scrubber**
  - Scrubber
- → `0x7038` **Memory Addressing**
  - Memory Addressing
- → `0x7039` **ACPI**
  - ACPI

_Settings:_

##### `0x47` — **Disable DF to external IP SyncFloodPropagation** (OneOf)
> Disable SyncFlood to UMC & downstream slaves.
- VarStore `0x5000` · offset `0xae` · 8-bit · range `0x0`..`0xff`
- options: `1` = Sync flood disabled, `0` = Sync flood enabled, `255` = Auto (default)

##### `0x48` — **Disable DF sync flood propagation** (OneOf)
> Control DF::PIEConfig[DisSyncFloodProp]
- VarStore `0x5000` · offset `0xaf` · 8-bit · range `0x0`..`0xff`
- options: `1` = Sync flood disabled, `0` = Sync flood enabled, `255` = Auto (default)

##### `0x4a` — **CC6 memory region encryption** (OneOf)
> Control whether or not the CC6 save/restore memory is encrypted
- VarStore `0x5000` · offset `0xb1` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x4b` — **System probe filter** (OneOf)
> Controls whether or not the probe filter is enabled. Has no effect on parts where the probe filter is fuse disabled.
- VarStore `0x5000` · offset `0xb2` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x4c` — **Memory Clear** (OneOf)
> When this feature is disabled, BIOS does not implement MemClear after memory training (only if non-ECC DIMMs are used).
- VarStore `0x5000` · offset `0xb3` · 8-bit · range `0x0`..`0x3`
- options: `0` = Enabled, `1` = Disabled, `3` = Auto (default)

##### `0x4d` — **PSP error injection support** (OneOf)
> 'True' enables error injection.
- VarStore `0x5000` · offset `0xb4` · 8-bit · range `0x0`..`0x1`
- options: `0` = False (default), `1` = True

#### Form `0x7037` — Scrubber

_Settings:_

##### `0x4e` — **DRAM scrub time** (OneOf)
> Provide a value that is the number of hours to scrub memory.
- VarStore `0x5000` · offset `0xb5` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = 1 hour, `4` = 4 hours, `8` = 8 hours, `16` = 16 hours, `24` = 24 hours, `48` = 48 hours, `255` = Auto (default)

##### `0x4f` — **Poison scrubber control** (OneOf)
> Control DF::RedirScrubCtrl[RedirScrubMode[1]]
- VarStore `0x5000` · offset `0xb6` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x50` — **Redirect scrubber control** (OneOf)
> Control DF::RedirScrubCtrl[RedirScrubMode[0]]
- VarStore `0x5000` · offset `0xb7` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x51` — **Redirect scrubber limit** (OneOf)
> Control DF::RedirScrubCtrl[RedirScrubReqLmt]
- VarStore `0x5000` · offset `0xb8` · 8-bit · range `0x0`..`0xff`
- options: `1` = 2, `2` = 4, `3` = 8, `0` = Infinite, `255` = Auto (default)

##### `0x52` — **Periodic Directory Rinse** (OneOf)
> Control Periodic Directory Rinse Mode.
- VarStore `0x5000` · offset `0xb9` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

#### Form `0x7038` — Memory Addressing

_Settings:_

##### `0x53` — **NUMA nodes per socket** (OneOf)
> Specifies the number of desired NUMA nodes per socket.  Zero will attempt to interleave the two sockets together.
- VarStore `0x5000` · offset `0xba` · 8-bit · range `0x0`..`0x7`
- options: `0` = NPS0, `1` = NPS1, `2` = NPS2, `3` = NPS4, `7` = Auto (default)

##### `0x54` — **Memory interleaving** (OneOf)
> Allows for disabling memory interleaving.  Note that NUMA nodes per socket will be honored regardless of this setting.
- VarStore `0x5000` · offset `0xbb` · 8-bit · range `0x0`..`0x7`
- options: `0` = Disabled, `7` = Auto (default)

##### `0x55` — **Memory interleaving size** (OneOf)
> Controls the memory interleaving size. The valid values are AUTO, 256 bytes, 512 bytes, 1 Kbytes or 2Kbytes. This determines the starting address of the interleave (bit 8, 9, 10 or 11).
- VarStore `0x5000` · offset `0xbc` · 8-bit · range `0x0`..`0x7`
- options: `0` = 256 Bytes, `1` = 512 Bytes, `2` = 1 KB, `3` = 2 KB, `7` = Auto (default)

##### `0x56` — **1TB remap** (OneOf)
> Attempt to remap DRAM out of the space just below the 1TB boundary.  The ability to remap depends on DRAM configuration, NPS, and interleaving selection, and may not always be possible.
- VarStore `0x5000` · offset `0xbd` · 8-bit · range `0x0`..`0xff`
- options: `0` = Do not remap, `1` = Attempt to remap, `255` = Auto (default)

##### `0x57` — **DRAM map inversion** (OneOf)
> Inverting the map will cause the highest memory channels to get assigned the lowest addresses in the system.
- VarStore `0x5000` · offset `0xbe` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x58` — **Location of private memory regions** (OneOf)
> Controls whether or not the private memory regions (PSP, SMU and CC6) are at the top of DRAM or distributed. Note that distributed requires memory on all dies. Note that it will always be at the top of DRAM if some dies don't have memory regardless of this option's setting.
- VarStore `0x5000` · offset `0xbf` · 8-bit · range `0x0`..`0xff`
- options: `0` = Distributed, `1` = Consolidated, `255` = Auto (default)

#### Form `0x7039` — ACPI

_Settings:_

##### `0x5a` — **ACPI SLIT Distance Control** (OneOf)
> Determines how the SLIT distances are declared.
- VarStore `0x5000` · offset `0xc1` · 8-bit · range `0x0`..`0xff`
- options: `0` = Manual, `255` = Auto (default)

##### `0x5b` — **ACPI SLIT remote relative distance** (OneOf)
> Set the remote socket distance for 2P systems as near (2.8) or far (3.2).
- VarStore `0x5000` · offset `0xc2` · 8-bit · range `0x0`..`0xff`
- options: `0` = Near, `1` = Far, `255` = Auto (default)
- conditions: SuppressIf(Q0x5a=0x0)

##### `0x5c` — **ACPI SLIT virtual distance** (Numeric)
> Specify the distance between two virtual domains (see L3 Cache as NUMA Domain) in the same physical domain.
- VarStore `0x5000` · offset `0xc3` · 8-bit · range `0xa`..`0xff` · default `11`

##### `0x5d` — **ACPI SLIT same socket distance** (Numeric)
> Specify the distance to other physical domains within the same socket.
- VarStore `0x5000` · offset `0xc4` · 8-bit · range `0xa`..`0xff` · default `12`
- conditions: SuppressIf(Q0x5a=0xff)

##### `0x5e` — **ACPI SLIT remote socket distance** (Numeric)
> Specify the distance to domains on the remote socket.
- VarStore `0x5000` · offset `0xc5` · 8-bit · range `0xa`..`0xff` · default `32`
- conditions: SuppressIf(Q0x5a=0xff)

##### `0x5f` — **ACPI SLIT local SLink distance** (Numeric)
> Specify the distance to an SLink domain on the same socket.
- VarStore `0x5000` · offset `0xc6` · 8-bit · range `0xa`..`0xff` · default `50`
- conditions: SuppressIf(Q0x5a=0xff)

##### `0x60` — **ACPI SLIT remote SLink distance** (Numeric)
> Specify the distance to an SLink domain on the other socket.
- VarStore `0x5000` · offset `0xc7` · 8-bit · range `0xa`..`0xff` · default `60`
- conditions: SuppressIf(Q0x5a=0xff)

##### `0x61` — **ACPI SLIT local inter-SLink distance** (Numeric)
> Specify the distance between two SLink domains on the same socket.
- VarStore `0x5000` · offset `0xc8` · 8-bit · range `0xa`..`0xff` · default `255`
- conditions: SuppressIf(Q0x5a=0xff)

##### `0x62` — **ACPI SLIT remote inter-SLink distance** (Numeric)
> Specify the distance between two SLink domains, each on a different socket.
- VarStore `0x5000` · offset `0xc9` · 8-bit · range `0xa`..`0xff` · default `255`
- conditions: SuppressIf(Q0x5a=0xff)

#### Form `0x703a` — Link

_Settings:_

##### `0x63` — **GMI encryption control** (OneOf)
> Control GMI link encryption
- VarStore `0x5000` · offset `0xca` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x64` — **xGMI encryption control** (OneOf)
> Control xGMI link encryption
- VarStore `0x5000` · offset `0xcb` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x65` — **CAKE CRC perf bounds Control** (OneOf)
> Customize the amount of performance loss that is acceptable to enable CRC protection
- VarStore `0x5000` · offset `0xcc` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x66` — **CAKE CRC perf bounds** (Numeric)
> Specify the amount of performance loss that is acceptable to enable CRC protection.  Units are in 0.00001%, Range: disabled (0) - 10% (1000000).
- VarStore `0x5000` · offset `0xcd` · 32-bit · range `0x0`..`0xf4240` · default `100`

##### `0x67` — **4-link xGMI max speed** (OneOf)
> Max speed for 4-link xGMI
- VarStore `0x5000` · offset `0xd1` · 8-bit · range `0x0`..`0xff`
- options: `0` = 6.4Gbps, `1` = 7.467Gbps, `2` = 8.533Gbps, `3` = 9.6Gbps, `4` = 10.667Gbps, `5` = 11Gbps, `6` = 12Gbps, `7` = 13Gbps, `8` = 14Gbps, `9` = 15Gbps, `10` = 16Gbps, `11` = 17Gbps, `12` = 18Gbps, `13` = 19Gbps, `14` = 20Gbps, `15` = 21Gbps, `16` = 22Gbps, `17` = 23Gbps, `18` = 24Gbps, `19` = 25Gbps, `255` = Auto (default)

##### `0x68` — **3-link xGMI max speed** (OneOf)
> Max speed for 3-link xGMI
- VarStore `0x5000` · offset `0xd2` · 8-bit · range `0x0`..`0xff`
- options: `0` = 6.4Gbps, `1` = 7.467Gbps, `2` = 8.533Gbps, `3` = 9.6Gbps, `4` = 10.667Gbps, `5` = 11Gbps, `6` = 12Gbps, `7` = 13Gbps, `8` = 14Gbps, `9` = 15Gbps, `10` = 16Gbps, `11` = 17Gbps, `12` = 18Gbps, `13` = 19Gbps, `14` = 20Gbps, `15` = 21Gbps, `16` = 22Gbps, `17` = 23Gbps, `18` = 24Gbps, `19` = 25Gbps, `255` = Auto (default)

##### `0x69` — **xGMI TXEQ Mode** (OneOf)
> Select XGMI TXEQ/RX vetting Mode
- VarStore `0x5000` · offset `0xd3` · 8-bit · range `0x0`..`0xf`
- options: `0` = TXEQ_Disabled, `1` = TXEQ_Lane, `2` = TXEQ_Link, `3` = TXEQ_RX_Vet, `15` = Auto (default)

#### Form `0x7003` — UMC Common Options

_Navigation (children):_
- → `0x703b` **DDR4 Common Options**
  - DDR4 Common Options
- → `0x703c` **DRAM Memory Mapping**
  - DRAM Memory Mapping
- → `0x703e` **Memory MBIST**
  - Memory MBIST

#### Form `0x703b` — DDR4 Common Options

_Navigation (children):_
- → `0x703f` **DRAM Timing Configuration**
  - DRAM Timing Configuration
- → `0x7040` **DRAM Controller Configuration**
  - DRAM Controller Configuration
- → `0x7041` **CAD Bus Configuration**
  - CAD Bus Configuration
- → `0x7042` **Data Bus Configuration**
  - Data Bus Configuration
- → `0x7043` **Common RAS**
  - Common RAS
- → `0x7044` **Security**
  - Security

#### Form `0x703f` — DRAM Timing Configuration

_Navigation (children):_
- → `0x7045` **Decline**
  - Decline
- → `0x7046` **Accept**
  - Accept

#### Form `0x7045` — Decline

#### Form `0x7046` — Accept

_Settings:_

##### `0x75` — **Overclock** (OneOf)
> Memory Overclock Settings
- VarStore `0x5000` · offset `0xd6` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Enabled

##### `0x76` — **Memory Clock Speed** (OneOf)
> Specifies the memory clock frequency.
- VarStore `0x5000` · offset `0xd7` · 8-bit · range `0x14`..`0xff`
- options: `255` = Auto (default), `20` = 667MHz, `24` = 800MHz, `28` = 933MHz, `32` = 1067MHz, `36` = 1200MHz, `40` = 1333MHz, `44` = 1467MHz, `48` = 1600MHz
- conditions: SuppressIf(Q0x75=0xff)

##### `0x77` — **Tcl** (OneOf)
> Specifies the CAS latency.
- VarStore `0x5000` · offset `0xd8` · 8-bit · range `0x8`..`0xff`
- options: `255` = Auto (default), `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk, `28` = 1Ch Clk, `29` = 1Dh Clk, `30` = 1Eh Clk, `31` = 1Fh Clk, `32` = 20h Clk, `33` = 21h Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x78` — **Trcdrd** (OneOf)
> Specifies the RAS# Active to CAS# Read Delay Time.
- VarStore `0x5000` · offset `0xd9` · 8-bit · range `0x8`..`0xff`
- options: `255` = Auto (default), `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x79` — **Trcdwr** (OneOf)
> Specifies the RAS# Active to CAS# Write Delay Time.
- VarStore `0x5000` · offset `0xda` · 8-bit · range `0x8`..`0xff`
- options: `255` = Auto (default), `8` = 8 Clk, `9` = 9 Clk, `10` = 0A Clk, `11` = 0B Clk, `12` = 0C Clk, `13` = 0D Clk, `14` = 0E Clk, `15` = 0F Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x7a` — **Trp** (OneOf)
> Specifies Row Precharge Delay Time.
- VarStore `0x5000` · offset `0xdb` · 8-bit · range `0x8`..`0xff`
- options: `255` = Auto (default), `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x7b` — **Tras** (OneOf)
> Specifies the Active to Precharge Delay Time.
- VarStore `0x5000` · offset `0xdc` · 8-bit · range `0x15`..`0xff`
- options: `255` = Auto (default), `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk, `28` = 1Ch Clk, `29` = 1Dh Clk, `30` = 1Eh Clk, `31` = 1Fh Clk, `32` = 20h Clk, `33` = 21h Clk, `34` = 22h Clk, `35` = 23h Clk, `36` = 24h Clk, `37` = 25h Clk, `38` = 26h Clk, `39` = 27h Clk, `40` = 28h Clk, `41` = 29h Clk, `42` = 2Ah Clk, `43` = 2Bh Clk, `44` = 2Ch Clk, `45` = 2Dh Clk, `46` = 2Eh Clk, `47` = 2Fh Clk, `48` = 30h Clk, `49` = 31h Clk, `50` = 32h Clk, `51` = 33h Clk, `52` = 34h Clk, `53` = 35h Clk, `54` = 36h Clk, `55` = 37h Clk, `56` = 38h Clk, `57` = 39h Clk, `58` = 3Ah Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x7c` — **Trc Ctrl** (OneOf)
> Specify Trc
- VarStore `0x5000` · offset `0xdd` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual
- conditions: SuppressIf(Q0x75=0xff)

##### `0x7d` — **Trc** (Numeric)
> Specifies Active to Active/Refresh Delay Time. Valid values 87h-1Dh.
- VarStore `0x5000` · offset `0xde` · 8-bit · range `0x1d`..`0x87` · default `57`

##### `0x7e` — **TrrdS** (OneOf)
> Specifies the Activate to Activate Delay Time, different bank group (tRRD_S)
- VarStore `0x5000` · offset `0xdf` · 8-bit · range `0x4`..`0xff`
- options: `255` = Auto (default), `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x7f` — **TrrdL** (OneOf)
> Specifies the Activate to Activate Delay Time, same bank group (tRRD_L)
- VarStore `0x5000` · offset `0xe0` · 8-bit · range `0x4`..`0xff`
- options: `255` = Auto (default), `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x80` — **Tfaw Ctrl** (OneOf)
> Specify Tfaw
- VarStore `0x5000` · offset `0xe1` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual
- conditions: SuppressIf(Q0x75=0xff)

##### `0x81` — **Tfaw** (Numeric)
> Specifies the Four Activate Window Time. Valid values 36h-6h.
- VarStore `0x5000` · offset `0xe2` · 8-bit · range `0x6`..`0x36` · default `26`

##### `0x82` — **TwtrS** (OneOf)
> Specifies the Minimum Write to Read Time, different bank group
- VarStore `0x5000` · offset `0xe3` · 8-bit · range `0x2`..`0xff`
- options: `255` = Auto (default), `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x83` — **TwtrL** (OneOf)
> Specifies the Minimum Write to Read Time, same bank group
- VarStore `0x5000` · offset `0xe4` · 8-bit · range `0x2`..`0xff`
- options: `255` = Auto (default), `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x84` — **Twr Ctrl** (OneOf)
> Specify Twr
- VarStore `0x5000` · offset `0xe5` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual
- conditions: SuppressIf(Q0x75=0xff)

##### `0x85` — **Twr** (Numeric)
> Specifies the Minimum Write Recovery Time. Valid value 51h-Ah
- VarStore `0x5000` · offset `0xe6` · 8-bit · range `0xa`..`0x51` · default `18`

##### `0x86` — **Trcpage Ctrl** (OneOf)
> Specify Trcpage
- VarStore `0x5000` · offset `0xe7` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual
- conditions: SuppressIf(Q0x75=0xff)

##### `0x87` — **Trcpage** (Numeric)
> SDRAM Optional Features (tMAW, MAC). Valid value 3FFh - 0h
- VarStore `0x5000` · offset `0xe8` · 16-bit · range `0x0`..`0x3ff` · default `0`

##### `0x88` — **TrdrdScL Ctrl** (OneOf)
> Specify TrdrdScL
- VarStore `0x5000` · offset `0xea` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual
- conditions: SuppressIf(Q0x75=0xff)

##### `0x89` — **TrdrdScL** (Numeric)
> Specifies the CAS to CAS Delay Time, same bank group. Valid values Fh-1h
- VarStore `0x5000` · offset `0xeb` · 8-bit · range `0x1`..`0xf` · default `3`

##### `0x8a` — **TwrwrScL Ctrl** (OneOf)
> Specify TwrwrScL
- VarStore `0x5000` · offset `0xec` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual
- conditions: SuppressIf(Q0x75=0xff)

##### `0x8b` — **TwrwrScL** (Numeric)
> Specifies the CAS to CAS Delay Time, same bank group. Valid values 3Fh-1h
- VarStore `0x5000` · offset `0xed` · 8-bit · range `0x1`..`0x3f` · default `3`

##### `0x8c` — **Trfc Ctrl** (OneOf)
> Specify Trfc
- VarStore `0x5000` · offset `0xee` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual
- conditions: SuppressIf(Q0x75=0xff)

##### `0x8d` — **Trfc** (Numeric)
> Specifies the Refresh Recovery Delay Time (tRFC1). Valid values 3DEh-3Ch
- VarStore `0x5000` · offset `0xef` · 16-bit · range `0x3c`..`0x3de` · default `312`

##### `0x8e` — **Trfc2 Ctrl** (OneOf)
> Specify Trfc2
- VarStore `0x5000` · offset `0xf1` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual
- conditions: SuppressIf(Q0x75=0xff)

##### `0x8f` — **Trfc2** (Numeric)
> Specifies the Refresh Recovery Delay Time (tRFC2).  Valid values 3DEh-3Ch
- VarStore `0x5000` · offset `0xf2` · 16-bit · range `0x3c`..`0x3de` · default `192`

##### `0x90` — **Trfc4 Ctrl** (OneOf)
> Specify Trfc4
- VarStore `0x5000` · offset `0xf4` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual
- conditions: SuppressIf(Q0x75=0xff)

##### `0x91` — **Trfc4** (Numeric)
> Specifies the Refresh Recovery Delay Time (tRFC4). Valid values 3DEh-3Ch
- VarStore `0x5000` · offset `0xf5` · 16-bit · range `0x3c`..`0x3de` · default `132`

##### `0x92` — **Tcwl** (OneOf)
> Specifies the CAS Write Latency
- VarStore `0x5000` · offset `0xf7` · 8-bit · range `0x9`..`0xff`
- options: `255` = Auto (default), `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `14` = 0Eh Clk, `16` = 10h Clk, `18` = 12h Clk, `20` = 14h Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x93` — **Trtp** (OneOf)
> Specifies the Read CAS# to Precharge Delay Time.
- VarStore `0x5000` · offset `0xf8` · 8-bit · range `0x5`..`0xff`
- options: `255` = Auto (default), `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x94` — **Tcke** (OneOf)
> Specifies the CKE minimum high and low pulse width in memory clock cycles.
- VarStore `0x5000` · offset `0xf9` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk, `28` = 1Ch Clk, `29` = 1Dh Clk, `30` = 1Eh Clk, `31` = 1Fh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x95` — **Trdwr** (OneOf)
> Specifies the Read to Write turnaround timing.
- VarStore `0x5000` · offset `0xfa` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk, `28` = 1Ch Clk, `29` = 1Dh Clk, `30` = 1Eh Clk, `31` = 1Fh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x96` — **Twrrd** (OneOf)
> Specifies the Write to Read turnaround timing.
- VarStore `0x5000` · offset `0xfb` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x97` — **TwrwrSc** (OneOf)
> Specifies the Write to Write turnaround timing in the same chipselect.
- VarStore `0x5000` · offset `0xfc` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x98` — **TwrwrSd** (OneOf)
> Specifies the Write to Write turnaround timing in the same DIMM.
- VarStore `0x5000` · offset `0xfd` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x99` — **TwrwrDd** (OneOf)
> Specifies the Write to Write turnaround timing in a different DIMM.
- VarStore `0x5000` · offset `0xfe` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x9a` — **TrdrdSc** (OneOf)
> Specifies the Read to Read turnaround timing in the same chipselect.
- VarStore `0x5000` · offset `0xff` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x9b` — **TrdrdSd** (OneOf)
> Specifies the Read to Read turnaround timing in the same DIMM.
- VarStore `0x5000` · offset `0x100` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x9c` — **TrdrdDd** (OneOf)
> Specifies the Read to Read turnaround timing in a different DIMM.
- VarStore `0x5000` · offset `0x101` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk
- conditions: SuppressIf(Q0x75=0xff)

##### `0x9d` — **ProcODT** (OneOf)
> Specifies the Processor ODT
- VarStore `0x5000` · offset `0x102` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = High Impedance, `1` = 480 ohm, `2` = 240 ohm, `3` = 160 ohm, `8` = 120 ohm, `9` = 96 ohm, `10` = 80 ohm, `11` = 68.6 ohm, `24` = 60 ohm, `25` = 53.3 ohm, `26` = 48 ohm, `27` = 43.6 ohm, `56` = 40 ohm, `57` = 36.9 ohm, `58` = 34.3 ohm, `59` = 32 ohm, `62` = 30 ohm, `63` = 28.2 ohm
- conditions: SuppressIf(Q0x75=0xff)

#### Form `0x7040` — DRAM Controller Configuration

_Navigation (children):_
- → `0x7047` **DRAM Power Options**
  - DRAM Power Options

_Settings:_

##### `0x9f` — **Cmd2T** (OneOf)
> Select between 1T and 2T mode on ADDR/CMD
- VarStore `0x5000` · offset `0x103` · 8-bit · range `0x0`..`0xff`
- options: `0` = 1T, `1` = 2T, `255` = Auto (default)

##### `0xa0` — **Gear Down Mode** (OneOf)
> Enable or Disable Gear Down Mode
- VarStore `0x5000` · offset `0x104` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

#### Form `0x7047` — DRAM Power Options

_Settings:_

##### `0xa1` — **Power Down Enable** (OneOf)
> Enable or disable DDR power down mode
- VarStore `0x5000` · offset `0x105` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0xa5` — **DRAM Refresh Rate** (OneOf)
> DRAM refresh rate
- VarStore `0x5000` · offset `0x109` · 8-bit · range `0x0`..`0x1`
- options: `0` = 7.8 usec (default), `1` = 3.9 usec

#### Form `0x7041` — CAD Bus Configuration

_Settings:_

##### `0xa7` — **CAD Bus Timing User Controls** (OneOf)
> Setup time on CAD bus signals to Auto or Manual
- VarStore `0x5000` · offset `0x10b` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Manual

##### `0xa8` — **AddrCmdSetup** (Numeric)
> Setup time on CAD bus signals. Valid values 3Fh-0h.
- VarStore `0x5000` · offset `0x10c` · 8-bit · range `0x0`..`0x3f` · default `0`
- conditions: SuppressIf(Q0xa7=0xff)

##### `0xa9` — **CsOdtSetup** (Numeric)
> Setup time on CAD bus signals. Valid values 3Fh-0h.
- VarStore `0x5000` · offset `0x10d` · 8-bit · range `0x0`..`0x3f` · default `0`
- conditions: SuppressIf(Q0xa7=0xff)

##### `0xaa` — **CkeSetup** (Numeric)
> Setup time on CAD bus signals. Valid values 3Fh-0h.
- VarStore `0x5000` · offset `0x10e` · 8-bit · range `0x0`..`0x3f` · default `0`
- conditions: SuppressIf(Q0xa7=0xff)

##### `0xab` — **CAD Bus Drive Strength User Controls** (OneOf)
> Drive Strength on CAD bus signals to Auto or Manual
- VarStore `0x5000` · offset `0x10f` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Manual

##### `0xac` — **ClkDrvStren** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x110` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 120.0 Ohm, `1` = 60.0 Ohm, `3` = 40.0 Ohm, `7` = 30.0 Ohm, `15` = 24.0 Ohm, `31` = 20.0 Ohm
- conditions: SuppressIf(Q0xab=0xff)

##### `0xad` — **AddrCmdDrvStren** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x111` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 120.0 Ohm, `1` = 60.0 Ohm, `3` = 40.0 Ohm, `7` = 30.0 Ohm, `15` = 24.0 Ohm, `31` = 20.0 Ohm
- conditions: SuppressIf(Q0xab=0xff)

##### `0xae` — **CsOdtDrvStren** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x112` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 120.0 Ohm, `1` = 60.0 Ohm, `3` = 40.0 Ohm, `7` = 30.0 Ohm, `15` = 24.0 Ohm, `31` = 20.0 Ohm
- conditions: SuppressIf(Q0xab=0xff)

##### `0xaf` — **CkeDrvStren** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x113` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 120.0 Ohm, `1` = 60.0 Ohm, `3` = 40.0 Ohm, `7` = 30.0 Ohm, `15` = 24.0 Ohm, `31` = 20.0 Ohm
- conditions: SuppressIf(Q0xab=0xff)

#### Form `0x7042` — Data Bus Configuration

_Settings:_

##### `0xb0` — **Data Bus Configuration User Controls** (OneOf)
> Specify the mode for drive strength to Auto or Manual
- VarStore `0x5000` · offset `0x114` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Manual

##### `0xb1` — **RttNom** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x115` · 8-bit · range `0x0`..`0xff`
- options: `0` = Rtt_Nom Disable, `1` = RZQ/4, `2` = RZQ/2, `3` = RZQ/6, `4` = RZQ/1, `5` = RZQ/5, `6` = RZQ/3, `7` = RZQ/7, `255` = Auto (default)
- conditions: SuppressIf(Q0xb0=0xff)

##### `0xb2` — **RttWr** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x116` · 8-bit · range `0x0`..`0xff`
- options: `0` = Dynamic ODT Off, `1` = RZQ/2, `2` = RZQ/1, `3` = Hi-Z, `4` = RZQ/3, `255` = Auto (default)
- conditions: SuppressIf(Q0xb0=0xff)

##### `0xb3` — **RttPark** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x117` · 8-bit · range `0x0`..`0xff`
- options: `0` = Rtt_PARK Disable, `1` = RZQ/4, `2` = RZQ/2, `3` = RZQ/6, `4` = RZQ/1, `5` = RZQ/5, `6` = RZQ/3, `7` = RZQ/7, `255` = Auto (default)
- conditions: SuppressIf(Q0xb0=0xff)

#### Form `0x7043` — Common RAS

_Navigation (children):_
- → `0x7048` **ECC Configuration**
  - ECC Configuration

_Settings:_

##### `0xb4` — **Data Poisoning** (OneOf)
> Enable/disable data poisoning: UMC_CH::EccCtrl[UcFatalEn] UMC_CH::EccCtrl[WrEccEn] Should be enabled/disabled together.
- VarStore `0x5000` · offset `0x118` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0xb6` — **RCD Parity** (OneOf)
> Enable or Disable RCD parity
- VarStore `0x5000` · offset `0x11a` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = Disabled, `1` = Enabled

##### `0xb7` — **DRAM Address Command Parity Retry** (OneOf)
> UMC_CH::RecCtrl[RecEn][0] and UMC_CH::RecCtrl[MaxParRply]
- VarStore `0x5000` · offset `0x11b` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = Disabled, `1` = Enabled

##### `0xb8` — **Max Parity Error Replay** (Numeric)
> Value in hex, 1, 2 or 3 is invalid
- VarStore `0x5000` · offset `0x11c` · 8-bit · range `0x0`..`0x3f` · default `8`

##### `0xb9` — **Write CRC Enable** (OneOf)
> Enable write CRC generation. UMC::CH::BeqCtrl1[WrCrcEn]
- VarStore `0x5000` · offset `0x11d` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = Disabled, `1` = Enabled

##### `0xba` — **DRAM Write CRC Enable and Retry Limit** (OneOf)
> UMC_CH::RecCtrl[RecEn][1] and UMC_CH::RecCtrl[MaxCrcRply]
- VarStore `0x5000` · offset `0x11e` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = Disabled, `1` = Enabled

##### `0xbb` — **Max Write CRC Error Replay** (Numeric)
> Value in hex, 1, 2 or 3 is invalid
- VarStore `0x5000` · offset `0x11f` · 8-bit · range `0x0`..`0x3f` · default `8`

##### `0xbc` — **Disable Memory Error Injection** (OneOf)
> True: UMC::CH::MiscCfg[DisErrInj]=1
- VarStore `0x5000` · offset `0x120` · 8-bit · range `0x0`..`0x1`
- options: `0` = False, `1` = True (default)

#### Form `0x7048` — ECC Configuration

_Settings:_

##### `0xbe` — **DRAM ECC Symbol Size** (OneOf)
> DRAM ECC Symbol Size (x4/x8/x16) - UMC_CH::EccCtrl[EccSymbolSize16, EccSymbolSize]
- VarStore `0x5000` · offset `0x121` · 8-bit · range `0x0`..`0xff`
- options: `0` = x4, `1` = x8, `2` = x16, `255` = Auto (default)

##### `0xbf` — **DRAM ECC Enable** (OneOf)
> Use this option to enable / disable DRAM ECC. Auto will set ECC to enable.
- VarStore `0x5000` · offset `0x122` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0xc0` — **DRAM UECC Retry** (OneOf)
> Use this option to enable / disable DRAM UECC Retry.
- VarStore `0x5000` · offset `0x123` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = Enabled, `0` = Disabled

#### Form `0x7044` — Security

_Settings:_

##### `0x7049` — **TSME** (OneOf)
> Transparent SME: AddrTweakEn = 1; ForceEncrEn =0; DataEncrEn = 1
- VarStore `0x5000` · offset `0x124` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0x704a` — **Data Scramble** (OneOf)
> Data scrambling: DataScrambleEn
- VarStore `0x5000` · offset `0x125` · 8-bit · range `0x0`..`0xff`
- options: `1` = Enabled, `0` = Disabled, `255` = Auto (default)

#### Form `0x703c` — DRAM Memory Mapping

_Settings:_

##### `0xc1` — **Chipselect Interleaving** (OneOf)
> Interleave memory blocks across the DRAM chip selects for node 0.
- VarStore `0x5000` · offset `0x126` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `255` = Auto (default)

##### `0xc4` — **Address Hash Bank** (OneOf)
> Enable or disable bank address hashing
- VarStore `0x5000` · offset `0x129` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0xc5` — **Address Hash CS** (OneOf)
> Enable or disable CS address hashing
- VarStore `0x5000` · offset `0x12a` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = Enabled, `0` = Disabled

##### `0xc6` — **Address Hash Rm** (OneOf)
> Enable or disable RM address hashing
- VarStore `0x5000` · offset `0x12b` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = Enabled, `0` = Disabled

##### `0xc7` — **SPD Read Optimization** (OneOf)
> Enable or disable SPD Read Optimization, Enabled - SPD reads are skipped for Reserved fields and most of upper 256 Bytes, Disabled - read all 512 SPD Bytes
- VarStore `0x5000` · offset `0x12c` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = Enabled, `0` = Disabled

#### Form `0x703d` — NVDIMM

_Settings:_

##### `0xc8` — **Disable NVDIMM-N Feature** (OneOf)
> Disable NVDIMM-N feature for memory margin tool
- VarStore `0x5000` · offset `0x12d` · 8-bit · range `0x0`..`0x1`
- options: `0` = No (default), `1` = Yes

#### Form `0x703e` — Memory MBIST

_Navigation (children):_
- → `0x704b` **Data Eye**
  - Data Eye

_Settings:_

##### `0xc9` — **MBIST Enable** (OneOf)
> Enable or disable Memory MBIST
- VarStore `0x5000` · offset `0x12e` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default), `1` = Enabled

##### `0xca` — **MBIST Test Mode** (OneOf)
> Select MBIST Test Mode -Interface Mode (Tests Single and Multiple CS transactions and Basic Connectivity) or Data Eye Mode (Measures Voltage vs. Timing)
- VarStore `0x5000` · offset `0x12f` · 8-bit · range `0x0`..`0xff`
- options: `0` = Interface Mode, `1` = Data Eye Mode, `2` = Both, `255` = Auto (default)
- conditions: GrayOutIf(Q0xc9=0x0)

##### `0xcb` — **MBIST Aggressors** (OneOf)
> Enable or disable MBIST Aggressor test
- VarStore `0x5000` · offset `0x130` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)
- conditions: GrayOutIf(Q0xc9=0x0)

##### `0xcc` — **MBIST Per Bit Slave Die Reporting** (OneOf)
> Reports 2D Data Eye Results in ABL Log for each DQ, Chipselect, and Channel
- VarStore `0x5000` · offset `0x131` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)
- conditions: GrayOutIf(Q0xc9=0x0)

##### `0xcf` — **Mem BIST Test Select** (OneOf)
> Select the vendor specific tests to use with BIOS memory healing BIST
- VarStore `0x5000` · offset `0x133` · 8-bit · range `0x0`..`0x2`
- options: `0` = Vendor Tests Enabled (default), `1` = Vendor Tests Disabled, `2` = All Tests - All Vendors

##### `0xd0` — **Mem BIST Post Package Repair Type** (OneOf)
> For DRAM errors found in the BIOS memory BIST select the repair type, soft, hard or test only and do not attempt to repair.
- VarStore `0x5000` · offset `0x134` · 8-bit · range `0x0`..`0x2`
- options: `0` = Soft Repair (default), `1` = Hard Repair, `2` = No Repairs - Test only

#### Form `0x704b` — Data Eye

_Settings:_

##### `0xd1` — **Pattern Select** (OneOf)
> Select pattern
- VarStore `0x5000` · offset `0x135` · 8-bit · range `0x0`..`0x2`
- options: `0` = PRBS (default), `1` = SSO, `2` = Both

##### `0xd2` — **Pattern Length** (Numeric)
> This token helps to determine the pattern length. The possible options are N=3...12
- VarStore `0x5000` · offset `0x136` · 8-bit · range `0x3`..`0xc` · default `3`

##### `0xd3` — **Aggressor Channel** (OneOf)
> This helps read the aggressors channels. If it is enabled, you can read from one or more than one aggressor channel. The default is set to disabled.
- VarStore `0x5000` · offset `0x137` · 8-bit · range `0x0`..`0x7`
- options: `0` = Disabled, `1` = 1 Aggressor Channel (default), `3` = 3 Aggressor Channels, `7` = 7 Aggressor Channels

##### `0xd5` — **Aggressor Static Lane Select Upper 32 bits** (Numeric)
> Static Lane Select for Upper 32 bits. The bit mask represents the bits to be read
- VarStore `0x5000` · offset `0x139` · 32-bit · range `0x0`..`0xffffffff` · default `0`
- conditions: GrayOutIf(Q0xd4=0x0)

##### `0xd6` — **Aggressor Static Lane Select Lower 32 Bits** (Numeric)
> Static Lane Select for Lower 32 bits. The bit mask represents the bits to be read
- VarStore `0x5000` · offset `0x13d` · 32-bit · range `0x0`..`0xffffffff` · default `0`
- conditions: GrayOutIf(Q0xd4=0x0)

##### `0xd7` — **Aggressor Static Lane Select ECC** (Numeric)
> Static Lane Select for ECC Lanes. The bit mask represents the bits to be read
- VarStore `0x5000` · offset `0x141` · 8-bit · range `0x0`..`0xa` · default `0`
- conditions: GrayOutIf(Q0xd4=0x0)

##### `0xd8` — **Aggressor Static Lane Value** (Numeric)
> TBD
- VarStore `0x5000` · offset `0x142` · 8-bit · range `0x0`..`0xa` · default `0`
- conditions: GrayOutIf(Q0xd4=0x0)

##### `0xd9` — **Target Static Lane Control** (OneOf)
> Enable or disable target static lane
- VarStore `0x5000` · offset `0x143` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default), `1` = Enabled

##### `0xda` — **Target Static Lane Select Upper 32 bit** (Numeric)
> Static Lane Select for Upper 32 bit. The bit mask represents the bits to be read
- VarStore `0x5000` · offset `0x144` · 32-bit · range `0x0`..`0xffffffff` · default `0`
- conditions: GrayOutIf(Q0xd9=0x0)

##### `0xdb` — **Target Static Lane Select Lower 32 Bits** (Numeric)
> Static Lane Select for Lower 32 bit. The bit mask represents the bits to be read
- VarStore `0x5000` · offset `0x148` · 32-bit · range `0x0`..`0xa` · default `0`
- conditions: GrayOutIf(Q0xd9=0x0)

##### `0xdc` — **Target Static Lane Select ECC** (Numeric)
> TBD
- VarStore `0x5000` · offset `0x14c` · 8-bit · range `0x0`..`0xa` · default `0`
- conditions: GrayOutIf(Q0xd9=0x0)

##### `0xdd` — **Target Static Lane Value** (Numeric)
> Static Lane value. Range 0-0xA
- VarStore `0x5000` · offset `0x14d` · 8-bit · range `0x0`..`0xa` · default `0`
- conditions: GrayOutIf(Q0xd9=0x0)

##### `0xde` — **Data Eye Type** (OneOf)
> This options determines which results are expected to be captured for Data Eye. Supported options are 1D Voltage Sweep, 1D Timing Sweep, 2D Full Data Eye and Worst Case Margin only.
- VarStore `0x5000` · offset `0x14e` · 8-bit · range `0x0`..`0x3`
- options: `0` = 1D Voltage Sweep, `1` = 1D Timing Sweep, `2` = 2D Full Data Eye, `3` = Worst Case Margin Only (default)

##### `0xdf` — **Worst Case Margin Granularity** (OneOf)
> Select per Chip or per Nibble
- VarStore `0x5000` · offset `0x14f` · 8-bit · range `0x0`..`0x1`
- options: `0` = Per Chip Select (default), `1` = Per Nibble

##### `0xe0` — **Read Voltage Sweep Step Size** (OneOf)
> This option determines the step size for Read Data Eye voltage sweep, Supported options are 1,2 and 4
- VarStore `0x5000` · offset `0x150` · 8-bit · range `0x0`..`0x4`
- options: `0` = 1, `2` = 2 (default), `4` = 4

##### `0xe1` — **Read Timing Sweep Step Size** (OneOf)
> This options supports step size for Read Data Eye. Supported options are 1, 2 and 4
- VarStore `0x5000` · offset `0x151` · 8-bit · range `0x1`..`0x4`
- options: `1` = 1 (default), `2` = 2, `4` = 4

##### `0xe2` — **Write Voltage Sweep Step Size** (OneOf)
> This option determines the step size for write Data Eye voltage sweep, Supported options are 1,2 and 4
- VarStore `0x5000` · offset `0x152` · 8-bit · range `0x1`..`0x4`
- options: `1` = 1, `2` = 2 (default), `4` = 4

##### `0xe3` — **Write Timing Sweep Step Size** (OneOf)
> This options supports step size for write Data Eye. Supported options are 1, 2 and 4
- VarStore `0x5000` · offset `0x153` · 8-bit · range `0x1`..`0x4`
- options: `1` = 1 (default), `2` = 2, `4` = 4

#### Form `0x7004` — NBIO Common Options

_Navigation (children):_
- → `0x704c` **XFR Enhancement**
  - XFR Enhancement
- → `0x704d` **SMU Common Options**
  - SMU Common Options
- → `0x704e` **NBIO RAS Common Options**
  - NBIO RAS Common Options

_Settings:_

##### `0xe4` — **IOMMU** (OneOf)
> Enable/Disable IOMMU
- VarStore `0x5000` · offset `0x154` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled (default), `1` = Enabled, `15` = Auto

##### `0xe7` — **ACS Enable** (OneOf)
> AER must be enabled for ACS enable to work
- VarStore `0x5000` · offset `0x156` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)
- conditions: SuppressIf(Q0xed=0x0)

##### `0xe8` — **PCIe ARI Support** (OneOf)
> Enables Alternative Routing-ID Interpretation
- VarStore `0x5000` · offset `0x157` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled (default), `1` = Enabled, `15` = Auto

##### `0xea` — **HD Audio Enable** (OneOf)
> Control HD audio enable or disable
- VarStore `0x5000` · offset `0x159` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0xed` — **Enable AER Cap** (OneOf)
> Enables Advanced Error Reporting Capability
- VarStore `0x5000` · offset `0x15a` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0xee` — **Enable Rcv Err and Bad TLP Mask** (OneOf)
> Enables Masking of Receiver Error and Bad TLP at Gen4 x2
- VarStore `0x5000` · offset `0x15b` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0xef` — **Early Link Speed** (OneOf)
> Set Early Link Speed
- VarStore `0x5000` · offset `0x15c` · 8-bit · range `0x0`..`0x2`
- options: `0` = Auto (default), `1` = Gen1, `2` = Gen2

##### `0xf0` — **Hot Plug Handling mode** (OneOf)
> Control the Hot Plug Handling mode
- VarStore `0x5000` · offset `0x15d` · 8-bit · range `0x0`..`0xf`
- options: `0` = A0 Mode, `1` = OS First, `3` = Firmware First, `15` = Auto (default)

##### `0xf1` — **Presence Detect Select mode** (OneOf)
> Control the Presence Detect Select mode
- VarStore `0x5000` · offset `0x15e` · 8-bit · range `0x0`..`0xf`
- options: `0` = OR, `1` = AND, `15` = Auto (default)

##### `0xf4` — **Enhanced Preferred IO Mode** (OneOf)
> Enhanced Preferred IO Mode
- VarStore `0x5000` · offset `0x162` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xf5` — **Loopback Mode** (OneOf)
> Enable/Disable Pcie Loopback Mode
- VarStore `0x5000` · offset `0x163` · 8-bit · range `0x0`..`0xf`
- options: `15` = Auto (default), `0` = Disabled, `1` = Enabled

##### `0xf7` — **CAC Weight Adjustment** (OneOf)
> EDC Mode Select
- VarStore `0x5000` · offset `0x165` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xf8` — **EDC Control Throttle** (OneOf)
> EDC Control Throttle
- VarStore `0x5000` · offset `0x166` · 8-bit · range `0x0`..`0xf`
- options: `15` = Auto (default), `1` = Enabled, `0` = Disabled

##### `0xf9` — **SRIS** (OneOf)
> SRIS
- VarStore `0x5000` · offset `0x167` · 8-bit · range `0x0`..`0xf`
- options: `15` = Auto (default), `0` = Disabled, `1` = Enabled

##### `0xfa` — **Compliance Loopback** (OneOf)
> Compliance Loopback Test
- VarStore `0x5000` · offset `0x168` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xfb` — **Multi Upstream Auto Speed Change** (OneOf)
> Defines the setting of this feature for all PCIe devices.  'Auto' uses the DXIO default setting of 0 for Gen1 and 1 for Gen2/3
- VarStore `0x5000` · offset `0x169` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x704c` — XFR Enhancement

_Navigation (children):_
- → `0x704f` **Declined**
  - Declined
- → `0x7050` **Accepted**
  - Accepted

_Settings:_

##### `0xff` — **FCLK Frequency** (OneOf)
> Specifies the FCLK frequency.
- VarStore `0x5000` · offset `0x16d` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 667MHz, `1` = 800MHz, `2` = 933MHz, `3` = 1067MHz, `4` = 1200MHz, `5` = 1333MHz, `6` = 1367MHz, `7` = 1400MHz, `8` = 1433MHz, `9` = 1467MHz, `10` = 1500MHz, `11` = 1533MHz, `12` = 1567MHz, `13` = 1600MHz, `14` = 1633MHz, `15` = 1667MHz, `16` = 1700MHz, `17` = 1733MHz, `18` = 1767MHz, `19` = 1800MHz, `20` = 1833MHz, `21` = 1867MHz, `22` = 1900MHz, `23` = 1933MHz, `24` = 1967MHz, `25` = 2000MHz, `26` = 2033MHz, `27` = 2067MHz, `28` = 2100MHz, `29` = 2133MHz, `30` = 2167MHz, `31` = 2200MHz, `32` = 2233MHz, `33` = 2267MHz, `34` = 2300MHz, `35` = 2333MHz, `36` = 2367MHz, `37` = 2400MHz, `38` = 2433MHz, `39` = 2467MHz, `40` = 2500MHz

##### `0x100` — **MEMCLK Frequency** (OneOf)
> Specifies the MEMCLK frequency.
- VarStore `0x5000` · offset `0x16e` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 667MHz, `1` = 800MHz, `2` = 933MHz, `3` = 1067MHz, `4` = 1200MHz, `5` = 1333MHz, `6` = 1367MHz, `7` = 1400MHz, `8` = 1433MHz, `9` = 1467MHz, `10` = 1500MHz, `11` = 1533MHz, `12` = 1567MHz, `13` = 1600MHz, `14` = 1633MHz, `15` = 1667MHz, `16` = 1700MHz, `17` = 1733MHz, `18` = 1767MHz, `19` = 1800MHz, `20` = 1833MHz, `21` = 1867MHz, `22` = 1900MHz, `23` = 1933MHz, `24` = 1967MHz, `25` = 2000MHz, `26` = 2033MHz, `27` = 2067MHz, `28` = 2100MHz, `29` = 2133MHz, `30` = 2167MHz, `31` = 2200MHz, `32` = 2233MHz, `33` = 2267MHz, `34` = 2300MHz, `35` = 2333MHz, `36` = 2367MHz, `37` = 2400MHz, `38` = 2433MHz, `39` = 2467MHz, `40` = 2500MHz

#### Form `0x704f` — Declined

#### Form `0x7050` — Accepted

_Settings:_

##### `0x104` — **PPT Limit** (Numeric)
> PPT Limit [W], Board Socket Power capability, adjustable up to motherboard programed PPT limit.
- VarStore `0x5000` · offset `0x172` · 32-bit · range `0x0`..`0xffff` · default `0`

##### `0x105` — **TDC Limit** (Numeric)
> TDC Limit [A], Board thermally constrained current delivery capability, adjustable up to motherboard programed board TDC limit.
- VarStore `0x5000` · offset `0x176` · 32-bit · range `0x0`..`0xffff` · default `0`

##### `0x106` — **EDC Limit** (Numeric)
> EDC Limit [A], Board electrically constrained current delivery capability, adjustable up to motherboard programed board EDC limit.
- VarStore `0x5000` · offset `0x17a` · 32-bit · range `0x0`..`0xffff` · default `0`

##### `0x108` — **customized Precision Boost Overdrive Scalar** (OneOf)
> Precision Boost Overdrive increases the maximum boost voltage used (runs above parts specified maximum) and the amount of time spent at that voltage. The larger the value entered the larger the boost voltage used and the longer that voltage will be maintained.
- VarStore `0x5000` · offset `0x17f` · 32-bit · range `0x64`..`0x3e8`
- options: `100` = 1X, `200` = 2X (default), `300` = 3X, `400` = 4X, `500` = 5X, `600` = 6X, `700` = 7X, `800` = 8X, `900` = 9X, `1000` = 10X

#### Form `0x704d` — SMU Common Options

_Settings:_

##### `0x10c` — **cTDP** (Numeric)
> cTDP [W] 0 = Invalid value.
- VarStore `0x5000` · offset `0x186` · 32-bit · range `0x0`..`0x18f` · default `0`
- conditions: SuppressIf(Q0x10b=0x0)

##### `0x10d` — **CLDO_VDDP Control** (OneOf)
> Manual = User can set customized CLDO_VDDP voltage
- VarStore `0x5000` · offset `0x18a` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x111` — **Package Power Limit** (Numeric)
> Package Power Limit (PPT) [W]
- VarStore `0x5000` · offset `0x191` · 32-bit · range `0x0`..`0xffffffff` · default `0`
- conditions: SuppressIf(Q0x110=0x0)

##### `0x118` — **Fixed SOC Pstate** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x19c` · 8-bit · range `0x0`..`0x3`
- options: `0` = P0 (default), `1` = P1, `2` = P2, `3` = P3

##### `0x7053` — **CPPC** (OneOf)
> FEATURE_CPPC_MASK
- VarStore `0x5000` · offset `0x19d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x7054` — **HSMP Support** (OneOf)
> Select HSMP support enable or disable
- VarStore `0x5000` · offset `0x19e` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x7055` — **Diagnostic Mode** (OneOf)
> Select Diag mode enable or disable
- VarStore `0x5000` · offset `0x19f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x7056` — **DLWM Support** (OneOf)
> Select DLWM support enable or disable
- VarStore `0x5000` · offset `0x1a0` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x11a` — **BoostFmax** (Numeric)
> Specify the boost Fmax frequency limit to apply to all cores (MHz)
- VarStore `0x5000` · offset `0x1a2` · 32-bit · range `0x0`..`0xffffffff` · default `0`
- conditions: SuppressIf(Q0x119=0x0)

##### `0x11b` — **EDC Current Tracking** (OneOf)
> The generation a correctable MCE when the telemetry current value is over the set threshold defined by EDC Current Tracking Current Threshold.
- VarStore `0x5000` · offset `0x1a6` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default), `1` = Enabled

##### `0x11c` — **EDC Tracking Current Threshold** (Numeric)
> The current threshold in AMPs for EDC Current Tracking feature
- VarStore `0x5000` · offset `0x1a7` · 16-bit · range `0x0`..`0xffff` · default `0`

##### `0x11d` — **EDC Tracking Report Interval** (Numeric)
> Reporting interval. Every nth observed excursion results in SMU logging a correctable MCE
- VarStore `0x5000` · offset `0x1a9` · 16-bit · range `0x0`..`0xffff` · default `1`

#### Form `0x7051` — Fan Control

_Settings:_

##### `0x11f` — **Low Temperature** (Numeric)
> Low Temperature ['C]
- VarStore `0x5000` · offset `0x1ac` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x120` — **Medium Temperature** (Numeric)
> Medium Temperature ['C]
- VarStore `0x5000` · offset `0x1ad` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x121` — **High Temperature** (Numeric)
> High Temperature ['C]
- VarStore `0x5000` · offset `0x1ae` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x122` — **Critical Temperature** (Numeric)
> Critical Temperature ['C]
- VarStore `0x5000` · offset `0x1af` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x123` — **Low Pwm** (Numeric)
> Low Pwm [0-100]
- VarStore `0x5000` · offset `0x1b0` · 8-bit · range `0x0`..`0x64` · default `0`

##### `0x124` — **Medium Pwm** (Numeric)
> Medium Pwm [0-100]
- VarStore `0x5000` · offset `0x1b1` · 8-bit · range `0x0`..`0x64` · default `0`

##### `0x125` — **High Pwm** (Numeric)
> High Pwm [0-100]
- VarStore `0x5000` · offset `0x1b2` · 8-bit · range `0x0`..`0x64` · default `0`

##### `0x126` — **Temperature Hysteresis** (Numeric)
> Temperature Hysteresis ['C]
- VarStore `0x5000` · offset `0x1b3` · 8-bit · range `0x0`..`0xff` · default `0`

#### Form `0x704e` — NBIO RAS Common Options

_Settings:_

##### `0x129` — **NBIO RAS Global Control** (OneOf)
> NBIO RAS Global Control
- VarStore `0x5000` · offset `0x1b6` · 8-bit · range `0x0`..`0x1`
- options: `1` = Manual, `0` = Auto (default)

##### `0x12a` — **NBIO RAS Control** (OneOf)
> (0) Disabled, (1) MCA
- VarStore `0x5000` · offset `0x1b7` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = MCA, `15` = Auto (default)

##### `0x12b` — **Egress Poison Severity High** (Numeric)
> Each bit set to 1 enables HIGH severity on the associated IOHC egress port. A bit of 0 indicates LOW severity.
- VarStore `0x5000` · offset `0x1b8` · 32-bit · range `0x0`..`0xffffffff` · default `196625`

##### `0x12c` — **Egress Poison Severity Low** (Numeric)
> Each bit set to 1 enables HIGH severity on the associated IOHC egress port. A bit of 0 indicates LOW severity.
- VarStore `0x5000` · offset `0x1bc` · 32-bit · range `0x0`..`0xffffffff` · default `4`

##### `0x12d` — **NBIO SyncFlood Generation** (OneOf)
> This value may be used to mask SyncFlood caused by NBIO RAS options.  When set to TRUE SyncFlood from NBIO is masked.  When set to FALSE NBIO is capable of generating SyncFlood.
- VarStore `0x5000` · offset `0x1c0` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x12e` — **NBIO SyncFlood Reporting** (OneOf)
> This value may be used to enable SyncFlood reporting to APML.  When set to TRUE SyncFlood will be reported to APML.  When set to FALSE that reporting well be disabled
- VarStore `0x5000` · offset `0x1c1` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x12f` — **Egress Poison Mask High** (Numeric)
> These set the enable mask for masking of errors logged in EGRESS_POISON_STATUS. For each bit set to 1, errors are masked.  For each bit set to 0, errors trigger response actions.
- VarStore `0x5000` · offset `0x1c2` · 32-bit · range `0x0`..`0xffffffff` · default `4294770687`

##### `0x130` — **Egress Poison Mask Low** (Numeric)
> These set the enable mask for masking of errors logged in EGRESS_POISON_STATUS. For each bit set to 1, errors are masked.  For each bit set to 0, errors trigger response actions.
- VarStore `0x5000` · offset `0x1c6` · 32-bit · range `0x0`..`0xffffffff` · default `4294967291`

##### `0x131` — **Uncorrected Converted to Poison Enable Mask High** (Numeric)
> These set the enable mask for masking of uncorrectable parity errors on internal arrays.  For each bit set to 1, a system fatal error event is triggered for UCP errors on arrays associated with that egress port.  For each bit set to 0, errors are masked.
- VarStore `0x5000` · offset `0x1ca` · 32-bit · range `0x0`..`0xffffffff` · default `196608`

##### `0x132` — **Uncorrected Converted to Poison Enable Mask Low** (Numeric)
> These set the enable mask for masking of uncorrectable parity errors on internal arrays.  For each bit set to 1, a system fatal error event is triggered for UCP errors on arrays associated with that egress port.  For each bit set to 0, errors are masked.
- VarStore `0x5000` · offset `0x1ce` · 32-bit · range `0x0`..`0xffffffff` · default `4`

##### `0x133` — **System Hub Watchdog Timer** (Numeric)
> This value specifies the timer interval of the SYSHUB Watchdog timer in miliseconds
- VarStore `0x5000` · offset `0x1d2` · 32-bit · range `0x0`..`0xffff` · default `2600`

##### `0x134` — **SLINK Read Response OK** (OneOf)
> This value specifies whether SLINK read response errors are converted to an Okay response.  When this value is set to TRUE, read response errors are converted to Okay responses with data of all FFs.  When set to FALSE read response errors are not converted.
- VarStore `0x5000` · offset `0x1d6` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled (default)

##### `0x135` — **SLINK Read Response Error Handling** (OneOf)
> This value specifies whether SLINK write response errors are converted to an Okay response.  When this value is set to 0, write response errors will be logged in the MCA.  When set to 1, write response errors will trigger an MCOMMIT error. When this value is set to 2, write response errors are converted to Okay responses.
- VarStore `0x5000` · offset `0x1d7` · 8-bit · range `0x0`..`0x2`
- options: `2` = Enabled, `1` = Trigger MCOMMIT Error, `0` = Log Errors in MCA (default)

##### `0x136` — **Log Poison Data from SLINK** (OneOf)
> This value specifies whether poison data propagated from SLINK will generate a deferred error.  When set to TRUE, deferred errors are enabled.  When set to FALSE, errors are not generated.
- VarStore `0x5000` · offset `0x1d8` · 8-bit · range `0x0`..`0x1`
- options: `1` = Enabled, `0` = Disabled (default)

##### `0x137` — **PCIe Aer Reporting Mechanism** (OneOf)
> This value selects the method of reporting AER errors from PCI Express.  A value of 0 indicates that the hardware will report the error through MCA.  A value of 1 allows OS First handling of the errors through generation of a system control interrupt (SCI).  A value of 2 provides for Firmware First handling of errors through generation of a system management interrupt (SMI).
- VarStore `0x5000` · offset `0x1d9` · 8-bit · range `0x0`..`0xf`
- options: `2` = Firmware First, `1` = OS First, `0` = MCA, `15` = Auto (default)

##### `0x138` — **Edpc Control** (OneOf)
> (0) Disabled; (1) Enabled; (3) Auto
- VarStore `0x5000` · offset `0x1da` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled (default), `1` = Enabled, `3` = Auto

##### `0x139` — **NBIO Poison Consumption** (OneOf)
> NBIO Poison Consumption
- VarStore `0x5000` · offset `0x1db` · 8-bit · range `0x0`..`0x2`
- options: `0` = Auto (default), `1` = Enabled, `2` = Disabled

#### Form `0x7005` — FCH Common Options

_Navigation (children):_
- → `0x7057` **SATA Configuration Options**
  - SATA Configuration Options
- → `0x7058` **USB Configuration Options**
  - USB Configuration Options
- → `0x7059` **SD Dump Options**
  - SD Dump Options
- → `0x705a` **Ac Power Loss Options**
  - Ac Power Loss Options
- → `0x705b` **I2C Configuration Options**
  - I2C Configuration Options
- → `0x705c` **Uart Configuration Options**
  - Uart Configuration Options
- → `0x705d` **ESPI Configuration Options**
  - ESPI Configuration Options
- → `0x705e` **eMMC Options**
  - eMMC Options
- → `0x705f` **FCH RAS Options**
  - FCH RAS Options

#### Form `0x7057` — SATA Configuration Options

_Navigation (children):_
- → `0x7062` **SATA Controller options**
  - SATA Controller options

_Settings:_

##### `0x7061` — **SATA Enable** (OneOf)
> Disable or enable OnChip SATA controller
- VarStore `0x5000` · offset `0x1dd` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x144` — **SATA Mode** (OneOf)
> Select OnChip SATA Type
- VarStore `0x5000` · offset `0x1de` · 8-bit · range `0x2`..`0xf`
- options: `2` = AHCI (default), `5` = AHCI as ID 0x7904, `15` = Auto

##### `0x145` — **Sata RAS Support** (OneOf)
> Disable or enable Sata RAS Support
- VarStore `0x5000` · offset `0x1df` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x146` — **Sata Disabled AHCI Prefetch Function** (OneOf)
> Disable or enable Sata Disabled AHCI Prefetch Function
- VarStore `0x5000` · offset `0x1e0` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x147` — **Aggresive SATA Device Sleep Port 0** (OneOf)
> Enable or disable aggresive SATA device sleep on port 0
- VarStore `0x5000` · offset `0x1e1` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x148` — **DevSleep0 Port Number** (Numeric)
> DEVSLP port 0
- VarStore `0x5000` · offset `0x1e2` · 8-bit · range `0x0`..`0x7` · default `0`

##### `0x149` — **Aggresive SATA Device Sleep Port 1** (OneOf)
> Enable or disable aggresive SATA device sleep on port 1
- VarStore `0x5000` · offset `0x1e3` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x14a` — **DevSleep1 Port Number** (Numeric)
> DEVSLP port 1
- VarStore `0x5000` · offset `0x1e4` · 8-bit · range `0x0`..`0x7` · default `0`

#### Form `0x7062` — SATA Controller options

_Navigation (children):_
- → `0x7063` **SATA Controller Enable**
  - SATA Controller Enable
- → `0x7064` **SATA Controller eSATA**
  - SATA Controller eSATA
- → `0x7065` **SATA Controller DevSlp**
  - SATA Controller DevSlp
- → `0x7066` **SATA Controller SGPIO**
  - SATA Controller SGPIO

#### Form `0x7063` — SATA Controller Enable

#### Form `0x7064` — SATA Controller eSATA

_Navigation (children):_
- → `0x7067` **Sata0 eSATA**
  - Sata0 eSATA
- → `0x7068` **Sata1 eSATA**
  - Sata1 eSATA
- → `0x7069` **Sata2 eSATA**
  - Sata2 eSATA
- → `0x706a` **Sata3 eSATA**
  - Sata3 eSATA
- → `0x706b` **Sata4 eSATA**
  - Sata4 eSATA
- → `0x706c` **Sata5 eSATA**
  - Sata5 eSATA
- → `0x706d` **Sata6 eSATA**
  - Sata6 eSATA
- → `0x706e` **Sata7 eSATA**
  - Sata7 eSATA

#### Form `0x7067` — Sata0 eSATA

_Settings:_

##### `0x160` — **Sata0 eSATA Port0** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x1ed` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x161` — **Sata0 eSATA Port1** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x1ee` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x162` — **Sata0 eSATA Port2** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x1ef` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x163` — **Sata0 eSATA Port3** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x1f0` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x164` — **Sata0 eSATA Port4** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x1f1` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x165` — **Sata0 eSATA Port5** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x1f2` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x166` — **Sata0 eSATA Port6** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x1f3` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

##### `0x167` — **Sata0 eSATA Port7** (OneOf)
> External SATA Port support
- VarStore `0x5000` · offset `0x1f4` · 8-bit · range `0x0`..`0xf`
- options: `0` = iSATA, `1` = eSATA, `15` = Auto (default)

#### Form `0x7068` — Sata1 eSATA

_Settings:_

##### `0x168` — **Sata1 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1f5` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x169` — **Sata1 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1f6` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x16a` — **Sata1 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1f7` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x16b` — **Sata1 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1f8` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x16c` — **Sata1 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1f9` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x16d` — **Sata1 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1fa` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x16e` — **Sata1 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1fb` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x16f` — **Sata1 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1fc` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7069` — Sata2 eSATA

_Settings:_

##### `0x170` — **Sata2 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1fd` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x171` — **Sata2 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1fe` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x172` — **Sata2 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1ff` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x173` — **Sata2 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x200` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x174` — **Sata2 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x201` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x175` — **Sata2 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x202` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x176` — **Sata2 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x203` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x177` — **Sata2 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x204` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x706a` — Sata3 eSATA

_Settings:_

##### `0x178` — **Sata3 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x205` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x179` — **Sata3 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x206` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x17a` — **Sata3 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x207` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x17b` — **Sata3 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x208` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x17c` — **Sata3 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x209` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x17d` — **Sata3 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x20a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x17e` — **Sata3 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x20b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x17f` — **Sata3 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x20c` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x706b` — Sata4 eSATA

_Settings:_

##### `0x180` — **Sata4 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x20d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x181` — **Sata4 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x20e` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x182` — **Sata4 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x20f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x183` — **Sata4 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x210` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x184` — **Sata4 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x211` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x185` — **Sata4 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x212` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x186` — **Sata4 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x213` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x187` — **Sata4 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x214` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x706c` — Sata5 eSATA

_Settings:_

##### `0x188` — **Sata5 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x215` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x189` — **Sata5 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x216` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x18a` — **Sata5 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x217` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x18b` — **Sata5 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x218` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x18c` — **Sata5 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x219` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x18d` — **Sata5 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x21a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x18e` — **Sata5 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x21b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x18f` — **Sata5 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x21c` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x706d` — Sata6 eSATA

_Settings:_

##### `0x190` — **Sata6 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x21d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x191` — **Sata6 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x21e` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x192` — **Sata6 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x21f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x193` — **Sata6 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x220` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x194` — **Sata6 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x221` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x195` — **Sata6 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x222` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x196` — **Sata6 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x223` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x197` — **Sata6 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x224` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x706e` — Sata7 eSATA

_Settings:_

##### `0x198` — **Sata7 eSATA Port0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x225` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x199` — **Sata7 eSATA Port1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x226` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x19a` — **Sata7 eSATA Port2** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x227` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x19b` — **Sata7 eSATA Port3** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x228` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x19c` — **Sata7 eSATA Port4** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x229` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x19d` — **Sata7 eSATA Port5** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x22a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x19e` — **Sata7 eSATA Port6** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x22b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x19f` — **Sata7 eSATA Port7** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x22c` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7065` — SATA Controller DevSlp

_Navigation (children):_
- → `0x706f` **Socket1 DevSlp**
  - Socket1 DevSlp

#### Form `0x706f` — Socket1 DevSlp

_Settings:_

##### `0x1a1` — **Socket1 DevSlp0 Enable** (OneOf)
> Only Sata0 on each IOD/socket support DevSlp.
- VarStore `0x5000` · offset `0x22d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a2` — **DevSleep0 Port Number** (Numeric)
> DEVSLP port 0
- VarStore `0x5000` · offset `0x22e` · 8-bit · range `0x0`..`0x7` · default `0`

##### `0x1a3` — **Socket1 DevSlp1 Enable** (OneOf)
> Only Sata0 on each IOD/socket support DevSlp.
- VarStore `0x5000` · offset `0x22f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a4` — **DevSleep1 Port Number** (Numeric)
> DEVSLP port 1
- VarStore `0x5000` · offset `0x230` · 8-bit · range `0x0`..`0x7` · default `1`

#### Form `0x7066` — SATA Controller SGPIO

_Settings:_

##### `0x1a5` — **Sata0 SGPIO** (OneOf)
> Eable Sata0 SGPIO feature
- VarStore `0x5000` · offset `0x231` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a6` — **Sata1 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata1
- VarStore `0x5000` · offset `0x232` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled (default), `1` = Enabled, `15` = Auto

##### `0x1a7` — **Sata2 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata2
- VarStore `0x5000` · offset `0x233` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a8` — **Sata3 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata3
- VarStore `0x5000` · offset `0x234` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1a9` — **Sata4 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata4 (Socket1)
- VarStore `0x5000` · offset `0x235` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1aa` — **Sata5 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata5
- VarStore `0x5000` · offset `0x236` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1ab` — **Sata6 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata6 (Socket1)
- VarStore `0x5000` · offset `0x237` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1ac` — **Sata7 SGPIO** (OneOf)
> Enable or Disable SataSgpio on Sata7 (Socket7)
- VarStore `0x5000` · offset `0x238` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7058` — USB Configuration Options

_Navigation (children):_
- → `0x7070` **MCM USB enable**
  - MCM USB enable

_Settings:_

##### `0x1ad` — **XHCI Controller0 enable** (OneOf)
> Enable or disable USB3 controller.
- VarStore `0x5000` · offset `0x239` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x1ae` — **XHCI Controller1 enable** (OneOf)
> Enable or disable USB3 controller.
- VarStore `0x5000` · offset `0x23a` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x1af` — **USB ecc SMI Enable** (OneOf)
> Enable or disable USB ecc SMI
- VarStore `0x5000` · offset `0x23b` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Off, `15` = Auto (default)

#### Form `0x7070` — MCM USB enable

_Settings:_

##### `0x1b1` — **XHCI2 enable (Socket1)** (OneOf)
> Enable or disable USB3 controller.
- VarStore `0x5000` · offset `0x23c` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x1b2` — **XHCI3 enable (Socket1)** (OneOf)
> Enable or disable USB3 controller.
- VarStore `0x5000` · offset `0x23d` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

#### Form `0x7059` — SD Dump Options

_Settings:_

##### `0x1b3` — **SD Configuration Mode** (OneOf)
> Select SD Mode
- VarStore `0x5000` · offset `0x23e` · 8-bit · range `0x0`..`0x6`
- options: `0` = SD Dump disabled (default), `6` = SD Dump enabled

#### Form `0x705a` — Ac Power Loss Options

_Settings:_

##### `0x1b4` — **Ac Loss Control** (OneOf)
> Select Ac Loss Control Method
- VarStore `0x5000` · offset `0x23f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Always Off, `1` = Always On, `2` = Reserved, `3` = Previous, `15` = Auto

#### Form `0x705b` — I2C Configuration Options

_Settings:_

##### `0x1b5` — **I2C 0 Enable** (OneOf)
> Enable or disable I2C 0
- VarStore `0x5000` · offset `0x240` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b6` — **I2C 1 Enable** (OneOf)
> Enable or disable I2C 1
- VarStore `0x5000` · offset `0x241` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b7` — **I2C 2 Enable** (OneOf)
> Enable or disable I2C 2
- VarStore `0x5000` · offset `0x242` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b8` — **I2C 3 Enable** (OneOf)
> Enable or disable I2C 3
- VarStore `0x5000` · offset `0x243` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1b9` — **I2C 4 Enable** (OneOf)
> Enable or disable I2C 4
- VarStore `0x5000` · offset `0x244` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1ba` — **I2C 5 Enable** (OneOf)
> Enable or disable I2C 5
- VarStore `0x5000` · offset `0x245` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x705c` — Uart Configuration Options

_Settings:_

##### `0x1bb` — **Uart 0 Enable** (OneOf)
> Uart 0 has no HW FC if Uart 2 is enabled
- VarStore `0x5000` · offset `0x246` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1bc` — **Uart 0 Legacy Options** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x247` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = 0x2E8, `2` = 0x2F8, `3` = 0x3E8, `4` = 0x3F8, `15` = Auto (default)

##### `0x1bd` — **Uart 1 Enable** (OneOf)
> Uart 1 has no HW FC if Uart 3 is enabled
- VarStore `0x5000` · offset `0x248` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1be` — **Uart 1 Legacy Options** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x249` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = 0x2E8, `2` = 0x2F8, `3` = 0x3E8, `4` = 0x3F8, `15` = Auto (default)

##### `0x1bf` — **Uart 2 Enable (no HW FC)** (OneOf)
> Uart 2 has no HW FC if Uart 0 is enabled
- VarStore `0x5000` · offset `0x24a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1c0` — **Uart 2 Legacy Options** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x24b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = 0x2E8, `2` = 0x2F8, `3` = 0x3E8, `4` = 0x3F8, `15` = Auto (default)

##### `0x1c1` — **Uart 3 Enable (no HW FC)** (OneOf)
> Uart 3 has no HW FC if Uart 1 is enabled
- VarStore `0x5000` · offset `0x24c` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1c2` — **Uart 3 Legacy Options** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x24d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = 0x2E8, `2` = 0x2F8, `3` = 0x3E8, `4` = 0x3F8, `15` = Auto (default)

#### Form `0x705d` — ESPI Configuration Options

_Settings:_

##### `0x1c3` — **ESPI Enable** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x24e` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x705e` — eMMC Options

_Settings:_

##### `0x1c4` — **eMMC/SD Configure** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x24f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = SD Normal Speed, `2` = SD High Speed, `3` = SD UHSI-SDR50, `4` = SD UHSI-DDR50, `5` = SD UHSI-SDR104, `6` = eMMC Emmc Backward Compatibility, `7` = eMMC High Speed SDR, `8` = eMMC High Speed DDR, `9` = eMMC HS200, `10` = eMMC HS400, `11` = eMMC HS300, `15` = Auto (default)

##### `0x1c5` — **Driver Type** (OneOf)
> Bios will select MS driver for SD selections.
- VarStore `0x5000` · offset `0x250` · 8-bit · range `0x0`..`0xf`
- options: `0` = AMD eMMC Driver, `1` = MS Driver, `15` = Auto (default)

##### `0x1c6` — **D3 Cold Support** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x251` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x1c7` — **eMMC Boot** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x252` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x705f` — FCH RAS Options

_Settings:_

##### `0x1c8` — **ALink RAS Support** (OneOf)
> Enable ALink RAS Support
- VarStore `0x5000` · offset `0x253` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7060` — Miscellaneous Options

#### Form `0x7007` — NTB Common Options

_Settings:_

##### `0x1cb` — **NTB Enable** (OneOf)
> Enable NTB
- VarStore `0x5000` · offset `0x27e` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Enabled

##### `0x1cc` — **NTB Location** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x27f` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = Socket0-Die0, `1` = Socket0-Die1, `2` = Socket0-Die2, `3` = Socket0-Die3, `4` = Socket1-Die0, `5` = Socket1-Die1, `6` = Socket1-Die2, `7` = Socket1-Die3
- conditions: SuppressIf(Q0x1cb=0x0)

##### `0x1cd` — **NTB active on PCIeCore** (OneOf)
> NTB enable on PCIe Core
- VarStore `0x5000` · offset `0x280` · 8-bit · range `0x0`..`0x10`
- options: `15` = Auto (default), `0` = Core0, `16` = Core1
- conditions: SuppressIf(Q0x1cb=0x0)

##### `0x1ce` — **NTB Mode** (OneOf)
> Select NTB Mode (Core 0, Port 0)
- VarStore `0x5000` · offset `0x281` · 8-bit · range `0x0`..`0xf`
- options: `0` = NTB Disabled, `1` = NTB Primary, `2` = NTB Secondary, `3` = NTB Random, `15` = Auto (default)
- conditions: SuppressIf(Q0x1cb=0x0)

##### `0x1cf` — **Link Speed** (OneOf)
> Select Link Speed for NTB Mode (Core 0, Port 0)
- VarStore `0x5000` · offset `0x282` · 8-bit · range `0x0`..`0xf`
- options: `0` = Max Speed, `1` = Gen 1, `2` = Gen 2, `3` = Gen 3, `15` = Auto (default), `4` = Gen 4
- conditions: SuppressIf(Q0x1cb=0x0)

#### Form `0x7008` — Soc Miscellaneous Control

## Module: `CbsSetupDxeZP.pe32.0.0.en-US.uefi.ifr.txt`
- FormSet GUID: `7C3CCF08-B8F4-4EF4-B58D-A470BFD2DE05`
- FormSet title: **AMD CBS**
- FormSet help: AMD CBS Setup Page

### VarStores
- `0x5000` **AmdSetupZP** — GUID `3A997502-647A-4C82-998E-52EF9486A247`, size `0x5b2`

### Forms

#### Form `0x7000` — AMD CBS

_Navigation (children):_
- → `0x7001` **Zen Common Options**
  - Zen Common Options
- → `0x7002` **DF Common Options**
  - DF Common Options
- → `0x7003` **UMC Common Options**
  - UMC Common Options
- → `0x7004` **NBIO Common Options**
  - NBIO Common Options
- → `0x7005` **FCH Common Options**
  - FCH Common Options
- → `0x7007` **NTB Common Options**
  - NTB Common Options

_Settings:_

##### `0x7` — **Combo CBS** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x20` · 8-bit · range `0x0`..`0xff` · default `254`

#### Form `0x7001` — Zen Common Options

_Navigation (children):_
- → `0x700c` **Custom Pstates / Throttling**
  - Custom Pstates / Throttling
- → `0x700d` **Core/Thread Enablement**
  - Core/Thread Enablement
- → `0x700e` **Prefetcher settings**
  - Prefetcher settings

_Settings:_

##### `0x8` — **RedirectForReturnDis** (OneOf)
> From a workaround for GCC/C000005 issue for XV Core on CZ A0, setting MSRC001_1029 Decode Configuration (DE_CFG) bit 14 [DecfgNoRdrctForReturns] to 1
- VarStore `0x5000` · offset `0x21` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = 1, `0` = 0

##### `0x9` — **L2 TLB Associativity** (OneOf)
> 0 - L2 TLB ways [11:8] are fully associative.  1 - =L2 TLB ways [11:8] are 4K-only.
- VarStore `0x5000` · offset `0x22` · 8-bit · range `0x0`..`0x3`
- options: `0` = 0, `1` = 1, `3` = Auto (default)

##### `0x7008` — **Platform First Error Handling** (OneOf)
> Enable/disable PFEH, cloak individual banks, and mask deferred error interrupts from each bank. This feature must be disabled on B1 stepping
- VarStore `0x5000` · offset `0x23` · 8-bit · range `0x0`..`0x3`
- options: `1` = Enabled, `0` = Disabled, `3` = Auto (default)

##### `0xa` — **Core Performance Boost** (OneOf)
> Disable CPB
- VarStore `0x5000` · offset `0x24` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Auto (default)

##### `0xb` — **Enable IBS** (OneOf)
> Enables IBS through MSRC001_1005[42] and disables SpecLockMap through MSRC001_1020[54]
- VarStore `0x5000` · offset `0x25` · 8-bit · range `0x0`..`0x3`
- options: `3` = Auto (default), `1` = Enabled, `0` = Disabled

##### `0xc` — **Global C-state Control** (OneOf)
> Controls IO based C-state generation and DF C-states.
- VarStore `0x5000` · offset `0x26` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0xd` — **Power Supply Idle Control** (OneOf)
> Power Supply Idle Control.
- VarStore `0x5000` · offset `0x27` · 8-bit · range `0x0`..`0xf`
- options: `1` = Low Current Idle, `0` = Typical Current Idle, `15` = Auto (default)

##### `0x7009` — **Opcache grayout flag** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x28` · 8-bit · range `0x0`..`0x2`
- options: `0` = 0 (default), `1` = 1, `2` = Display

##### `0x700a` — **Opcache Control** (OneOf)
> Enables or disables the Opcache
- VarStore `0x5000` · offset `0x29` · 8-bit · range `0x0`..`0xff`
- options: `1` = Disabled, `0` = Enabled, `255` = Auto (default)

##### `0x700b` — **OC Mode** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x2a` · 8-bit · range `0x0`..`0x5`
- options: `0` = Normal Operation (default), `1` = OC1, `2` = OC2, `3` = OC3, `5` = Customized

##### `0x10` — **SEV-ES ASID Space Limit** (Numeric)
> SEV VMs using ASIDs below the SEV-ES ASID Space Limit must enable the SEV-ES feature. The valid values for this field are from 0x1 (1) - 0x10 (16).
- VarStore `0x5000` · offset `0x2b` · 32-bit · range `0x1`..`0x10` · default `1`

##### `0x11` — **Streaming Stores Control** (OneOf)
> Enables or disables the streaming stores functionality
- VarStore `0x5000` · offset `0x2f` · 8-bit · range `0x0`..`0xff`
- options: `1` = Disabled, `0` = Enabled, `255` = Auto (default)

##### `0x12` — **ACPI _CST C1 Declaration** (OneOf)
> Determines whether or not to declare the C1 state to the OS.
- VarStore `0x5000` · offset `0x30` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x14` — **SMU and PSP Production Mode** (OneOf)
> When this option is disabled, specific uncorrected errors detected by the PSP FW or SMU FW will hang and not reset the system
- VarStore `0x5000` · offset `0x1d1` · 8-bit · range `0x0`..`0x3`
- options: `0` = Enabled, `1` = Disabled, `3` = Auto (default)

#### Form `0x700c` — Custom Pstates / Throttling

_Navigation (children):_
- → `0x700f` **Decline**
  - Decline
- → `0x7010` **Accept**
  - Accept

#### Form `0x700f` — Decline

#### Form `0x7010` — Accept

_Settings:_

##### `0x17` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x34` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x18` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x38` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7012` — **Pstate0 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x3c` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7013` — **Pstate0 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x3d` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7014` — **Pstate0 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x3e` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x19` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x40` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x1a` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x44` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7016` — **Pstate1 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x48` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7017` — **Pstate1 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x49` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7018` — **Pstate1 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x4a` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x1b` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x4c` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x1c` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x50` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x701a` — **Pstate2 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x54` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x701b` — **Pstate2 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x55` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x701c` — **Pstate2 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x56` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x1d` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x58` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x1e` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x5c` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x701e` — **Pstate3 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x60` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x701f` — **Pstate3 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x61` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7020` — **Pstate3 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x62` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x1f` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x64` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x20` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x68` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7022` — **Pstate4 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x6c` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7023` — **Pstate4 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x6d` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7024` — **Pstate4 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x6e` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x21` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x70` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x22` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x74` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x7026` — **Pstate5 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x78` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x7027` — **Pstate5 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x79` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7028` — **Pstate5 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x7a` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x23` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x7c` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x24` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x80` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x702a` — **Pstate6 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x84` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x702b` — **Pstate6 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x85` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x702c` — **Pstate6 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x86` · 8-bit · range `0x0`..`0xff` · default `255`

##### `0x25` — **Frequency (MHz)** (Numeric)
> Current core frequency in MHz
- VarStore `0x5000` · offset `0x88` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x26` — **Voltage (uV)** (Numeric)
> Voltage in uV (1V = 1000 * 1000 uV)
- VarStore `0x5000` · offset `0x8c` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x702e` — **Pstate7 FID** (Numeric)
> Specifies the core frequency multiplier. COF = 200MHz * FID / DID
- VarStore `0x5000` · offset `0x90` · 8-bit · range `0x10`..`0xff` · default `16`

##### `0x702f` — **Pstate7 DID** (Numeric)
> Specifies the core frequency divisor (DID[0] should zero if DID[5:0]>1Ah).
- VarStore `0x5000` · offset `0x91` · 8-bit · range `0x8`..`0x30` · default `8`

##### `0x7030` — **Pstate7 VID** (Numeric)
> Specifies the core voltage.
- VarStore `0x5000` · offset `0x92` · 8-bit · range `0x0`..`0xff` · default `255`

#### Form `0x700d` — Core/Thread Enablement

_Navigation (children):_
- → `0x7032` **Disagree**
  - Disagree
- → `0x7033` **Agree**
  - Agree

#### Form `0x7032` — Disagree

#### Form `0x7033` — Agree

_Settings:_

##### `0x7034` — **Downcore control** (OneOf)
> Sets the number of cores to be used. Once this option has been used to remove any cores, a POWER CYCLE is required in order for future selections to take effect.
- VarStore `0x5000` · offset `0x95` · 8-bit · range `0x0`..`0x7`
- options: `1` = ONE (1 + 0), `2` = TWO (1 + 1), `3` = TWO (2 + 0), `4` = THREE (3 + 0), `5` = FOUR (2 + 2), `6` = FOUR (4 + 0), `7` = SIX (3 + 3), `0` = Auto (default)

##### `0x29` — **SMTEN** (OneOf)
> Can be used to disable symmetric multithreading. To re-enable SMT, a POWER CYCLE is needed after selecting the 'Auto' option. WARNING - S3 is NOT SUPPORTED on systems where SMT is disabled.
- VarStore `0x5000` · offset `0x96` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled, `1` = Auto (default)

##### `0x2a` — **Die0 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x1b7` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x2b` — **Die1 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x1b4` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x2c` — **Die2 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x1b5` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0x2d` — **Die3 DownCore Bitmap** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x1b6` · 8-bit · range `0x0`..`0xff` · default `0`

#### Form `0x700e` — Prefetcher settings

_Settings:_

##### `0x2e` — **L1 Stream HW Prefetcher** (OneOf)
> Option to Enable | Disable L1 Stream HW Prefetcher
- VarStore `0x5000` · offset `0x97` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x2f` — **L2 Stream HW Prefetcher** (OneOf)
> Option to Enable | Disable L2 Stream HW Prefetcher
- VarStore `0x5000` · offset `0x98` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

#### Form `0x7002` — DF Common Options

_Settings:_

##### `0x30` — **DRAM scrub time** (OneOf)
> Provide a value that is the number of hours to scrub memory.
- VarStore `0x5000` · offset `0x99` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = 1 hour, `4` = 4 hours, `8` = 8 hours, `16` = 16 hours, `24` = 24 hours, `48` = 48 hours, `255` = Auto (default)

##### `0x31` — **Redirect scrubber control** (OneOf)
> Control DF::RedirScrubCtrl[EnRedirScrub]
- VarStore `0x5000` · offset `0x9a` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x32` — **Disable DF sync flood propagation** (OneOf)
> Control DF::PIEConfig[DisSyncFloodProp]
- VarStore `0x5000` · offset `0x9b` · 8-bit · range `0x0`..`0x3`
- options: `0` = Sync flood disabled, `1` = Sync flood enabled, `3` = Auto (default)

##### `0x34` — **GMI encryption control** (OneOf)
> Control GMI link encryption
- VarStore `0x5000` · offset `0x9d` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x35` — **xGMI encryption control** (OneOf)
> Control xGMI link encryption
- VarStore `0x5000` · offset `0x9e` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x36` — **CC6 memory region encryption** (OneOf)
> Control whether or not the CC6 save/restore memory is encrypted
- VarStore `0x5000` · offset `0x9f` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x37` — **Location of private memory regions** (OneOf)
> Controls whether or not the private memory regions (PSP, SMU and CC6) are at the top of DRAM or distributed. Note that distributed requires memory on all dies. Note that it will always be at the top of DRAM if some dies don't have memory regardless of this option's setting.
- VarStore `0x5000` · offset `0xa0` · 8-bit · range `0x0`..`0x3`
- options: `0` = Distributed, `1` = Consolidated, `3` = Auto (default)

##### `0x38` — **System probe filter** (OneOf)
> Controls whether or not the probe filter is enabled. Has no effect on parts where the probe filter is fuse disabled.
- VarStore `0x5000` · offset `0xa1` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x39` — **Memory interleaving** (OneOf)
> Controls fabric level memory interleaving (AUTO, none, channel, die, socket). Note that channel, die, and socket has requirements on memory populations and it will be ignored if the memory doesn't support the selected option.
- VarStore `0x5000` · offset `0xa2` · 8-bit · range `0x0`..`0x7`
- options: `0` = None, `1` = Channel, `2` = Die, `3` = Socket, `7` = Auto (default)

##### `0x3a` — **Memory interleaving size** (OneOf)
> Controls the memory interleaving size. The valid values are AUTO, 256 bytes, 512 bytes, 1 Kbytes or 2Kbytes. This determines the starting address of the interleave (bit 8, 9, 10 or 11).
- VarStore `0x5000` · offset `0xa3` · 8-bit · range `0x0`..`0x7`
- options: `0` = 256 Bytes, `1` = 512 Bytes, `2` = 1 KB, `3` = 2 KB, `7` = Auto (default)

##### `0x3b` — **Channel interleaving hash** (OneOf)
> Controls whether or not the address bits are hashed during channel interleave mode. This field should not be used unless the interleaving is set to channel and the interleaving size is 256 or 512 bytes.
- VarStore `0x5000` · offset `0xa4` · 8-bit · range `0x0`..`0x3`
- options: `0` = Disabled, `1` = Enabled, `3` = Auto (default)

##### `0x3c` — **Memory Clear** (OneOf)
> When this feature is disabled, BIOS does not implement MemClear after memory training (only if non-ECC DIMMs are used).
- VarStore `0x5000` · offset `0xa5` · 8-bit · range `0x0`..`0x3`
- options: `0` = Enabled, `1` = Disabled, `3` = Auto (default)

##### `0x3d` — **ACPI SLIT Distance Control** (OneOf)
> Determines how the SLIT distances are declared.
- VarStore `0x5000` · offset `0xa6` · 8-bit · range `0x0`..`0xff`
- options: `0` = Hardware, `1` = Local, `2` = Max 2 Distances, `3` = Max 3 Distances, `255` = Auto (default)

##### `0x3e` — **ACPI SLIT non-self distance** (Numeric)
> Specify the distance to other domains.
- VarStore `0x5000` · offset `0xa7` · 8-bit · range `0xa`..`0xff` · default `28`

##### `0x3f` — **ACPI SLIT same socket distance** (Numeric)
> Specify the distance to other domains within the same socket.
- VarStore `0x5000` · offset `0xa8` · 8-bit · range `0xa`..`0xff` · default `16`

##### `0x40` — **ACPI SLIT remote socket distance** (Numeric)
> Specify the distance to other domains on the remote socket.
- VarStore `0x5000` · offset `0xa9` · 8-bit · range `0xa`..`0xff` · default `32`

#### Form `0x7003` — UMC Common Options

_Navigation (children):_
- → `0x7035` **DDR4 Common Options**
  - DDR4 Common Options
- → `0x7036` **DRAM Memory Mapping**
  - DRAM Memory Mapping
- → `0x7037` **NVDIMM**
  - NVDIMM
- → `0x7038` **Memory MBIST**
  - Memory MBIST

#### Form `0x7035` — DDR4 Common Options

_Navigation (children):_
- → `0x7039` **DRAM Timing Configuration**
  - DRAM Timing Configuration
- → `0x703a` **DRAM Controller Configuration**
  - DRAM Controller Configuration
- → `0x703b` **CAD Bus Configuration**
  - CAD Bus Configuration
- → `0x703c` **Data Bus Configuration**
  - Data Bus Configuration
- → `0x703d` **Common RAS**
  - Common RAS
- → `0x703e` **Security**
  - Security

#### Form `0x7039` — DRAM Timing Configuration

_Navigation (children):_
- → `0x703f` **I Decline**
  - I Decline
- → `0x7040` **I Accept**
  - I Accept

#### Form `0x703f` — I Decline

#### Form `0x7040` — I Accept

_Settings:_

##### `0x4d` — **Overclock** (OneOf)
> Memory Overclock Settings
- VarStore `0x5000` · offset `0xac` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Enabled

##### `0x4e` — **Memory Clock Speed** (OneOf)
> Set the memory clock frequency.
- VarStore `0x5000` · offset `0xad` · 8-bit · range `0x4`..`0xff`
- options: `255` = Auto (default), `20` = 667MHz, `24` = 800MHz, `28` = 933MHz, `32` = 1067MHz, `36` = 1200MHz, `40` = 1333MHz, `41` = 1367MHz, `42` = 1400MHz, `43` = 1433MHz, `44` = 1467MHz, `45` = 1500MHz, `46` = 1533MHz, `47` = 1567MHz, `48` = 1600MHz, `49` = 1633MHz, `50` = 1667MHz, `51` = 1700MHz, `52` = 1733MHz, `53` = 1767MHz, `54` = 1800MHz, `55` = 1833MHz, `56` = 1867MHz, `57` = 1900MHz, `58` = 1933MHz, `59` = 1967MHz, `60` = 2000MHz, `61` = 2033MHz, `62` = 2067MHz, `63` = 2100MHz, `4` = 333MHz, `6` = 400MHz, `10` = 533MHz, `25` = 1050MHz, `26` = 1066MHz

##### `0x4f` — **Tcl** (OneOf)
> Sets the tCL time.
- VarStore `0x5000` · offset `0xae` · 8-bit · range `0x8`..`0xff`
- options: `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `255` = Auto (default), `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk, `28` = 1Ch Clk, `29` = 1Dh Clk, `30` = 1Eh Clk, `31` = 1Fh Clk, `32` = 20h Clk, `33` = 21h Clk

##### `0x50` — **Trcdrd** (OneOf)
> This sets the RAS# Active to CAS# read/write delay.
- VarStore `0x5000` · offset `0xaf` · 8-bit · range `0x8`..`0xff`
- options: `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `255` = Auto (default), `27` = 1Bh Clk

##### `0x51` — **Trcdwr** (OneOf)
> This sets the RAS# Active to CAS# read/write delay.
- VarStore `0x5000` · offset `0xb0` · 8-bit · range `0x8`..`0xff`
- options: `255` = Auto (default), `8` = 8 Clk, `9` = 9 Clk, `10` = 0xA Clk, `11` = 0xB Clk, `12` = 0xC Clk, `13` = 0xD Clk, `14` = 0xE Clk, `15` = 0xF Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk

##### `0x52` — **Trp** (OneOf)
> Specify the row precharge time.
- VarStore `0x5000` · offset `0xb1` · 8-bit · range `0x8`..`0xff`
- options: `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `255` = Auto (default), `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk

##### `0x53` — **Tras** (OneOf)
> Specify the min RAS# active time.
- VarStore `0x5000` · offset `0xb2` · 8-bit · range `0x15`..`0xff`
- options: `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk, `28` = 1Ch Clk, `29` = 1Dh Clk, `30` = 1Eh Clk, `31` = 1Fh Clk, `32` = 20h Clk, `33` = 21h Clk, `34` = 22h Clk, `35` = 23h Clk, `36` = 24h Clk, `37` = 25h Clk, `38` = 26h Clk, `39` = 27h Clk, `40` = 28h Clk, `41` = 29h Clk, `42` = 2Ah Clk, `255` = Auto (default), `43` = 2Bh Clk, `44` = 2Ch Clk, `45` = 2Dh Clk, `46` = 2Eh Clk, `47` = 2Fh Clk, `48` = 30h Clk, `49` = 31h Clk, `50` = 32h Clk, `51` = 33h Clk, `52` = 34h Clk, `53` = 35h Clk, `54` = 36h Clk, `55` = 37h Clk, `56` = 38h Clk, `57` = 39h Clk, `58` = 3Ah Clk

##### `0x54` — **Trc Ctrl** (OneOf)
> Specify Trc
- VarStore `0x5000` · offset `0xb3` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x55` — **Trc** (Numeric)
> Active to Active/Refresh Delay Time. Valid values 87h-1Dh.
- VarStore `0x5000` · offset `0xb4` · 8-bit · range `0x1d`..`0x87` · default `57`

##### `0x56` — **TrrdS** (OneOf)
> Activate to Activate Delay Time, different bank group (tRRD_S)
- VarStore `0x5000` · offset `0xb5` · 8-bit · range `0x4`..`0xff`
- options: `255` = Auto (default), `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk

##### `0x57` — **TrrdL** (OneOf)
> Activate to Activate Delay Time, same bank group (tRRD_L)
- VarStore `0x5000` · offset `0xb6` · 8-bit · range `0x4`..`0xff`
- options: `255` = Auto (default), `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk

##### `0x58` — **Tfaw Ctrl** (OneOf)
> Specify Tfaw
- VarStore `0x5000` · offset `0xb7` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x59` — **Tfaw** (Numeric)
> Four Activate Window Time. Valid values 36h-6h.
- VarStore `0x5000` · offset `0xb8` · 8-bit · range `0x6`..`0x36` · default `26`

##### `0x5a` — **TwtrS** (OneOf)
> Minimum Write to Read Time, different bank group
- VarStore `0x5000` · offset `0xb9` · 8-bit · range `0x2`..`0xff`
- options: `255` = Auto (default), `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk

##### `0x5b` — **TwtrL** (OneOf)
> Minimum Write to Read Time, same bank group
- VarStore `0x5000` · offset `0xba` · 8-bit · range `0x2`..`0xff`
- options: `255` = Auto (default), `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk

##### `0x5c` — **Twr Ctrl** (OneOf)
> Specify Twr
- VarStore `0x5000` · offset `0xbb` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x5d` — **Twr** (Numeric)
> Minimum Write Recovery Time. Valid value 51h-Ah
- VarStore `0x5000` · offset `0xbc` · 8-bit · range `0xa`..`0x51` · default `18`

##### `0x5e` — **Trcpage Ctrl** (OneOf)
> Specify Trcpage
- VarStore `0x5000` · offset `0xbd` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x5f` — **Trcpage** (Numeric)
> SDRAM Optional Features (tMAW, MAC). Valid value 3FFh - 0h
- VarStore `0x5000` · offset `0xbe` · 16-bit · range `0x0`..`0x3ff` · default `0`

##### `0x60` — **TrdrdScL Ctrl** (OneOf)
> Specify TrdrdScL
- VarStore `0x5000` · offset `0xc0` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x61` — **TrdrdScL** (Numeric)
> CAS to CAS Delay Time, same bank group. Valid values Fh-1h
- VarStore `0x5000` · offset `0xc1` · 8-bit · range `0x1`..`0xf` · default `3`

##### `0x62` — **TwrwrScL Ctrl** (OneOf)
> Specify TwrwrScL
- VarStore `0x5000` · offset `0xc2` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x63` — **TwrwrScL** (Numeric)
> CAS to CAS Delay Time, same bank group. Valid values 3Fh-1h
- VarStore `0x5000` · offset `0xc3` · 8-bit · range `0x1`..`0x3f` · default `3`

##### `0x64` — **Trfc Ctrl** (OneOf)
> Specify Trfc
- VarStore `0x5000` · offset `0xc4` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x65` — **Trfc** (Numeric)
> Refresh Recovery Delay Time (tRFC1). Valid values 3DEh-3Ch
- VarStore `0x5000` · offset `0xc5` · 16-bit · range `0x3c`..`0x3de` · default `312`

##### `0x66` — **Trfc2 Ctrl** (OneOf)
> Specify Trfc2
- VarStore `0x5000` · offset `0xc7` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x67` — **Trfc2** (Numeric)
> Refresh Recovery Delay Time (tRFC2).  Valid values 3DEh-3Ch
- VarStore `0x5000` · offset `0xc8` · 16-bit · range `0x3c`..`0x3de` · default `192`

##### `0x68` — **Trfc4 Ctrl** (OneOf)
> Specify Trfc4
- VarStore `0x5000` · offset `0xca` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0x69` — **Trfc4** (Numeric)
> Refresh Recovery Delay Time (tRFC4). Valid values 3DEh-3Ch
- VarStore `0x5000` · offset `0xcb` · 16-bit · range `0x3c`..`0x3de` · default `132`

##### `0x6a` — **Fail_CNT** (Numeric)
> The number of training failure/retries required before boot from recovery mode
- VarStore `0x5000` · offset `0x1b3` · 8-bit · range `0x0`..`0xa` · default `5`

##### `0x6b` — **ProcODT** (OneOf)
> Specifies the Processor ODT
- VarStore `0x5000` · offset `0xcd` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = High Impedance, `1` = 480 ohm, `2` = 240 ohm, `3` = 160 ohm, `8` = 120 ohm, `9` = 96 ohm, `10` = 80 ohm, `11` = 68.6 ohm, `24` = 60 ohm, `25` = 53.3 ohm, `26` = 48 ohm, `27` = 43.6 ohm, `56` = 40 ohm, `57` = 36.9 ohm, `58` = 34.3 ohm, `59` = 32 ohm, `62` = 30 ohm, `63` = 28.2 ohm

##### `0x6c` — **Tcwl** (OneOf)
> No help string
- VarStore `0x5000` · offset `0xce` · 8-bit · range `0x9`..`0xff`
- options: `255` = Auto (default), `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `14` = 0Eh Clk, `16` = 10h Clk, `18` = 12h Clk, `20` = 14h Clk

##### `0x6d` — **Trtp** (OneOf)
> Specifies the read CAS# to precharge time.
- VarStore `0x5000` · offset `0xcf` · 8-bit · range `0x5`..`0xff`
- options: `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `255` = Auto (default), `12` = 0Ch Clk, `13` = 0Dh Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `14` = 0Eh Clk

##### `0x6e` — **Trdwr** (OneOf)
> This sets the tWRTTO time.
- VarStore `0x5000` · offset `0xd0` · 8-bit · range `0x1`..`0xff`
- options: `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk, `255` = Auto (default), `1` = 1 Clk, `28` = 1Ch Clk, `29` = 1Dh Clk, `30` = 1Eh Clk, `31` = 1Fh Clk

##### `0x6f` — **Twrrd** (OneOf)
> Specify the write to read delay when accessing different DIMMs.
- VarStore `0x5000` · offset `0xd1` · 8-bit · range `0x1`..`0xff`
- options: `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `255` = Auto (default), `12` = 0Ch, `13` = 0Dh, `14` = 0Eh, `15` = 0Fh

##### `0x70` — **TwrwrSc** (OneOf)
> write to write timing same DIMM same chip select.
- VarStore `0x5000` · offset `0xd2` · 8-bit · range `0x1`..`0xff`
- options: `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `255` = Auto (default), `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk

##### `0x71` — **TwrwrSd** (OneOf)
> write to write timing same DIMM same chip select.
- VarStore `0x5000` · offset `0xd3` · 8-bit · range `0x1`..`0xff`
- options: `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `255` = Auto (default), `1` = 1 Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk

##### `0x72` — **TwrwrDd** (OneOf)
> write to write timing same DIMM same chip select.
- VarStore `0x5000` · offset `0xd4` · 8-bit · range `0x1`..`0xff`
- options: `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `255` = Auto (default), `1` = 1 Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk

##### `0x73` — **TrdrdSc** (OneOf)
> write to write timing same DIMM same chip select.
- VarStore `0x5000` · offset `0xd5` · 8-bit · range `0x1`..`0xff`
- options: `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `255` = Auto (default)

##### `0x74` — **TrdrdSd** (OneOf)
> write to write timing same DIMM same chip select.
- VarStore `0x5000` · offset `0xd6` · 8-bit · range `0x1`..`0xff`
- options: `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `255` = Auto (default), `1` = 1 Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk

##### `0x75` — **TrdrdDd** (OneOf)
> write to write timing same DIMM same chip select.
- VarStore `0x5000` · offset `0xd7` · 8-bit · range `0x1`..`0xff`
- options: `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `255` = Auto (default), `1` = 1 Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk

##### `0x76` — **Tcke** (OneOf)
> Specifies the CKE minimum high and low pulse width in memory clock cycles.
- VarStore `0x5000` · offset `0xd8` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = 1 Clk, `2` = 2 Clk, `3` = 3 Clk, `4` = 4 Clk, `5` = 5 Clk, `6` = 6 Clk, `7` = 7 Clk, `8` = 8 Clk, `9` = 9 Clk, `10` = 0Ah Clk, `11` = 0Bh Clk, `12` = 0Ch Clk, `13` = 0Dh Clk, `14` = 0Eh Clk, `15` = 0Fh Clk, `16` = 10h Clk, `17` = 11h Clk, `18` = 12h Clk, `19` = 13h Clk, `20` = 14h Clk, `21` = 15h Clk, `22` = 16h Clk, `23` = 17h Clk, `24` = 18h Clk, `25` = 19h Clk, `26` = 1Ah Clk, `27` = 1Bh Clk, `28` = 1Ch Clk, `29` = 1Dh Clk, `30` = 1Eh Clk, `31` = 1Fh Clk

#### Form `0x703a` — DRAM Controller Configuration

_Navigation (children):_
- → `0x7041` **DRAM Power Options**
  - DRAM Power Options

_Settings:_

##### `0x78` — **Cmd2T** (OneOf)
> Select between 1T and 2T mode on ADDR/CMD
- VarStore `0x5000` · offset `0xd9` · 8-bit · range `0x0`..`0xff`
- options: `0` = 1T, `1` = 2T, `255` = Auto (default)

##### `0x79` — **Gear Down Mode** (OneOf)
> No help string
- VarStore `0x5000` · offset `0xda` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

#### Form `0x7041` — DRAM Power Options

_Settings:_

##### `0x7a` — **Power Down Enable** (OneOf)
> Enable or disable DDR power down mode
- VarStore `0x5000` · offset `0xdb` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

#### Form `0x703b` — CAD Bus Configuration

_Settings:_

##### `0x7b` — **CAD Bus Timing User Controls** (OneOf)
> Setup time on CAD bus signals to Auto or Manual
- VarStore `0x5000` · offset `0xdc` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Manual

##### `0x7c` — **AddrCmdSetup** (Numeric)
> Setup time on CAD bus signals. Valid values 3Fh-0h.
- VarStore `0x5000` · offset `0xdd` · 8-bit · range `0x0`..`0x3f` · default `0`

##### `0x7d` — **CsOdtSetup** (Numeric)
> Setup time on CAD bus signals. Valid values 3Fh-0h.
- VarStore `0x5000` · offset `0xde` · 8-bit · range `0x0`..`0x3f` · default `0`

##### `0x7e` — **CkeSetup** (Numeric)
> Setup time on CAD bus signals. Valid values 3Fh-0h.
- VarStore `0x5000` · offset `0xdf` · 8-bit · range `0x0`..`0x3f` · default `0`

##### `0x7f` — **CAD Bus Drive Strength User Controls** (OneOf)
> Drive Strength on CAD bus signals to Auto or Manual
- VarStore `0x5000` · offset `0xe0` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Manual

##### `0x80` — **ClkDrvStren** (OneOf)
> No help string
- VarStore `0x5000` · offset `0xe1` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 120.0 Ohm, `1` = 60.0 Ohm, `3` = 40.0 Ohm, `7` = 30.0 Ohm, `15` = 24.0 Ohm, `31` = 20.0 Ohm

##### `0x81` — **AddrCmdDrvStren** (OneOf)
> No help string
- VarStore `0x5000` · offset `0xe2` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 120.0 Ohm, `1` = 60.0 Ohm, `3` = 40.0 Ohm, `7` = 30.0 Ohm, `15` = 24.0 Ohm, `31` = 20.0 Ohm

##### `0x82` — **CsOdtDrvStren** (OneOf)
> No help string
- VarStore `0x5000` · offset `0xe3` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 120.0 Ohm, `1` = 60.0 Ohm, `3` = 40.0 Ohm, `7` = 30.0 Ohm, `15` = 24.0 Ohm, `31` = 20.0 Ohm

##### `0x83` — **CkeDrvStren** (OneOf)
> No help string
- VarStore `0x5000` · offset `0xe4` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = 120.0 Ohm, `1` = 60.0 Ohm, `3` = 40.0 Ohm, `7` = 30.0 Ohm, `15` = 24.0 Ohm, `31` = 20.0 Ohm

#### Form `0x703c` — Data Bus Configuration

_Settings:_

##### `0x84` — **Data Bus Configuration User Controls** (OneOf)
> Specify the mode for drive strength to Auto or Manual
- VarStore `0x5000` · offset `0xe5` · 8-bit · range `0x1`..`0xff`
- options: `255` = Auto (default), `1` = Manual

##### `0x85` — **RttNom** (OneOf)
> No help string
- VarStore `0x5000` · offset `0xe6` · 8-bit · range `0x0`..`0xff`
- options: `0` = Rtt_Nom Disable, `1` = RZQ/4, `2` = RZQ/2, `3` = RZQ/6, `4` = RZQ/1, `5` = RZQ/5, `6` = RZQ/3, `7` = RZQ/7, `255` = Auto (default)

##### `0x86` — **RttWr** (OneOf)
> No help string
- VarStore `0x5000` · offset `0xe7` · 8-bit · range `0x0`..`0xff`
- options: `0` = Dynamic ODT Off, `1` = RZQ/2, `2` = RZQ/1, `3` = Hi-Z, `4` = RZQ/3, `255` = Auto (default)

##### `0x87` — **RttPark** (OneOf)
> No help string
- VarStore `0x5000` · offset `0xe8` · 8-bit · range `0x0`..`0xff`
- options: `0` = Rtt_PARK Disable, `1` = RZQ/4, `2` = RZQ/2, `3` = RZQ/6, `4` = RZQ/1, `5` = RZQ/5, `6` = RZQ/3, `7` = RZQ/7, `255` = Auto (default)

#### Form `0x703d` — Common RAS

_Navigation (children):_
- → `0x7042` **ECC Configuration**
  - ECC Configuration

_Settings:_

##### `0x88` — **Data Poisoning** (OneOf)
> Enable/disable data poisoning: UMC_CH::EccCtrl[UcFatalEn] UMC_CH::EccCtrl[WrEccEn] Should be enabled/disabled together.
- VarStore `0x5000` · offset `0xe9` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

#### Form `0x7042` — ECC Configuration

_Settings:_

##### `0x8a` — **DRAM ECC Symbol Size** (OneOf)
> DRAM ECC Symbol Size (x4/x8) - UMC_CH::EccCtrl[EccSymbolSize]
- VarStore `0x5000` · offset `0xea` · 8-bit · range `0x0`..`0xff`
- options: `0` = x4, `1` = x8, `255` = Auto (default)

##### `0x8b` — **DRAM ECC Enable** (OneOf)
> Use this option to enable / disable DRAM ECC. Auto will set ECC to enable.
- VarStore `0x5000` · offset `0xeb` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

#### Form `0x703e` — Security

_Settings:_

##### `0x7043` — **TSME** (OneOf)
> Transparent SME: AddrTweakEn = 1; ForceEncrEn =0; DataEncrEn = 1
- VarStore `0x5000` · offset `0xec` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0x7044` — **Data Scramble** (OneOf)
> Data scrambling: DataScrambleEn
- VarStore `0x5000` · offset `0xed` · 8-bit · range `0x0`..`0xff`
- options: `1` = Enabled, `0` = Disabled, `255` = Auto (default)

#### Form `0x7036` — DRAM Memory Mapping

_Settings:_

##### `0x8c` — **Chipselect Interleaving** (OneOf)
> Interleave memory blocks across the DRAM chip selects for node 0.
- VarStore `0x5000` · offset `0xee` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `255` = Auto (default)

##### `0x8d` — **BankGroupSwap** (OneOf)
> No help string
- VarStore `0x5000` · offset `0xef` · 8-bit · range `0x0`..`0xff`
- options: `1` = Enabled, `0` = Disabled, `255` = Auto (default)

##### `0x8e` — **BankGroupSwapAlt** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1d3` · 8-bit · range `0x0`..`0xff`
- options: `1` = Enabled, `0` = Disabled, `255` = Auto (default)

##### `0x8f` — **Address Hash Bank** (OneOf)
> Enable or disable bank address hashing
- VarStore `0x5000` · offset `0xf0` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0x90` — **Address Hash CS** (OneOf)
> Enable or disable CS address hashing
- VarStore `0x5000` · offset `0xf1` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `1` = Enabled, `0` = Disabled

##### `0x91` — **SPD Read Optimization** (OneOf)
> Enable or disable SPD Read Optimization, Enabled - SPD reads are skipped for Reserved fields and most of upper 256 Bytes, Disabled - read all 512 SPD Bytes
- VarStore `0x5000` · offset `0x1d4` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto, `1` = Enabled, `0` = Disabled

#### Form `0x7037` — NVDIMM

#### Form `0x7038` — Memory MBIST

_Settings:_

##### `0x92` — **MBIST Enable** (OneOf)
> Enable or disable Memory MBIST
- VarStore `0x5000` · offset `0xf2` · 8-bit · range `0x0`..`0x1`
- options: `0` = Disabled (default), `1` = Enabled

##### `0x93` — **MBIST Test Mode** (OneOf)
> Select MBIST Test Mode -Interface Mode (Tests Single and Multiple CS transactions and Basic Connectivity) or Data Eye Mode (Measures Voltage vs. Timing)
- VarStore `0x5000` · offset `0x1d0` · 8-bit · range `0x0`..`0x1`
- options: `0` = Interface Mode (default), `1` = Data Eye Mode

##### `0x94` — **MBIST Aggressors** (OneOf)
> Enable or disable MBIST Aggressor test
- VarStore `0x5000` · offset `0xf4` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

##### `0x95` — **MBIST Per Bit Slave Die Reporting** (OneOf)
> Reports 2D Data Eye Results in ABL Log for each DQ, Chipselect, and Channel
- VarStore `0x5000` · offset `0xf5` · 8-bit · range `0x0`..`0xff`
- options: `0` = Disabled, `1` = Enabled, `255` = Auto (default)

#### Form `0x7004` — NBIO Common Options

_Navigation (children):_
- → `0x7045` **NB Configuration**
  - NB Configuration
- → `0x7046` **Fan Control**
  - Fan Control
- → `0x7047` **XFR Enhancement**
  - XFR Enhancement

_Settings:_

##### `0x98` — **NBIO Internal Poison Consumption** (OneOf)
> NBIO Internal Poison Consumption
- VarStore `0x5000` · offset `0xf7` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x99` — **NBIO RAS Control** (OneOf)
> NBIO RAS Control
- VarStore `0x5000` · offset `0xf8` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0x9c` — **cTDP** (Numeric)
> cTDP [W] 0 = Invalid value.
- VarStore `0x5000` · offset `0xfb` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0x9e` — **PSI** (OneOf)
> Disable PSI
- VarStore `0x5000` · offset `0xff` · 8-bit · range `0x1`..`0xf`
- options: `1` = Disabled, `15` = Auto (default)

##### `0x9f` — **ACS Enable** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x100` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0xa0` — **Enable AER Cap** (OneOf)
> Enables Advanced Error Reporting Capability
- VarStore `0x5000` · offset `0x1cf` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0xa1` — **PCIe ARI Support** (OneOf)
> Enables Alternative Routing-ID Interpretation
- VarStore `0x5000` · offset `0x101` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled (default), `1` = Enabled, `15` = Auto

##### `0xa2` — **CLDO_VDDP Control** (OneOf)
> Manual = User can set customized CLDO_VDDP voltage
- VarStore `0x5000` · offset `0x102` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Manual

##### `0xa4` — **HD Audio Enable** (OneOf)
> Enable or Disable HD Audio
- VarStore `0x5000` · offset `0x107` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0xa5` — **Block PCIe Loopback** (OneOf)
> Block PCIe loopback mode for hot plug slots
- VarStore `0x5000` · offset `0x1d2` · 8-bit · range `0x0`..`0x2`
- options: `0` = Disabled, `1` = Enabled, `2` = Auto (default)

##### `0xa6` — **Force PCIe gen speed** (OneOf)
> Force PCIe gen speed to Gen1 or Gen3
- VarStore `0x5000` · offset `0x1c6` · 8-bit · range `0x1`..`0xf`
- options: `1` = Gen1, `3` = Gen3, `15` = Auto (default)

##### `0xa8` — **Processor temperature limit** (Numeric)
> sets the thermal throttle limit[C] for the CPU
- VarStore `0x5000` · offset `0x130` · 32-bit · range `0x0`..`0xffffffff` · default `0`

##### `0xa9` — **Managed overclocking Control** (OneOf)
> Managed overclocking Control
- VarStore `0x5000` · offset `0x1c0` · 8-bit · range `0x1`..`0xfe`
- options: `1` = MOC_X, `2` = MOC_PT, `254` = Auto (default)

##### `0xac` — **Mode0** (OneOf)
> Enable/Disable Mode0
- VarStore `0x5000` · offset `0x1c7` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

#### Form `0x7045` — NB Configuration

_Settings:_

##### `0xad` — **IOMMU** (OneOf)
> Enable/Disable IOMMU
- VarStore `0x5000` · offset `0x10a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled (default), `1` = Enabled, `15` = Auto

#### Form `0x7046` — Fan Control

_Settings:_

##### `0xb0` — **Force PWM** (Numeric)
> Specify the PWM to force the fan to [0-100]
- VarStore `0x5000` · offset `0x10d` · 8-bit · range `0x0`..`0x64` · default `0`

##### `0xb2` — **Low Temperature** (Numeric)
> Low Temperature ['C]
- VarStore `0x5000` · offset `0x10f` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0xb3` — **Medium Temperature** (Numeric)
> Medium Temperature ['C]
- VarStore `0x5000` · offset `0x110` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0xb4` — **High Temperature** (Numeric)
> High Temperature ['C]
- VarStore `0x5000` · offset `0x111` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0xb5` — **Critical Temperature** (Numeric)
> Critical Temperature ['C]
- VarStore `0x5000` · offset `0x112` · 8-bit · range `0x0`..`0xff` · default `0`

##### `0xb6` — **Low Pwm** (Numeric)
> Low Pwm [0-100]
- VarStore `0x5000` · offset `0x113` · 8-bit · range `0x0`..`0x64` · default `0`

##### `0xb7` — **Medium Pwm** (Numeric)
> Medium Pwm [0-100]
- VarStore `0x5000` · offset `0x114` · 8-bit · range `0x0`..`0x64` · default `0`

##### `0xb8` — **High Pwm** (Numeric)
> High Pwm [0-100]
- VarStore `0x5000` · offset `0x115` · 8-bit · range `0x0`..`0x64` · default `0`

##### `0xb9` — **Temperature Hysteresis** (Numeric)
> Temperature Hysteresis ['C]
- VarStore `0x5000` · offset `0x116` · 8-bit · range `0x0`..`0xff` · default `0`

#### Form `0x7047` — XFR Enhancement

_Navigation (children):_
- → `0x7048` **Declined**
  - Declined
- → `0x7049` **Accepted**
  - Accepted

#### Form `0x7048` — Declined

#### Form `0x7049` — Accepted

#### Form `0x7005` — FCH Common Options

_Navigation (children):_
- → `0x704a` **SATA Configuration Options**
  - SATA Configuration Options
- → `0x704b` **USB Configuration Options**
  - USB Configuration Options
- → `0x704c` **SD (Secure Digital) Options**
  - SD (Secure Digital) Options
- → `0x704d` **Ac Power Loss Options**
  - Ac Power Loss Options
- → `0x704e` **I2C Configuration Options**
  - I2C Configuration Options
- → `0x704f` **Uart Configuration Options**
  - Uart Configuration Options
- → `0x7050` **ESPI Configuration Options**
  - ESPI Configuration Options
- → `0x7051` **XGBE Configuration Options**
  - XGBE Configuration Options
- → `0x7052` **eMMC Options**
  - eMMC Options

#### Form `0x704a` — SATA Configuration Options

_Settings:_

##### `0x7053` — **SATA Controller** (OneOf)
> Disable or enable OnChip SATA controller
- VarStore `0x5000` · offset `0x134` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xc8` — **SATA Mode** (OneOf)
> Select OnChip SATA Type
- VarStore `0x5000` · offset `0x135` · 8-bit · range `0x1`..`0xf`
- options: `2` = AHCI (default), `5` = AHCI as ID 0x7904, `15` = Auto, `1` = RAID

##### `0xc9` — **Sata RAS Support** (OneOf)
> Disable or enable Sata RAS Support
- VarStore `0x5000` · offset `0x136` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xca` — **Sata Disabled AHCI Prefetch Function** (OneOf)
> Disable or enable Sata Disabled AHCI Prefetch Function
- VarStore `0x5000` · offset `0x137` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xcb` — **Aggresive SATA Device Sleep Port 0** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x138` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xcc` — **DevSleep0 Port Number** (Numeric)
> DEVSLP port 0
- VarStore `0x5000` · offset `0x139` · 8-bit · range `0x0`..`0x7` · default `0`

##### `0xcd` — **Aggresive SATA Device Sleep Port 1** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x13a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xce` — **DevSleep1 Port Number** (Numeric)
> DEVSLP port 1
- VarStore `0x5000` · offset `0x13b` · 8-bit · range `0x0`..`0x7` · default `0`

#### Form `0x704b` — USB Configuration Options

_Navigation (children):_
- → `0x7054` **MCM USB enable**
  - MCM USB enable
- → `0x7055` **XHCI Port 0 PHY Parameter Adjustment**
  - XHCI Port 0 PHY Parameter Adjustment
- → `0x7056` **XHCI Port 1 PHY Parameter Adjustment**
  - XHCI Port 1 PHY Parameter Adjustment
- → `0x7057` **XHCI Port 2 PHY Parameter Adjustment**
  - XHCI Port 2 PHY Parameter Adjustment
- → `0x7058` **XHCI Port 3 PHY Parameter Adjustment**
  - XHCI Port 3 PHY Parameter Adjustment

_Settings:_

##### `0xcf` — **XHCI controller enable** (OneOf)
> Enable or disable USB3 controller.
- VarStore `0x5000` · offset `0x13c` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

#### Form `0x7054` — MCM USB enable

_Settings:_

##### `0xd5` — **XHCI Controller1 enable (Die1)** (OneOf)
> Enable or disable USB3 controller.
- VarStore `0x5000` · offset `0x13d` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0xd6` — **XHCI2 enable (MCM1/Die0)** (OneOf)
> Enable or disable USB3 controller.
- VarStore `0x5000` · offset `0x13e` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

##### `0xd7` — **XHCI3 enable (MCM1/Die1)** (OneOf)
> Enable or disable USB3 controller.
- VarStore `0x5000` · offset `0x13f` · 8-bit · range `0x0`..`0xf`
- options: `1` = Enabled, `0` = Disabled, `15` = Auto (default)

#### Form `0x7055` — XHCI Port 0 PHY Parameter Adjustment

_Settings:_

##### `0xd8` — **tx_vboost_lvl** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x140` · 8-bit · range `0x2`..`0x5`
- options: `3` = 3h, `4` = 4h, `5` = 5h, `2` = 2h (default)

##### `0xd9` — **rx_eq** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x141` · 8-bit · range `0x2`..`0x4`
- options: `2` = 2h, `3` = 3h (default), `4` = 4h

##### `0xda` — **los_bias** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x142` · 8-bit · range `0x1`..`0x7`
- options: `1` = 1h, `2` = 2h, `3` = 3h, `4` = 4h, `5` = 5h (default), `6` = 6h, `7` = 7h

##### `0xdb` — **pcs_tx_deemph_3p5db** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x143` · 8-bit · range `0x0`..`0x3f` · default `28`

##### `0xdc` — **pcs_tx_deemph_6db** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x144` · 8-bit · range `0x0`..`0x3f` · default `28`

##### `0xdd` — **pcs_tx_swing_full** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x145` · 8-bit · range `0x0`..`0x7f` · default `127`

#### Form `0x7056` — XHCI Port 1 PHY Parameter Adjustment

_Settings:_

##### `0xde` — **tx_vboost_lvl** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x146` · 8-bit · range `0x2`..`0x5`
- options: `3` = 3h, `4` = 4h, `5` = 5h, `2` = 2h (default)

##### `0xdf` — **rx_eq** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x147` · 8-bit · range `0x2`..`0x4`
- options: `2` = 2h, `3` = 3h (default), `4` = 4h

##### `0xe0` — **los_bias** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x148` · 8-bit · range `0x1`..`0x7`
- options: `1` = 1h, `2` = 2h, `3` = 3h, `4` = 4h, `5` = 5h (default), `6` = 6h, `7` = 7h

##### `0xe1` — **pcs_tx_deemph_3p5db** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x149` · 8-bit · range `0x0`..`0x3f` · default `28`

##### `0xe2` — **pcs_tx_deemph_6db** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x14a` · 8-bit · range `0x0`..`0x3f` · default `28`

##### `0xe3` — **pcs_tx_swing_full** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x14b` · 8-bit · range `0x0`..`0x7f` · default `127`

#### Form `0x7057` — XHCI Port 2 PHY Parameter Adjustment

_Settings:_

##### `0xe4` — **tx_vboost_lvl** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x14c` · 8-bit · range `0x2`..`0x5`
- options: `3` = 3h, `4` = 4h, `5` = 5h, `2` = 2h (default)

##### `0xe5` — **rx_eq** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x14d` · 8-bit · range `0x2`..`0x4`
- options: `2` = 2h, `3` = 3h (default), `4` = 4h

##### `0xe6` — **los_bias** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x14e` · 8-bit · range `0x1`..`0x7`
- options: `1` = 1h, `2` = 2h, `3` = 3h, `4` = 4h, `5` = 5h (default), `6` = 6h, `7` = 7h

##### `0xe7` — **pcs_tx_deemph_3p5db** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x14f` · 8-bit · range `0x0`..`0x3f` · default `28`

##### `0xe8` — **pcs_tx_deemph_6db** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x150` · 8-bit · range `0x0`..`0x3f` · default `28`

##### `0xe9` — **pcs_tx_swing_full** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x151` · 8-bit · range `0x0`..`0x7f` · default `127`

#### Form `0x7058` — XHCI Port 3 PHY Parameter Adjustment

_Settings:_

##### `0xea` — **tx_vboost_lvl** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x152` · 8-bit · range `0x2`..`0x5`
- options: `3` = 3h, `4` = 4h, `5` = 5h, `2` = 2h (default)

##### `0xeb` — **rx_eq** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x153` · 8-bit · range `0x2`..`0x4`
- options: `2` = 2h, `3` = 3h (default), `4` = 4h

##### `0xec` — **los_bias** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x154` · 8-bit · range `0x1`..`0x7`
- options: `1` = 1h, `2` = 2h, `3` = 3h, `4` = 4h, `5` = 5h (default), `6` = 6h, `7` = 7h

##### `0xed` — **pcs_tx_deemph_3p5db** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x155` · 8-bit · range `0x0`..`0x3f` · default `28`

##### `0xee` — **pcs_tx_deemph_6db** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x156` · 8-bit · range `0x0`..`0x3f` · default `28`

##### `0xef` — **pcs_tx_swing_full** (Numeric)
> No help string
- VarStore `0x5000` · offset `0x157` · 8-bit · range `0x0`..`0x7f` · default `127`

#### Form `0x704c` — SD (Secure Digital) Options

_Settings:_

##### `0xf0` — **SD Configuration Mode** (OneOf)
> Select SD Mode
- VarStore `0x5000` · offset `0x158` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled (default), `1` = Ver2.0, `6` = SdDump, `15` = Auto (Version 2.0 + Low Speed)

#### Form `0x704d` — Ac Power Loss Options

_Settings:_

##### `0xf1` — **Ac Loss Control** (OneOf)
> Select Ac Loss Control Method
- VarStore `0x5000` · offset `0x159` · 8-bit · range `0x0`..`0x3`
- options: `0` = Always Off (default), `1` = Always On, `2` = Reserved, `3` = Previous

#### Form `0x704e` — I2C Configuration Options

_Settings:_

##### `0xf2` — **I2C 0 Enable** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x15a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xf3` — **I2C 1 Enable** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x15b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xf4` — **I2C 2 Enable** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x15c` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xf5` — **I2C 3 Enable** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x15d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xf6` — **I2C 4 Enable** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x15e` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xf7` — **I2C 5 Enable** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x15f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x704f` — Uart Configuration Options

_Settings:_

##### `0xf8` — **Uart 0 Enable** (OneOf)
> Uart 0 has no HW FC if Uart 2 is enabled
- VarStore `0x5000` · offset `0x160` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled (default), `1` = Enabled, `15` = Auto

##### `0xf9` — **Uart 0 Legacy Options** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x161` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = 0x2E8, `2` = 0x2F8, `3` = 0x3E8, `4` = 0x3F8, `15` = Auto (default)

##### `0xfa` — **Uart 1 Enable** (OneOf)
> Uart 1 has no HW FC if Uart 3 is enabled
- VarStore `0x5000` · offset `0x162` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xfb` — **Uart 1 Legacy Options** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x163` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = 0x2E8, `2` = 0x2F8, `3` = 0x3E8, `4` = 0x3F8, `15` = Auto (default)

##### `0xfc` — **Uart 2 Enable (no HW FC)** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x164` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xfd` — **Uart 2 Legacy Options** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x165` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = 0x2E8, `2` = 0x2F8, `3` = 0x3E8, `4` = 0x3F8, `15` = Auto (default)

##### `0xfe` — **Uart 3 Enable (no HW FC)** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x166` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0xff` — **Uart 3 Legacy Options** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x167` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = 0x2E8, `2` = 0x2F8, `3` = 0x3E8, `4` = 0x3F8, `15` = Auto (default)

#### Form `0x7050` — ESPI Configuration Options

_Settings:_

##### `0x100` — **ESPI Enable** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x168` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7051` — XGBE Configuration Options

_Settings:_

##### `0x101` — **AMD XGBE Controller 0** (OneOf)
> Enable or Disable Ethernet Controller 0
- VarStore `0x5000` · offset `0x169` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x102` — **AMD XGBE Controller 1** (OneOf)
> Enable or Disable Ethernet Controller 1
- VarStore `0x5000` · offset `0x16a` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x103` — **AMD XGBE Controller 2** (OneOf)
> Enable or Disable Ethernet Controller 2
- VarStore `0x5000` · offset `0x16b` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x104` — **AMD XGBE Controller 3** (OneOf)
> Enable or Disable Ethernet Controller 3
- VarStore `0x5000` · offset `0x16c` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x105` — **AMD XGBE Controller 4** (OneOf)
> Enable or Disable Ethernet Controller 4
- VarStore `0x5000` · offset `0x16d` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x106` — **AMD XGBE Controller 5** (OneOf)
> AMD XGBE Controller 5
- VarStore `0x5000` · offset `0x16e` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x107` — **AMD XGBE Controller 6** (OneOf)
> Enable or Disable Ethernet Controller 6
- VarStore `0x5000` · offset `0x16f` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x108` — **AMD XGBE Controller 7** (OneOf)
> Enable or Disable Ethernet Controller 7
- VarStore `0x5000` · offset `0x170` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7052` — eMMC Options

_Settings:_

##### `0x109` — **eMMC/SD Configure** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x171` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = SD Normal Speed, `2` = SD High Speed, `3` = SD UHSI-SDR50, `4` = SD UHSI-DDR50, `5` = SD UHSI-SDR104, `6` = eMMC Emmc Backward Compatibility, `7` = eMMC High Speed SDR, `8` = eMMC High Speed DDR, `9` = eMMC HS200, `10` = eMMC HS400, `11` = eMMC HS300, `15` = Auto (default)

##### `0x10a` — **Driver Type** (OneOf)
> Bios will select MS driver for SD selections.
- VarStore `0x5000` · offset `0x172` · 8-bit · range `0x0`..`0xf`
- options: `0` = AMD eMMC Driver, `1` = MS Driver, `15` = Auto (default)

##### `0x10b` — **D3 Cold Support** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x173` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

##### `0x10c` — **eMMC Boot** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x174` · 8-bit · range `0x0`..`0xf`
- options: `0` = Disabled, `1` = Enabled, `15` = Auto (default)

#### Form `0x7007` — NTB Common Options

_Settings:_

##### `0x10d` — **NTB Enable** (OneOf)
> Enable NTB
- VarStore `0x5000` · offset `0x1ad` · 8-bit · range `0x0`..`0x1`
- options: `0` = Auto (default), `1` = Enabled

##### `0x10e` — **NTB Location** (OneOf)
> No help string
- VarStore `0x5000` · offset `0x1ae` · 8-bit · range `0x0`..`0xff`
- options: `255` = Auto (default), `0` = Socket0-Die0, `1` = Socket0-Die1, `2` = Socket0-Die2, `3` = Socket0-Die3, `4` = Socket1-Die0, `5` = Socket1-Die1, `6` = Socket1-Die2, `7` = Socket1-Die3

##### `0x10f` — **NTB active on PCIeCore** (OneOf)
> NTB enable on PCIe Core
- VarStore `0x5000` · offset `0x1af` · 8-bit · range `0x0`..`0x10`
- options: `15` = Auto (default), `0` = Core0, `16` = Core1

##### `0x110` — **NTB Mode** (OneOf)
> Select NTB Mode (Core 0, Port 0)
- VarStore `0x5000` · offset `0x1b0` · 8-bit · range `0x0`..`0xf`
- options: `0` = NTB Disabled, `1` = NTB Primary, `2` = NTB Secondary, `3` = NTB Random, `15` = Auto (default)

##### `0x111` — **Link Speed** (OneOf)
> Select Link Speed for NTB Mode (Core 0, Port 0)
- VarStore `0x5000` · offset `0x1b1` · 8-bit · range `0x0`..`0xf`
- options: `0` = Max Speed, `1` = Gen 1, `2` = Gen 2, `3` = Gen 3, `15` = Auto (default)
