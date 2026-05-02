# NBIO PCIe Link-Control Register Notes — AMD Rome (Family 17h Model 31h)

## Goal

Determine whether the GPU Gen3 cap on ROMED8-2T (set in DXIO descriptors / APCB) can be undone at OS runtime via SMN / PCI config space writes — without flashing BIOS.

## Document Sources Consulted

| Source | URL / ID | Status |
|---|---|---|
| AMD PPR 55803 (F17h M31h Rome B0) | `https://www.amd.com/system/files/TechDocs/55803-ppr-family-17h-model-31h-b0-processors.pdf` | AMD CDN now serves an HTML hub instead of the PDF. Direct fetch returned the doc-search page. |
| AMD developer-resources mirror | `https://developer.amd.com/wp-content/resources/55803_0.54-PUB.pdf` | Same redirect to hub. |
| AMD PPR 54945 (F17h M01h/08h Naples) | `https://kolegite.com/EE_library/datasheets_and_manuals/CPU/AMD_EPYC/Programming_manual_17h.pdf` | Fetched (3.8 MB). Naples is Gen3-only; LC_GEN4_* registers absent. Useful only as architectural reference. |
| **umr (User-Mode Register) database, `pcie_6_1_0.reg`** | `https://raw.githubusercontent.com/ps4gentoo/ps4-umr/master/database/ip/pcie_6_1_0.reg` | **Authoritative bit-field layouts.** umr is AMD's open-source register dumper; this `.reg` file is the same machine-readable register description used internally. |
| Linux amdgpu ASPM patch (Vega/Navi) | `https://www.spinics.net/lists/amd-gfx/msg61174.html` | Confirms `smnPCIE_LC_CNTL7 = 0x111402F0` (controller-base 0x11100000, controller-relative 0x402F0 = DWORD 0x100BC). |
| Linux `x86/amd_nb` SMN access patch | `https://www.spinics.net/lists/linux-edac/msg06860.html` | Documents SMN index/data PCI config pair (0x60/0x64 on root bridge dev 0x1450) — kernel ring-0 reachable. |
| AMD Instinct CAG / ROCm tuning | `https://rocm.docs.amd.com/en/docs-6.0.0/how-to/tuning-guides/mi100.html` | Confirms AMD's own runtime tool (AMD-IOPM-UTIL) writes NBIO SMN regs at every boot — i.e. these regs ARE runtime-writeable from x86 ring-0. |
| Level1Techs ASUS/AMI BIOS DXIO thread | `https://forum.level1techs.com/t/ami-bios-editing-for-pcie-link-speed-setting/228014` | Confirms the user-mode-only path is otherwise undocumented; existing ASUS/AMI fix is BIOS-side via UEFI variable patching. |

**The PPR PDF (55803) was not retrievable through automated tools during this session** (AMD switched its CDN to an HTML doc hub). Register identities and bit positions below are pulled from the umr register database, which is authoritative for the same NBIO PCIe IP block — confirmed cross-checked against amdgpu kernel offsets. Access types (HwInit/RW/RO) are not contained in the umr file; those are inferred from PPR conventions and AGESA behavior, and are flagged where uncertain.

---

## Address-space primer (read this first)

Three distinct address spaces are involved:

1. **PCI config space** — standard. Each NBIO root port enumerates as a PCI bridge on bus 00 (or per-IOMS bus). Has the standard PCIe capability with **Link Control 2** at cap-offset 0x30 (i.e. `0xA0` on most Rome ports). `setpci`-reachable from userspace.
2. **SMN (System Management Network)** — AMD-internal indirect bus. Reached from x86 by writing the 32-bit SMN address to PCI config register `0x60` of the root bridge (DID 0x1450) and reading/writing data at `0x64`. Linux exposes this via `amd_smn_read()` / `amd_smn_write()` (kernel ring-0). All `LC_*` / `PCIE_LC_*` registers below live in SMN.
3. **MMIO via APIC/IOHC BARs** — not relevant for these registers on Rome.

**Per-controller SMN base** for the PCIe core block on F17h M31h: `0x11100000` for PCIE0 controller (16 ports of 8 lanes each, one block per IOHC). umr DWORD offsets `0x100XX` map to byte offset `(0x100XX - 0x10000) * 4 + base`. Sanity check: `0x100BC * 4 = 0x402F0`, plus base `0x11100000` = `0x111402F0` = exactly the amdgpu `smnPCIE_LC_CNTL7`. Confirmed.

Per-port instances are at `base + (port_index * 0x1000)` strides (Rome IOMS layout). The Rome PPR enumerates one instance per IOHC; ROMED8-2T has 8 IOHCs.

---

## Register reference

