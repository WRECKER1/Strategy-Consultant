"""Validate the Layer 1/2 configuration and print its fingerprint.

Usage (from the repository root):
    python -m engine.config_check

What it checks:
  * every config file loads and has a version
  * constructs, indicators, rules and options refer to each other consistently
  * every rule/band/modifier expression parses under the safe evaluator
  * every threshold used by a rule or modifier exists
Then it prints a SHA-256 fingerprint of the core config. The generalisability
test (MT §7.3) compares this fingerprint across all case runs: it must not change.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

from engine import expr

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
CORE_FILES = ["codebook.yaml", "evidence_rules.yaml", "modifiers.yaml", "rules.yaml",
              "options.yaml", "source_checklist.yaml", "register_schema.yaml"]


def load_all() -> dict:
    out = {}
    for name in CORE_FILES:
        with open(CONFIG / name, encoding="utf-8") as fh:
            out[name.removesuffix(".yaml")] = yaml.safe_load(fh)
    return out


def fingerprint() -> str:
    h = hashlib.sha256()
    for name in CORE_FILES:
        data = yaml.safe_load((CONFIG / name).read_text(encoding="utf-8"))
        # canonical JSON so comments and whitespace do not change the fingerprint
        h.update(name.encode())
        h.update(json.dumps(data, sort_keys=True, default=str).encode())
    return h.hexdigest()


def check(cfg: dict) -> list[str]:
    errs: list[str] = []
    cb, rules, mods, opts, ev = cfg["codebook"], cfg["rules"], cfg["modifiers"], cfg["options"], cfg["evidence_rules"]
    for k, v in cfg.items():
        if not isinstance(v, dict) or "version" not in v:
            errs.append(f"{k}: missing version")

    inds, cons = cb["indicators"], cb["constructs"]
    for code, c in cons.items():
        for i in c["mean_of"]:
            if i not in inds:
                errs.append(f"construct {code}: unknown indicator {i}")
            elif inds[i]["construct"] != code:
                errs.append(f"construct {code}: {i} belongs to {inds[i]['construct']}")
        if c["min_rated_indicators"] > len(c["mean_of"]):
            errs.append(f"construct {code}: min_rated_indicators > number of indicators")

    for code, ind in inds.items():
        m = ind["scoring_method"]
        if m == "anchored":
            missing = [k for k in (1, 2, 3, 4, 5) if k not in ind.get("anchors", {})]
            if missing:
                errs.append(f"{code}: anchors missing {missing}")
        elif m == "share_band":
            for b in ind["bands"]:
                if b["rule"] != "otherwise":
                    _try(errs, f"{code} band", b["rule"])
        elif m == "structured":
            for mp in ind["mapping"]:
                _try(errs, f"{code} mapping", mp["when"])
        elif m == "categorical":
            if not ind.get("categories"):
                errs.append(f"{code}: categorical without categories")
        else:
            errs.append(f"{code}: unknown scoring_method {m}")

    known_names = set(inds) | set(cons) | {"EC1_unit_exists", "EC1_integration_link", "no_misfit_fired"}
    thresholds = rules["thresholds"]
    for section in ("rules", "outcomes"):
        for rid, r in rules[section].items():
            if "condition" not in r:
                continue
            _try(errs, f"rule {rid}", r["condition"])
            try:
                unknown = expr.names_in(r["condition"]) - known_names
                if unknown:
                    errs.append(f"rule {rid}: unknown names {sorted(unknown)}")
                for t in expr.threshold_refs(r["condition"]):
                    if t not in thresholds:
                        errs.append(f"rule {rid}: unknown threshold t.{t}")
            except ValueError:
                pass
            for o in r.get("options", []):
                if o not in opts["options"]:
                    errs.append(f"rule {rid}: unknown option {o}")

    for oid, o in opts["options"].items():
        for m in o["addresses"]:
            if m not in rules["rules"]:
                errs.append(f"option {oid}: addresses unknown rule {m}")
            elif oid not in rules["rules"][m]["options"]:
                errs.append(f"option {oid}: addresses {m} but {m} does not list it")
        for i in o["evidence_hooks"]:
            if i not in inds:
                errs.append(f"option {oid}: unknown evidence hook {i}")

    for mname, m in mods["modifiers"].items():
        if mname not in mods["context_fields"]:
            errs.append(f"modifier {mname}: not a context field")
        allowed = set(mods["context_fields"][mname].get("values", []))
        for val, effects in m["effects"].items():
            if allowed and val not in allowed:
                errs.append(f"modifier {mname}: value {val} not in {sorted(allowed)}")
            for e in effects:
                if e["type"] == "threshold_shift" and e["threshold"] not in thresholds:
                    errs.append(f"modifier {mname}: unknown threshold {e['threshold']}")
                if "indicator" in e and e["indicator"] not in inds:
                    errs.append(f"modifier {mname}: unknown indicator {e['indicator']}")

    for t in rules["sensitivity"]["shiftable"]:
        if t not in thresholds:
            errs.append(f"sensitivity: unknown threshold {t}")

    if ev["precedence"] != ["F", "T", "E", "C"]:
        errs.append("evidence precedence must be F > T > E > C (MT §5.2 R6)")
    return errs


def _try(errs, where, e):
    try:
        expr.parse(e)
    except (ValueError, SyntaxError) as exc:
        errs.append(f"{where}: {exc}")


def main() -> int:
    cfg = load_all()
    errs = check(cfg)
    if errs:
        print("CONFIG CHECK FAILED")
        for e in errs:
            print("  -", e)
        return 1
    cb = cfg["codebook"]
    print("CONFIG CHECK PASSED")
    print(f"  constructs: {len(cb['constructs'])}   indicators: {len(cb['indicators'])}   "
          f"rules: {len(cfg['rules']['rules'])}   options: {len(cfg['options']['options'])}")
    print(f"  core config fingerprint (SHA-256): {fingerprint()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
