"""Human checkpoints (MT §8.2, Table 11). Each checkpoint is a file the analyst
edits (in Excel or a text editor now, in the Streamlit app from Phase 3). The
orchestrator refuses to continue until every item is decided. Every decision is
written to the run log with the analyst's name.

CP1  evidence approval      cp1_review.csv     accept / reject / edit each verified row
CP2  judgement calls        cp2_review.yaml    borderline modifiers, contradictions, DI1 ties, ownership
CP3  option selection       cp3_selection.yaml analyst chooses among library options
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import yaml

CP1_COLUMNS = ["evidence_id", "source_id", "indicator", "location", "excerpt", "evidence_class", "class_justification",
               "proposed_level", "proposed_category", "structured_fields", "level_scope", "rationale",
               "verification_status", "similarity", "flags", "reject_reason",
               "analyst_decision", "analyst_level", "analyst_category", "analyst_class", "analyst_note"]
DECISIONS = {"accepted", "rejected", "edited"}


class CheckpointIncomplete(Exception):
    pass


# ----------------------------------------------------------------- CP1
def write_cp1(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:   # utf-8-sig so Excel on Windows shows ₹, é etc.
        w = csv.DictWriter(fh, fieldnames=CP1_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            out = dict(r)
            out["flags"] = ";".join(r.get("flags") or [])
            sf = {k: v for k, v in (r.get("structured_fields") or {}).items() if v is not None}
            out["structured_fields"] = ";".join(f"{k}={v}" for k, v in sf.items())
            out.setdefault("analyst_decision", "pending")
            w.writerow(out)


def read_cp1(path: Path, rows: list[dict], analyst: str) -> tuple[list[dict], list[str]]:
    """Merge analyst decisions into rows. Returns (rows, problems). Problems block the run."""
    by_id = {r["evidence_id"]: r for r in rows}
    problems: list[str] = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for rec in csv.DictReader(fh):
            r = by_id.get(rec.get("evidence_id", ""))
            if r is None:
                problems.append(f"unknown evidence_id {rec.get('evidence_id')} in CP1 file (rows cannot be added by hand)")
                continue
            dec = (rec.get("analyst_decision") or "pending").strip().lower()
            if r.get("analyst_decision") == "auto_rejected" or (r.get("verification_status") or "").startswith("rejected"):
                if dec in ("accepted", "edited"):
                    problems.append(f"{r['evidence_id']}: verifier rejected this excerpt ({r.get('reject_reason')}); it cannot be accepted")
                continue
            if dec not in DECISIONS:
                problems.append(f"{r['evidence_id']}: decision is '{dec}', expected accepted / rejected / edited")
                continue
            r["analyst_decision"] = dec
            r["analyst_note"] = rec.get("analyst_note") or ""
            r["decided_by"] = analyst
            if dec == "edited":
                lvl, cat, cls = (rec.get("analyst_level") or "").strip(), (rec.get("analyst_category") or "").strip(), \
                    (rec.get("analyst_class") or "").strip().upper()
                if not (lvl or cat or cls):
                    problems.append(f"{r['evidence_id']}: 'edited' needs analyst_level, analyst_category or analyst_class")
                if lvl:
                    if lvl not in {"1", "2", "3", "4", "5"}:
                        problems.append(f"{r['evidence_id']}: analyst_level must be 1–5")
                    else:
                        r["analyst_level"] = int(lvl)
                if cat:
                    r["analyst_category"] = cat
                if cls:
                    if cls not in {"F", "C", "T", "E"}:
                        problems.append(f"{r['evidence_id']}: analyst_class must be F, C, T or E")
                    else:
                        r["analyst_class"] = cls
            if dec in ("accepted", "edited") and not (r.get("analyst_class") or r.get("evidence_class")):
                problems.append(f"{r['evidence_id']}: no evidence class; set analyst_class")
    return rows, problems


def bulk_accept_verified(rows: list[dict]) -> tuple[int, int]:
    """Accept verified rows that carry no review flag; flagged rows stay pending for individual review."""
    review_flags = {"contradiction", "unclassified", "duplicate", "embedded_instruction", "e_sample_below_30", "e_older_24m"}
    accepted = left = 0
    for r in rows:
        if r.get("analyst_decision") != "pending":
            continue
        if set(r.get("flags") or []) & review_flags:
            left += 1
            continue
        r["analyst_decision"] = "accepted"
        accepted += 1
    return accepted, left


def final_level(r: dict):
    return r.get("analyst_level") if r.get("analyst_level") is not None else r.get("proposed_level")


def final_class(r: dict):
    return r.get("analyst_class") or r.get("evidence_class")


# ----------------------------------------------------------------- CP2
def build_cp2(intake: dict, rows: list[dict], cfg: dict) -> dict:
    accepted = [r for r in rows if r.get("analyst_decision") in ("accepted", "edited")]
    items = []
    for c in intake["cp2_confirmations"]:
        allowed = cfg["modifiers"]["context_fields"][c["modifier"]].get("values")
        items.append({"id": f"MOD_{c['modifier']}", "type": "modifier",
                      "question": f"Confirm context modifier '{c['modifier']}' = '{c['value']}' (borderline / judgement call: {c['reason']}).",
                      "default": c["value"], "allowed": allowed, "answer": None})
    gap = cfg["evidence_rules"]["rules"]["R6_contradiction"]["min_level_gap"]
    by_ind: dict[str, list[dict]] = {}
    for r in accepted:
        if final_level(r) is not None:
            by_ind.setdefault(r["indicator"], []).append(r)
    prec = cfg["evidence_rules"]["precedence"]
    for ind, rs in sorted(by_ind.items()):
        lv = [final_level(r) for r in rs]
        if max(lv) - min(lv) >= gap:
            items.append({"id": f"CONTRA_{ind}", "type": "contradiction", "indicator": ind,
                          "question": f"{ind}: accepted evidence conflicts (levels {sorted(set(lv))}). Default: precedence "
                                      f"{' > '.join(prec)} and confidence capped at Medium (MT §5.2 R6). Answer 'default', "
                                      "or an evidence_id that should prevail plus a reason.",
                          "evidence": [{"evidence_id": r["evidence_id"], "class": final_class(r), "level": final_level(r),
                                        "source_id": r["source_id"], "excerpt": r["excerpt"]} for r in rs],
                          "default": "default", "answer": None, "reason": None})
    cats = Counter(r.get("analyst_category") or r.get("proposed_category") for r in accepted if r["indicator"] == "DI1")
    if cats:
        top = cats.most_common()
        if len(top) > 1 and top[0][1] == top[1][1]:
            tied = [c for c, n in top if n == top[0][1]]
            items.append({"id": "TIE_DI1", "type": "di1_tie",
                          "question": f"DI1 tie between {tied} ({dict(cats)}). Choose the category that best describes the announced digital work (D-11).",
                          "allowed": tied, "default": None, "answer": None})
    own = intake["context"].get("ownership")
    if own in ("state_owned", "mnc_subsidiary"):
        parent_rows = [r["evidence_id"] for r in accepted if r["indicator"] == "SO2" and r.get("level_scope") == "parent"]
        items.append({"id": "OWN_SO2", "type": "ownership",
                      "question": f"Ownership is '{own}': SO2 needs parent/ministry evidence (D-14). Parent-level rows accepted: "
                                  f"{parent_rows or 'none'}. Answer 'keep' (default rule) or 'override' with a reason to "
                                  "rate SO2 from firm-level evidence.",
                      "default": "keep", "allowed": ["keep", "override"], "answer": None, "reason": None})
    return {"checkpoint": "CP2", "instructions": "Fill every 'answer' (and 'reason' where asked). To accept a default, "
            "copy it into 'answer'. Then resume the run.", "analyst": None, "items": items}


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")


def read_cp2(path: Path) -> tuple[dict, list[str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    problems = []
    if not data.get("analyst"):
        problems.append("CP2: fill 'analyst' with your name")
    for it in data["items"]:
        a = it.get("answer")
        if a in (None, ""):
            problems.append(f"{it['id']}: no answer")
        elif it.get("allowed") and a not in it["allowed"]:
            problems.append(f"{it['id']}: answer '{a}' not in {it['allowed']}")
        if it["type"] == "contradiction" and a not in (None, "", "default"):
            ids = [e["evidence_id"] for e in it["evidence"]]
            if a not in ids:
                problems.append(f"{it['id']}: answer must be 'default' or one of {ids}")
            if not it.get("reason"):
                problems.append(f"{it['id']}: give a reason for overriding precedence")
        if it["type"] == "ownership" and a == "override" and not it.get("reason"):
            problems.append(f"{it['id']}: give a reason for the override")
    return data, problems


# ----------------------------------------------------------------- CP3
def build_cp3(recommendations: dict) -> dict:
    by_rule: dict[str, list] = {}
    for o in recommendations["options"]:
        by_rule.setdefault(o["rule_id"], []).append(o["option_id"])
    for s in recommendations.get("analyst_suggested", []):
        by_rule.setdefault(s["rule_id"], []).append(f"SUGGESTED: {s['title']}")
    return {"checkpoint": "CP3",
            "instructions": "For each misfit, list the option IDs you select under 'chosen' (one or more, or 'none') "
                            "and give a rationale. The tool never selects for you (MT §6.3).",
            "analyst": None,
            "items": [{"rule_id": r, "available": opts, "chosen": None, "rationale": None} for r, opts in by_rule.items()]}


def read_cp3(path: Path) -> tuple[dict, list[str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    problems = [] if data.get("analyst") else ["CP3: fill 'analyst' with your name"]
    for it in data["items"]:
        ch = it.get("chosen")
        if ch in (None, "", []):
            problems.append(f"{it['rule_id']}: nothing chosen (write none if no option fits)")
            continue
        ch = [ch] if isinstance(ch, str) else ch
        bad = [c for c in ch if c != "none" and c not in it["available"]]
        if bad:
            problems.append(f"{it['rule_id']}: {bad} not among available options {it['available']}")
        if not it.get("rationale"):
            problems.append(f"{it['rule_id']}: give a rationale")
    return data, problems
