# Suppressed BIOS Settings (P3.70)

Every setup setting in P3.70 whose currently-active condition stack includes at least one `SuppressIf` clause. Sourced by walking the IFR of every HII Forms-bearing UEFI module and tracking SuppressIf nesting.

**Counts:** 133 suppressed of 1598 total settings — 17 permanent (`SuppressIf True`), 0 admin-only-visible (suppressed from users), 0 user-only-visible (suppressed from admin), 116 conditional on other QuestionIds.

Notes:
- `SuppressIf True` settings are permanently deleted from the menu — they live in the IFR but never render. They are the most interesting.
- `SuppressIf Q0x14A == 0x0` hides the setting in **user mode**, so logging in to BIOS as Administrator (set BIOS supervisor password, then enter setup with that password) reveals them. These are NOT truly hidden.
- `SuppressIf Q0x14A == 0x1` hides in **admin mode** (rare — usually informational text shown only to users).
- A condition like `SuppressIf Q0x158 == 0x0` is a runtime check on a sibling setup variable — flipping that variable in NVRAM unlocks the child. See companion JSON `SUPPRESSED_OPTIONS.json` for full data.


---

## 1. Candidates of interest (PCIe / Gen4 / DXIO / link / force / override)

7 suppressed settings whose prompt or help mentions one of: PCIe, Gen3, Gen4, link speed/width, lane, ESM, DXIO, force, override, hotplug, preset, compliance, negotiation, 10GT/16GT.


### Module `CbsSetupDxeSSP`

- [conditional] **`0x700d` — SEV-ES ASID Space Limit** _(Numeric)_ — · VS `0x5000` (AmdSetupSSP) · off `0x28` · 32-bit — cond: SuppressIf(Q0x11 == 0x0) — _help:_ SEV VMs using ASIDs below the SEV-ES ASID Space Limit must enable the SEV-ES feature. ASIDs from SEV-ES ASID Space Limit to (SEV ASID Count + 1) can only be used with SEV VMs. If this field is set to 
  - matched keywords: `force`
- [conditional] **`0x1cd` — NTB active on PCIeCore** _(OneOf)_ — · VS `0x5000` (AmdSetupSSP) · off `0x280` · 8-bit — opts: `15`=Auto, `0`=Core0, `16`=Core1 — cond: SuppressIf(Q0x1cb == 0x0) — _help:_ NTB enable on PCIe Core
  - matched keywords: `pcie`
- [conditional] **`0x1cf` — Link Speed** _(OneOf)_ — · VS `0x5000` (AmdSetupSSP) · off `0x282` · 8-bit — opts: `0`=Max Speed, `1`=Gen 1, `2`=Gen 2, `3`=Gen 3, `15`=Auto, `4`=Gen 4, `0`=Disabled, `1`=Enabled, `2`=Auto, `0`=Disabled, `1`=Enabled, `255`=Auto, `5`=Detailed debug message, `10`=Coarse debug message, `200`=Stage completion, `254`=Firmware completion message only, `255`=Auto — cond: SuppressIf(Q0x1cb == 0x0) — _help:_ Select Link Speed for NTB Mode (Core 0, Port 0)
  - matched keywords: `link speed`

### Module `IntelLanUefiDriver`

- [conditional] **`0x110c` — Link Speed Status** _(OneOf)_ — · VS `0x1234` (UndiNVData) · off `0x2c` · 8-bit — opts: `0`=Auto Negotiated, `1`=10 Mbps Half, `2`=10 Mbps Full, `3`=100 Mbps Half, `4`=100 Mbps Full, `5`=1000 Mbps Half, `6`=1000 Mbps Full, `7`=10 Gbps Half, `8`=10 Gbps Full, `9`=20 Gbps, `10`=40 Gbps, `32`=N/A — cond: SuppressIf(Q0x1408 == 0x0) ; GrayOutIf(True) — _help:_ Link Speed Status
  - matched keywords: `link speed`

### Module `Setup`

- [conditional] **`0x2a` —   Disable Block Sid** _(OneOf)_ — · VS `0x1` (Setup) · off `0x21` · 8-bit — opts: `1`=Enabled, `0`=Disabled — cond: SuppressIf(Q0x1ce == 0x0) — _help:_ Override to allow SID authentication in TCG Storage device
  - matched keywords: `override`
