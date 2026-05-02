# Long-form report — ROMED8-2T BIOS reverse-engineering

This directory contains the original Phase 1 long-form narrative, split for navigability. For the current synthesis (post-Phase 2) read [`../BIOS_LATEST.md`](../BIOS_LATEST.md) first; the documents here capture the earlier IFR-based analysis and the empirical follow-up that motivated Phase 2.

## Contents

| Part | Document | Subject |
|------|----------|---------|
| I | [`part-1-findings.md`](part-1-findings.md) | Phase 1 IFR-only analysis: per-slot offset table, Setup variable layout, original (since-superseded) verdict, risks, and what was deliberately not done. |
| III | [`part-3-empirical-followup.md`](part-3-empirical-followup.md) | Empirical follow-up after the rig NVRAM dump (2026-04-27): Q1–Q6 drilldown that contradicted the IFR-only conclusions and pointed at the APCB / DXIO descriptors as the actual cap source. |
| II | [`../docs/BIOS_REFERENCE_P3.70.md`](../docs/BIOS_REFERENCE_P3.70.md) | Complete machine-readable enumeration of every BIOS setting in P3.70 (15 modules, 291 forms, 1565 settings). Lookup table; not narrative. |

## Reading order

1. [`../BIOS_LATEST.md`](../BIOS_LATEST.md) — current synthesis (Phase 1 + Phase 2). Read first.
2. [`part-1-findings.md`](part-1-findings.md) — the IFR-only baseline. Most §1 conclusions are now superseded; preserved with strikethroughs for traceability.
3. [`part-3-empirical-followup.md`](part-3-empirical-followup.md) — what changed once the rig NVRAM dump arrived. This is what triggered Phase 2.
4. [`../docs/BIOS_REFERENCE_P3.70.md`](../docs/BIOS_REFERENCE_P3.70.md) — reference data, consulted as needed.

## Numbering note

Parts are labelled I / II / III for historical reasons (Part III was added after Part II had already been written as a long appendix). The split preserves the original labelling rather than renumbering.
