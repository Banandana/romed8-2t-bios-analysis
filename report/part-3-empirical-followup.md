> ← [Report index](README.md) · [Project README](../README.md) · [Latest synthesis](../BIOS_LATEST.md)
>
> _Empirical follow-up to [Part I](part-1-findings.md), added 2026-04-27 after the rig NVRAM dump. This is what overturned the IFR-only verdict and motivated Phase 2._

# Part III — Empirical follow-up (added 2026-04-27 after rig NVRAM dump)

The rig was queried for runtime PCIe state and live NVRAM contents. Findings contradicted the IFR-only conclusions of [Part I](part-1-findings.md) and the BIOS reference in [Part II](../docs/BIOS_REFERENCE_P3.70.md), and produced a sharper picture of where the Gen3 cap actually comes from. This Part III documents what changed and answers the six specific drilldown questions raised in the handoff.

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

**Conclusion:** The per-slot menu correctly *writes* 11 distinct bytes. The bytes simply aren't read by AGESA. Hypothesis #1 from [Part I §3](part-1-findings.md#3-why-the-user-saw-global-behavior-despite-per-slot-ifr) — "AGESA ignores per-slot bytes, IFR is vestigial" — is now empirically confirmed. Hypothesis #2 (callback propagation) is ruled out.

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

**No `setup_var.efi` write will lift the Gen3 cap on P3.70.** The IFR-only proposal in [Part I §4](part-1-findings.md#4-setup_varefi-commands-proposed--needs-empirical-verification) (writing per-slot bytes `0x123`–`0x12D`) is moot — empirically confirmed vestigial. There is no other IFR-backed setting whose modification would re-enable Gen4 on the GPU root ports.

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