- [conditional] **`0x40` —   Disable Block Sid** _(OneOf)_ — · VS `0x1` (Setup) · off `0x21` · 8-bit — opts: `1`=Enabled, `0`=Disabled — cond: SuppressIf(Q0x1ce == 0x0) — _help:_ Override to allow SID authentication in TCG Storage device
  - matched keywords: `override`
- [PERMANENT] **`0x5f` — PCIE1 ASPM Support** _(OneOf)_ — · VS `0x1` (Setup) · off `0x15d` · 8-bit — opts: `0`=Disabled, `1`=ASPM L0s, `2`=ASPM L1, `3`=ASPM L0sL1 — cond: SuppressIf(True) — _help:_ Configure the ASPM of PCIE1
  - matched keywords: `pcie`

---

## 2. Permanently suppressed (`SuppressIf True`)

17 settings wrapped by `SuppressIf True` — the IFR carries them but the menu never renders them. These are the strongest candidates for hidden engineering options.


### Module `IntelLanUefiDriver`

- **`0x1517` — (unnamed)** _(Numeric)_ — · VS `0x1234` (UndiNVData) · off `0x35` · 8-bit — cond: SuppressIf(True)
- **`0x1408` — (unnamed)** _(Numeric)_ — · VS `0x1234` (UndiNVData) · off `0x2d` · 8-bit — cond: SuppressIf(True)
- **`0x1407` — (unnamed)** _(Numeric)_ — · VS `0x1234` (UndiNVData) · off `0x5` · 8-bit — cond: SuppressIf(True)
- **`0x5` — Number of Virtual Functions Supported** _(Numeric)_ — · VS `0x1234` (UndiNVData) · off `0x44` · 16-bit — cond: SuppressIf(True) — _help:_ Number of virtual functions supported on this port.
- **`0x1181` — (unnamed)** _(Numeric)_ — · VS `0x1234` (UndiNVData) · off `0x33` · 8-bit — cond: SuppressIf(True)
- **`0x8` — (unnamed)** _(Numeric)_ — · VS `0x1234` (UndiNVData) · off `0x0` · 8-bit — cond: SuppressIf(True)
- **`0x9` — (unnamed)** _(Numeric)_ — · VS `0x1234` (UndiNVData) · off `0x2` · 8-bit — cond: SuppressIf(True)
- **`0x1409` — (unnamed)** _(Numeric)_ — · VS `0x1234` (UndiNVData) · off `0x38` · 8-bit — cond: SuppressIf(True)

### Module `PciDynamicSetup`

- **`0x7008` — Hot-Plug Support** _(CheckBox)_ — · VS `0xcccc` (PCI_COMMON) · off `0x2` — cond: SuppressIf(True) — _help:_ Globally Enables or Disables Hot-Plug support for the entire System. If System has Hot-Plug capable Slots and this option set to Enabled, it provides a Setup screen for selecting PCI resource padding 

### Module `ServerMgmtSetup`

- **`0x1` — BMC Support** _(OneOf)_ — · VS `0x1` (ServerSetup) · off `0x0` · 8-bit — opts: `1`=Enabled, `0`=Disabled — cond: SuppressIf(True) — _help:_ Enable/Disable interfaces to communicate with BMC
- **`0x2` — IPMI Interface Type** _(OneOf)_ — · VS `0x1` (ServerSetup) · off `0x16` · 8-bit — opts: `1`=Kcs Interface, `3`=Bt Interface, `4`=Ssif Interface, `5`=Ipmb Interface, `6`=Usb Interface, `7`=Oem1 Interface, `8`=Oem2 Interface — cond: SuppressIf(True) — _help:_ Type of Interface to communicate BMC from HOST
- **`0x4` — FRB-2 Timer** _(OneOf)_ — · VS `0x1` (ServerSetup) · off `0x21f` · 8-bit — opts: `1`=Enabled, `0`=Disabled — cond: SuppressIf(True) ; SuppressIf(Q0x1 == 0x0) ; GrayOutIf(Q0x22 == 0x1) — _help:_ Enable or Disable FRB-2 timer(POST timer)

### Module `Setup`

