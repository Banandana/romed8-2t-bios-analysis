#!/usr/bin/env python3
"""
Parse ifrextractor-rs output files and emit a structured Markdown reference
of every BIOS setting, organized: Module → FormSet → Form → Setting.

Designed for LLM consumption: every setting gets stable identifiers
(Module + FormSet GUID + QuestionId), full Help text, exact NVRAM offset,
and option values.
"""

import os
import re
import sys
import json
from pathlib import Path
from collections import defaultdict

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
    r'^\s*Ref Prompt: "(?P<prompt>[^"]*)", Help: "(?P<help>[^"]*)", QuestionFlags: (?P<qf>0x[0-9A-Fa-f]+), QuestionId: (?P<qid>0x[0-9A-Fa-f]+),.*FormId: (?P<formid>0x[0-9A-Fa-f]+)(?P<rest>.*)?'
)
RE_FORMSET_GUID_TAIL = re.compile(r'FormSetGuid: (?P<guid>[0-9A-F-]+)', re.IGNORECASE)

# OneOf — option-style setting
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
    r'^\s*OneOfOption Option: "(?P<text>[^"]*)" Value: (?P<val>[\w]+)(?P<flags>.*)?'
)

# Suppression / GrayOut conditions
RE_SUPPRESS_BEGIN = re.compile(r'^\s*SuppressIf\s*$')
RE_GRAYOUT_BEGIN = re.compile(r'^\s*GrayOutIf\s*$')
RE_DISABLE_BEGIN = re.compile(r'^\s*DisableIf\s*$')
RE_END = re.compile(r'^\s*End\s*$')
RE_EQ_ID_VAL = re.compile(
    r'^\s*EqIdVal QuestionId: (?P<qid>0x[0-9A-Fa-f]+), Value: (?P<val>0x[0-9A-Fa-f]+)'
)


# ----------------------------- Parser -----------------------------

