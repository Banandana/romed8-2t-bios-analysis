# AMD-IOPM-UTIL Research Findings

**Status:** Negative result for the killer question. AMD-IOPM-UTIL is real and AMD-published, but it is **not** a tool for changing per-port PCIe Gen capability. It only locks NBIO/PCIe-RC dynamic power management (DPM) into the highest-performance state. It will not lift a Gen3 cap to Gen4.

This document records what was searched, what was found, and what the implications are for the ROMED8-2T BIOS Gen3 cap problem.

---

## 1. What AMD-IOPM-UTIL actually is

AMD-IOPM-UTIL is an AMD-published userspace utility for **EPYC 7002 ("Rome", Family 17h Model 31h)** that disables I/O Dynamic Power Management on every PCIe Root Complex / NBIO instance in the platform and locks the link-clock logic ("LCLK") into its highest-performance state at runtime. It exists because on Rome the NBIO LCLK state machine cannot be pinned through BIOS settings alone.

Direct quotes from the HPC Advisory Council "AMD 2nd Gen EPYC CPU Tuning Guide for InfiniBand HPC" and the AMD/ROCm MI100 tuning guide:

> "AMD-IOPM-UTIL must be run at every server boot to disable Dynamic Power Management for all PCIe Root Complexes and NBIOs within the system and to lock the logic into the highest performance operational mode."

> "Disabling I/O DPM will reduce the latency and/or improve the throughput of low-bandwidth messages for PCI-e InfiniBand NICs and GPUs."

> "The utility does not have any command-line options, and it must be run with super-user permissions. Additionally, the actions of the utility do not persist across reboots."

> "For AMD EPYC 7003 series processors, configuring all NBIOs to be in 'Enhanced Preferred I/O' mode is sufficient to enable highest link clock frequency for the NBIO components." (i.e. the utility is a Rome-era workaround.)

### Canonical download

The tool is referenced from AMD's own documentation:

- ROCm MI100 tuning guide explicitly cites `https://developer.amd.com/iopm-utility/` as the installer source.
- The page **404s as of this research** (developer.amd.com has been folded into amd.com). This is consistent with the AMD developer-portal migration and the community-forum URL that now redirects to `amd.com/en/site-notifications/community-updates.html`.
- The tool is bundled / re-distributed by ROCm, by NVIDIA's HPC tuning bundles for Rome+Mellanox, and by some OEM HPC stacks.

So it is **AMD-official**, distributed historically via AMD Developer Central, currently surviving via mirrors (ROCm docs reference, OEM HPC packages, NVIDIA Mellanox tuning bundles). It is not on AMD's GitHub orgs (AMDESE, amd/) — those host E-SMI, AMDSEV, amd-perf-tools, ESMI-OOB, APML, etc., none of which are AMD-IOPM-UTIL.

---

## 2. What it can and cannot modify at runtime

### Can:

- Disable IO DPM (Dynamic Power Management) on every NBIO / PCIe Root Complex.
- Lock LCLK (link clock) at the maximum DPM state.
- That is the entire scope. Per AMD's own documentation: it has zero command-line options.

### Cannot (and this is the load-bearing finding):

- It does **not** change per-port PCIe Maximum Link Speed.
- It does **not** flip `LC_GEN4_EN_STRAP` or any equivalent per-port "Gen4 enable" hardware strap.
- It does **not** enable ESM (Extended Speed Mode).
- It does **not** rewrite PCIe Link Capabilities (LnkCap) Max Link Speed bits.
- It is purely a power-state lock for an already-configured topology.

The Gen3 cap on ROMED8-2T's GPU root ports is set by the **APCB DXIO descriptors** that ABL/PSP consumes during cold init, **before** PCIe link training. By the time any OS-side tool runs, the link has already been brought up at Gen3, and the Max Link Speed in LnkCap reflects the value the SMU/PSP latched. AMD-IOPM-UTIL runs late and only touches DPM/clock state — wrong layer, wrong knob.

---

## 3. Hardware / OS requirements

- **Hardware:** EPYC 7002 (Rome, Zen 2, F17M31h) — yes, exactly the project target.
- **Hardware (newer parts):** Not needed on Milan/7003, where BIOS "Enhanced Preferred I/O" + APBDIS achieve the same effect.
- **OS:** Linux, x86_64. Distributed as an installer that drops a binary plus a systemd one-shot service unit (the docs explicitly recommend "systemd service unit (one-shot mode)"). Must be re-run after every boot.
- **Permissions:** root. Likely uses `/dev/mem` or sysfs-pci to poke MMIO config space of NBIO / SMU. No standalone kernel module is shipped with it according to the documentation surfaced.

---

## 4. Required interfaces (SMM? ACPI? pure userspace?)

Public docs do not enumerate the exact mechanism, but the constraints (root-only, no command-line options, runs late on a booted Linux, no driver) strongly imply the tool talks to NBIO/SMU via:

