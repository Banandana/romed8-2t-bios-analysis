#!/usr/bin/env python3
"""
Walk every ifrextractor-rs text dump under <ifr_dir> and emit a structured
markdown listing of every BIOS setting that is gated by at least one
SuppressIf clause.

Approach: tracks the SuppressIf / GrayOutIf / DisableIf stack while walking
each IFR file (same as scripts/ifr_to_reference.py). When a setting opcode
(OneOf, Numeric, CheckBox, String, Password, Ref) is encountered, we record
its currently-active SuppressIf frames. Each frame's expression body is
captured as raw IFR opcode tokens and rendered into a compact human-readable
form (e.g. SuppressIf(Q0x14A == 0x1), SuppressIf(True),
SuppressIf(Q0x158 in [1,2,3,4,5,6])).

Companion JSON dump is written next to the markdown so downstream consumers
can filter / re-process without re-parsing.

Usage:
    list_suppressed.py <ifr_dir> <out_md>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ----------------------------- IFR line patterns -----------------------------

RE_FORMSET = re.compile(
    r'^FormSet Guid: (?P<guid>[0-9A-F-]+), Title: "(?P<title>[^"]*)", Help: "(?P<help>[^"]*)"',
    re.IGNORECASE,
)
RE_VARSTORE = re.compile(
    r'^\s*VarStore Guid: (?P<guid>[0-9A-F-]+), VarStoreId: (?P<id>0x[0-9A-Fa-f]+), Size: (?P<size>0x[0-9A-Fa-f]+), Name: "(?P<name>[^"]*)"',
    re.IGNORECASE,
)
RE_VARSTORE_EFI = re.compile(
    r'^\s*VarStoreEfi Guid: (?P<guid>[0-9A-F-]+), VarStoreId: (?P<id>0x[0-9A-Fa-f]+), Attributes: (?P<attr>0x[0-9A-Fa-f]+), Size: (?P<size>0x[0-9A-Fa-f]+), Name: "(?P<name>[^"]*)"',
    re.IGNORECASE,
)
RE_FORM = re.compile(
    r'^\s*Form FormId: (?P<id>0x[0-9A-Fa-f]+), Title: "(?P<title>[^"]*)"'
)
RE_REF_LOCAL = re.compile(
    r'^\s*Ref Prompt: "(?P<prompt>[^"]*)", Help: "(?P<help>[^"]*)", QuestionFlags: (?P<qf>0x[0-9A-Fa-f]+), QuestionId: (?P<qid>0x[0-9A-Fa-f]+),.*FormId: (?P<formid>0x[0-9A-Fa-f]+)'
)

RE_ONEOF = re.compile(
    r'^\s*OneOf Prompt: "(?P<prompt>[^"]*)", Help: "(?P<help>[^"]*?)", '
    r'QuestionFlags: (?P<qflags>0x[0-9A-Fa-f]+), QuestionId: (?P<qid>0x[0-9A-Fa-f]+), '
    r'VarStoreId: (?P<vsid>0x[0-9A-Fa-f]+), VarOffset: (?P<voff>0x[0-9A-Fa-f]+), '
    r'Flags: (?P<flags>0x[0-9A-Fa-f]+), Size: (?P<size>\d+), '
    r'Min: (?P<min>0x[0-9A-Fa-f]+), Max: (?P<max>0x[0-9A-Fa-f]+), Step: (?P<step>0x[0-9A-Fa-f]+)'
)
RE_NUMERIC = re.compile(
    r'^\s*Numeric Prompt: "(?P<prompt>[^"]*)", Help: "(?P<help>[^"]*?)", '
    r'QuestionFlags: (?P<qflags>0x[0-9A-Fa-f]+), QuestionId: (?P<qid>0x[0-9A-Fa-f]+), '
    r'VarStoreId: (?P<vsid>0x[0-9A-Fa-f]+), VarOffset: (?P<voff>0x[0-9A-Fa-f]+), '
    r'Flags: (?P<flags>0x[0-9A-Fa-f]+), Size: (?P<size>\d+), '
    r'Min: (?P<min>0x[0-9A-Fa-f]+), Max: (?P<max>0x[0-9A-Fa-f]+), Step: (?P<step>0x[0-9A-Fa-f]+)'
)
RE_CHECKBOX = re.compile(
    r'^\s*CheckBox Prompt: "(?P<prompt>[^"]*)", Help: "(?P<help>[^"]*?)", '
    r'QuestionFlags: (?P<qflags>0x[0-9A-Fa-f]+), QuestionId: (?P<qid>0x[0-9A-Fa-f]+), '
    r'VarStoreId: (?P<vsid>0x[0-9A-Fa-f]+), VarOffset: (?P<voff>0x[0-9A-Fa-f]+), '
    r'Flags: (?P<flags>0x[0-9A-Fa-f]+)'
)
RE_STRING = re.compile(
    r'^\s*String Prompt: "(?P<prompt>[^"]*)", Help: "(?P<help>[^"]*?)", '
    r'QuestionFlags: (?P<qflags>0x[0-9A-Fa-f]+), QuestionId: (?P<qid>0x[0-9A-Fa-f]+), '
    r'VarStoreId: (?P<vsid>0x[0-9A-Fa-f]+), VarOffset: (?P<voff>0x[0-9A-Fa-f]+).*MinSize: (?P<minsize>\d+), MaxSize: (?P<maxsize>\d+)'
)
RE_PASSWORD = re.compile(
    r'^\s*Password Prompt: "(?P<prompt>[^"]*)", Help: "(?P<help>[^"]*?)", '
    r'QuestionFlags: (?P<qflags>0x[0-9A-Fa-f]+), QuestionId: (?P<qid>0x[0-9A-Fa-f]+)'
)
RE_OPTION = re.compile(
    r'^\s*OneOfOption Option: "(?P<text>[^"]*)" Value: (?P<val>\w+)(?P<flags>.*)?'
)

RE_SUPPRESS_BEGIN = re.compile(r'^\s*SuppressIf\s*$')
RE_GRAYOUT_BEGIN = re.compile(r'^\s*GrayOutIf\s*$')
RE_DISABLE_BEGIN = re.compile(r'^\s*DisableIf\s*$')
RE_END = re.compile(r'^\s*End\s*$')

# Expression opcodes that can appear in a condition body
RE_EQ_ID_VAL = re.compile(
    r'^\s*EqIdVal QuestionId: (?P<qid>0x[0-9A-Fa-f]+), Value: (?P<val>0x[0-9A-Fa-f]+)'
)
RE_EQ_ID_VAL_LIST = re.compile(
    r'^\s*EqIdValList QuestionId: (?P<qid>0x[0-9A-Fa-f]+), Values: \[(?P<vals>[^\]]*)\]'
)
RE_EQ_ID_ID = re.compile(
    r'^\s*EqIdId QuestionId: (?P<qid>0x[0-9A-Fa-f]+), OtherQuestionId: (?P<oqid>0x[0-9A-Fa-f]+)'
)
RE_TRUE = re.compile(r'^\s*True\s*$')
RE_FALSE = re.compile(r'^\s*False\s*$')
RE_AND = re.compile(r'^\s*And\s*$')
RE_OR = re.compile(r'^\s*Or\s*$')
RE_NOT = re.compile(r'^\s*Not\s*$')

# Setting opcode regexes that consume conditions
SETTING_TYPES = [
    ("OneOf", RE_ONEOF),
    ("Numeric", RE_NUMERIC),
    ("CheckBox", RE_CHECKBOX),
    ("String", RE_STRING),
    ("Password", RE_PASSWORD),
]


# ----------------------------- Condition rendering -----------------------------

def render_token(tok):
    """Pretty-print a single expression token captured during parse."""
    kind = tok["op"]
    if kind == "EqIdVal":
        return f"Q{tok['qid']} == {tok['val']}"
    if kind == "EqIdValList":
        return f"Q{tok['qid']} in [{tok['vals']}]"
    if kind == "EqIdId":
        return f"Q{tok['qid']} == Q{tok['oqid']}"
    if kind in ("True", "False"):
        return kind
    if kind in ("And", "Or", "Not"):
        return kind
    return tok.get("raw", kind)


def render_expr(tokens):
    """Render the full token list. We don't try to fully reconstruct the postfix
    expression — instead we present it as a compact comma-separated list of the
    primitive comparisons, with logical glue joiners noted. For 95% of real-world
    SuppressIf clauses in this BIOS the body is either {True} or a single
    EqIdVal/EqIdValList, so this is fine."""
    if not tokens:
        return "(empty)"
    primitives = [t for t in tokens if t["op"] in ("EqIdVal", "EqIdValList", "EqIdId", "True", "False")]
    glue = [t for t in tokens if t["op"] in ("And", "Or", "Not")]
    if not primitives:
        return ", ".join(render_token(t) for t in tokens)
    if len(primitives) == 1 and not glue:
        return render_token(primitives[0])
    joiner = " AND "
    if any(g["op"] == "Or" for g in glue):
        joiner = " OR "
    body = joiner.join(render_token(t) for t in primitives)
    if any(g["op"] == "Not" for g in glue):
        body = f"NOT ({body})"
    return body


def is_admin_gate_suppress(tokens):
    """A SuppressIf body referencing only Q0x14A is the BIOS admin-mode gate."""
    if not tokens:
        return False
    for t in tokens:
        if t["op"] == "EqIdVal" and t["qid"].lower() == "0x14a":
            continue
        if t["op"] in ("And", "Or", "Not"):
            continue
        return False
    return any(t["op"] == "EqIdVal" and t["qid"].lower() == "0x14a" for t in tokens)


def is_permanent_suppress(tokens):
    """SuppressIf True — setting is permanently hidden from menu."""
    if not tokens:
        return False
    # Only a True opcode (possibly with no others)
    has_true = any(t["op"] == "True" for t in tokens)
    has_other_primitive = any(
        t["op"] in ("EqIdVal", "EqIdValList", "EqIdId", "False")
        for t in tokens
    )
    return has_true and not has_other_primitive


# ----------------------------- Parser -----------------------------

def parse_ifr(text, module_name):
    formset = None
    varstores = {}
    cur_form = None
    cond_stack = []  # list of {kind, exprs:[token,...], raw_lines:[...]}
    settings = []

    lines = text.splitlines()
    for ln in lines:
        m = RE_FORMSET.match(ln)
        if m:
            formset = {
                "guid": m["guid"].upper(),
                "title": m["title"],
                "help": m["help"],
            }
            continue

        m = RE_VARSTORE.match(ln) or RE_VARSTORE_EFI.match(ln)
        if m:
            vid = m["id"].lower()
            varstores[vid] = {
                "id": vid,
                "guid": m["guid"].upper(),
                "size": m["size"].lower(),
                "name": m["name"],
            }
            continue

        m = RE_FORM.match(ln)
        if m:
            cur_form = {
                "id": m["id"].lower(),
                "title": m["title"],
            }
            cond_stack = []
            continue

        if cur_form is None:
            continue

        # Condition stack management
        if RE_SUPPRESS_BEGIN.match(ln):
            cond_stack.append({"kind": "SuppressIf", "exprs": []})
            continue
        if RE_GRAYOUT_BEGIN.match(ln):
            cond_stack.append({"kind": "GrayOutIf", "exprs": []})
            continue
        if RE_DISABLE_BEGIN.match(ln):
            cond_stack.append({"kind": "DisableIf", "exprs": []})
            continue
        if RE_END.match(ln):
            if cond_stack:
                cond_stack.pop()
            continue

        # Expression body tokens — append to top of stack
        if cond_stack:
            top = cond_stack[-1]
            m = RE_EQ_ID_VAL.match(ln)
            if m:
                top["exprs"].append({"op": "EqIdVal", "qid": m["qid"].lower(), "val": m["val"].lower()})
                continue
            m = RE_EQ_ID_VAL_LIST.match(ln)
            if m:
                top["exprs"].append({"op": "EqIdValList", "qid": m["qid"].lower(), "vals": m["vals"].strip()})
                continue
            m = RE_EQ_ID_ID.match(ln)
            if m:
                top["exprs"].append({"op": "EqIdId", "qid": m["qid"].lower(), "oqid": m["oqid"].lower()})
                continue
            if RE_TRUE.match(ln):
                top["exprs"].append({"op": "True"})
                continue
            if RE_FALSE.match(ln):
                top["exprs"].append({"op": "False"})
                continue
            if RE_AND.match(ln):
                top["exprs"].append({"op": "And"})
                continue
            if RE_OR.match(ln):
                top["exprs"].append({"op": "Or"})
                continue
            if RE_NOT.match(ln):
                top["exprs"].append({"op": "Not"})
                continue

        # Setting opcodes
        for kind, regex in SETTING_TYPES:
            m = regex.match(ln)
            if not m:
                continue
            gd = m.groupdict()
            setting = {
                "module": module_name,
                "formset_guid": formset["guid"] if formset else None,
                "formset_title": formset["title"] if formset else None,
                "form_id": cur_form["id"],
                "form_title": cur_form["title"],
                "kind": kind,
                "prompt": gd["prompt"],
                "help": gd.get("help") or "",
                "qid": gd["qid"].lower(),
                "varstore_id": gd.get("vsid", "").lower() or None,
                "offset": gd.get("voff", "").lower() or None,
                "size_bits": int(gd["size"]) if gd.get("size") and gd["size"].isdigit() else None,
                "options": [],
                "conditions": [
                    {"kind": c["kind"], "exprs": [dict(e) for e in c["exprs"]]}
                    for c in cond_stack
                ],
            }
            settings.append(setting)
            break
        else:
            # Option line attaches to the most recent OneOf
            mo = RE_OPTION.match(ln)
            if mo and settings and settings[-1]["kind"] == "OneOf":
                settings[-1]["options"].append({"text": mo["text"], "value": mo["val"]})

    return {
        "module": module_name,
        "formset": formset,
        "varstores": varstores,
        "settings": settings,
    }


# ----------------------------- Filtering -----------------------------

def has_active_suppress(setting):
    return any(c["kind"] == "SuppressIf" for c in setting["conditions"])


def classify(setting):
    """Returns 'permanent', 'admin_only', 'user_only', or 'conditional'.

    - permanent: at least one SuppressIf body is True (always-suppressed)
    - admin_only: only SuppressIf is on Q0x14A == 0x0 (hide for users — admin sees it)
    - user_only: only SuppressIf is on Q0x14A == 0x1 (hide for admin — users see it)
    - conditional: anything else
    """
    suppress_frames = [c for c in setting["conditions"] if c["kind"] == "SuppressIf"]
    if not suppress_frames:
        return None
    if any(is_permanent_suppress(c["exprs"]) for c in suppress_frames):
        return "permanent"
    if all(is_admin_gate_suppress(c["exprs"]) for c in suppress_frames):
        # check value direction
        for c in suppress_frames:
            for t in c["exprs"]:
                if t["op"] == "EqIdVal" and t["qid"].lower() == "0x14a":
                    if t["val"] == "0x0":
                        return "admin_only"
                    if t["val"] == "0x1":
                        return "user_only"
        return "admin_only"
    return "conditional"


# ----------------------------- Rendering -----------------------------

INTEREST_KEYWORDS = [
    "pcie", "pci-e", "gen4", "gen 4", "gen3", "gen 3", "link speed", "linkspeed",
    "linkwidth", "link width", "esm", "dxio", "force", "override",
    "lane", "negotiation", "preset", "compliance", "hotplug", "10gt", "16gt",
]
DEBUG_KEYWORDS = [
    "debug", "engineering", "manufacturing", "hidden", "internal", " test",
    "factory", "developer", "validation",
]


def matches_keywords(setting, keywords):
    blob = (setting["prompt"] + " " + setting["help"]).lower()
    return [k for k in keywords if k in blob]


def render_setting(s, varstores):
    """Compact markdown block for one suppressed setting."""
    parts = []
    name = s["prompt"] or "(unnamed)"
    parts.append(f"**`{s['qid']}` — {name}** _({s['kind']})_")

    info = []
    if s["varstore_id"]:
        v = varstores.get(s["varstore_id"], {})
        vname = v.get("name", "?")
        info.append(f"VS `{s['varstore_id']}` ({vname})")
    if s["offset"]:
        info.append(f"off `{s['offset']}`")
    if s["size_bits"]:
        info.append(f"{s['size_bits']}-bit")
    if info:
        parts.append("· " + " · ".join(info))

    if s["kind"] == "OneOf" and s["options"]:
        opt_strs = [f"`{o['value']}`={o['text']}" for o in s["options"]]
        parts.append("opts: " + ", ".join(opt_strs))

    cond_strs = []
    for c in s["conditions"]:
        body = render_expr(c["exprs"])
        cond_strs.append(f"{c['kind']}({body})")
    parts.append("cond: " + " ; ".join(cond_strs))

    if s["help"]:
        h = s["help"].replace("\\n", " ").strip()
        if h:
            parts.append(f"_help:_ {h[:200]}")

    return " — ".join(parts)


def section_header(title, level=2):
    return ("#" * level) + " " + title + "\n"


def main():
    if len(sys.argv) < 3:
        print("usage: list_suppressed.py <ifr_dir> <out_md>", file=sys.stderr)
        sys.exit(1)

    ifr_dir = Path(sys.argv[1])
    out_md = Path(sys.argv[2])

    all_settings = []
    per_module = {}

    for path in sorted(ifr_dir.rglob("*.uefi.ifr.txt")):
        module_name = path.stem.split(".")[0]
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        try:
            parsed = parse_ifr(text, module_name)
        except Exception as e:
            print(f"WARN: parse failed for {path}: {e}", file=sys.stderr)
            continue
        per_module[module_name] = parsed
        for s in parsed["settings"]:
            if has_active_suppress(s):
                s["_class"] = classify(s)
                s["_interest"] = matches_keywords(s, INTEREST_KEYWORDS)
                s["_debug"] = matches_keywords(s, DEBUG_KEYWORDS)
                s["_module"] = module_name
                all_settings.append(s)

    # Stats
    total_examined = sum(len(p["settings"]) for p in per_module.values())
    n_suppressed = len(all_settings)
    n_permanent = sum(1 for s in all_settings if s["_class"] == "permanent")
    n_admin = sum(1 for s in all_settings if s["_class"] == "admin_only")
    n_user = sum(1 for s in all_settings if s["_class"] == "user_only")
    n_cond = sum(1 for s in all_settings if s["_class"] == "conditional")

    interest = [s for s in all_settings if s["_interest"]]
    debug = [s for s in all_settings if s["_debug"] and not s["_interest"]]

    # ----- write JSON companion -----
    json_path = out_md.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "summary": {
                    "total_settings_examined": total_examined,
                    "suppressed_total": n_suppressed,
                    "permanent": n_permanent,
                    "admin_only": n_admin,
                    "user_only": n_user,
                    "conditional": n_cond,
                },
                "settings": all_settings,
                "varstores_by_module": {
                    m: p["varstores"] for m, p in per_module.items()
                },
            },
            fh,
            indent=2,
        )

    # ----- write markdown -----
    out = []
    out.append("# Suppressed BIOS Settings (P3.70)\n")
    out.append(
        "Every setup setting in P3.70 whose currently-active condition stack "
        "includes at least one `SuppressIf` clause. Sourced by walking the IFR "
        "of every HII Forms-bearing UEFI module and tracking SuppressIf nesting.\n"
    )
    out.append(
        f"**Counts:** {n_suppressed} suppressed of {total_examined} total settings — "
        f"{n_permanent} permanent (`SuppressIf True`), "
        f"{n_admin} admin-only-visible (suppressed from users), "
        f"{n_user} user-only-visible (suppressed from admin), "
        f"{n_cond} conditional on other QuestionIds.\n"
    )
    out.append(
        "Notes:\n"
        "- `SuppressIf True` settings are permanently deleted from the menu — "
        "they live in the IFR but never render. They are the most interesting.\n"
        "- `SuppressIf Q0x14A == 0x0` hides the setting in **user mode**, so "
        "logging in to BIOS as Administrator (set BIOS supervisor password, then "
        "enter setup with that password) reveals them. These are NOT truly hidden.\n"
        "- `SuppressIf Q0x14A == 0x1` hides in **admin mode** (rare — usually "
        "informational text shown only to users).\n"
        "- A condition like `SuppressIf Q0x158 == 0x0` is a runtime check on a "
        "sibling setup variable — flipping that variable in NVRAM unlocks the "
        "child. See companion JSON `SUPPRESSED_OPTIONS.json` for full data.\n"
    )

    # ---------- 1. Candidates of interest ----------
    out.append("\n---\n\n## 1. Candidates of interest (PCIe / Gen4 / DXIO / link / force / override)\n")
    if not interest:
        out.append("_(no suppressed settings whose prompt or help text matched the keyword set)_\n")
    else:
        out.append(
            f"{len(interest)} suppressed settings whose prompt or help mentions "
            "one of: PCIe, Gen3, Gen4, link speed/width, lane, ESM, DXIO, force, "
            "override, hotplug, preset, compliance, negotiation, 10GT/16GT.\n"
        )
        # group by module for readability
        by_mod = {}
        for s in interest:
            by_mod.setdefault(s["_module"], []).append(s)
        for mod in sorted(by_mod):
            out.append(f"\n### Module `{mod}`\n")
            for s in by_mod[mod]:
                hits = ", ".join(s["_interest"])
                cls = s["_class"]
                badge = {
                    "permanent": "[PERMANENT]",
                    "admin_only": "[admin-only]",
                    "user_only": "[user-only]",
                    "conditional": "[conditional]",
                }.get(cls, "")
                varstores = per_module[s["_module"]]["varstores"]
                out.append(f"- {badge} {render_setting(s, varstores)}")
                out.append(f"  - matched keywords: `{hits}`")

    # ---------- 2. Permanently suppressed ----------
    out.append("\n---\n\n## 2. Permanently suppressed (`SuppressIf True`)\n")
    perm = [s for s in all_settings if s["_class"] == "permanent"]
    if not perm:
        out.append("_(none)_\n")
    else:
        out.append(
            f"{len(perm)} settings wrapped by `SuppressIf True` — the IFR carries "
            "them but the menu never renders them. These are the strongest "
            "candidates for hidden engineering options.\n"
        )
        by_mod = {}
        for s in perm:
            by_mod.setdefault(s["_module"], []).append(s)
        for mod in sorted(by_mod):
            out.append(f"\n### Module `{mod}`\n")
            for s in by_mod[mod]:
                varstores = per_module[s["_module"]]["varstores"]
                out.append(f"- {render_setting(s, varstores)}")

    # ---------- 3. Admin-only ----------
    out.append("\n---\n\n## 3. Admin-only visible (`SuppressIf Q0x14A == 0x0`)\n")
    admin_only = [s for s in all_settings if s["_class"] == "admin_only"]
    out.append(
        f"{len(admin_only)} settings hidden in user mode but visible if you "
        "enter BIOS with the supervisor password. **Not truly hidden** — these "
        "appear in the menu under admin login. Listed by module + form for "
        "context, NVRAM offsets only:\n"
    )
    if admin_only:
        by_mod = {}
        for s in admin_only:
            by_mod.setdefault(s["_module"], []).append(s)
        for mod in sorted(by_mod):
            out.append(f"\n#### Module `{mod}` ({len(by_mod[mod])})\n")
            # Compact table-style row per setting
            for s in by_mod[mod][:80]:
                vs = s["varstore_id"] or "-"
                off = s["offset"] or "-"
                out.append(f"- `{s['qid']}` **{s['prompt'] or '(unnamed)'}** ({s['kind']}) — VS `{vs}` off `{off}`")
            if len(by_mod[mod]) > 80:
                out.append(f"- _… and {len(by_mod[mod]) - 80} more in this module — see JSON_")

    # ---------- 3b. User-only ----------
    user_only = [s for s in all_settings if s["_class"] == "user_only"]
    if user_only:
        out.append("\n---\n\n## 3b. User-only visible (`SuppressIf Q0x14A == 0x1`)\n")
        out.append(
            f"{len(user_only)} settings hidden when in admin mode (typically "
            "informational text or warnings shown only to non-admin users).\n"
        )
        by_mod = {}
        for s in user_only:
            by_mod.setdefault(s["_module"], []).append(s)
        for mod in sorted(by_mod):
            out.append(f"\n#### Module `{mod}`\n")
            for s in by_mod[mod]:
                varstores = per_module[s["_module"]]["varstores"]
                out.append(f"- {render_setting(s, varstores)}")

    # ---------- 4. Debug / engineering hints ----------
    out.append("\n---\n\n## 4. Debug / engineering / hidden-mode hints\n")
    if not debug:
        out.append("_(no suppressed settings whose prompt or help text matched "
                   "Debug/Engineering/Manufacturing/Hidden/Internal/Test/Factory/Validation)_\n")
    else:
        out.append(
            f"{len(debug)} suppressed settings whose prompt/help suggests "
            "engineering, debug, or manufacturing-only intent. May gate richer "
            "hidden submenus.\n"
        )
        by_mod = {}
        for s in debug:
            by_mod.setdefault(s["_module"], []).append(s)
        for mod in sorted(by_mod):
            out.append(f"\n### Module `{mod}`\n")
            for s in by_mod[mod]:
                hits = ", ".join(s["_debug"])
                cls = s["_class"]
                badge = {
                    "permanent": "[PERMANENT]",
                    "admin_only": "[admin-only]",
                    "user_only": "[user-only]",
                    "conditional": "[conditional]",
                }.get(cls, "")
                varstores = per_module[s["_module"]]["varstores"]
                out.append(f"- {badge} {render_setting(s, varstores)}")
                out.append(f"  - matched keywords: `{hits}`")

    # ---------- 5. Conditional summary by module ----------
    out.append("\n---\n\n## 5. All other suppressed (conditional, by module)\n")
    cond_settings = [s for s in all_settings if s["_class"] == "conditional"]
    out.append(
        f"{len(cond_settings)} settings gated on other setup questions. Full "
        "enumeration is in `SUPPRESSED_OPTIONS.json` — below is a per-module "
        "summary plus the most-referenced gating QuestionIds.\n"
    )
    # gating qid frequency
    qid_freq = {}
    for s in cond_settings:
        for c in s["conditions"]:
            if c["kind"] != "SuppressIf":
                continue
            for t in c["exprs"]:
                if t["op"] in ("EqIdVal", "EqIdValList", "EqIdId"):
                    qid_freq[t["qid"]] = qid_freq.get(t["qid"], 0) + 1
    top_qids = sorted(qid_freq.items(), key=lambda kv: -kv[1])[:25]
    out.append("\n### Top gating QuestionIds\n")
    out.append("| QuestionId | Times referenced in SuppressIf |")
    out.append("|---|---|")
    for qid, n in top_qids:
        out.append(f"| `{qid}` | {n} |")

    # per-module breakdown
    by_mod = {}
    for s in cond_settings:
        by_mod.setdefault(s["_module"], []).append(s)
    out.append("\n### Per-module counts\n")
    out.append("| Module | Conditionally suppressed |")
    out.append("|---|---|")
    for mod in sorted(by_mod):
        out.append(f"| `{mod}` | {len(by_mod[mod])} |")

    # Per-module compact listing — keep concise (one-liner per setting)
    for mod in sorted(by_mod):
        out.append(f"\n#### `{mod}` — {len(by_mod[mod])} suppressed\n")
        for s in by_mod[mod]:
            cond_strs = []
            for c in s["conditions"]:
                if c["kind"] == "SuppressIf":
                    cond_strs.append(render_expr(c["exprs"]))
            cond = " ; ".join(cond_strs)
            vs = s["varstore_id"] or "-"
            off = s["offset"] or "-"
            name = (s["prompt"] or "(unnamed)").strip()
            out.append(
                f"- `{s['qid']}` **{name}** ({s['kind']}, VS `{vs}` off `{off}`) "
                f"— SuppressIf: {cond}"
            )

    out.append("\n---\n\n_See `SUPPRESSED_OPTIONS.json` for the full machine-readable enumeration._\n")

    out_md.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {out_md} and {json_path}")
    print(
        f"  total settings: {total_examined}, suppressed: {n_suppressed} "
        f"(permanent {n_permanent}, admin-only {n_admin}, user-only {n_user}, "
        f"conditional {n_cond})"
    )
    print(f"  PCIe/Gen4-interest matches: {len(interest)}, debug-keyword matches: {len(debug)}")


if __name__ == "__main__":
    main()