def parse_ifr(text):
    """Return a dict describing a single IFR file."""
    out = {
        "formset": None,
        "varstores": {},  # by id
        "forms": [],      # ordered list
    }
    cur_form = None
    cur_setting = None
    cond_stack = []   # stack of {kind, exprs:[(qid,val)]}

    lines = text.splitlines()
    for ln in lines:
        m = RE_FORMSET.match(ln)
        if m:
            out["formset"] = {
                "guid": m["guid"].upper(),
                "title": m["title"],
                "help": m["help"],
            }
            continue

        m = RE_VARSTORE.match(ln) or RE_VARSTORE_EFI.match(ln)
        if m:
            vid = m["id"].lower()
            out["varstores"][vid] = {
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
                "settings": [],
                "refs": [],   # navigation children
            }
            out["forms"].append(cur_form)
            cond_stack = []
            cur_setting = None
            continue

        if cur_form is None:
            continue

        # Track suppression conditions (best-effort)
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
            cur_setting = None
            continue

        m = RE_EQ_ID_VAL.match(ln)
        if m and cond_stack:
            cond_stack[-1]["exprs"].append({
                "qid": m["qid"].lower(),
                "val": m["val"].lower(),
            })
            continue

        # Local Ref (navigation to subform)
        m = RE_REF_LOCAL.match(ln)
        if m:
            ref = {
                "prompt": m["prompt"],
                "help": m["help"],
                "qid": m["qid"].lower(),
                "formid": m["formid"].lower(),
            }
            tail = m["rest"] or ""
            gm = RE_FORMSET_GUID_TAIL.search(tail)
            if gm:
                ref["external_formset_guid"] = gm["guid"].upper()
            cur_form["refs"].append(ref)
            continue

        # OneOf
        m = RE_ONEOF.match(ln)
        if m:
            cur_setting = {
                "kind": "OneOf",
                "prompt": m["prompt"],
                "help": m["help"],
                "qid": m["qid"].lower(),
                "varstore_id": m["vsid"].lower(),
                "offset": m["voff"].lower(),
                "size_bits": int(m["size"]),
                "min": m["min"].lower(),
                "max": m["max"].lower(),
                "options": [],
                "conditions": [
                    {"kind": c["kind"], "exprs": list(c["exprs"])}
                    for c in cond_stack
                ],
            }
            cur_form["settings"].append(cur_setting)
            continue

        m = RE_NUMERIC.match(ln)
        if m:
            cur_setting = {
                "kind": "Numeric",
                "prompt": m["prompt"],
                "help": m["help"],
                "qid": m["qid"].lower(),
                "varstore_id": m["vsid"].lower(),
                "offset": m["voff"].lower(),
                "size_bits": int(m["size"]),
                "min": m["min"].lower(),
                "max": m["max"].lower(),
                "step": m["step"].lower(),
                "default": None,
                "conditions": [
                    {"kind": c["kind"], "exprs": list(c["exprs"])}
                    for c in cond_stack
                ],
            }
            cur_form["settings"].append(cur_setting)
            continue

        m = RE_CHECKBOX.match(ln)
        if m:
            cur_setting = {
                "kind": "CheckBox",
                "prompt": m["prompt"],
                "help": m["help"],
                "qid": m["qid"].lower(),
                "varstore_id": m["vsid"].lower(),
                "offset": m["voff"].lower(),
                "size_bits": 8,
                "options": [
                    {"text": "Disabled", "value": "0"},
                    {"text": "Enabled", "value": "1"},
                ],
                "conditions": [
                    {"kind": c["kind"], "exprs": list(c["exprs"])}
                    for c in cond_stack
                ],
            }
            cur_form["settings"].append(cur_setting)
            continue

        m = RE_STRING.match(ln)
        if m:
            cur_setting = {
                "kind": "String",
                "prompt": m["prompt"],
                "help": m["help"],
                "qid": m["qid"].lower(),
                "varstore_id": m["vsid"].lower(),
                "offset": m["voff"].lower(),
                "min_size": int(m["minsize"]),
                "max_size": int(m["maxsize"]),
                "conditions": [
                    {"kind": c["kind"], "exprs": list(c["exprs"])}
                    for c in cond_stack
                ],
            }
            cur_form["settings"].append(cur_setting)
            continue

        m = RE_PASSWORD.match(ln)
        if m:
            cur_setting = {
                "kind": "Password",
                "prompt": m["prompt"],
                "help": m["help"],
                "qid": m["qid"].lower(),
                "conditions": [
                    {"kind": c["kind"], "exprs": list(c["exprs"])}
                    for c in cond_stack
                ],
            }
            cur_form["settings"].append(cur_setting)
            continue

        m = RE_OPTION.match(ln)
        if m and cur_setting and cur_setting["kind"] == "OneOf":
            opt = {
                "text": m["text"],
                "value": m["val"],
                "default": "Default" in (m["flags"] or ""),
                "mfg_default": "MfgDefault" in (m["flags"] or ""),
            }
            cur_setting["options"].append(opt)
            continue

        # Numeric default value
        if cur_setting and cur_setting["kind"] == "Numeric":
            md = re.match(r'^\s*Default DefaultId: (?P<did>0x[0-9A-Fa-f]+) Value: (?P<val>\S+)', ln)
            if md and md["did"] == "0x0":
                cur_setting["default"] = md["val"]

    return out


# ----------------------------- Renderer -----------------------------

def render_setting(s):
    """Render one setting as Markdown."""
    out = []
    name = s["prompt"] or "(unnamed)"
    out.append(f"##### `{s['qid']}` — **{name}** ({s['kind']})")
    if s.get("help"):
        # collapse multi-line help
        help_text = s["help"].replace("\\n", " ").replace("\n", " ").strip()
        if help_text:
            out.append(f"> {help_text}")
    info = []
    if "varstore_id" in s:
        info.append(f"VarStore `{s['varstore_id']}`")
    if "offset" in s:
        info.append(f"offset `{s['offset']}`")
    if "size_bits" in s:
        info.append(f"{s['size_bits']}-bit")
    if "min" in s and "max" in s:
        info.append(f"range `{s['min']}`..`{s['max']}`")
    if s.get("default") is not None:
        info.append(f"default `{s['default']}`")
    if info:
        out.append(f"- {' · '.join(info)}")

    # Options
    if s["kind"] in ("OneOf", "CheckBox") and s.get("options"):
        opt_strs = []
        for o in s["options"]:
            tag = ""
            if o.get("default") and o.get("mfg_default"):
                tag = " (default, mfg)"
            elif o.get("default"):
                tag = " (default)"
            elif o.get("mfg_default"):
                tag = " (mfg default)"
            opt_strs.append(f"`{o['value']}` = {o['text']}{tag}")
        out.append("- options: " + ", ".join(opt_strs))

    # Conditions (keep concise)
    if s.get("conditions"):
        cond_strs = []
        for c in s["conditions"]:
            if not c["exprs"]:
                continue
            es = ", ".join(f"Q{e['qid']}={e['val']}" for e in c["exprs"])
            cond_strs.append(f"{c['kind']}({es})")
        if cond_strs:
            out.append(f"- conditions: {'; '.join(cond_strs)}")
    return "\n".join(out)