- direct MMIO writes to NBIO IOHC config registers (PCI ECAM or SMN aperture), and/or
- HSMP/SMU mailbox commands via a PCI BAR.

It does **not** require SMM cooperation, does not call a BIOS-exposed ACPI method, and does not depend on a UEFI runtime service. The fact that the action does not persist across reboot is consistent with "I just wrote some live registers; the next cold boot reverts to PSP/ABL defaults."

This is good news in one sense: it confirms that on Rome, certain NBIO state **is** writable from x86 ring-0 userspace, without SMM permission. It is bad news in another: the writable state is the DPM/LCLK latch, not the Gen3/Gen4 cap latch.

---

## 5. Related / adjacent AMD-published tools

| Tool | Org | What it does | Relevance to Gen-cap override |
|---|---|---|---|
| **AMD-IOPM-UTIL** | AMD (developer.amd.com legacy) | NBIO/RC DPM lock | None for Gen cap. |
| **E-SMI in-band library** (`amd/esmi_ib_library`) | AMD GitHub | Userspace lib over `amd_hsmp` driver: power, energy, perf, bandwidth, freq controls via SMU mailbox. | No PCIe-link-speed control surface exposed. |
| **E-SMI out-of-band** (`amd/esmi_oob_library`) | AMD GitHub | APML / SB-RMI / SB-TSI side-channel mgmt. | OOB only, not user-relevant here. |
| **APML library** | AMD developer | Same family as ESMI-OOB. | Out of scope. |
| **`amd_hsmp` driver** | mainline Linux | SMU mailbox to NBIO | Mailbox commands are a closed set — none documented for "set per-port PCIe gen cap." |
| **AMD μProf** | AMD developer | Profiling/power telemetry. | Read-only; not a configuration tool. |
| **amd-perf-tools** (AMDESE) | AMD GitHub | `perf` helpers, IBS docs, etc. | Not relevant. |
| **AMDSEV / linux-svsm** (AMDESE) | AMD GitHub | SEV-SNP enabling. | Not relevant. |
| **ROCm "amd-smi" / amdgpu kernel NBIO drivers** | AMD/ROCm | Configures GPU-side NBIO blocks (Vega/Navi NBIO IP). | These are the *GPU's* NBIO IP, not the Rome host NBIO. Different silicon block. |

There is no AMD-published "amd-pcie-tools" or "amd-link-speed" utility. Searches for that returned nothing.

---

## 6. The killer question: is there *any* userspace path to override per-port Gen3 cap to Gen4?

**Short answer: no — not for the cap.** The PCIe `LnkCap.MaxLinkSpeed` bits are HwInit per the PCIe spec; on AMD Rome they are populated from the PSP/ABL DXIO descriptors at cold reset. They are read-only to external initiators on the link, and on Rome they are not writable from x86 ring-0 in any documented way after PSP has handed control to ABL/UEFI.

What userspace **can** do (for completeness, none of these solve our problem):

- **`setpci` LNKCTL2 target speed write + retrain**: Writes `Target Link Speed` (LnkCtl2 bits [3:0]) and triggers retrain via LnkCtl bit 5. This only changes the *negotiated* speed within the cap — typically used to *downshift* a Gen4-capable link to Gen3/Gen2 for testing. It cannot push above LnkCap MaxLinkSpeed; the LTSSM will refuse to advertise a speed the cap forbids.
- **AMD-IOPM-UTIL**: locks LCLK; does not change cap. (Confirmed above.)
- **`amd_hsmp` mailbox commands**: documented set is power/freq/bandwidth; nothing for PCIe gen cap.
- **AMD PPR-defined NBIO root-port LnkCap shadow registers**: on Rome, these exist in the IOHC SMN space and are programmed by PSP/ABL from DXIO. They are not officially exposed for runtime modification, and even if poked, the LTSSM has already trained — re-training with a higher cap requires a hot reset of the port at minimum, and possibly a re-init of the PHY which on Rome is owned by the SMU.
- **ESM (PCIe 4.0 Extended Speed Mode)**: ESM is a PCIe-spec feature (16GT/s+ extension); it is not a back door to lift a Gen3 cap to Gen4 on a port the BIOS declared Gen3.

**The cap is set in APCB/DXIO, before any OS is running. AMD has not published a userspace knob to change it post-boot.** That matches the team's earlier empirical finding that ROMED8-2T's per-port DXIO descriptors are what gate Gen.

---

## 7. Searches performed