- **`0x5f` — PCIE1 ASPM Support** _(OneOf)_ — · VS `0x1` (Setup) · off `0x15d` · 8-bit — opts: `0`=Disabled, `1`=ASPM L0s, `2`=ASPM L1, `3`=ASPM L0sL1 — cond: SuppressIf(True) — _help:_ Configure the ASPM of PCIE1
- **`0x6e` — Vlan ID** _(Numeric)_ — · VS `0x1` (Setup) · off `0xad` · 32-bit — cond: SuppressIf(True) — _help:_ Enter Vlan ID
- **`0xa1` — USB 2.0 Controller Mode** _(OneOf)_ — · VS `0x14` (UsbSupport) · off `0x2e` · 8-bit — opts: `1`=HiSpeed, `0`=FullSpeed — cond: SuppressIf(True) ; GrayOutIf(Q0x14b == 0x1) — _help:_ Configures the USB 2.0 controller in HiSpeed (480Mbps) or FullSpeed (12Mbps).
- **`0xa2` — Legacy USB 3.0 Support** _(OneOf)_ — · VS `0x14` (UsbSupport) · off `0x2a` · 8-bit — opts: `1`=Enabled, `0`=Disabled — cond: SuppressIf(True) ; GrayOutIf(Q0x14b == 0x1) — _help:_ Enable or disable Legacy OS Support for USB 3.0 devices.
- **`0x142` — Refresh attribute registry** _(OneOf)_ — · VS `0xb` (RefreshAttribRegistry) · off `0x0` · 8-bit — opts: `0`=Disabled, `1`=Enabled — cond: SuppressIf(True) — _help:_ Refreshes the attribute registry in next boot. This will be helpful for complex condition evaluation

---

## 3. Admin-only visible (`SuppressIf Q0x14A == 0x0`)

0 settings hidden in user mode but visible if you enter BIOS with the supervisor password. **Not truly hidden** — these appear in the menu under admin login. Listed by module + form for context, NVRAM offsets only:


---

## 4. Debug / engineering / hidden-mode hints

_(no suppressed settings whose prompt or help text matched Debug/Engineering/Manufacturing/Hidden/Internal/Test/Factory/Validation)_


---

## 5. All other suppressed (conditional, by module)

116 settings gated on other setup questions. Full enumeration is in `SUPPRESSED_OPTIONS.json` — below is a per-module summary plus the most-referenced gating QuestionIds.


### Top gating QuestionIds

| QuestionId | Times referenced in SuppressIf |
|---|---|
| `0x75` | 31 |
| `0x5a` | 7 |
| `0x2` | 7 |
| `0x1` | 7 |
| `0x9f` | 6 |
| `0x7013` | 5 |
| `0xab` | 4 |
| `0x1cb` | 4 |
| `0x32` | 4 |
| `0xcb` | 4 |
| `0xa7` | 3 |
| `0xb0` | 3 |
| `0x1405` | 2 |
| `0x1ce` | 2 |
| `0x2760` | 2 |
| `0x14a` | 2 |
| `0xb` | 1 |
| `0x11` | 1 |
| `0xed` | 1 |
| `0x10b` | 1 |
| `0x110` | 1 |
| `0x119` | 1 |
| `0x8` | 1 |
| `0x1408` | 1 |
| `0x1601` | 1 |

### Per-module counts

| Module | Conditionally suppressed |
|---|---|
| `AmdPbsSetupDxe` | 1 |
| `CbsSetupDxeSSP` | 62 |
| `EventLogsSetupPage` | 7 |
| `IntelLanUefiDriver` | 6 |
| `Ip4Dxe` | 1 |
| `ServerMgmtSetup` | 11 |
| `Setup` | 28 |

#### `AmdPbsSetupDxe` — 1 suppressed

- `0xc` **SMI Threshold** (Numeric, VS `0x1` off `0x1`) — SuppressIf: Q0xb == 0x0

#### `CbsSetupDxeSSP` — 62 suppressed

