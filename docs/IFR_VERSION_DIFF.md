# IFR Cross-Version Diff (P3.70 / P3.80 / P3.90 / P4.10)

Cross-version comparison of every IFR-defined BIOS setting. Each version's IFR text was extracted from every PE32 image section, deduplicated to one module per name, and parsed with the Phase-1 parser (`scripts/list_suppressed.py`).


## Summary

| Version | Modules | Settings | Suppressed | Permanent | Conditional |
|---|---:|---:|---:|---:|---:|
| P3.70 | 15 | 1619 | 134 | 17 | 117 |
| P3.80 | 15 | 1619 | 134 | 17 | 117 |
| P3.90 | 15 | 1624 | 133 | 17 | 116 |
| P4.10 | 15 | 1624 | 133 | 17 | 116 |

## Verdict

- **Settings added in P3.80 / P3.90 / P4.10:** 139
- **Settings removed across versions:** 134
- **Settings with changed SuppressIf/GrayOutIf condition:** 102
- **Settings with changed prompt/name:** 0
- **Settings whose Gen4/ESM/DXIO keyword profile changed:** 0
- **New VarStores introduced in P3.80+:** 0


## 1. Settings added in P3.80+ (the highest-leverage diff)

139 settings appear in some version but were absent from P3.70.


| First seen | Module | QID | VS | Offset | Type | Prompt | SuppressIf |
|---|---|---|---|---|---|---|---|
| P3.80 | `CbsSetupDxeSSP` | `0x31` | `0x5000` | `0x9a` | OneOf | CCDs Control | - |
| P3.90 | `CbsSetupDxeGN` | `0x166` | `0x5000` | `0x227` | OneOf | Preset Search Mask Configuration (Gen3) | - |
| P3.90 | `CbsSetupDxeGN` | `0x167` | `0x5000` | `0x228` | Numeric | Preset Search Mask (Gen3) | - |
| P3.90 | `CbsSetupDxeGN` | `0x168` | `0x5000` | `0x22a` | OneOf | Preset Search Mask Configuration (Gen4) | - |
| P3.90 | `CbsSetupDxeGN` | `0x169` | `0x5000` | `0x22b` | Numeric | Preset Search Mask (Gen4) | - |
| P3.90 | `CbsSetupDxeGN` | `0x707a` | `0x5000` | `0x22d` | OneOf | SATA Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x172` | `0x5000` | `0x22e` | OneOf | SATA Mode | - |
| P3.90 | `CbsSetupDxeGN` | `0x173` | `0x5000` | `0x22f` | OneOf | Sata RAS Support | - |
| P3.90 | `CbsSetupDxeGN` | `0x174` | `0x5000` | `0x230` | OneOf | Sata Disabled AHCI Prefetch Function | - |
| P3.90 | `CbsSetupDxeGN` | `0x175` | `0x5000` | `0x231` | OneOf | Aggresive SATA Device Sleep Port 0 | - |
| P3.90 | `CbsSetupDxeGN` | `0x176` | `0x5000` | `0x232` | Numeric | DevSleep0 Port Number | - |
| P3.90 | `CbsSetupDxeGN` | `0x177` | `0x5000` | `0x233` | OneOf | Aggresive SATA Device Sleep Port 1 | - |
| P3.90 | `CbsSetupDxeGN` | `0x178` | `0x5000` | `0x234` | Numeric | DevSleep1 Port Number | - |
| P3.90 | `CbsSetupDxeGN` | `0x18e` | `0x5000` | `0x23d` | OneOf | Sata0 eSATA Port0 | - |
| P3.90 | `CbsSetupDxeGN` | `0x18f` | `0x5000` | `0x23e` | OneOf | Sata0 eSATA Port1 | - |
| P3.90 | `CbsSetupDxeGN` | `0x190` | `0x5000` | `0x23f` | OneOf | Sata0 eSATA Port2 | - |
| P3.90 | `CbsSetupDxeGN` | `0x191` | `0x5000` | `0x240` | OneOf | Sata0 eSATA Port3 | - |
| P3.90 | `CbsSetupDxeGN` | `0x192` | `0x5000` | `0x241` | OneOf | Sata0 eSATA Port4 | - |
| P3.90 | `CbsSetupDxeGN` | `0x193` | `0x5000` | `0x242` | OneOf | Sata0 eSATA Port5 | - |
| P3.90 | `CbsSetupDxeGN` | `0x194` | `0x5000` | `0x243` | OneOf | Sata0 eSATA Port6 | - |
| P3.90 | `CbsSetupDxeGN` | `0x195` | `0x5000` | `0x244` | OneOf | Sata0 eSATA Port7 | - |
| P3.90 | `CbsSetupDxeGN` | `0x196` | `0x5000` | `0x245` | OneOf | Sata1 eSATA Port0 | - |
| P3.90 | `CbsSetupDxeGN` | `0x197` | `0x5000` | `0x246` | OneOf | Sata1 eSATA Port1 | - |
| P3.90 | `CbsSetupDxeGN` | `0x198` | `0x5000` | `0x247` | OneOf | Sata1 eSATA Port2 | - |
| P3.90 | `CbsSetupDxeGN` | `0x199` | `0x5000` | `0x248` | OneOf | Sata1 eSATA Port3 | - |
| P3.90 | `CbsSetupDxeGN` | `0x19a` | `0x5000` | `0x249` | OneOf | Sata1 eSATA Port4 | - |
| P3.90 | `CbsSetupDxeGN` | `0x19b` | `0x5000` | `0x24a` | OneOf | Sata1 eSATA Port5 | - |
| P3.90 | `CbsSetupDxeGN` | `0x19c` | `0x5000` | `0x24b` | OneOf | Sata1 eSATA Port6 | - |
| P3.90 | `CbsSetupDxeGN` | `0x19d` | `0x5000` | `0x24c` | OneOf | Sata1 eSATA Port7 | - |
| P3.90 | `CbsSetupDxeGN` | `0x19e` | `0x5000` | `0x24d` | OneOf | Sata2 eSATA Port0 | - |
| P3.90 | `CbsSetupDxeGN` | `0x19f` | `0x5000` | `0x24e` | OneOf | Sata2 eSATA Port1 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1a0` | `0x5000` | `0x24f` | OneOf | Sata2 eSATA Port2 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1a1` | `0x5000` | `0x250` | OneOf | Sata2 eSATA Port3 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1a2` | `0x5000` | `0x251` | OneOf | Sata2 eSATA Port4 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1a3` | `0x5000` | `0x252` | OneOf | Sata2 eSATA Port5 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1a4` | `0x5000` | `0x253` | OneOf | Sata2 eSATA Port6 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1a5` | `0x5000` | `0x254` | OneOf | Sata2 eSATA Port7 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1a6` | `0x5000` | `0x255` | OneOf | Sata3 eSATA Port0 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1a7` | `0x5000` | `0x256` | OneOf | Sata3 eSATA Port1 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1a8` | `0x5000` | `0x257` | OneOf | Sata3 eSATA Port2 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1a9` | `0x5000` | `0x258` | OneOf | Sata3 eSATA Port3 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1aa` | `0x5000` | `0x259` | OneOf | Sata3 eSATA Port4 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1ab` | `0x5000` | `0x25a` | OneOf | Sata3 eSATA Port5 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1ac` | `0x5000` | `0x25b` | OneOf | Sata3 eSATA Port6 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1ad` | `0x5000` | `0x25c` | OneOf | Sata3 eSATA Port7 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1ae` | `0x5000` | `0x25d` | OneOf | Sata4 eSATA Port0 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1af` | `0x5000` | `0x25e` | OneOf | Sata4 eSATA Port1 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1b0` | `0x5000` | `0x25f` | OneOf | Sata4 eSATA Port2 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1b1` | `0x5000` | `0x260` | OneOf | Sata4 eSATA Port3 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1b2` | `0x5000` | `0x261` | OneOf | Sata4 eSATA Port4 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1b3` | `0x5000` | `0x262` | OneOf | Sata4 eSATA Port5 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1b4` | `0x5000` | `0x263` | OneOf | Sata4 eSATA Port6 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1b5` | `0x5000` | `0x264` | OneOf | Sata4 eSATA Port7 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1b6` | `0x5000` | `0x265` | OneOf | Sata5 eSATA Port0 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1b7` | `0x5000` | `0x266` | OneOf | Sata5 eSATA Port1 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1b8` | `0x5000` | `0x267` | OneOf | Sata5 eSATA Port2 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1b9` | `0x5000` | `0x268` | OneOf | Sata5 eSATA Port3 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1ba` | `0x5000` | `0x269` | OneOf | Sata5 eSATA Port4 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1bb` | `0x5000` | `0x26a` | OneOf | Sata5 eSATA Port5 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1bc` | `0x5000` | `0x26b` | OneOf | Sata5 eSATA Port6 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1bd` | `0x5000` | `0x26c` | OneOf | Sata5 eSATA Port7 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1be` | `0x5000` | `0x26d` | OneOf | Sata6 eSATA Port0 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1bf` | `0x5000` | `0x26e` | OneOf | Sata6 eSATA Port1 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1c0` | `0x5000` | `0x26f` | OneOf | Sata6 eSATA Port2 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1c1` | `0x5000` | `0x270` | OneOf | Sata6 eSATA Port3 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1c2` | `0x5000` | `0x271` | OneOf | Sata6 eSATA Port4 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1c3` | `0x5000` | `0x272` | OneOf | Sata6 eSATA Port5 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1c4` | `0x5000` | `0x273` | OneOf | Sata6 eSATA Port6 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1c5` | `0x5000` | `0x274` | OneOf | Sata6 eSATA Port7 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1c6` | `0x5000` | `0x275` | OneOf | Sata7 eSATA Port0 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1c7` | `0x5000` | `0x276` | OneOf | Sata7 eSATA Port1 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1c8` | `0x5000` | `0x277` | OneOf | Sata7 eSATA Port2 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1c9` | `0x5000` | `0x278` | OneOf | Sata7 eSATA Port3 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1ca` | `0x5000` | `0x279` | OneOf | Sata7 eSATA Port4 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1cb` | `0x5000` | `0x27a` | OneOf | Sata7 eSATA Port5 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1cc` | `0x5000` | `0x27b` | OneOf | Sata7 eSATA Port6 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1cd` | `0x5000` | `0x27c` | OneOf | Sata7 eSATA Port7 | - |
| P3.90 | `CbsSetupDxeGN` | `0x1cf` | `0x5000` | `0x27d` | OneOf | Socket1 DevSlp0 Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1d0` | `0x5000` | `0x27e` | Numeric | DevSleep0 Port Number | - |
| P3.90 | `CbsSetupDxeGN` | `0x1d1` | `0x5000` | `0x27f` | OneOf | Socket1 DevSlp1 Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1d2` | `0x5000` | `0x280` | Numeric | DevSleep1 Port Number | - |
| P3.90 | `CbsSetupDxeGN` | `0x1d3` | `0x5000` | `0x281` | OneOf | Sata0 SGPIO | - |
| P3.90 | `CbsSetupDxeGN` | `0x1d4` | `0x5000` | `0x282` | OneOf | Sata1 SGPIO | - |
| P3.90 | `CbsSetupDxeGN` | `0x1d5` | `0x5000` | `0x283` | OneOf | Sata2 SGPIO | - |
| P3.90 | `CbsSetupDxeGN` | `0x1d6` | `0x5000` | `0x284` | OneOf | Sata3 SGPIO | - |
| P3.90 | `CbsSetupDxeGN` | `0x1d7` | `0x5000` | `0x285` | OneOf | Sata4 SGPIO | - |
| P3.90 | `CbsSetupDxeGN` | `0x1d8` | `0x5000` | `0x286` | OneOf | Sata5 SGPIO | - |
| P3.90 | `CbsSetupDxeGN` | `0x1d9` | `0x5000` | `0x287` | OneOf | Sata6 SGPIO | - |
| P3.90 | `CbsSetupDxeGN` | `0x1da` | `0x5000` | `0x288` | OneOf | Sata7 SGPIO | - |
| P3.90 | `CbsSetupDxeGN` | `0x1db` | `0x5000` | `0x289` | OneOf | XHCI Controller0 enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1dc` | `0x5000` | `0x28a` | OneOf | XHCI Controller1 enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1dd` | `0x5000` | `0x28b` | OneOf | USB ecc SMI Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1df` | `0x5000` | `0x28c` | OneOf | XHCI2 enable (Socket1) | - |
| P3.90 | `CbsSetupDxeGN` | `0x1e0` | `0x5000` | `0x28d` | OneOf | XHCI3 enable (Socket1) | - |
| P3.90 | `CbsSetupDxeGN` | `0x1e1` | `0x5000` | `0x28e` | OneOf | SD Configuration Mode | - |
| P3.90 | `CbsSetupDxeGN` | `0x1e2` | `0x5000` | `0x28f` | OneOf | Ac Loss Control | - |
| P3.90 | `CbsSetupDxeGN` | `0x1e3` | `0x5000` | `0x290` | OneOf | I2C 0 Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1e4` | `0x5000` | `0x291` | OneOf | I2C 1 Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1e5` | `0x5000` | `0x292` | OneOf | I2C 2 Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1e6` | `0x5000` | `0x293` | OneOf | I2C 3 Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1e7` | `0x5000` | `0x294` | OneOf | I2C 4 Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1e8` | `0x5000` | `0x295` | OneOf | I2C 5 Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1e9` | `0x5000` | `0x296` | OneOf | Uart 0 Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1ea` | `0x5000` | `0x297` | OneOf | Uart 0 Legacy Options | - |
| P3.90 | `CbsSetupDxeGN` | `0x1eb` | `0x5000` | `0x298` | OneOf | Uart 1 Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1ec` | `0x5000` | `0x299` | OneOf | Uart 1 Legacy Options | - |
| P3.90 | `CbsSetupDxeGN` | `0x1ed` | `0x5000` | `0x29a` | OneOf | Uart 2 Enable (no HW FC) | - |
| P3.90 | `CbsSetupDxeGN` | `0x1ee` | `0x5000` | `0x29b` | OneOf | Uart 2 Legacy Options | - |
| P3.90 | `CbsSetupDxeGN` | `0x1ef` | `0x5000` | `0x29c` | OneOf | Uart 3 Enable (no HW FC) | - |
| P3.90 | `CbsSetupDxeGN` | `0x1f0` | `0x5000` | `0x29d` | OneOf | Uart 3 Legacy Options | - |
| P3.90 | `CbsSetupDxeGN` | `0x1f1` | `0x5000` | `0x29e` | OneOf | ALink RAS Support | - |
| P3.90 | `CbsSetupDxeGN` | `0x1f4` | `0x5000` | `0x2a1` | OneOf | Socket-0 P0 NTB Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1f5` | `0x5000` | `0x2a2` | Numeric | Socket-0 P0 Start Lane | - |
| P3.90 | `CbsSetupDxeGN` | `0x1f6` | `0x5000` | `0x2a3` | Numeric | Socket-0 P0 End Lane | - |
| P3.90 | `CbsSetupDxeGN` | `0x1f7` | `0x5000` | `0x2a4` | OneOf | Socket-0 P0 Link Speed | - |
| P3.90 | `CbsSetupDxeGN` | `0x1f8` | `0x5000` | `0x2a5` | OneOf | Socket-0 P0 NTB Mode | - |
| P3.90 | `CbsSetupDxeGN` | `0x1f9` | `0x5000` | `0x2a6` | OneOf | Socket-0 P1 NTB Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1fa` | `0x5000` | `0x2a7` | Numeric | Socket-0 P1 Start Lane | - |
| P3.90 | `CbsSetupDxeGN` | `0x1fb` | `0x5000` | `0x2a8` | Numeric | Socket-0 P1 End Lane | - |
| P3.90 | `CbsSetupDxeGN` | `0x1fc` | `0x5000` | `0x2a9` | OneOf | Socket-0 P1 Link Speed | - |
| P3.90 | `CbsSetupDxeGN` | `0x1fd` | `0x5000` | `0x2aa` | OneOf | Socket-0 P1 NTB Mode | - |
| P3.90 | `CbsSetupDxeGN` | `0x1fe` | `0x5000` | `0x2ab` | OneOf | Socket-0 P2 NTB Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x1ff` | `0x5000` | `0x2ac` | Numeric | Socket-0 P2 Start Lane | - |
| P3.90 | `CbsSetupDxeGN` | `0x200` | `0x5000` | `0x2ad` | Numeric | Socket-0 P2 End Lane | - |
| P3.90 | `CbsSetupDxeGN` | `0x201` | `0x5000` | `0x2ae` | OneOf | Socket-0 P2 Link Speed | - |
| P3.90 | `CbsSetupDxeGN` | `0x202` | `0x5000` | `0x2af` | OneOf | Socket-0 P2 NTB Mode | - |
| P3.90 | `CbsSetupDxeGN` | `0x203` | `0x5000` | `0x2b0` | OneOf | Socket-0 P3 NTB Enable | - |
| P3.90 | `CbsSetupDxeGN` | `0x204` | `0x5000` | `0x2b1` | Numeric | Socket-0 P3 Start Lane | - |
| P3.90 | `CbsSetupDxeGN` | `0x205` | `0x5000` | `0x2b2` | Numeric | Socket-0 P3 End Lane | - |
| P3.90 | `CbsSetupDxeGN` | `0x206` | `0x5000` | `0x2b3` | OneOf | Socket-0 P3 Link Speed | - |
| P3.90 | `CbsSetupDxeGN` | `0x207` | `0x5000` | `0x2b4` | OneOf | Socket-0 P3 NTB Mode | - |
| P3.90 | `CbsSetupDxeGN` | `0x20d` | `0x5000` | `0x2d0` | OneOf | Workload Profile | - |
| P3.90 | `CbsSetupDxeGN` | `0x20e` | `0x5000` | `0x2d1` | OneOf | Performance Tracing | - |
| P3.90 | `Setup` | `0x55` | `0x1` | `0x16e` | OneOf | Disable PrepareLink For Power Down Command | GrayOutIf(Q0x14b == 0x1) |
| P3.90 | `Setup` | `0xfd` | `0x1` | `0x16f` | OneOf | SATA Hot Plug | GrayOutIf(Q0x14b == 0x1) |
| P3.90 | `Setup` | `0x68` | `0x1` | `0x172` | OneOf | Onboard Debug Port LED | - |
| P3.90 | `Setup` | `0x131` | `0x1` | `0x173` | OneOf | Boot Beep | GrayOutIf(Q0x14b == 0x1) |
| P3.90 | `Setup` | `0x127` | `-` | `-` | Password | Supervisor Password | GrayOutIf(Q0x14b == 0x1) |
| P3.90 | `Setup` | `0x128` | `-` | `-` | Password | User Password | GrayOutIf(Q0x14b == 0x1) |

## 2. Settings removed in P3.80+

134 settings present in P3.70 disappeared in some later version.


| Last seen | Module | QID | VS | Offset | Type | Prompt |
|---|---|---|---|---|---|---|
| P3.70 | `CbsSetupDxeSSP` | `0x31` | `0x5000` | `0x9a` | OneOf | CCD Control |
| P3.80 | `CbsSetupDxeGN` | `0x7077` | `0x5000` | `0x227` | OneOf | SATA Enable |
| P3.80 | `CbsSetupDxeGN` | `0x16b` | `0x5000` | `0x228` | OneOf | SATA Mode |
| P3.80 | `CbsSetupDxeGN` | `0x16c` | `0x5000` | `0x229` | OneOf | Sata RAS Support |
| P3.80 | `CbsSetupDxeGN` | `0x16d` | `0x5000` | `0x22a` | OneOf | Sata Disabled AHCI Prefetch Function |
| P3.80 | `CbsSetupDxeGN` | `0x16e` | `0x5000` | `0x22b` | OneOf | Aggresive SATA Device Sleep Port 0 |
| P3.80 | `CbsSetupDxeGN` | `0x16f` | `0x5000` | `0x22c` | Numeric | DevSleep0 Port Number |
| P3.80 | `CbsSetupDxeGN` | `0x170` | `0x5000` | `0x22d` | OneOf | Aggresive SATA Device Sleep Port 1 |
| P3.80 | `CbsSetupDxeGN` | `0x171` | `0x5000` | `0x22e` | Numeric | DevSleep1 Port Number |
| P3.80 | `CbsSetupDxeGN` | `0x187` | `0x5000` | `0x237` | OneOf | Sata0 eSATA Port0 |
| P3.80 | `CbsSetupDxeGN` | `0x188` | `0x5000` | `0x238` | OneOf | Sata0 eSATA Port1 |
| P3.80 | `CbsSetupDxeGN` | `0x189` | `0x5000` | `0x239` | OneOf | Sata0 eSATA Port2 |
| P3.80 | `CbsSetupDxeGN` | `0x18a` | `0x5000` | `0x23a` | OneOf | Sata0 eSATA Port3 |
| P3.80 | `CbsSetupDxeGN` | `0x18b` | `0x5000` | `0x23b` | OneOf | Sata0 eSATA Port4 |
| P3.80 | `CbsSetupDxeGN` | `0x18c` | `0x5000` | `0x23c` | OneOf | Sata0 eSATA Port5 |
| P3.80 | `CbsSetupDxeGN` | `0x18d` | `0x5000` | `0x23d` | OneOf | Sata0 eSATA Port6 |
| P3.80 | `CbsSetupDxeGN` | `0x18e` | `0x5000` | `0x23e` | OneOf | Sata0 eSATA Port7 |
| P3.80 | `CbsSetupDxeGN` | `0x18f` | `0x5000` | `0x23f` | OneOf | Sata1 eSATA Port0 |
| P3.80 | `CbsSetupDxeGN` | `0x190` | `0x5000` | `0x240` | OneOf | Sata1 eSATA Port1 |
| P3.80 | `CbsSetupDxeGN` | `0x191` | `0x5000` | `0x241` | OneOf | Sata1 eSATA Port2 |
| P3.80 | `CbsSetupDxeGN` | `0x192` | `0x5000` | `0x242` | OneOf | Sata1 eSATA Port3 |
| P3.80 | `CbsSetupDxeGN` | `0x193` | `0x5000` | `0x243` | OneOf | Sata1 eSATA Port4 |
| P3.80 | `CbsSetupDxeGN` | `0x194` | `0x5000` | `0x244` | OneOf | Sata1 eSATA Port5 |
| P3.80 | `CbsSetupDxeGN` | `0x195` | `0x5000` | `0x245` | OneOf | Sata1 eSATA Port6 |
| P3.80 | `CbsSetupDxeGN` | `0x196` | `0x5000` | `0x246` | OneOf | Sata1 eSATA Port7 |
| P3.80 | `CbsSetupDxeGN` | `0x197` | `0x5000` | `0x247` | OneOf | Sata2 eSATA Port0 |
| P3.80 | `CbsSetupDxeGN` | `0x198` | `0x5000` | `0x248` | OneOf | Sata2 eSATA Port1 |
| P3.80 | `CbsSetupDxeGN` | `0x199` | `0x5000` | `0x249` | OneOf | Sata2 eSATA Port2 |
| P3.80 | `CbsSetupDxeGN` | `0x19a` | `0x5000` | `0x24a` | OneOf | Sata2 eSATA Port3 |
| P3.80 | `CbsSetupDxeGN` | `0x19b` | `0x5000` | `0x24b` | OneOf | Sata2 eSATA Port4 |
| P3.80 | `CbsSetupDxeGN` | `0x19c` | `0x5000` | `0x24c` | OneOf | Sata2 eSATA Port5 |
| P3.80 | `CbsSetupDxeGN` | `0x19d` | `0x5000` | `0x24d` | OneOf | Sata2 eSATA Port6 |
| P3.80 | `CbsSetupDxeGN` | `0x19e` | `0x5000` | `0x24e` | OneOf | Sata2 eSATA Port7 |
| P3.80 | `CbsSetupDxeGN` | `0x19f` | `0x5000` | `0x24f` | OneOf | Sata3 eSATA Port0 |
| P3.80 | `CbsSetupDxeGN` | `0x1a0` | `0x5000` | `0x250` | OneOf | Sata3 eSATA Port1 |
| P3.80 | `CbsSetupDxeGN` | `0x1a1` | `0x5000` | `0x251` | OneOf | Sata3 eSATA Port2 |
| P3.80 | `CbsSetupDxeGN` | `0x1a2` | `0x5000` | `0x252` | OneOf | Sata3 eSATA Port3 |
| P3.80 | `CbsSetupDxeGN` | `0x1a3` | `0x5000` | `0x253` | OneOf | Sata3 eSATA Port4 |
| P3.80 | `CbsSetupDxeGN` | `0x1a4` | `0x5000` | `0x254` | OneOf | Sata3 eSATA Port5 |
| P3.80 | `CbsSetupDxeGN` | `0x1a5` | `0x5000` | `0x255` | OneOf | Sata3 eSATA Port6 |
| P3.80 | `CbsSetupDxeGN` | `0x1a6` | `0x5000` | `0x256` | OneOf | Sata3 eSATA Port7 |
| P3.80 | `CbsSetupDxeGN` | `0x1a7` | `0x5000` | `0x257` | OneOf | Sata4 eSATA Port0 |
| P3.80 | `CbsSetupDxeGN` | `0x1a8` | `0x5000` | `0x258` | OneOf | Sata4 eSATA Port1 |
| P3.80 | `CbsSetupDxeGN` | `0x1a9` | `0x5000` | `0x259` | OneOf | Sata4 eSATA Port2 |
| P3.80 | `CbsSetupDxeGN` | `0x1aa` | `0x5000` | `0x25a` | OneOf | Sata4 eSATA Port3 |
| P3.80 | `CbsSetupDxeGN` | `0x1ab` | `0x5000` | `0x25b` | OneOf | Sata4 eSATA Port4 |
| P3.80 | `CbsSetupDxeGN` | `0x1ac` | `0x5000` | `0x25c` | OneOf | Sata4 eSATA Port5 |
| P3.80 | `CbsSetupDxeGN` | `0x1ad` | `0x5000` | `0x25d` | OneOf | Sata4 eSATA Port6 |
| P3.80 | `CbsSetupDxeGN` | `0x1ae` | `0x5000` | `0x25e` | OneOf | Sata4 eSATA Port7 |
| P3.80 | `CbsSetupDxeGN` | `0x1af` | `0x5000` | `0x25f` | OneOf | Sata5 eSATA Port0 |
| P3.80 | `CbsSetupDxeGN` | `0x1b0` | `0x5000` | `0x260` | OneOf | Sata5 eSATA Port1 |
| P3.80 | `CbsSetupDxeGN` | `0x1b1` | `0x5000` | `0x261` | OneOf | Sata5 eSATA Port2 |
| P3.80 | `CbsSetupDxeGN` | `0x1b2` | `0x5000` | `0x262` | OneOf | Sata5 eSATA Port3 |
| P3.80 | `CbsSetupDxeGN` | `0x1b3` | `0x5000` | `0x263` | OneOf | Sata5 eSATA Port4 |
| P3.80 | `CbsSetupDxeGN` | `0x1b4` | `0x5000` | `0x264` | OneOf | Sata5 eSATA Port5 |
| P3.80 | `CbsSetupDxeGN` | `0x1b5` | `0x5000` | `0x265` | OneOf | Sata5 eSATA Port6 |
| P3.80 | `CbsSetupDxeGN` | `0x1b6` | `0x5000` | `0x266` | OneOf | Sata5 eSATA Port7 |
| P3.80 | `CbsSetupDxeGN` | `0x1b7` | `0x5000` | `0x267` | OneOf | Sata6 eSATA Port0 |
| P3.80 | `CbsSetupDxeGN` | `0x1b8` | `0x5000` | `0x268` | OneOf | Sata6 eSATA Port1 |
| P3.80 | `CbsSetupDxeGN` | `0x1b9` | `0x5000` | `0x269` | OneOf | Sata6 eSATA Port2 |
| P3.80 | `CbsSetupDxeGN` | `0x1ba` | `0x5000` | `0x26a` | OneOf | Sata6 eSATA Port3 |
| P3.80 | `CbsSetupDxeGN` | `0x1bb` | `0x5000` | `0x26b` | OneOf | Sata6 eSATA Port4 |
| P3.80 | `CbsSetupDxeGN` | `0x1bc` | `0x5000` | `0x26c` | OneOf | Sata6 eSATA Port5 |
| P3.80 | `CbsSetupDxeGN` | `0x1bd` | `0x5000` | `0x26d` | OneOf | Sata6 eSATA Port6 |
| P3.80 | `CbsSetupDxeGN` | `0x1be` | `0x5000` | `0x26e` | OneOf | Sata6 eSATA Port7 |
| P3.80 | `CbsSetupDxeGN` | `0x1bf` | `0x5000` | `0x26f` | OneOf | Sata7 eSATA Port0 |
| P3.80 | `CbsSetupDxeGN` | `0x1c0` | `0x5000` | `0x270` | OneOf | Sata7 eSATA Port1 |
| P3.80 | `CbsSetupDxeGN` | `0x1c1` | `0x5000` | `0x271` | OneOf | Sata7 eSATA Port2 |
| P3.80 | `CbsSetupDxeGN` | `0x1c2` | `0x5000` | `0x272` | OneOf | Sata7 eSATA Port3 |
| P3.80 | `CbsSetupDxeGN` | `0x1c3` | `0x5000` | `0x273` | OneOf | Sata7 eSATA Port4 |
| P3.80 | `CbsSetupDxeGN` | `0x1c4` | `0x5000` | `0x274` | OneOf | Sata7 eSATA Port5 |
| P3.80 | `CbsSetupDxeGN` | `0x1c5` | `0x5000` | `0x275` | OneOf | Sata7 eSATA Port6 |
| P3.80 | `CbsSetupDxeGN` | `0x1c6` | `0x5000` | `0x276` | OneOf | Sata7 eSATA Port7 |
| P3.80 | `CbsSetupDxeGN` | `0x1c8` | `0x5000` | `0x277` | OneOf | Socket1 DevSlp0 Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1c9` | `0x5000` | `0x278` | Numeric | DevSleep0 Port Number |
| P3.80 | `CbsSetupDxeGN` | `0x1ca` | `0x5000` | `0x279` | OneOf | Socket1 DevSlp1 Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1cb` | `0x5000` | `0x27a` | Numeric | DevSleep1 Port Number |
| P3.80 | `CbsSetupDxeGN` | `0x1cc` | `0x5000` | `0x27b` | OneOf | Sata0 SGPIO |
| P3.80 | `CbsSetupDxeGN` | `0x1cd` | `0x5000` | `0x27c` | OneOf | Sata1 SGPIO |
| P3.80 | `CbsSetupDxeGN` | `0x1ce` | `0x5000` | `0x27d` | OneOf | Sata2 SGPIO |
| P3.80 | `CbsSetupDxeGN` | `0x1cf` | `0x5000` | `0x27e` | OneOf | Sata3 SGPIO |
| P3.80 | `CbsSetupDxeGN` | `0x1d0` | `0x5000` | `0x27f` | OneOf | Sata4 SGPIO |
| P3.80 | `CbsSetupDxeGN` | `0x1d1` | `0x5000` | `0x280` | OneOf | Sata5 SGPIO |
| P3.80 | `CbsSetupDxeGN` | `0x1d2` | `0x5000` | `0x281` | OneOf | Sata6 SGPIO |
| P3.80 | `CbsSetupDxeGN` | `0x1d3` | `0x5000` | `0x282` | OneOf | Sata7 SGPIO |
| P3.80 | `CbsSetupDxeGN` | `0x1d4` | `0x5000` | `0x283` | OneOf | XHCI Controller0 enable |
| P3.80 | `CbsSetupDxeGN` | `0x1d5` | `0x5000` | `0x284` | OneOf | XHCI Controller1 enable |
| P3.80 | `CbsSetupDxeGN` | `0x1d6` | `0x5000` | `0x285` | OneOf | USB ecc SMI Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1d8` | `0x5000` | `0x286` | OneOf | XHCI2 enable (Socket1) |
| P3.80 | `CbsSetupDxeGN` | `0x1d9` | `0x5000` | `0x287` | OneOf | XHCI3 enable (Socket1) |
| P3.80 | `CbsSetupDxeGN` | `0x1da` | `0x5000` | `0x288` | OneOf | SD Configuration Mode |
| P3.80 | `CbsSetupDxeGN` | `0x1db` | `0x5000` | `0x289` | OneOf | Ac Loss Control |
| P3.80 | `CbsSetupDxeGN` | `0x1dc` | `0x5000` | `0x28a` | OneOf | I2C 0 Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1dd` | `0x5000` | `0x28b` | OneOf | I2C 1 Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1de` | `0x5000` | `0x28c` | OneOf | I2C 2 Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1df` | `0x5000` | `0x28d` | OneOf | I2C 3 Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1e0` | `0x5000` | `0x28e` | OneOf | I2C 4 Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1e1` | `0x5000` | `0x28f` | OneOf | I2C 5 Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1e2` | `0x5000` | `0x290` | OneOf | Uart 0 Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1e3` | `0x5000` | `0x291` | OneOf | Uart 0 Legacy Options |
| P3.80 | `CbsSetupDxeGN` | `0x1e4` | `0x5000` | `0x292` | OneOf | Uart 1 Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1e5` | `0x5000` | `0x293` | OneOf | Uart 1 Legacy Options |
| P3.80 | `CbsSetupDxeGN` | `0x1e6` | `0x5000` | `0x294` | OneOf | Uart 2 Enable (no HW FC) |
| P3.80 | `CbsSetupDxeGN` | `0x1e7` | `0x5000` | `0x295` | OneOf | Uart 2 Legacy Options |
| P3.80 | `CbsSetupDxeGN` | `0x1e8` | `0x5000` | `0x296` | OneOf | Uart 3 Enable (no HW FC) |
| P3.80 | `CbsSetupDxeGN` | `0x1e9` | `0x5000` | `0x297` | OneOf | Uart 3 Legacy Options |
| P3.80 | `CbsSetupDxeGN` | `0x1ea` | `0x5000` | `0x298` | OneOf | ALink RAS Support |
| P3.80 | `CbsSetupDxeGN` | `0x1ed` | `0x5000` | `0x29b` | OneOf | Socket-0 P0 NTB Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1ee` | `0x5000` | `0x29c` | Numeric | Socket-0 P0 Start Lane |
| P3.80 | `CbsSetupDxeGN` | `0x1ef` | `0x5000` | `0x29d` | Numeric | Socket-0 P0 End Lane |
| P3.80 | `CbsSetupDxeGN` | `0x1f0` | `0x5000` | `0x29e` | OneOf | Socket-0 P0 Link Speed |
| P3.80 | `CbsSetupDxeGN` | `0x1f1` | `0x5000` | `0x29f` | OneOf | Socket-0 P0 NTB Mode |
| P3.80 | `CbsSetupDxeGN` | `0x1f2` | `0x5000` | `0x2a0` | OneOf | Socket-0 P1 NTB Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1f3` | `0x5000` | `0x2a1` | Numeric | Socket-0 P1 Start Lane |
| P3.80 | `CbsSetupDxeGN` | `0x1f4` | `0x5000` | `0x2a2` | Numeric | Socket-0 P1 End Lane |
| P3.80 | `CbsSetupDxeGN` | `0x1f5` | `0x5000` | `0x2a3` | OneOf | Socket-0 P1 Link Speed |
| P3.80 | `CbsSetupDxeGN` | `0x1f6` | `0x5000` | `0x2a4` | OneOf | Socket-0 P1 NTB Mode |
| P3.80 | `CbsSetupDxeGN` | `0x1f7` | `0x5000` | `0x2a5` | OneOf | Socket-0 P2 NTB Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1f8` | `0x5000` | `0x2a6` | Numeric | Socket-0 P2 Start Lane |
| P3.80 | `CbsSetupDxeGN` | `0x1f9` | `0x5000` | `0x2a7` | Numeric | Socket-0 P2 End Lane |
| P3.80 | `CbsSetupDxeGN` | `0x1fa` | `0x5000` | `0x2a8` | OneOf | Socket-0 P2 Link Speed |
| P3.80 | `CbsSetupDxeGN` | `0x1fb` | `0x5000` | `0x2a9` | OneOf | Socket-0 P2 NTB Mode |
| P3.80 | `CbsSetupDxeGN` | `0x1fc` | `0x5000` | `0x2aa` | OneOf | Socket-0 P3 NTB Enable |
| P3.80 | `CbsSetupDxeGN` | `0x1fd` | `0x5000` | `0x2ab` | Numeric | Socket-0 P3 Start Lane |
| P3.80 | `CbsSetupDxeGN` | `0x1fe` | `0x5000` | `0x2ac` | Numeric | Socket-0 P3 End Lane |
| P3.80 | `CbsSetupDxeGN` | `0x1ff` | `0x5000` | `0x2ad` | OneOf | Socket-0 P3 Link Speed |
| P3.80 | `CbsSetupDxeGN` | `0x200` | `0x5000` | `0x2ae` | OneOf | Socket-0 P3 NTB Mode |
| P3.80 | `CbsSetupDxeGN` | `0x205` | `0x5000` | `0x2c9` | OneOf | Workload Profile |
| P3.80 | `CbsSetupDxeGN` | `0x206` | `0x5000` | `0x2ca` | OneOf | Performance Tracing |
| P3.80 | `Setup` | `0xfc` | `0x1` | `0x16e` | OneOf | SATA Hot Plug |
| P3.80 | `Setup` | `0x67` | `0x1` | `0x171` | OneOf | Onboard Debug Port LED |
| P3.80 | `Setup` | `0x130` | `0x1` | `0x172` | OneOf | Boot Beep |
| P3.80 | `Setup` | `0x126` | `-` | `-` | Password | Supervisor Password |
| P3.80 | `Setup` | `0x127` | `-` | `-` | Password | User Password |

## 3. Settings with changed SuppressIf/GrayOutIf/DisableIf

102 settings had a different condition stack in some version.


| Module | QID | Prompt | P3.70 | P3.80 | P3.90 | P4.10 |
|---|---|---|---|---|---|---|
| `Setup` | `0x12f` | Bootup Num-Lock | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x2f` | TCM State | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x2c` | TPM State | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x2760` | CSM | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x132` | AddOn ROM Display | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xd4` | HDD Connection Order | SuppressIf(Q0x12d == 0x2) | SuppressIf(Q0x12d == 0x2) | SuppressIf(Q0x12e == 0x2) | SuppressIf(Q0x12e == 0x2) |
| `Setup` | `0x134` | Launch PXE OpROM Policy | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xf5` | PCIE Devices Power On | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xf6` | Ring-In Power On | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xf7` | RTC Alarm Power On | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xf8` | RTC Alarm Date | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xda` | PCIE1 Link Width | GrayOutIf(Q0x14a == 0x1); GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1); GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1); GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1); GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xdb` | PCIE2/M2_1 Link Width | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xdc` | PCIE3 Link Width | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xdd` | PCIE4 Link Width | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xde` | PCIE5 Link Width | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xdf` | PCIE6 Link Width | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xe0` | PCIE7 Link Width | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xe1` | PCIE1 Link Speed | GrayOutIf(Q0x14a == 0x1); GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1); GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1); GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1); GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xe2` | PCIE2 Link Speed | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xe3` | PCIE3 Link Speed | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xe4` | PCIE4 Link Speed | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xe5` | PCIE5 Link Speed | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xe6` | PCIE6 Link Speed | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xe7` | PCIE7 Link Speed | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xe8` | OCU1 Link Speed | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xe9` | OCU2 Link Speed | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xea` | M2_1 Link Speed | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xeb` | M2_2 Link Speed | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xec` | PCIE1 HotPlug | GrayOutIf(Q0x14a == 0x1); GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1); GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1); GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1); GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x3f` | Device Select | GrayOutIf(Q0x14a == 0x1); SuppressIf(Q0x32 == 0x0) | GrayOutIf(Q0x14a == 0x1); SuppressIf(Q0x32 == 0x0) | GrayOutIf(Q0x14b == 0x1); SuppressIf(Q0x32 == 0x0) | GrayOutIf(Q0x14b == 0x1); SuppressIf(Q0x32 == 0x0) |
| `Setup` | `0xed` | PCIE2 HotPlug | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xee` | PCIE3 HotPlug | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xef` | PCIE4 HotPlug | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xf0` | PCIE5 HotPlug | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xf1` | PCIE6 HotPlug | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xf2` | PCIE7 HotPlug | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xf3` | OCU1 HotPlug | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xf4` | OCU2 HotPlug | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x108` | Watch Dog Timer | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x58` | Onboard LAN1 | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x56` | Onboard VGA | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x55` | Primary Graphics Adapter | SuppressIf(Q0x2760 == 0x0); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0x2760 == 0x0); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0x2760 == 0x0); GrayOutIf(Q0x14b == 0x1) | SuppressIf(Q0x2760 == 0x0); GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x57` | SPI/LPC TPM switch | - | - | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x40` | Disable Block Sid | SuppressIf(Q0x1cd == 0x0) | SuppressIf(Q0x1cd == 0x0) | SuppressIf(Q0x1ce == 0x0) | SuppressIf(Q0x1ce == 0x0) |
| `Setup` | `0x69` | Enable ACPI Auto Configuration | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x32` | Security Device Support | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x113` | Aggressive Link PM Capability | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x114` | Port Multiplier Capability | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x115` | SATA Ports Auto Clock Control | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x116` | SATA Partial State Capability | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x117` | SATA FIS Based Switching | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x118` | SATA Command Completion Coalescing Support | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x119` | SATA Slumber State Capability | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x11a` | SATA Target Support 8 Devices | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x11b` | Generic Mode | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x11c` | SATA AHCI Enclosure | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x11d` | SATA SGPIO 0 | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x11e` | TimerTick Tracking | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x11f` | Clock Interrupt Tag | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x120` | SB Clock Spread Spectrum | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x121` | HPET In SB | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x122` | MsiDis in HPET | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x6e` | OnBrd/Ext VGA Select | SuppressIf(Q0x136 == 0x1) | SuppressIf(Q0x136 == 0x1) | SuppressIf(Q0x137 == 0x1) | SuppressIf(Q0x137 == 0x1) |
| `Setup` | `0x76` | Console Redirection | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x78` | Console Redirection | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x84` | Terminal Type | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x8e` | Terminal Type | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x7b` | Console Redirection EMS | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x7d` | Out-of-Band Mgmt Port | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x7e` | Terminal Type EMS | GrayOutIf(Q0x7b == 0x0) | GrayOutIf(Q0x7b == 0x0) | GrayOutIf(Q0x7c == 0x0) | GrayOutIf(Q0x7c == 0x0) |
| `Setup` | `0x7f` | Bits per second EMS | GrayOutIf(Q0x7b == 0x0) | GrayOutIf(Q0x7b == 0x0) | GrayOutIf(Q0x7c == 0x0) | GrayOutIf(Q0x7c == 0x0) |
| `Setup` | `0x80` | Flow Control EMS | GrayOutIf(Q0x7b == 0x0) | GrayOutIf(Q0x7b == 0x0) | GrayOutIf(Q0x7c == 0x0) | GrayOutIf(Q0x7c == 0x0) |
| `Setup` | `0x81` | Redirection COM Port | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x9e` | USB Support | SuppressIf(Q0x9e == Q0x9e); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0x9e == Q0x9e); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0x9f == Q0x9f); GrayOutIf(Q0x14b == 0x1) | SuppressIf(Q0x9f == Q0x9f); GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x107` | Legacy USB Support | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xa3` | EHCI Hand-off | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xa1` | Legacy USB 3.0 Support | SuppressIf(True); GrayOutIf(Q0x14a == 0x1) | SuppressIf(True); GrayOutIf(Q0x14a == 0x1) | SuppressIf(True); GrayOutIf(Q0x14b == 0x1) | SuppressIf(True); GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xa2` | XHCI Hand-off | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xa9` | Device power-up delay in seconds | SuppressIf(Q0xa8 == 0x0) | SuppressIf(Q0xa8 == 0x0) | SuppressIf(Q0xa9 == 0x0) | SuppressIf(Q0xa9 == 0x0) |
| `Setup` | `0xa0` | USB 2.0 Controller Mode | SuppressIf(True); GrayOutIf(Q0x14a == 0x1) | SuppressIf(True); GrayOutIf(Q0x14a == 0x1) | SuppressIf(True); GrayOutIf(Q0x14b == 0x1) | SuppressIf(True); GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xa4` | USB Mass Storage Driver Support | SuppressIf(Q0x9e == 0x0) | SuppressIf(Q0x9e == 0x0) | SuppressIf(Q0x9f == 0x0) | SuppressIf(Q0x9f == 0x0) |
| `Setup` | `0xa5` | Port 60/64 Emulation | SuppressIf(Q0x9e == 0x0); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0x9e == 0x0); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0x9f == 0x0); GrayOutIf(Q0x14b == 0x1) | SuppressIf(Q0x9f == 0x0); GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0xa7` | Device reset time-out | SuppressIf(Q0x9e == 0x0) | SuppressIf(Q0x9e == 0x0) | SuppressIf(Q0x9f == 0x0) | SuppressIf(Q0x9f == 0x0) |
| `Setup` | `0xa6` | USB transfer time-out | SuppressIf(Q0x9e == 0x0) | SuppressIf(Q0x9e == 0x0) | SuppressIf(Q0x9f == 0x0) | SuppressIf(Q0x9f == 0x0) |
| `Setup` | `0xca` | Network Stack | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | - | - |
| `Setup` | `0xcb` | IPv4 PXE Support | SuppressIf(Q0xca == 0x0); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0xca == 0x0); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0xcb == 0x0) | SuppressIf(Q0xcb == 0x0) |
| `Setup` | `0xcd` | IPv6 PXE Support | SuppressIf(Q0xca == 0x0); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0xca == 0x0); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0xcb == 0x0) | SuppressIf(Q0xcb == 0x0) |
| `Setup` | `0xcf` | PXE boot wait time | SuppressIf(Q0xca == 0x0); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0xca == 0x0); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0xcb == 0x0) | SuppressIf(Q0xcb == 0x0) |
| `Setup` | `0xd0` | Media detect count | SuppressIf(Q0xca == 0x0); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0xca == 0x0); GrayOutIf(Q0x14a == 0x1) | SuppressIf(Q0xcb == 0x0) | SuppressIf(Q0xcb == 0x0) |
| `Setup` | `0xcc` | IPv4 HTTP Support | SuppressIf(Q0xca == 0x0) | SuppressIf(Q0xca == 0x0) | - | - |
| `Setup` | `0xce` | IPv6 HTTP Support | SuppressIf(Q0xca == 0x0) | SuppressIf(Q0xca == 0x0) | - | - |
| `Setup` | `0x2785` | Secure Boot | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x72` | Serial Port | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x73` | Change Settings | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1); SuppressIf(Q0x73 == 0x0) | GrayOutIf(Q0x14b == 0x1); SuppressIf(Q0x73 == 0x0) |
| `Setup` | `0x74` | SOL Port | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x75` | Change Settings | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x12a` | Driver Option #%d | SuppressIf(Q0x14c in [65535]) | SuppressIf(Q0x14c in [65535]) | SuppressIf(Q0x14d in [65535]) | SuppressIf(Q0x14d in [65535]) |
| `Setup` | `0x12e` | Setup Prompt Timeout | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |
| `Setup` | `0x12c` | Boot Option #%d | SuppressIf(Q0x149 in [65535]) | SuppressIf(Q0x149 in [65535]) | SuppressIf(Q0x14a in [65535]) | SuppressIf(Q0x14a in [65535]) |
| `Setup` | `0x7` | System Language | SuppressIf(Q0x1d6 == 0xffff) | SuppressIf(Q0x1d6 == 0xffff) | SuppressIf(Q0x1d7 == 0xffff) | SuppressIf(Q0x1d7 == 0xffff) |
| `Setup` | `0x131` | Full Screen Logo | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14a == 0x1) | GrayOutIf(Q0x14b == 0x1) | GrayOutIf(Q0x14b == 0x1) |

## 4. Settings with changed prompt/name across versions

_(no prompt changes)_


## 5. New VarStores introduced post-P3.70

_(no new VarStores)_


## 6. Settings matching Gen4/ESM/DXIO/Strap/Override/Force/Speed keywords (per version)

Keyword set: gen4, gen5, esm, dxio, strap, override, force, linkcap, linkspeed, link speed, link width, rev 1.02, rev 1.03, 1.02a, 1.03.


| Version | Settings matching |
|---|---:|
| P3.70 | 53 |
| P3.80 | 53 |
| P3.90 | 55 |
| P4.10 | 55 |

### 6a. Settings whose keyword-match status changed across versions

_(no setting's Gen4/DXIO keyword profile changed — i.e., no version added or removed a Gen4-related option)_


### 6b. Top-priority Gen4-relevant settings — full listing per version

16 (version, setting) pairs hit a high-priority keyword.


| Version | Module | QID | Prompt | Hits |
|---|---|---|---|---|
| P3.70 | `CbsSetupDxeGN` | `0x116` | Multi Upstream Auto Speed Change | dxio |
| P3.70 | `CbsSetupDxeSSP` | `0xee` | Enable Rcv Err and Bad TLP Mask | gen4 |
| P3.70 | `CbsSetupDxeSSP` | `0xfb` | Multi Upstream Auto Speed Change | dxio |
| P3.80 | `CbsSetupDxeGN` | `0x116` | Multi Upstream Auto Speed Change | dxio |
| P3.80 | `CbsSetupDxeSSP` | `0xee` | Enable Rcv Err and Bad TLP Mask | gen4 |
| P3.80 | `CbsSetupDxeSSP` | `0xfb` | Multi Upstream Auto Speed Change | dxio |
| P3.90 | `CbsSetupDxeGN` | `0x116` | Multi Upstream Auto Speed Change | dxio |
| P3.90 | `CbsSetupDxeGN` | `0x168` | Preset Search Mask Configuration (Gen4) | gen4 |
| P3.90 | `CbsSetupDxeGN` | `0x169` | Preset Search Mask (Gen4) | gen4 |
| P3.90 | `CbsSetupDxeSSP` | `0xee` | Enable Rcv Err and Bad TLP Mask | gen4 |
| P3.90 | `CbsSetupDxeSSP` | `0xfb` | Multi Upstream Auto Speed Change | dxio |
| P4.10 | `CbsSetupDxeGN` | `0x116` | Multi Upstream Auto Speed Change | dxio |
| P4.10 | `CbsSetupDxeGN` | `0x168` | Preset Search Mask Configuration (Gen4) | gen4 |
| P4.10 | `CbsSetupDxeGN` | `0x169` | Preset Search Mask (Gen4) | gen4 |
| P4.10 | `CbsSetupDxeSSP` | `0xee` | Enable Rcv Err and Bad TLP Mask | gen4 |
| P4.10 | `CbsSetupDxeSSP` | `0xfb` | Multi Upstream Auto Speed Change | dxio |

## 7. Per-slot Link Speed entries (Setup VS `0x1`, offsets `0x123`–`0x130`)

**Correction to CLAUDE.md baseline:** the per-slot Link Speed OneOf in P3.70 ALREADY offers a GEN4 option (value=4) — see raw IFR for `Setup` module. Earlier Phase-1 narrative ('Auto/GEN1/GEN2/GEN3') was inaccurate. This section verifies the option set is identical across all 4 versions and that the user's NVRAM byte (currently 0x01 = GEN1) could in principle be set to 0x04 = GEN4.

Empirically (per CLAUDE.md), AGESA ignores these per-slot bytes — they are vestigial. So the GEN4 option in this OneOf is also vestigial. But the IFR has it.


### P3.70

| QID | Offset | Prompt | Option values |
|---|---|---|---|
| `0xe1` | `0x123` | PCIE1 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe2` | `0x124` | PCIE2 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe3` | `0x125` | PCIE3 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe4` | `0x126` | PCIE4 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe5` | `0x127` | PCIE5 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe6` | `0x128` | PCIE6 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe7` | `0x129` | PCIE7 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe8` | `0x12a` | OCU1 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe9` | `0x12b` | OCU2 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xea` | `0x12c` | M2_1 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xeb` | `0x12d` | M2_2 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xec` | `0x12f` | PCIE1 HotPlug | 0=Disabled, 1=Enabled |
| `0xed` | `0x130` | PCIE2 HotPlug | 0=Disabled, 1=Enabled |

