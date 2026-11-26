"""Intake agent (rule-based, no LLM): MT §2 stage 1–2, §4.3 step 1.

* validates the context profile (Form A) against modifiers.yaml → context_fields
* derives size and transformation stage where the data allow (modifiers.yaml → derivations)
* validates the source register against source_checklist.yaml and the files on disk
* reports missing source types and the indicators they would have fed
* lists context modifiers that need analyst confirmation at CP2
"""
from __future__ import annotations

import csv
from pathlib import Path

from engine import expr
from engine.common import load_yaml, months_between, to_date


def load_case(case_dir: Path) -> tuple[dict, dict]:
    case = load_yaml(case_dir / "case.yaml")
    register = {}
    with open(case_dir / "source_register.csv", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
            if row.get("source_id"):
                register[row["source_id"]] = row
    return case, register


def run_intake(case_dir: Path, case: dict, register: dict, cfg: dict) -> dict:
    mods, chk = cfg["modifiers"], cfg["source_checklist"]
    errors, warnings, derived = [], [], {}
    ctx = dict(case.get("context") or {})

    # ---- derivations (deterministic)
    if ctx.get("employees") not in (None, ""):
        for d in mods["derivations"]["size"]:
            if d["rule"] == "otherwise" or expr.evaluate(d["rule"], {"employees": int(ctx["employees"])}):
                if ctx.get("size") and ctx["size"] != d["value"]:
                    warnings.append(f"size given as '{ctx['size']}' but employees={ctx['employees']} implies '{d['value']}'; using derived value")
                ctx["size"] = derived["size"] = d["value"]
                break
    ann, as_of = to_date(ctx.get("transformation_announcement_date")), to_date(case.get("as_of_date"))
    if ann and as_of:
        m = months_between(ann, as_of)
        ctx["months_since_announcement"] = round(m, 1)
        for d in mods["derivations"]["transformation_stage"]:
            if d["rule"] == "otherwise" or expr.evaluate(d["rule"], {"months_since_announcement": m}):
                ctx["transformation_stage"] = derived["transformation_stage"] = d["value"]
                break

    # ---- Form A validation
    fields = mods["context_fields"]
    merged = {**ctx, "as_of_date": case.get("as_of_date"), "synthetic": case.get("synthetic")}
    for name, spec in fields.items():
        v = merged.get(name)
        if v in (None, ""):
            if spec.get("required"):
                errors.append(f"context: '{name}' is required")
            continue
        if spec["type"] == "enum" and v not in spec["values"]:
            errors.append(f"context: '{name}'='{v}' not in {spec['values']}")
        if spec["type"] == "date":
            try:
                to_date(v)
            except ValueError as e:
                errors.append(f"context: {e}")

    # ---- source register validation
    req = chk["source_register_fields"]["required"]
    import re
    counts: dict[str, int] = {}
    for sid, s in register.items():
        missing = [f for f in req if not s.get(f)]
        if missing:
            errors.append(f"{sid}: missing register fields {missing}")
        if not re.match(chk["source_register_fields"]["id_pattern"], sid):
            errors.append(f"{sid}: source_id must look like S01")
        if s.get("access_type") and s["access_type"] not in chk["source_register_fields"]["access_type_values"]:
            errors.append(f"{sid}: access_type '{s['access_type']}' not allowed (public / institutional_licence only, MT §5.3)")
        st = s.get("source_type")
        if st and st not in chk["source_types"]:
            errors.append(f"{sid}: unknown source_type '{st}'")
        f = case_dir / "sources" / (s.get("file") or "")
        if not s.get("file") or not f.is_file():
            errors.append(f"{sid}: file not found: sources/{s.get('file')}")
        elif f.suffix.lower() not in chk["file_formats_accepted"]:
            errors.append(f"{sid}: file type {f.suffix} not accepted")
        try:
            to_date(s.get("date"))
        except ValueError as e:
            errors.append(f"{sid}: {e}")
        n = int(s["units"]) if s.get("units", "").isdigit() else 1
        counts[st] = counts.get(st, 0) + n

    # ---- checklist gap report
    gaps = []
    for st, spec in chk["source_types"].items():
        if st in ("synthetic_document", "course_case"):
            continue
        if "required_if" in spec:
            own = ctx.get("ownership")
            needed = own in ("state_owned", "mnc_subsidiary")
            if not needed:
                continue
            minimum = 1
        else:
            minimum = spec["min"]
        have = counts.get(st, 0)
        if have < minimum or have < spec["target"]:
            gaps.append({"source_type": st, "have": have, "min": minimum, "target": spec["target"],
                         "below_minimum": have < minimum, "feeds": spec.get("feeds", []),
                         "note": spec.get("note")})

    # ---- CP2 confirmations needed
    confirm = []
    eval_vars = {**ctx, "value": None}
    for mname, m in mods["modifiers"].items():
        cond = m.get("confirm_at_cp2_if")
        if not cond:
            continue
        val = ctx.get(mname)
        if cond == "always":
            need = True
        elif cond == "employees is missing":
            need = ctx.get("employees") in (None, "")
        else:
            need = _confirm_rule(cond, {**eval_vars, "value": val})
        if need:
            confirm.append({"modifier": mname, "value": val, "reason": cond})

    return {"ok": not errors, "errors": errors, "warnings": warnings, "derived": derived, "context": ctx,
            "source_counts": counts, "checklist_gaps": gaps, "cp2_confirmations": confirm,
            "synthetic": bool(case.get("synthetic"))}


def _confirm_rule(cond: str, vars_: dict) -> bool:
    if "between" in cond:   # "months_since_announcement between 10 and 14 or between 34 and 38"
        import re
        m = vars_.get("months_since_announcement")
        if m is None:
            return True
        pairs = re.findall(r"between (\d+) and (\d+)", cond)
        return any(float(a) <= m <= float(b) for a, b in pairs)
    return bool(expr.evaluate(cond, vars_))