- `0x700d` **SEV-ES ASID Space Limit** (Numeric, VS `0x5000` off `0x28`) — SuppressIf: Q0x11 == 0x0
- `0x1f` **Frequency (MHz)** (Numeric, VS `0x5000` off `0x3a`) — SuppressIf: Q0x7013 == 0x2
- `0x20` **Voltage (uV)** (Numeric, VS `0x5000` off `0x3e`) — SuppressIf: Q0x7013 == 0x2
- `0x7014` **Pstate0 FID** (Numeric, VS `0x5000` off `0x42`) — SuppressIf: Q0x7013 == 0x2
- `0x7015` **Pstate0 DID** (Numeric, VS `0x5000` off `0x43`) — SuppressIf: Q0x7013 == 0x2
- `0x7016` **Pstate0 VID** (Numeric, VS `0x5000` off `0x44`) — SuppressIf: Q0x7013 == 0x2
- `0x5b` **ACPI SLIT remote relative distance** (OneOf, VS `0x5000` off `0xc2`) — SuppressIf: Q0x5a == 0x0
- `0x5d` **ACPI SLIT same socket distance** (Numeric, VS `0x5000` off `0xc4`) — SuppressIf: Q0x5a == 0xff
- `0x5e` **ACPI SLIT remote socket distance** (Numeric, VS `0x5000` off `0xc5`) — SuppressIf: Q0x5a == 0xff
- `0x5f` **ACPI SLIT local SLink distance** (Numeric, VS `0x5000` off `0xc6`) — SuppressIf: Q0x5a == 0xff
- `0x60` **ACPI SLIT remote SLink distance** (Numeric, VS `0x5000` off `0xc7`) — SuppressIf: Q0x5a == 0xff
- `0x61` **ACPI SLIT local inter-SLink distance** (Numeric, VS `0x5000` off `0xc8`) — SuppressIf: Q0x5a == 0xff
- `0x62` **ACPI SLIT remote inter-SLink distance** (Numeric, VS `0x5000` off `0xc9`) — SuppressIf: Q0x5a == 0xff
- `0x76` **Memory Clock Speed** (OneOf, VS `0x5000` off `0xd7`) — SuppressIf: Q0x75 == 0xff
- `0x77` **Tcl** (OneOf, VS `0x5000` off `0xd8`) — SuppressIf: Q0x75 == 0xff
- `0x78` **Trcdrd** (OneOf, VS `0x5000` off `0xd9`) — SuppressIf: Q0x75 == 0xff
- `0x79` **Trcdwr** (OneOf, VS `0x5000` off `0xda`) — SuppressIf: Q0x75 == 0xff
- `0x7a` **Trp** (OneOf, VS `0x5000` off `0xdb`) — SuppressIf: Q0x75 == 0xff
- `0x7b` **Tras** (OneOf, VS `0x5000` off `0xdc`) — SuppressIf: Q0x75 == 0xff
- `0x7c` **Trc Ctrl** (OneOf, VS `0x5000` off `0xdd`) — SuppressIf: Q0x75 == 0xff
- `0x7e` **TrrdS** (OneOf, VS `0x5000` off `0xdf`) — SuppressIf: Q0x75 == 0xff
- `0x7f` **TrrdL** (OneOf, VS `0x5000` off `0xe0`) — SuppressIf: Q0x75 == 0xff
- `0x80` **Tfaw Ctrl** (OneOf, VS `0x5000` off `0xe1`) — SuppressIf: Q0x75 == 0xff
- `0x82` **TwtrS** (OneOf, VS `0x5000` off `0xe3`) — SuppressIf: Q0x75 == 0xff
- `0x83` **TwtrL** (OneOf, VS `0x5000` off `0xe4`) — SuppressIf: Q0x75 == 0xff
- `0x84` **Twr Ctrl** (OneOf, VS `0x5000` off `0xe5`) — SuppressIf: Q0x75 == 0xff
- `0x86` **Trcpage Ctrl** (OneOf, VS `0x5000` off `0xe7`) — SuppressIf: Q0x75 == 0xff
- `0x88` **TrdrdScL Ctrl** (OneOf, VS `0x5000` off `0xea`) — SuppressIf: Q0x75 == 0xff
- `0x8a` **TwrwrScL Ctrl** (OneOf, VS `0x5000` off `0xec`) — SuppressIf: Q0x75 == 0xff
- `0x8c` **Trfc Ctrl** (OneOf, VS `0x5000` off `0xee`) — SuppressIf: Q0x75 == 0xff
- `0x8e` **Trfc2 Ctrl** (OneOf, VS `0x5000` off `0xf1`) — SuppressIf: Q0x75 == 0xff
- `0x90` **Trfc4 Ctrl** (OneOf, VS `0x5000` off `0xf4`) — SuppressIf: Q0x75 == 0xff
- `0x92` **Tcwl** (OneOf, VS `0x5000` off `0xf7`) — SuppressIf: Q0x75 == 0xff
- `0x93` **Trtp** (OneOf, VS `0x5000` off `0xf8`) — SuppressIf: Q0x75 == 0xff
- `0x94` **Tcke** (OneOf, VS `0x5000` off `0xf9`) — SuppressIf: Q0x75 == 0xff
- `0x95` **Trdwr** (OneOf, VS `0x5000` off `0xfa`) — SuppressIf: Q0x75 == 0xff
- `0x96` **Twrrd** (OneOf, VS `0x5000` off `0xfb`) — SuppressIf: Q0x75 == 0xff
- `0x97` **TwrwrSc** (OneOf, VS `0x5000` off `0xfc`) — SuppressIf: Q0x75 == 0xff
- `0x98` **TwrwrSd** (OneOf, VS `0x5000` off `0xfd`) — SuppressIf: Q0x75 == 0xff
- `0x99` **TwrwrDd** (OneOf, VS `0x5000` off `0xfe`) — SuppressIf: Q0x75 == 0xff
- `0x9a` **TrdrdSc** (OneOf, VS `0x5000` off `0xff`) — SuppressIf: Q0x75 == 0xff
- `0x9b` **TrdrdSd** (OneOf, VS `0x5000` off `0x100`) — SuppressIf: Q0x75 == 0xff
- `0x9c` **TrdrdDd** (OneOf, VS `0x5000` off `0x101`) — SuppressIf: Q0x75 == 0xff
- `0x9d` **ProcODT** (OneOf, VS `0x5000` off `0x102`) — SuppressIf: Q0x75 == 0xff
- `0xa8` **AddrCmdSetup** (Numeric, VS `0x5000` off `0x10c`) — SuppressIf: Q0xa7 == 0xff
- `0xa9` **CsOdtSetup** (Numeric, VS `0x5000` off `0x10d`) — SuppressIf: Q0xa7 == 0xff
- `0xaa` **CkeSetup** (Numeric, VS `0x5000` off `0x10e`) — SuppressIf: Q0xa7 == 0xff
- `0xac` **ClkDrvStren** (OneOf, VS `0x5000` off `0x110`) — SuppressIf: Q0xab == 0xff
- `0xad` **AddrCmdDrvStren** (OneOf, VS `0x5000` off `0x111`) — SuppressIf: Q0xab == 0xff
- `0xae` **CsOdtDrvStren** (OneOf, VS `0x5000` off `0x112`) — SuppressIf: Q0xab == 0xff
- `0xaf` **CkeDrvStren** (OneOf, VS `0x5000` off `0x113`) — SuppressIf: Q0xab == 0xff
- `0xb1` **RttNom** (OneOf, VS `0x5000` off `0x115`) — SuppressIf: Q0xb0 == 0xff
- `0xb2` **RttWr** (OneOf, VS `0x5000` off `0x116`) — SuppressIf: Q0xb0 == 0xff
- `0xb3` **RttPark** (OneOf, VS `0x5000` off `0x117`) — SuppressIf: Q0xb0 == 0xff
- `0xe7` **ACS Enable** (OneOf, VS `0x5000` off `0x156`) — SuppressIf: Q0xed == 0x0
- `0x10c` **cTDP** (Numeric, VS `0x5000` off `0x186`) — SuppressIf: Q0x10b == 0x0
- `0x111` **Package Power Limit** (Numeric, VS `0x5000` off `0x191`) — SuppressIf: Q0x110 == 0x0
- `0x11a` **BoostFmax** (Numeric, VS `0x5000` off `0x1a2`) — SuppressIf: Q0x119 == 0x0
- `0x1cc` **NTB Location** (OneOf, VS `0x5000` off `0x27f`) — SuppressIf: Q0x1cb == 0x0
- `0x1cd` **NTB active on PCIeCore** (OneOf, VS `0x5000` off `0x280`) — SuppressIf: Q0x1cb == 0x0
- `0x1ce` **NTB Mode** (OneOf, VS `0x5000` off `0x281`) — SuppressIf: Q0x1cb == 0x0
- `0x1cf` **Link Speed** (OneOf, VS `0x5000` off `0x282`) — SuppressIf: Q0x1cb == 0x0