### P3.80

| QID | Offset | Prompt | Option values |
|---|---|---|---|
| `0xe1` | `0x123` | PCIE1 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe2` | `0x124` | PCIE2 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe3` | `0x125` | PCIE3 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe4` | `0x126` | PCIE4 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe5` | `0x127` | PCIE5 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe6` | `0x128` | PCIE6 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe7` | `0x129` | PCIE7 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe8` | `0x12a` | OCU1 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe9` | `0x12b` | OCU2 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xea` | `0x12c` | M2_1 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xeb` | `0x12d` | M2_2 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xec` | `0x12f` | PCIE1 HotPlug | 0=Disabled, 1=Enabled |
| `0xed` | `0x130` | PCIE2 HotPlug | 0=Disabled, 1=Enabled |

### P3.90

| QID | Offset | Prompt | Option values |
|---|---|---|---|
| `0xe2` | `0x123` | PCIE1 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe3` | `0x124` | PCIE2 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe4` | `0x125` | PCIE3 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe5` | `0x126` | PCIE4 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe6` | `0x127` | PCIE5 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe7` | `0x128` | PCIE6 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe8` | `0x129` | PCIE7 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe9` | `0x12a` | OCU1 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xea` | `0x12b` | OCU2 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xeb` | `0x12c` | M2_1 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xec` | `0x12d` | M2_2 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xed` | `0x12f` | PCIE1 HotPlug | 0=Disabled, 1=Enabled |
| `0xee` | `0x130` | PCIE2 HotPlug | 0=Disabled, 1=Enabled |

