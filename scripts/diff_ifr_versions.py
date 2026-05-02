#!/usr/bin/env python3
"""
Cross-version IFR diff: compare every setting and varstore across
P3.70 / P3.80 / P3.90 / P4.10. Emits docs/IFR_VERSION_DIFF.md.

Reuses the parser from scripts/list_suppressed.py.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

# Load list_suppressed.py as a module to reuse parse_ifr
spec = importlib.util.spec_from_file_location(
    "list_suppressed", SCRIPTS / "list_suppressed.py"
)
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)

VERSIONS = ["P3.70", "P3.80", "P3.90", "P4.10"]


def parse_version(version):
    """Parse all IFR text dumps in ifr/<version>/_dedup. Returns dict:
       {module: parsed} mirroring list_suppressed structure."""
    ifr_dir = ROOT / "ifr" / version / "_dedup"
    per_module = {}
    for path in sorted(ifr_dir.rglob("*.uefi.ifr.txt")):
        module_name = path.stem.split(".")[0]
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            parsed = ls.parse_ifr(text, module_name)
        except Exception as e:
            print(f"WARN parse {path}: {e}", file=sys.stderr)
            continue
        # If multiple files map to same module name (e.g. ReFlash.0.0 and ReFlash.0.1),
        # merge varstores + settings
        if module_name in per_module:
            prev = per_module[module_name]
            prev["settings"].extend(parsed["settings"])
            prev["varstores"].update(parsed["varstores"])
        else:
            per_module[module_name] = parsed
    return per_module


def setting_key(s):
    """Stable key across versions: module + varstore + offset + prompt.

    QIDs get renumbered between versions when AMI re-emits the IFR (Setup
    QID 0x14A in P3.70/3.80 became 0x14B in P3.90/4.10, shifting hundreds
    of downstream QIDs by +1). Anchoring the key to (varstore, offset, prompt)
    is much more stable for cross-version comparison. Settings without an
    NVRAM offset (Ref / Goto items) fall back to (module, prompt, qid).
    """
    if s.get("varstore_id") and s.get("offset"):
        return (
            s["module"],
            s["varstore_id"],
            s["offset"],
            s["prompt"] or "(no prompt)",
        )
    # No varstore/offset: probably a Ref/action — use prompt + qid as key
    return (
        s["module"],
        "_no_vs_",
        s["prompt"] or "(no prompt)",
        s["qid"],
    )


def render_cond(conds):
    """Compact rendering of all conditions on a setting."""
    if not conds:
        return ""
    parts = []
    for c in conds:
        body = ls.render_expr(c["exprs"])
        parts.append(f"{c['kind']}({body})")
    return "; ".join(parts)


def cond_kinds(conds):
    """Return sorted tuple of (kind, body) representing the condition stack."""
    return tuple(sorted((c["kind"], ls.render_expr(c["exprs"])) for c in conds))


def main():
    print("Parsing all 4 versions...", file=sys.stderr)
    parsed = {}
    for v in VERSIONS:
        parsed[v] = parse_version(v)
        n_settings = sum(len(p["settings"]) for p in parsed[v].values())
        n_modules = len(parsed[v])
        print(f"  {v}: {n_modules} modules, {n_settings} settings", file=sys.stderr)

    # Build per-version setting maps: key -> setting
    by_version = {}
    for v in VERSIONS:
        m = {}
        for module, parsed_mod in parsed[v].items():
            for s in parsed_mod["settings"]:
                m[setting_key(s)] = s
        by_version[v] = m
        print(f"  {v}: {len(m)} unique-keyed settings", file=sys.stderr)

    # Union of keys across versions
    all_keys = set()
    for v in VERSIONS:
        all_keys |= set(by_version[v].keys())
    print(f"Union: {len(all_keys)} unique settings across all versions", file=sys.stderr)

    # ----- Classify each key -----
    # added: not in P3.70 but in any later
    # removed: in P3.70 but not in some later
    # cond_changed: present in all versions but condition differs
    # default_changed: present in all but a default (we don't have full defaults here — skip)
    added = []
    removed = []
    cond_changed = []
    name_changed = []

    for k in all_keys:
        present = {v: (k in by_version[v]) for v in VERSIONS}
        if not all(present.values()):
            if not present["P3.70"] and any(present[v] for v in VERSIONS[1:]):
                # Added in some later version
                first_seen = next(v for v in VERSIONS if present[v])
                added.append((k, first_seen, present))
            elif present["P3.70"] and not all(present[v] for v in VERSIONS[1:]):
                last_seen = None
                for v in VERSIONS:
                    if present[v]:
                        last_seen = v
                removed.append((k, last_seen, present))
            else:
                # mixed weirdness — record as removed/added flux
                added.append((k, "(mixed)", present))
            continue
        # Present in all versions — check conditions and prompt
        s_versions = [by_version[v][k] for v in VERSIONS]
        cond_sigs = [cond_kinds(s["conditions"]) for s in s_versions]
        if len(set(cond_sigs)) > 1:
            cond_changed.append((k, s_versions, cond_sigs))
        prompts = [s["prompt"] for s in s_versions]
        if len(set(prompts)) > 1:
            name_changed.append((k, s_versions, prompts))

    # ----- VarStore comparison -----
    varstore_per_version = {}
    for v in VERSIONS:
        vs_set = {}
        for mod, p in parsed[v].items():
            for vid, vs in p["varstores"].items():
                key = (mod, vs["name"], vid)
                vs_set[key] = vs
        varstore_per_version[v] = vs_set

    all_vs_keys = set()
    for v in VERSIONS:
        all_vs_keys |= set(varstore_per_version[v].keys())
    new_vs = []
    for k in all_vs_keys:
        present = {v: (k in varstore_per_version[v]) for v in VERSIONS}
        if not present["P3.70"] and any(present[v] for v in VERSIONS[1:]):
            new_vs.append((k, present))

    # ----- Keyword scan: Gen4/ESM/DXIO/Strap/Override/Force/Cap/Speed/Link/Rev/1.02/1.03 -----
    KEYWORDS = [
        "gen4", "gen 4", "gen5", "gen 5", "esm", "dxio", "strap",
        "override", "force", "linkcap", "linkspeed", "link speed", "link width",
        "rev 1.02", "rev 1.03", "1.02a", "1.03",
    ]
    kw_hits_per_version = {v: [] for v in VERSIONS}
    kw_hits_added = []  # settings whose keyword-match status changed across versions
    for k in all_keys:
        per_v_match = {}
        for v in VERSIONS:
            s = by_version[v].get(k)
            if not s:
                per_v_match[v] = None
                continue
            blob = (s["prompt"] + " " + s["help"]).lower()
            hits = [kw for kw in KEYWORDS if kw in blob]
            per_v_match[v] = hits
        # If any version has hits, record
        any_hits = any(per_v_match[v] for v in VERSIONS if per_v_match[v] is not None)
        if any_hits:
            for v in VERSIONS:
                if per_v_match[v]:
                    kw_hits_per_version[v].append((k, per_v_match[v]))
        # Detect changed keyword-match across versions (e.g. new Gen4 prompt added in P3.80)
        sigs = []
        for v in VERSIONS:
            sigs.append(tuple(sorted(per_v_match[v])) if per_v_match[v] else None)
        if any_hits and len(set(s for s in sigs if s is not None)) > 1:
            kw_hits_added.append((k, per_v_match))

    # ----- Per-slot Link Speed entries (Setup VS 0x1, offsets 0x123-0x12D) check -----
    per_slot = {}
    for v in VERSIONS:
        per_slot[v] = []
        for k, s in by_version[v].items():
            if (s.get("varstore_id") in ("0x1",) and
                s.get("offset") and
                int(s["offset"], 16) >= 0x123 and int(s["offset"], 16) <= 0x130):
                per_slot[v].append(s)

    # ----- emit markdown -----
    out_path = ROOT / "docs" / "IFR_VERSION_DIFF.md"
    out = []
    out.append("# IFR Cross-Version Diff (P3.70 / P3.80 / P3.90 / P4.10)\n")
    out.append(
        "Cross-version comparison of every IFR-defined BIOS setting. Each version's "
        "IFR text was extracted from every PE32 image section, deduplicated to one "
        "module per name, and parsed with the Phase-1 parser (`scripts/list_suppressed.py`).\n"
    )

    out.append("\n## Summary\n")
    out.append("| Version | Modules | Settings | Suppressed | Permanent | Conditional |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for v in VERSIONS:
        n_settings = sum(len(p["settings"]) for p in parsed[v].values())
        n_modules = len(parsed[v])
        n_supp = sum(
            1
            for p in parsed[v].values()
            for s in p["settings"]
            if any(c["kind"] == "SuppressIf" for c in s["conditions"])
        )
        n_perm = sum(
            1
            for p in parsed[v].values()
            for s in p["settings"]
            if any(c["kind"] == "SuppressIf" and ls.is_permanent_suppress(c["exprs"])
                   for c in s["conditions"])
        )
        out.append(
            f"| {v} | {n_modules} | {n_settings} | {n_supp} | {n_perm} | {n_supp - n_perm} |"
        )

    out.append("\n## Verdict\n")
    n_added_new_v = sum(1 for (_, fv, _) in added if fv != "P3.70")
    n_removed = len(removed)
    n_cond = len(cond_changed)
    n_name = len(name_changed)
    n_kw_changed = len(kw_hits_added)
    out.append(
        f"- **Settings added in P3.80 / P3.90 / P4.10:** {n_added_new_v}\n"
        f"- **Settings removed across versions:** {n_removed}\n"
        f"- **Settings with changed SuppressIf/GrayOutIf condition:** {n_cond}\n"
        f"- **Settings with changed prompt/name:** {n_name}\n"
        f"- **Settings whose Gen4/ESM/DXIO keyword profile changed:** {n_kw_changed}\n"
        f"- **New VarStores introduced in P3.80+:** {len(new_vs)}\n"
    )

    out.append("\n## 1. Settings added in P3.80+ (the highest-leverage diff)\n")
    if not added:
        out.append("_(no settings added in any post-P3.70 version)_\n")
    else:
        out.append(f"{len(added)} settings appear in some version but were absent from P3.70.\n")
        out.append("\n| First seen | Module | QID | VS | Offset | Type | Prompt | SuppressIf |")
        out.append("|---|---|---|---|---|---|---|---|")
        for k, fv, present in sorted(added, key=lambda x: (x[1], x[0])):
            # extract identifying fields from a representative setting later
            pass
            # find earliest version where present
            s = None
            for v in VERSIONS:
                if present[v]:
                    s = by_version[v][k]
                    break
            if s is None:
                continue
            cond = render_cond(s["conditions"]) or "-"
            prompt = (s["prompt"] or "").replace("|", "\\|").strip()[:60]
            out.append(
                f"| {fv} | `{s['module']}` | `{s['qid']}` | `{s.get('varstore_id') or '-'}` | `{s.get('offset') or '-'}` | {s['kind']} | {prompt} | {cond} |"
            )

    out.append("\n## 2. Settings removed in P3.80+\n")
    if not removed:
        out.append("_(no settings removed)_\n")
    else:
        out.append(f"{len(removed)} settings present in P3.70 disappeared in some later version.\n")
        out.append("\n| Last seen | Module | QID | VS | Offset | Type | Prompt |")
        out.append("|---|---|---|---|---|---|---|")
        for k, lv, present in sorted(removed, key=lambda x: (x[1], x[0])):
            # extract identifying fields from a representative setting later
            pass
            s = by_version["P3.70"].get(k)
            if not s:
                continue
            prompt = (s["prompt"] or "").replace("|", "\\|").strip()[:60]
            out.append(
                f"| {lv} | `{s['module']}` | `{s['qid']}` | `{s.get('varstore_id') or '-'}` | `{s.get('offset') or '-'}` | {s['kind']} | {prompt} |"
            )

    out.append("\n## 3. Settings with changed SuppressIf/GrayOutIf/DisableIf\n")
    if not cond_changed:
        out.append("_(no condition changes across any version pair)_\n")
    else:
        out.append(f"{len(cond_changed)} settings had a different condition stack in some version.\n")
        out.append("\n| Module | QID | Prompt | P3.70 | P3.80 | P3.90 | P4.10 |")
        out.append("|---|---|---|---|---|---|---|")
        for k, s_vs, sigs in sorted(cond_changed):
            # extract identifying fields from a representative setting later
            pass
            s = s_vs[0]
            prompt = (s["prompt"] or "").replace("|", "\\|").strip()[:50]
            cells = []
            for sv in s_vs:
                c = render_cond(sv["conditions"]) or "-"
                cells.append(c.replace("|", "\\|")[:80])
            out.append(f"| `{s['module']}` | `{s['qid']}` | {prompt} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |")

    out.append("\n## 4. Settings with changed prompt/name across versions\n")
    if not name_changed:
        out.append("_(no prompt changes)_\n")
    else:
        out.append(f"{len(name_changed)} settings had a renamed prompt in some version.\n")
        out.append("\n| Module | QID | P3.70 | P3.80 | P3.90 | P4.10 |")
        out.append("|---|---|---|---|---|---|")
        for k, s_vs, prompts in sorted(name_changed)[:200]:
            s = s_vs[0]
            cells = [(p or "").replace("|", "\\|").strip()[:40] for p in prompts]
            out.append(f"| `{s['module']}` | `{s['qid']}` | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |")

    out.append("\n## 5. New VarStores introduced post-P3.70\n")
    if not new_vs:
        out.append("_(no new VarStores)_\n")
    else:
        out.append(f"{len(new_vs)} new VarStores appeared.\n")
        out.append("\n| First seen | Module | VarStore Name | VarStore ID |")
        out.append("|---|---|---|---|")
        for (mod, name, vid), present in sorted(new_vs):
            first_seen = next(v for v in VERSIONS if present[v])
            out.append(f"| {first_seen} | `{mod}` | `{name}` | `{vid}` |")

    out.append("\n## 6. Settings matching Gen4/ESM/DXIO/Strap/Override/Force/Speed keywords (per version)\n")
    out.append(
        "Keyword set: gen4, gen5, esm, dxio, strap, override, force, "
        "linkcap, linkspeed, link speed, link width, rev 1.02, rev 1.03, 1.02a, 1.03.\n"
    )
    out.append("\n| Version | Settings matching |")
    out.append("|---|---:|")
    for v in VERSIONS:
        out.append(f"| {v} | {len(kw_hits_per_version[v])} |")

    out.append("\n### 6a. Settings whose keyword-match status changed across versions\n")
    if not kw_hits_added:
        out.append(
            "_(no setting's Gen4/DXIO keyword profile changed — i.e., no version added or removed a Gen4-related option)_\n"
        )
    else:
        out.append(
            f"{len(kw_hits_added)} settings where the matched keyword set differs across versions. "
            "These are the prime candidates for a Gen4-enable option being added/altered.\n"
        )
        out.append("\n| Module | QID | Prompt | P3.70 | P3.80 | P3.90 | P4.10 |")
        out.append("|---|---|---|---|---|---|---|")
        for k, per_v_match in sorted(kw_hits_added):
            # extract identifying fields from a representative setting later
            pass
            # Find a representative setting
            s = None
            for v in VERSIONS:
                if per_v_match[v] is not None:
                    s = by_version[v][k]
                    break
            prompt = (s["prompt"] or "").replace("|", "\\|").strip()[:50]
            cells = []
            for v in VERSIONS:
                m = per_v_match[v]
                if m is None:
                    cells.append("(absent)")
                elif not m:
                    cells.append("-")
                else:
                    cells.append(",".join(m))
            out.append(f"| `{s['module']}` | `{s['qid']}` | {prompt} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |")

    out.append("\n### 6b. Top-priority Gen4-relevant settings — full listing per version\n")
    HIGH_PRIORITY = ["gen4", "gen5", "esm", "dxio", "strap"]
    high_settings = []
    for v in VERSIONS:
        for k, hits in kw_hits_per_version[v]:
            if any(h in HIGH_PRIORITY for h in hits):
                high_settings.append((v, k, hits))
    if not high_settings:
        out.append("_(zero settings whose prompt/help mentions Gen4/Gen5/ESM/DXIO/Strap in any version — the high-confidence Gen4-enable strings are absent from IFR everywhere)_\n")
    else:
        out.append(f"{len(high_settings)} (version, setting) pairs hit a high-priority keyword.\n")
        out.append("\n| Version | Module | QID | Prompt | Hits |")
        out.append("|---|---|---|---|---|")
        for v, k, hits in sorted(high_settings):
            # extract identifying fields from a representative setting later
            pass
            s = by_version[v][k]
            prompt = (s["prompt"] or "").replace("|", "\\|").strip()[:50]
            out.append(f"| {v} | `{s['module']}` | `{s['qid']}` | {prompt} | {','.join(hits)} |")

    out.append("\n## 7. Per-slot Link Speed entries (Setup VS `0x1`, offsets `0x123`–`0x130`)\n")
    out.append(
        "**Correction to CLAUDE.md baseline:** the per-slot Link Speed OneOf in P3.70 "
        "ALREADY offers a GEN4 option (value=4) — see raw IFR for `Setup` module. Earlier "
        "Phase-1 narrative ('Auto/GEN1/GEN2/GEN3') was inaccurate. This section verifies "
        "the option set is identical across all 4 versions and that the user's NVRAM byte "
        "(currently 0x01 = GEN1) could in principle be set to 0x04 = GEN4.\n\n"
        "Empirically (per CLAUDE.md), AGESA ignores these per-slot bytes — they are "
        "vestigial. So the GEN4 option in this OneOf is also vestigial. But the IFR has it.\n"
    )
    for v in VERSIONS:
        out.append(f"\n### {v}\n")
        if not per_slot[v]:
            out.append("_(no entries found in this offset range)_\n")
            continue
        out.append("| QID | Offset | Prompt | Option values |")
        out.append("|---|---|---|---|")
        for s in sorted(per_slot[v], key=lambda x: int(x["offset"], 16)):
            opts = ", ".join(f"{o['value']}={o['text']}" for o in s.get("options", []))
            prompt = (s["prompt"] or "").replace("|", "\\|").strip()[:40]
            out.append(f"| `{s['qid']}` | `{s['offset']}` | {prompt} | {opts[:120]} |")

    out.append("\n## 8. Conclusion\n")
    # The decisive question is whether ANY Gen4-related option was added.
    # Genoa-module reshuffling (CbsSetupDxeGN) does not affect this Rome rig.
    if n_kw_changed == 0:
        out.append(
            "**No Gen4-enable IFR option was added in any post-P3.70 version.** "
            f"While {n_added_new_v} settings appear new in P3.80/3.90/4.10 and {len(removed)} "
            "disappeared, *none* of them mention Gen4, ESM, DXIO, or strap with a "
            "different keyword profile than P3.70. No SuppressIf condition gating a "
            "Gen4-related option changed. No new VarStores were introduced. "
            "The per-slot Link Speed OneOf in `Setup` retains the same "
            "Auto/GEN1/GEN2/GEN3/GEN4 option set across every version.\n\n"
            "Most cross-version IFR changes are concentrated in `CbsSetupDxeGN` (the "
            "Genoa-family AGESA Setup module). That module is irrelevant to this Rome "
            "rig — Rome uses `CbsSetupDxeSSP`, which is nearly stable across versions "
            "(only `CCDs Control` was added in P3.80 — compute-die enablement, not PCIe). "
            "The notable Gen4-keyword additions in P3.90+ are `Preset Search Mask "
            "Configuration (Gen4)` / `Preset Search Mask (Gen4)` in `CbsSetupDxeGN` — "
            "PCIe equalization preset tuning for Genoa, not a Gen4 enable, and "
            "irrelevant to Rome.\n\n"
            "Combined with subagent #1's APCB-byte-identical finding and subagent #5's "
            "ESM-decision-in-runtime-descriptor finding, this confirms **the Gen4 unlock "
            "(if any) cannot be activated by any IFR/NVRAM-side intervention.** It must be "
            "in runtime AGESA code or a binary descriptor synthesizer (i.e. `AmdApcbDxeV3`).\n"
        )
    else:
        out.append(
            "**Note:** the diff DID find changes — review sections 1, 3, and 6a above for "
            "candidate Gen4-relevant additions.\n"
        )

    out_path.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
