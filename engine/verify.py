"""Verifier: deterministic, no LLM (non-negotiables 4 and 7).

Checks every proposed evidence row:
  1. the excerpt actually appears in the source text (exact or near-exact)
  2. the cited page matches (±1) where a page number is given
  3. excerpt length, indicator/field validity, class/source consistency
  4. recency (R3), employee-review sample and age (R4), duplicates
  5. contradictions on proposed levels (R6 pre-flag; final check after CP1)
  6. instruction-like text inside the source (treated as data and flagged)
Rejected rows are kept in the register with their reason and never reach scoring.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from rapidfuzz import fuzz

from engine.common import months_between, to_date

QUOTE_MAP = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'",
                           "“": '"', "”": '"', "„": '"', "–": "-", "—": "-",
                           "−": "-", " ": " ", "…": "..."})

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above) (instructions|rules)",
    r"disregard (your|the) (instructions|rules|system prompt)",
    r"you are (now )?(an? )?(ai|assistant|language model)",
    r"system prompt",
    r"(rate|score) (this|the) (company|firm|organi[sz]ation) (as )?[1-5]",
    r"do not (report|flag|mention)",
]


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).translate(QUOTE_MAP)
    t = re.sub(r"-\s*\n\s*", "", t)                      # join words split across lines
    t = t.replace("-", "")                                 # then ignore hyphens: "sign-off" == "signoff"
    t = PAGE_MARK_RE.sub(" ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


PAGE_MARK_RE = re.compile(r"\[\[PAGE\s+\d+\]\]")


def _segments(excerpt: str) -> list[str]:
    parts = re.split(r"\s*(?:\.\.\.|…|\[\.\.\.\])\s*", excerpt)
    return [p for p in (normalize(x) for x in parts) if len(p) >= 3]


def match_excerpt(excerpt: str, pages: dict[int, str]) -> tuple[float, list[int]]:
    """Return (similarity 0–1, pages where the best match was found)."""
    segs = _segments(excerpt)
    if not segs:
        return 0.0, []
    norm_pages = {p: normalize(t) for p, t in pages.items()}
    seg_scores, seg_pages = [], []
    for seg in segs:
        best, best_pages = 0.0, []
        for p, txt in norm_pages.items():
            if seg in txt:
                score = 1.0
            elif len(seg) > len(txt):
                score = fuzz.ratio(seg, txt) / 100
            else:
                score = fuzz.partial_ratio(seg, txt) / 100
            if score > best:
                best, best_pages = score, [p]
            elif score == best and score > 0:
                best_pages.append(p)
        seg_scores.append(best)
        seg_pages.extend(best_pages)
    # the weakest segment decides, so one invented segment fails the whole quote
    return min(seg_scores), sorted(set(seg_pages))


def detect_injection(text: str) -> list[str]:
    low = normalize(text)
    return [pat for pat in INJECTION_PATTERNS if re.search(pat, low)]


def _page_number(location: str) -> int | None:
    m = re.search(r"\bp(?:age|g)?\.?\s*(\d+)", location or "", re.I)
    return int(m.group(1)) if m else None


def verify_rows(rows: list[dict], docs: dict, register: dict, case: dict, cfg: dict) -> list[dict]:
    """Annotate rows in place with verification_status, similarity, flags, reject_reason."""
    ev = cfg["evidence_rules"]
    cb = cfg["codebook"]["indicators"]
    vcfg = ev["verification"]
    max_words = ev["rules"]["R7_quotation_discipline"]["max_excerpt_words"]
    stale_m = ev["rules"]["R3_recency"]["downgrade_after_months"]
    e_age_m = ev["rules"]["R3_recency"]["employee_review_max_age_months"]
    min_reviews = ev["rules"]["R4_employee_review_discipline"]["min_reviews"]
    as_of: date = to_date(case["as_of_date"])
    seen: dict[tuple, str] = {}

    for r in rows:
        flags: list[str] = list(r.get("flags") or [])
        reason = None
        src = register.get(r["source_id"])
        doc = docs.get(r["source_id"])
        ind = cb.get(r.get("indicator"))

        if src is None or doc is None:
            reason = "unknown_source"
        elif ind is None:
            reason = "unknown_indicator"
        elif len(r["excerpt"].split()) > max_words:
            reason = f"excerpt_over_{max_words}_words"

        sim, found_pages = (0.0, [])
        if reason is None:
            sim, found_pages = match_excerpt(r["excerpt"], doc.pages)
            if sim < vcfg["accept_min_similarity"]:
                reason = "not_found_in_source"
            else:
                page = _page_number(r.get("location", ""))
                if page is not None and found_pages and min(abs(page - fp) for fp in found_pages) > 1 \
                        and max(doc.pages) > 1:
                    reason = "page_mismatch"

        if reason is None:
            reason = _method_check(r, ind, src)

        if reason is None and src is not None:
            sdate = to_date(src.get("date"))
            is_e = r.get("evidence_class") == "E" or src.get("source_type") == "employee_review_aggregate"
            period_end = to_date((r.get("structured_fields") or {}).get("period_end")) or sdate
            if sdate and months_between(sdate, as_of) > stale_m:
                flags.append("stale_36m")
            if is_e:
                if period_end and months_between(period_end, as_of) > e_age_m:
                    flags.append("e_older_24m")
                n = (r.get("structured_fields") or {}).get("n_reviews")
                if n is None or n < min_reviews:
                    flags.append("e_sample_below_30")
            if r.get("evidence_class") == "E" and src.get("source_type") != "employee_review_aggregate":
                reason = "class_E_from_non_review_source"
            if src.get("source_type") == "employee_review_aggregate" and r.get("evidence_class") not in (None, "E"):
                r["evidence_class"] = "E"     # deterministic rule; logged via class_justification
                r["class_justification"] = (r.get("class_justification") or "") + " [set to E by verifier: review-aggregate source]"

        key = (r.get("source_id"), r.get("indicator"), normalize(r.get("excerpt", ""))[:120])
        if r.get("indicator") == "SO3":                    # each posting is its own unit, even with boilerplate text
            key = key + (normalize(r.get("location", "")),)
        if reason is None and key in seen:
            flags.append("duplicate")
            r["duplicate_of"] = seen[key]
        elif reason is None:
            seen[key] = r["evidence_id"]

        r["similarity"] = round(sim, 3)
        r["flags"] = sorted(set(flags))
        if reason:
            r["verification_status"] = "rejected_page_mismatch" if reason == "page_mismatch" else "rejected_not_found" \
                if reason == "not_found_in_source" else "rejected_invalid"
            r["reject_reason"] = reason
            r["analyst_decision"] = "auto_rejected"
        else:
            r["verification_status"] = "verified_exact" if sim >= vcfg["exact_match_score"] else "verified_near"
            r["reject_reason"] = None

    flag_contradictions(rows, cfg, level_field="proposed_level")
    return rows


def _method_check(r: dict, ind: dict, src: dict | None) -> str | None:
    m = ind["scoring_method"]
    sf = r.get("structured_fields") or {}
    if m == "anchored":
        if r.get("proposed_level") not in (1, 2, 3, 4, 5):
            return "anchored_indicator_without_level"
    elif m == "categorical":
        if r.get("proposed_category") not in ind["categories"]:
            return "missing_category"
    elif m == "structured":
        if sf.get("unit_exists") in (None, "unknown"):
            return "ec1_unit_exists_unknown"
    elif m == "share_band":
        if r["indicator"] == "SO3":
            if sf.get("posting_code") not in ("autonomy", "procedure", "mixed"):
                return "so3_missing_posting_code"
        else:
            if src and src.get("source_type") != "employee_review_aggregate":
                return "review_theme_from_non_review_source"
            if sf.get("theme_count") is None or sf.get("n_reviews") in (None, 0) or not sf.get("theme"):
                return "review_theme_missing_counts"
    return None


def flag_contradictions(rows: list[dict], cfg: dict, level_field: str) -> None:
    """R6: flag rows on the same indicator whose levels differ by >= min_level_gap."""
    gap = cfg["evidence_rules"]["rules"]["R6_contradiction"]["min_level_gap"]
    by_ind: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("analyst_decision") in ("auto_rejected", "rejected"):
            continue
        lvl = r.get(level_field)
        if lvl is None:
            continue
        by_ind.setdefault(r["indicator"], []).append(r)
    for ind, rs in by_ind.items():
        levels = [r[level_field] for r in rs]
        if max(levels) - min(levels) >= gap:
            for r in rs:
                if "contradiction" not in r["flags"]:
                    r["flags"] = sorted(set(r["flags"]) | {"contradiction"})