- `AMD-IOPM-UTIL EPYC Rome utility download`
- `"AMD-IOPM-UTIL" OR "amd_iopm" EPYC NBIO PCIe`
- `HPC Advisory Council AMD EPYC Rome tuning guide IOPM`
- `AMD EPYC Rome PCIe Gen4 enable runtime LC_GEN4_EN_STRAP NBIO`
- `"iopm-util" github source "Dynamic Power Management" PCIe`
- `"AMD-IOPM-UTIL" kernel module mmio ioperm iopl source`
- `AMD EPYC Rome ESM "Extended Speed Mode" enable PCIe Gen4 root port`
- `"esmi" amd EPYC PCIe link speed control library`
- `AMD AMDESE github linux NBIO PCIe runtime tool`
- `AMD EPYC Rome PCIe runtime change link speed setpci lnkctl2 Gen4`
- `EPYC Rome DXIO "PCIe Gen3" "Gen4" cap force runtime override BIOS`
- `PCIe Link Capabilities "Max Link Speed" hardware initialized read-only spec`

URLs fetched / attempted:

- `https://developer.amd.com/iopm-utility/` — 404 (page deprecated; AMD developer-portal migration).
- `https://community.amd.com/.../locating-quot-amd-iopm-util-quot/...` — 301 → community-shutdown notice.
- `https://hpcadvisorycouncil.atlassian.net/.../AMD+2nd+Gen+EPYC+CPU+Tuning+Guide+for+InfiniBand+HPC` — Confluence, content not accessible to fetch but title and excerpts surfaced via search.
- `https://rocm.docs.amd.com/en/docs-6.0.0/how-to/tuning-guides/mi100.html` — fetched; primary source for the verbatim quotes above.
- `https://alexforencich.com/wiki/en/pcie/set-speed` — fetched; documents the LNKCTL2 retrain mechanism (which cannot exceed LnkCap).

---

## 8. Implications for the ROMED8-2T project

1. AMD-IOPM-UTIL is a dead end for our objective. It modifies the wrong state.
2. AMD has not published a runtime tool that can rewrite per-port `LnkCap.MaxLinkSpeed` on Rome. None of E-SMI, HSMP, μProf, amd-perf-tools, AMDESE repos, amd/* GitHub repos expose such a knob.
3. The PSP/ABL DXIO programming path is the only documented place where the per-port cap is set on Rome. The team's existing plan — modify APCB DXIO descriptors — is in fact the AMD-supported configuration path; the "no BIOS flashing" constraint is what removes the AMD-supported option. There is no AMD-supported alternative.
4. Possible (unsupported) avenues if pursuing further: direct SMN pokes to NBIO IOHC strap shadows from `/dev/mem`, followed by hot-reset of the root port. This is undocumented, almost certainly fragile, and assumes the SMU does not re-latch from PSP-stored DXIO state on link retrain. It is a research project, not a fix.
5. The cleanest non-flash path remains: feed an alternate APCB blob via a method that does not require flashing the SPI part — e.g. an external SPI presenter / serial-flash emulator, or boot-time injection if the platform allows. Those are hardware/topology hacks, outside the scope of "userspace utility."

**Bottom line: the AMD-IOPM-UTIL lead does not solve the Gen3-cap problem. It is correctly named — it manages I/O Power Management, not link speed.**

---

## Sources

- [MI100 high-performance computing and tuning guide — ROCm Documentation](https://rocm.docs.amd.com/en/docs-6.0.0/how-to/tuning-guides/mi100.html)
- [AMD Instinct MI100 system optimization — ROCm Documentation](https://rocm.docs.amd.com/en/docs-6.2.4/how-to/system-optimization/mi100.html)
- [AMD 2nd Gen EPYC CPU Tuning Guide for InfiniBand HPC — HPC Advisory Council](https://hpcadvisorycouncil.atlassian.net/wiki/spaces/HPCWORKS/pages/1280442391/AMD+2nd+Gen+EPYC+CPU+Tuning+Guide+for+InfiniBand+HPC)
- [AMD Developer Central — IOPM utility (now 404)](https://developer.amd.com/iopm-utility/)
- [AMD Community thread: locating "AMD-IOPM-UTIL" (redirects to community shutdown notice)](https://community.amd.com/t5/pc-drivers-software/locating-quot-amd-iopm-util-quot/m-p/676178)
- [E-SMI In-band Library — github.com/amd/esmi_ib_library](https://github.com/amd/esmi_ib_library)
- [E-SMI Out-of-band Library — github.com/amd/esmi_oob_library](https://github.com/amd/esmi_oob_library)
- [AMDESE GitHub org](https://github.com/AMDESE)
- [amd-perf-tools — github.com/AMDESE/amd-perf-tools](https://github.com/AMDESE/amd-perf-tools)
- [PCIe Set Speed via setpci — Alex Forencich](https://alexforencich.com/wiki/en/pcie/set-speed)
- [Debugging PCIe Issues using lspci and setpci — AMD Adaptive Support](https://adaptivesupport.amd.com/s/article/1148199?language=en_US)
- [AMD HSMP & eSMI — Level1Techs forum overview](https://forum.level1techs.com/t/amd-hsmp-esmi-on-the-fly-control-of-fabric-clocks-power-and-more/230560)
