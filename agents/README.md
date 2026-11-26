# Agents and pipeline (Phase 2)

## Pipeline

```
 case folder (case.yaml + source_register.csv + sources/)
        │
 INTAKE ─────────── intake agent (rule-based)      validates Form A, derives size + stage, checks register,
        │                                          lists source-pack gaps and CP2 confirmations
 EXTRACT ────────── extraction agent (LLM)          per chunk → proposed evidence rows (verbatim excerpt,
        │                                          location, indicator, proposed level/category/fields)
 VERIFY_QUOTES ──── verifier (code)                 excerpt must be found in the source text (≥0.92), page ±1,
        │                                          ≤60 words, valid fields → otherwise auto-rejected + logged
 CLASSIFY ───────── classification agent (LLM)      F / C / T / E + one-line justification (verified rows only)
        │
 VERIFY_FULL ────── verifier (code)                 recency, review sample/age, E-only-from-reviews,
        │                                          duplicates, contradictions, embedded-instruction flags
 ══ CP1 ══ analyst  cp1_review.csv                  accept / reject / edit every row (MT Table 11 row 1)
        │
 ══ CP2 ══ analyst  cp2_review.yaml                 borderline modifiers, contradictions, DI1 tie, ownership
        │                                          (MT Table 11 rows 2–3)
 SCORE ──────────── scoring engine (code)           anchors, claim ceiling, recency, triangulation, confidence,
        │                                          modifiers → thresholds                     [Phase 3]
 DIAGNOSE ───────── diagnosis engine (code)         M1–M5, FIT, GAP, Cannot assess, compound tensions [Phase 3]
        │
 RECOMMEND ──────── recommendation agent (LLM)      tailors library options to the firm's accepted evidence
        │
 ══ CP3 ══ analyst  cp3_selection.yaml              chooses among options (MT Table 11 row 4)
        │
 REPORT ─────────── report agent (LLM) + code       LLM drafts the summary statements only; code builds
                                                   everything else, incl. Show Evidence       [Phase 3]
```

Everything a run produces is in `runs/<case_id>/<run_id>/`:

| File | Content |
|---|---|
| `state.json` | stage, status, config fingerprint, runtime settings, excluded sources |
| `run_log.jsonl` | every event: agent calls (tokens, cost), verifier results, every analyst decision |
| `intake_report.json` | Form A validation, derived values, source-pack gaps |
| `evidence_register.json` | all proposed rows, with verification and analyst decisions (Appendix B, extended) |
| `cp1_review.csv`, `cp2_review.yaml`, `cp3_selection.yaml` | the checkpoint files the analyst edits |
| `embedded_instructions.json` | any instruction-like text found inside sources |
| `agent_io/<agent>/<call>.json` | the exact input and output of every live agent call |
| `paste/` | paste-mode prompts and replies |

## Who may decide what (principle 1)

| Decision | Made by | Never made by |
|---|---|---|
| Which excerpts are relevant; the anchor level each excerpt suggests | extraction agent **proposes**, analyst **confirms** (CP1) | — |
| Evidence class | classification agent proposes, analyst may edit (CP1); E is fixed by code for review sources | — |
| Whether a quote exists in the source | verifier (code) | LLM, analyst |
| Indicator and construct scores, confidence | scoring engine (code, from config) | LLM |
| Modifiers at the margin, contradiction resolution | analyst (CP2) with a code default | LLM |
| Misfit rules | diagnosis engine (code, from config) | LLM |
| Which options are shown | code (library lookup) | LLM |
| Which option is chosen | analyst (CP3) | LLM, code |
| Narrative wording | recommendation / report agents; every statement must cite evidence or a rule, else code drops it | — |

## Agent contracts

| Agent | Prompt | Input | Output schema | Post-checks in code |
|---|---|---|---|---|
| Intake (rule-based) | — | `case.yaml`, `source_register.csv`, files | `intake_report.json` | — |
| Extraction (LLM) | `prompts/extraction.md` + rendered codebook | source metadata + one chunk inside `<source_document>` tags | `schemas.extraction_schema`: rows[], embedded_instruction_detected | verifier (quote, page, length, method fields) |
| Classification (LLM) | `prompts/classification.md` | batches of up to 40 rows with source type/publisher | `schemas.classification_schema` | every row must come back; E only from review sources |
| Verifier (code) | — | rows + source text + register + case | fields on each row | — |
| Recommendation (LLM) | `prompts/recommendation.md` | fired rules, library options (text from config), accepted evidence, tensions | `schemas.recommendation_schema` | no option outside those retrieved; invalid evidence IDs removed and logged; library text inserted by code |
| Report (LLM) | `prompts/report.md` | diagnosis JSON | `schemas.report_schema` | statements without valid evidence or rule citations are dropped and listed |

Agent outputs are constrained by JSON Schema in API mode and validated against the same schema in every mode.

## Running a case (Windows PowerShell, from the repo folder, with the venv active)

```powershell
# 1. start a run from the command line (or ask Claude in the desktop app: "Use orgfit to start a run of T1")
#    --mode paste writes the prompts and a PASTE_PLAN.md for claude.ai, then pauses
python -m engine.orchestrator run --case cases\T1_coherent_misfit --mode paste --analyst "Your Name"

# 2. CP1: open runs\T1_coherent_misfit\<run_id>\cp1_review.csv in Excel.
#    Set analyst_decision per row: accepted / rejected / edited (edited: fill analyst_level or analyst_class).
#    Shortcut for verified rows with no flags (flagged rows still need your individual decision):
python -m engine.orchestrator accept-verified --run runs\T1_coherent_misfit\<run_id> --analyst "Your Name"

# 3. continue; it pauses at CP2 and CP3 the same way (edit the .yaml file, then resume)
python -m engine.orchestrator resume --run runs\T1_coherent_misfit\<run_id> --analyst "Your Name"

# status at any time
python -m engine.orchestrator status --run runs\T1_coherent_misfit\<run_id>
```

**Live stress demo (a), deleting sources:** `run --case ... --exclude S02,S03,S05`. Remaining chunks come from the cache, so this costs nothing and works offline.
**Live stress demo (b), injecting a contradiction:** add the new file and its register row, then `run` again. Only the prompt holding the new source needs a claude.ai round. Keep a saved reply as backup.
**Replay mode** (`--mode replay`) never calls the API. With a warm cache, it reproduces a previous run exactly.

## Desktop mode: the default (D-31)
The Claude desktop app fetches and answers the tasks itself through the local connector. Setup and usage: `docs/claude_desktop_setup.md`. In desktop mode the files below are written in the same way; the connector serves them to Claude and writes the replies.

## Paste mode: the fallback (no API credit, D-29, D-30)
1. `run` (or `resume`) writes **all** prompts of the current stage to `runs\<case>\<run_id>\paste\`, plus `PASTE_PLAN.md`, which assigns them to M1–M7.
2. For each prompt: open a **new** claude.ai chat, attach the `.prompt.md` file (or paste its text), and send.
3. Save Claude's reply as the `.reply.json` name given in the plan, in the same folder. Code fences around the JSON are fine.
4. When every reply of the stage is saved, run `resume`. The tool validates each reply against the schema; then the verifier checks every quote against the source text.
5. If a reply is cut off, ask Claude in the same chat to "continue the JSON exactly where you stopped", join the two parts, and save.

Stages that need prompts: EXTRACT (several), CLASSIFY (1–2), RECOMMEND (1), REPORT (1). Every paste reply is saved in `cache\`, so reruns and **replay mode** need no claude.ai at all.
