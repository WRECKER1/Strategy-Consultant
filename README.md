# Digital Transformation Organization-Fit Tool

DWO group project, IIM Lucknow PGP 2026-28.

This is an agentic diagnostic tool. It asks whether an organization's structure, culture and learning systems support its stated digital transformation (midterm report §1.1).

**Design rule: theory is the brain, AI is the engine.**
- Language models extract, classify and draft.
- Deterministic code applies the scores, confidence grades, context modifiers and misfit rules M1–M5. It reads them from editable files in `config/`.
- An analyst approves evidence (checkpoint CP1), confirms borderline context calls (CP2) and chooses among options (CP3).

## Status

| Phase | Content | Status |
|---|---|---|
| 0 | Spec digest, change proposals, build choice | done: `docs/phase0_spec_digest.md` |
| 1 | Config files (codebook, evidence rules, modifiers, rules, options, source checklist) | done |
| 2 | Agent prompts, schemas, LLM gateway (api / paste / replay), verifier, intake, orchestrator, checkpoints CP1–CP3, run log | **done, awaiting review**: see `agents/README.md` |
| 3 | Scoring/diagnosis engine, report, Show Evidence, cross-case dashboard | not started (`engine/expr.py` exists) |
| 4 | Test harness: T1–T5, reliability, sensitivity, AI vs manual | not started |
| 5 | Demo package | not started |
| 6 | AI Use Log and requirement map | not started |

Every design decision is in `docs/decision_log.md`.

## Repository layout

```
config/        THE THEORY. Edit these files, never the code, to change rules.
  codebook.yaml          constructs, indicators, 1–5 anchors (MT §3, App. A)
  evidence_rules.yaml    evidence classes, R1–R7, confidence ladder, verification (MT §5)
  modifiers.yaml         context profile fields and modifiers (MT §4.2)
  rules.yaml             thresholds, M1–M5, FIT, GAP, compound tensions (MT §6.1)
  options.yaml           options library A–G (MT §6.3)
  source_checklist.yaml  source-pack checklist (MT §2)
  register_schema.yaml   evidence register and run-log fields (App. B)
agents/        LLM agent prompts, output schemas, gateway (api / paste / replay)
engine/        deterministic code: intake, verifier, orchestrator, checkpoints (no AI inside)
cases/         one folder per case; T1 synthetic pack included
tests/         automated tests (python -m pytest)
docs/          spec digest, decision log, later the demo script and AI Use Log
```

## Setup on Windows 11 (no coding experience needed)

1. Install Python 3.12 from https://www.python.org/downloads/. On the first installer screen, **tick "Add python.exe to PATH"**.
2. Install Git from https://git-scm.com/download/win and accept the defaults.
3. Open **PowerShell** from the Start menu and run these commands one at a time:
   ```powershell
   git clone https://github.com/WRECKER1/Strategy-Consultant.git
   cd Strategy-Consultant
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python -m engine.config_check
   ```
   If PowerShell refuses to run `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, answer `Y`, and try again.
4. You should see `CONFIG CHECK PASSED` and a fingerprint. That fingerprint identifies the theory version: it must stay the same across every case we run.

To run a case from the command line, see `agents/README.md`. The Streamlit app (`streamlit run app/app.py`) arrives in Phase 3.

### API key (for api mode)
Create a key in the Anthropic Console and set a spend limit there. Then, in PowerShell:
```powershell
setx ANTHROPIC_API_KEY "paste-key-here"
```
Close PowerShell and open it again. Never commit the key. Without a key, use `--mode paste`.

## Ethics

- The tool uses only public or institutionally licensed sources.
- No scraping against site terms, no paywall bypass, no personal data on individual employees, no primary data.
- Instructions found inside source documents are treated as data (MT §5.3).
- Real-company source files are **not committed** to this public repository.