def render_module(module_name, parsed):
    out = []
    out.append(f"## Module: `{module_name}`")
    fs = parsed.get("formset")
    if fs:
        out.append(f"- FormSet GUID: `{fs['guid']}`")
        out.append(f"- FormSet title: **{fs['title']}**")
        if fs["help"]:
            out.append(f"- FormSet help: {fs['help']}")
    if parsed.get("varstores"):
        out.append("\n### VarStores")
        for vid in sorted(parsed["varstores"].keys(), key=lambda x: int(x, 16)):
            v = parsed["varstores"][vid]
            out.append(f"- `{v['id']}` **{v['name']}** — GUID `{v['guid']}`, size `{v['size']}`")

    out.append("\n### Forms")
    for f in parsed["forms"]:
        title = f['title'] or "(untitled)"
        out.append(f"\n#### Form `{f['id']}` — {title}")
        if f["refs"]:
            out.append("\n_Navigation (children):_")
            for r in f["refs"]:
                ext = ""
                if "external_formset_guid" in r:
                    ext = f" (external FormSet `{r['external_formset_guid']}`)"
                out.append(f"- → `{r['formid']}` **{r['prompt']}**{ext}")
                if r.get("help"):
                    out.append(f"  - {r['help']}")
        if f["settings"]:
            out.append("\n_Settings:_")
            for s in f["settings"]:
                out.append("\n" + render_setting(s))
    return "\n".join(out)


def main():
    if len(sys.argv) < 3:
        print("usage: ifr_to_reference.py <ifr_dir> <out_md>", file=sys.stderr)
        sys.exit(1)
    ifr_dir = Path(sys.argv[1])
    out_md = Path(sys.argv[2])

    parsed_modules = {}
    for path in sorted(ifr_dir.rglob("*.uefi.ifr.txt")):
        name = path.stem.split(".")[0]   # e.g. "72_Setup"
        # de-dup: only keep first per file basename, but we'll show all
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        try:
            p = parse_ifr(text)
        except Exception as e:
            print(f"WARN: parse failed for {path}: {e}", file=sys.stderr)
            continue
        parsed_modules[str(path.relative_to(ifr_dir))] = p

    # Emit
    sections = []
    for rel, parsed in sorted(parsed_modules.items()):
        try:
            sections.append(render_module(rel, parsed))
        except Exception as e:
            print(f"WARN: render failed for {rel}: {e}", file=sys.stderr)

    # Summary
    n_modules = len(parsed_modules)
    n_forms = sum(len(p["forms"]) for p in parsed_modules.values())
    n_settings = sum(
        len(f["settings"]) for p in parsed_modules.values() for f in p["forms"]
    )

    header = (
        "# ROMED8-2T BIOS Setting Reference (P3.70)\n\n"
        "This is the complete enumeration of every BIOS setup setting in P3.70, "
        "extracted from the IFR (Internal Forms Representation) of every UEFI "
        "module that defines a HII Forms package. Organized hierarchically as "
        "Module → FormSet → Form → Setting, with full metadata: NVRAM VarStore + "
        "byte offset, size, allowed values/options, defaults, and the SuppressIf / "
        "GrayOutIf conditions that gate each setting.\n\n"
        f"**Summary:** {n_modules} modules, {n_forms} forms, {n_settings} settings.\n\n"
        "**How to read a setting block:**\n"
        "- `0xNNN` (e.g. `0xe1`) is the QuestionId — a stable per-FormSet identifier.\n"
        "- `VarStore 0xN` is the NVRAM variable that backs the setting (look up its "
        "name + GUID in the module's VarStore table).\n"
        "- `offset 0xNNN` is the byte offset inside that variable. This is what you "
        "feed to `setup_var.efi` from the EFI shell, or to `efivar` from Linux.\n"
        "- Options like `0x3 = GEN3` mean writing the byte value `0x03` selects the "
        "GEN3 option.\n"
        "- `conditions: GrayOutIf(Qabc=0x1)` means the setting is grayed in the GUI "
        "when the referenced QuestionId equals 0x1. The NVRAM byte is still "
        "writable directly — gray-out is a UI policy, not a write protection.\n\n"
        "---\n"
    )
    out_md.write_text(header + "\n\n".join(sections), encoding="utf-8")
    print(f"Wrote {out_md} ({n_modules} modules, {n_forms} forms, {n_settings} settings)")


if __name__ == "__main__":
    main()
