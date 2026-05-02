"""
Shared Python modules for ROMED8-2T BIOS analysis tooling.

Modules:
- ffs: FFS dump tree navigation (UEFIExtract output)
- pe32: PE32 module utilities (load, strings, function listing via r2-pipe)
- ifr: IFR text parser (ifrextractor-rs output)
- apcb: APCB binary structure decoder
- versions: per-BIOS-version path conventions

Convention: all functions take BIOS version as a string ("3.70", "3.80", "L3.11", etc.)
and resolve paths via the module-level conventions in `versions`.
"""