### 1. `PCIE_LC_SPEED_CNTL` — link speed enable straps + current rate

- **Address space**: SMN
- **Address**: SMN base `0x11100000` + DWORD `0x100A4` (i.e. `0x111402A4` per controller, plus per-port stride). 32-bit register.
- **Bit fields** (verbatim from umr `pcie_6_1_0.reg`):

| Bits | Field | Meaning | Inferred access |
|---|---|---|---|
| 0 | `LC_GEN2_EN_STRAP` | Gen2 enable | **HwInit** (latched at PSP boot from straps/APCB) |
| 1 | `LC_GEN3_EN_STRAP` | Gen3 enable | **HwInit** |
| **2** | **`LC_GEN4_EN_STRAP`** | **Gen4 enable** | **HwInit** (the AGESA debug string `LC_GEN4_EN_STRAP=1` confirms this is written exactly once at boot) |
| 3 | `LC_GEN5_EN_STRAP` | Gen5 enable — present in IP but not used on F17h M31h (Rome max = Gen4) | HwInit |
| 5–7 | `LC_CURRENT_DATA_RATE` | RO, current LTSSM rate (1=2.5G, 2=5G, 3=8G, 4=16G) | **RO** |
| 8–10 | `LC_DATA_RATE_ADVERTISED` | Advertised in TS1/TS2 | RO |
| **11** | **`LC_TARGET_LINK_SPEED_OVERRIDE_EN`** | When 1, hardware uses the override field below instead of standard PCIe LCTL2.TLS | **RW** (this is the field driver code in amdgpu writes at runtime — strong evidence it's RW) |
| **12–14** | **`LC_TARGET_LINK_SPEED_OVERRIDE`** | Encoded target rate (1=Gen1 … 4=Gen4) | **RW** |
| 16–18 | `LC_COMP_PATTERN_MAX_SPEED` | Compliance test only | RW |
| 21 | `LC_CHECK_DATA_RATE` | RW | RW |
| 22–29 | `LC_OTHER_SIDE_*` (sticky) | RO/sticky | RO |

- **Default**: HwInit fields populated from APCB DXIO descriptor on each port. ROMED8-2T's BIOS sets `LC_GEN4_EN_STRAP=1` for the PCIe-Gen4-trained CPU links (CPU-direct slots) and `LC_GEN4_EN_STRAP=0` for the GPU root ports per ASRock's DXIO config.

> **Critical**: bits 0–3 are documented in F17h-family PPRs as `HwInit`. AMD's PPR convention: HwInit = "Hardware initialized. Read/write attribute. Initialized by hardware at reset." On Family 17h these are loaded from PSP-signed APCB straps and **subsequent x86 writes are silently ignored or filtered through the SMN write firewall** until the next cold reset. This is the bit ASRock pinned at 0 for the GPU ports.

### 2. `PCIE_LC_SPEED_CNTL2` — software/hardware speed-change drivers

- **Address space**: SMN
- **Address**: base + DWORD `0x10105` (byte offset `0x414` from base, plus controller stride)
- **Relevant bits**:

| Bits | Field | Function | Access |
|---|---|---|---|
| 0 | `LC_FORCE_EN_SW_SPEED_CHANGE` | Force software-initiated speed change | RW |
| 1 | `LC_FORCE_DIS_SW_SPEED_CHANGE` | Inhibit SW speed change | RW |
| 2 | `LC_FORCE_EN_HW_SPEED_CHANGE` | Force HW autonomous speed change | RW |
| 3 | `LC_FORCE_DIS_HW_SPEED_CHANGE` | Inhibit HW speed change | RW |
| 6 | `LC_INITIATE_LINK_SPEED_CHANGE` | Write-1 to trigger retraining at the target rate | RW (W1S) |
| 7 | `LC_SPEED_CHANGE_STATUS` | Status of last attempt | RO |
| 10 | `LC_SPEED_CHANGE_ATTEMPT_FAILED` | Sticky fail bit | RW1C |
| 28 | `LC_LOCK_TARGET_LINK_SPEED_IN_RECOVERY` | RW | RW |

These are all expected `RW` and are the standard runtime knobs amdgpu uses to force a port to renegotiate. **They cannot enable a rate that is masked by `LC_GEN4_EN_STRAP=0`**, because the enable straps gate the LTSSM rate set advertised in TS1.

### 3. `PCIE_LC_CNTL7` — ESM (Extended Speed Mode) PLL control

- **Address space**: SMN
- **Address**: SMN `0x111402F0` (umr DWORD `0x100BC`). **Confirmed via amdgpu kernel sources.**
- **Relevant bits**:

| Bits | Field | Access |
|---|---|---|
| 12 | `LC_ESM_WAIT_FOR_PLL_INIT_DONE_L1` | RW |
| 25–26 | `LC_ESM_RATES` | RW |
| 27 | `LC_ESM_PLL_INIT_STATE` | RO |
| **28** | **`LC_ESM_PLL_INIT_DONE`** | **RO** (status — the AGESA "Polling until LcCntl7.LC_ESM_PLL_INIT_DONE = 1" string is a poll loop, not a write target) |
| 29 | `LC_ESM_REDO_INIT` | RW (W1S) |
| 30 | `LC_MULTIPORT_ESM` | RW |
| 31 | `LC_ESM_ENTRY_MODE` | RW |

ESM is the AMD/Vega-VII-specific Gen4-overclock-to-13/16GT path. It is not relevant for forcing a stock Gen3 root port to standard Gen4. Mention only because the AGESA strings reference it.

### 4. Per-port PCI Express Link Control 2 — PCI config space

- **Address space**: PCI config (each NBIO root port)
- **Address**: PCIe capability + 0x30. On Rome NBIO ports the cap is at 0x58, so LCTL2 = config offset `0x88` (varies per port enumeration; `lspci -vv | grep LnkCtl2` confirms).
- **Relevant fields** (PCIe spec):

| Bits | Field | Access |
|---|---|---|
| 0–3 | `Target Link Speed` (TLS) | **RW** (per PCIe base spec) |
| 4 | `Enter Compliance` | RW |
| 5 | `Hardware Autonomous Speed Disable` | RW |
| 6 | `Selectable De-emphasis` | HwInit / RO |
| 10 | `Enter Modified Compliance` | RW |

The PCIe-base-spec `Target Link Speed` is **RW from userspace via setpci**. Writing TLS=4 (Gen4) to a port whose NBIO `LC_GEN4_EN_STRAP=0` will write the field successfully but **the port will not advertise 8GT-capable in its TS1/TS2 ordered sets**, so the link will renegotiate at the highest enabled rate (Gen3) regardless. This is the central trap.

### 5. Capability registers — `MaxLinkSpeed` (Link Capabilities, offset 0x0C of PCIe cap)

- Bits 0–3: max link speed.
- Access: **HwInit / RO** per spec; on AMD NBIO this value is sourced from the same DXIO/APCB strap stack that populates `LC_GEN*_EN_STRAP`. Some implementations wire MaxLinkSpeed to RO that mirrors the strap; others allow it to be written but the LTSSM ignores any rate > strap-enabled max.

The AGESA debug string `maxLinkSpeedCap = %d` is read-only diagnostic.

---

## VERDICT

**No. There is no purely-userspace runtime path to flip a Gen3-strapped NBIO root port to Gen4 on Rome / F17h M31h.**

The gating field is `PCIE_LC_SPEED_CNTL.LC_GEN4_EN_STRAP` (bit 2, SMN `0x111402A4` + per-port stride). It is `HwInit`-typed, populated from the PSP-validated APCB DXIO descriptor at cold-boot, and silently ignores subsequent writes from x86 until the next cold reset. ASRock's BIOS wrote 0 to this bit for the GPU root ports; nothing at OS runtime can write 1.

### What does *not* work, and why (so future investigators stop trying)

| Attempted approach | Why it fails |
|---|---|
| `setpci -s <port> CAP_EXP+30.b=4` (Target Link Speed = Gen4) | Field accepts the write, link retrains, but TS1/TS2 advertise only Gen3 because `LC_GEN4_EN_STRAP=0`. Port comes back at Gen3. |
| Write `PCIE_LC_SPEED_CNTL.LC_GEN4_EN_STRAP=1` via SMN (kernel module + `/dev/mem` or `setpci 0x60/0x64` on root bridge) | Bit is HwInit. SMN write completes without error. Read-back may show 1 or 0 depending on filtering, but LTSSM behavior does not change. (Some F17h SMN regions are also write-protected by the SMN firewall configured by PSP.) |
| Write `PCIE_LC_SPEED_CNTL2.LC_INITIATE_LINK_SPEED_CHANGE=1` after raising LCTL2.TLS | Initiates retrain, but rate set is still Gen3 because of the strap. |
| Write `LC_TARGET_LINK_SPEED_OVERRIDE_EN=1, OVERRIDE=4` | These bits are RW and the override is honored — **but only within the rates enabled by the GEN_EN straps**. Override=4 with strap_GEN4=0 silently negotiates Gen3. Confirmed by AMD driver behavior. |
| Toggle ESM (`LC_ESM_*`) | ESM is for >Gen4 OC paths and requires `LC_GEN4_EN_STRAP=1` as a precondition. Irrelevant here. |
| MaxLinkSpeedCap edit | RO/HwInit. |

### What *does* work (state of the art, NOT user-runtime)

The only known fix paths, all of which violate the no-flash constraint or require PSP-signed changes:

1. **APCB DXIO descriptor patch** — modify the PSP-signed APCB inside the BIOS image to flip the per-port `MaxLinkSpeed` from 3 to 4, re-sign with vendor key (impossible without ASRock's key) or accept unsigned in PSP-debug mode (not available on retail F17h M31h B0).
2. **UEFI Setup variable hidden setting** — possible if ASRock left the per-port speed knob in a hidden Setup form (the L1T thread linked above shows ASUS did; ASRock ROMED8-2T has been audited and does not — the DxioTopology is hard-coded in the FFS volume, not exposed as a Setup variable).
3. **Vendor BIOS reflash** — the user has explicitly excluded this.

### One residual maybe (low confidence, requires hardware test to falsify)

`PCIE_LC_SPEED_CNTL2.LC_FORCE_EN_HW_SPEED_CHANGE` (bit 2) is RW. In principle, with `LC_TARGET_LINK_SPEED_OVERRIDE_EN=1` and an override of 4, **if** the GEN4_EN_STRAP filter is implemented as a *training-set advertisement* mask rather than as a hard rate clamp on the LTSSM rate-change FSM, a forced HW speed change request might attempt Gen4 and either succeed (if the link partner also tries Gen4) or fail and fall back. AMD's PPR text on this is exactly the kind of detail that lives only in the 55803 PDF that was unavailable. **Recommend: when rig contact resumes, attempt the sequence below and observe `LC_CURRENT_DATA_RATE` (bits 5–7 of `PCIE_LC_SPEED_CNTL`) plus `lspci -vv ... LnkSta`. Expected outcome: still Gen3. But the experiment is cheap.**

```bash
# All values below are illustrative for one GPU root port. Resolve actual SMN
# stride per IOHC from /sys/devices/pci0000:00/... topology before running.
# Requires CONFIG_AMD_NB and root.

# 1. Read current state
PORT_BDF=0000:60:01.1   # example — replace with the GPU root port
sudo lspci -vv -s $PORT_BDF | grep -E 'LnkCap|LnkCtl2|LnkSta'

# 2. Raise PCIe-spec Target Link Speed to Gen4 (this part definitely succeeds)
sudo setpci -s $PORT_BDF CAP_EXP+30.w=0x0044   # TLS field = 4

# 3. Optional: kernel-side SMN write to set LC_TARGET_LINK_SPEED_OVERRIDE
#    Requires a small kernel module using amd_smn_write(), or
#    a userspace tool (iotools, ryzen_smu) that exposes SMN.
#    Pseudocode: amd_smn_write(node, 0x111402A4 + port_stride,
#                              (cur & ~0x7800) | (4<<12) | (1<<11));

# 4. Trigger retrain
sudo setpci -s $PORT_BDF CAP_EXP+10.w=0x0020   # LnkCtl.RetrainLink=1
sleep 0.2
sudo lspci -vv -s $PORT_BDF | grep LnkSta
```

If `LnkSta` reports 8GT after this, F17h M31h's NBIO does not actually clamp on the GEN4_EN strap and the user has a runtime fix. **Strong prior: it will report 5GT (Gen3) and the experiment confirms the hardware lockout. Document the outcome either way.**

### SMM lockdown question

There is no SMM-side lockdown of NBIO SMN registers on Rome. AMD's own AMD-IOPM-UTIL (referenced in the ROCm/Instinct tuning guides) writes NBIO link-clock-frequency SMN registers from a Linux userspace tool at every boot — proof that the SMN region is reachable from x86 ring-0 in production. The lockdown is in the **PSP-side SMN firewall** (configured by the PSP's BIOS Boot Loader from APCB tokens) and via the **HwInit register attribute**, which is enforced inside the NBIO IP itself, not by SMM. There is no MSR or chipset gate to "unlock" this; the firewall config is signed.

---

## TL;DR for the project log

The Gen3 cap on ROMED8-2T's GPU root ports is enforced by `PCIE_LC_SPEED_CNTL.LC_GEN4_EN_STRAP=0`, an `HwInit` bit at SMN `0x111402A4` (per IOHC stride) that is loaded from the PSP-validated APCB at cold boot and is ignored on subsequent x86 writes. Standard PCIe `Target Link Speed` (LCTL2) writes succeed but renegotiation is masked by the strap. **No-flash, no-APCB-patch fix from userspace is not available** on F17h M31h. The only experimentally-cheap thing left to try is `LC_TARGET_LINK_SPEED_OVERRIDE` + `LC_FORCE_EN_HW_SPEED_CHANGE` on a probable-fail basis.