### P4.10

| QID | Offset | Prompt | Option values |
|---|---|---|---|
| `0xe2` | `0x123` | PCIE1 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe3` | `0x124` | PCIE2 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe4` | `0x125` | PCIE3 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe5` | `0x126` | PCIE4 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe6` | `0x127` | PCIE5 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe7` | `0x128` | PCIE6 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe8` | `0x129` | PCIE7 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xe9` | `0x12a` | OCU1 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xea` | `0x12b` | OCU2 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xeb` | `0x12c` | M2_1 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xec` | `0x12d` | M2_2 Link Speed | 0=Auto, 4=GEN4, 3=GEN3, 2=GEN2, 1=GEN1 |
| `0xed` | `0x12f` | PCIE1 HotPlug | 0=Disabled, 1=Enabled |
| `0xee` | `0x130` | PCIE2 HotPlug | 0=Disabled, 1=Enabled |

## 8. Conclusion

**No Gen4-enable IFR option was added in any post-P3.70 version.** While 139 settings appear new in P3.80/3.90/4.10 and 134 disappeared, *none* of them mention Gen4, ESM, DXIO, or strap with a different keyword profile than P3.70. No SuppressIf condition gating a Gen4-related option changed. No new VarStores were introduced. The per-slot Link Speed OneOf in `Setup` retains the same Auto/GEN1/GEN2/GEN3/GEN4 option set across every version.

Most cross-version IFR changes are concentrated in `CbsSetupDxeGN` (the Genoa-family AGESA Setup module). That module is irrelevant to this Rome rig — Rome uses `CbsSetupDxeSSP`, which is nearly stable across versions (only `CCDs Control` was added in P3.80 — compute-die enablement, not PCIe). The notable Gen4-keyword additions in P3.90+ are `Preset Search Mask Configuration (Gen4)` / `Preset Search Mask (Gen4)` in `CbsSetupDxeGN` — PCIe equalization preset tuning for Genoa, not a Gen4 enable, and irrelevant to Rome.

Combined with subagent #1's APCB-byte-identical finding and subagent #5's ESM-decision-in-runtime-descriptor finding, this confirms **the Gen4 unlock (if any) cannot be activated by any IFR/NVRAM-side intervention.** It must be in runtime AGESA code or a binary descriptor synthesizer (i.e. `AmdApcbDxeV3`).