#### `EventLogsSetupPage` — 7 suppressed

- `0x3` **Erase Event Log** (OneOf, VS `0x1` off `0xcd`) — SuppressIf: Q0x2 == 0x0
- `0x4` **When Log is Full** (OneOf, VS `0x1` off `0xcc`) — SuppressIf: Q0x2 == 0x0
- `0x5` **Log System Boot Event** (OneOf, VS `0x1` off `0xce`) — SuppressIf: Q0x2 == 0x0
- `0x6` **MECI** (Numeric, VS `0x1` off `0xd1`) — SuppressIf: Q0x2 == 0x0
- `0x7` **METW** (Numeric, VS `0x1` off `0xd0`) — SuppressIf: Q0x2 == 0x0
- `0x8` **Log EFI Status Code** (OneOf, VS `0x1` off `0xcf`) — SuppressIf: Q0x2 == 0x0
- `0x9` **Convert EFI Status Codes to Standard Smbios Type** (OneOf, VS `0x1` off `0xd2`) — SuppressIf: Q0x2 == 0x0 ; Q0x8 == 0x0

#### `IntelLanUefiDriver` — 6 suppressed

- `0x110c` **Link Speed Status** (OneOf, VS `0x1234` off `0x2c`) — SuppressIf: Q0x1408 == 0x0
- `0x1602` **Shared Memory Features** (OneOf, VS `0x1234` off `0x30`) — SuppressIf: Q0x1601 == 0x0
- `0x110d` **Virtual LAN ID** (Numeric, VS `0x1234` off `0x3a`) — SuppressIf: Q0x1409 == 0x0
- `0xa` **PCI Virtual Functions Advertised** (Numeric, VS `0x1234` off `0x40`) — SuppressIf: Q0x1501 == 0x0 ; Q0x140a == 0x0
- `0x1200` **TCP/IP Parameters via DHCP** (OneOf, VS `0x1234` off `0x48`) — SuppressIf: Q0x1405 == 0x0
- `0x1221` **TCP Port** (Numeric, VS `0x1234` off `0x3b2`) — SuppressIf: Q0x1405 == 0x0

#### `Ip4Dxe` — 1 suppressed

- `0x101` **Enable DHCP** (CheckBox, VS `0x1` off `0x1`) — SuppressIf: Q0x100 == 0x0

#### `ServerMgmtSetup` — 11 suppressed

- `0x5` **FRB-2 Timer timeout** (Numeric, VS `0x1` off `0x220`) — SuppressIf: Q0x1 == 0x0
- `0x6` **FRB-2 Timer Policy** (OneOf, VS `0x1` off `0x221`) — SuppressIf: Q0x1 == 0x0
- `0x7` **OS Watchdog Timer** (OneOf, VS `0x1` off `0x222`) — SuppressIf: Q0x1 == 0x0
- `0x8` **OS Wtd Timer Timeout** (Numeric, VS `0x1` off `0x223`) — SuppressIf: Q0x1 == 0x0
- `0x9` **OS Wtd Timer Policy** (OneOf, VS `0x1` off `0x224`) — SuppressIf: Q0x1 == 0x0
- `0xa` **Serial Mux** (OneOf, VS `0x1` off `0x22d`) — SuppressIf: Q0x1 == 0x0
- `0xd` **Configuration address source** (OneOf, VS `0x1` off `0x19`) — SuppressIf: Q0x2724 == 0x2
- `0x11` **Configuration address source** (OneOf, VS `0x1` off `0x1a`) — SuppressIf: Q0x2725 == 0x2
- `0x15` **Manual setting IPMI LAN(IPV6)** (OneOf, VS `0x1` off `0x175`) — SuppressIf: Q0x2750 == 0x0
- `0x17` **Manual setting IPMI LAN(IPV6)** (OneOf, VS `0x1` off `0x176`) — SuppressIf: Q0x2751 == 0x0
- `0x21` **KCS control** (OneOf, VS `0x1` off `0x2fa`) — SuppressIf: Q0x1 == 0x0

#### `Setup` — 28 suppressed

- `0x7` **System Language** (OneOf, VS `0xf009` off `0x0`) — SuppressIf: Q0x1d7 == 0xffff
- `0x2a` **Disable Block Sid** (OneOf, VS `0x1` off `0x21`) — SuppressIf: Q0x1ce == 0x0
- `0x2b` **Security Device Support** (OneOf, VS `0x1` off `0x6`) — SuppressIf: Q0x1d3 == 0x0
- `0x2e` **Security Device Support** (OneOf, VS `0x1` off `0x6`) — SuppressIf: Q0x1d2 == 0x0
- `0x33` **SHA-1 PCR Bank** (OneOf, VS `0x1` off `0x1a`) — SuppressIf: Q0x32 == 0x0
- `0x38` **Pending operation** (OneOf, VS `0x1` off `0x2`) — SuppressIf: Q0x32 == 0x0
- `0x3e` **TPM 2.0 InterfaceType** (OneOf, VS `0x1` off `0x12`) — SuppressIf: Q0x32 == 0x0
- `0x3f` **Device Select** (OneOf, VS `0x1` off `0x13`) — SuppressIf: Q0x32 == 0x0
- `0x40` **Disable Block Sid** (OneOf, VS `0x1` off `0x21`) — SuppressIf: Q0x1ce == 0x0
- `0x56` **Primary Graphics Adapter** (OneOf, VS `0x1` off `0x16c`) — SuppressIf: Q0x2760 == 0x0
- `0x6f` **OnBrd/Ext VGA Select** (OneOf, VS `0x1` off `0xc9`) — SuppressIf: Q0x137 == 0x1
- `0x74` **Change Settings** (OneOf, VS `0x4` off `0x1`) — SuppressIf: Q0x73 == 0x0
- `0x9f` **USB Support** (OneOf, VS `0x14` off `0x0`) — SuppressIf: Q0x9f == Q0x9f
- `0xa0` **Legacy USB Support** (OneOf, VS `0x14` off `0x1`) — SuppressIf: Q0x9f == 0x0
- `0xa5` **USB Mass Storage Driver Support** (OneOf, VS `0x14` off `0x2f`) — SuppressIf: Q0x9f == 0x0
- `0xa6` **Port 60/64 Emulation** (OneOf, VS `0x14` off `0x7`) — SuppressIf: Q0x9f == 0x0
- `0xa7` **USB transfer time-out** (OneOf, VS `0x14` off `0x9`) — SuppressIf: Q0x9f == 0x0
- `0xa8` **Device reset time-out** (OneOf, VS `0x14` off `0x8`) — SuppressIf: Q0x9f == 0x0
- `0xaa` **Device power-up delay in seconds** (Numeric, VS `0x14` off `0x2d`) — SuppressIf: Q0xa9 == 0x0
- `0xcc` **IPv4 PXE Support** (OneOf, VS `0x15` off `0x1`) — SuppressIf: Q0xcb == 0x0
- `0xce` **IPv6 PXE Support** (OneOf, VS `0x15` off `0x2`) — SuppressIf: Q0xcb == 0x0
- `0xd0` **PXE boot wait time** (Numeric, VS `0x15` off `0x4`) — SuppressIf: Q0xcb == 0x0
- `0xd1` **Media detect count** (Numeric, VS `0x15` off `0x5`) — SuppressIf: Q0xcb == 0x0
- `0xd5` **HDD Connection Order** (OneOf, VS `0x1` off `0x10a`) — SuppressIf: Q0x12e == 0x2
- `0x12a` **Boot Option #%d** (OneOf, VS `0xf006` off `0x0`) — SuppressIf: Q0x14a in [65535]
- `0x12b` **Driver Option #%d** (OneOf, VS `0xf` off `0x0`) — SuppressIf: Q0x14d in [65535]
- `0x12d` **Boot Option #%d** (OneOf, VS `0xf006` off `0x0`) — SuppressIf: Q0x14a in [65535]
- `0x12e` **Boot option filter** (OneOf, VS `0x1` off `0x10c`) — SuppressIf: Q0x2760 == 0x0

---

_See `SUPPRESSED_OPTIONS.json` for the full machine-readable enumeration._
