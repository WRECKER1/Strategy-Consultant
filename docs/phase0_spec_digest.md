# Phase 0 — Spec Digest, Spec Change Proposals, Build Recommendation

Project: Digital Transformation Organization-Fit Tool (DWO, IIM Lucknow PGP 2026-28)
Status: reviewed 26 Nov 2026 — all proposals accepted with defaults; see docs/decision_log.md (D-01…D-22)
Source of truth: midterm report (`DWO_MidTerm_Submission_First_Draft.docx`), cited below as "MT §x".
Not yet received: the course project guidelines PDF (Sections 5, 10, 11). See Open Question Q1.

---

## 1. Spec digest (as I understand it)

**Core question (MT §1.1).** Do an organization's structure, culture and learning systems support its stated digital transformation? Strategy is taken as given; the tool tests design fit, not strategic merit (MT §9).

**Users (MT §1.2).** Primary: external consultants doing an outside-in diagnostic with public data only. Secondary: CDOs / transformation offices / strategy teams benchmarking themselves or peers.

**Acceptance criteria for a "good diagnosis" (MT §1.3).** (1) traceable to framework + indicator + ≥1 cited source; (2) F / C / T / I visibly separated; (3) names specific fits and misfits; (4) options with trade-offs, not one answer; (5) states confidence, says "insufficient evidence" instead of guessing.

**Manual baseline (MT §2, Table 1).** 7 stages: Scoping (Form A) → Source pack (Source Register S01…) → Evidence coding (Evidence Register, App. B) → Indicator scoring → Construct roll-up (equal weights, modifiers on thresholds) → Diagnosis (M1–M5) → Options + 20% re-code. AI assists stages 2–3 only; stages 4–7 are rules.

**Constructs and indicators (MT §3, Table 4, App. A).**

| Construct | Indicators | Notes |
|---|---|---|
| SO Structural Organicity | SO1 reporting distance, SO2 decision authority, SO3 posting language, SO4 employee-reported friction | 1–5 anchors |
| DI Digital Work Interdependence | DI1 nature of work (pooled / sequential / reciprocal), DI2 coordination mechanisms, DI3 data/tech integration | DI1 classified, not scored |
| CA Culture Adaptiveness | CA1 espoused values, CA2 artifacts, CA3 employee openness, CA4 leadership signals | CA1 recorded as claim, used for gap test |
| EC Exploration Capacity | EC1 separated + linked unit, EC2 new-capability spend/hiring share, EC3 learning infrastructure | |
| DA Digital Ambition | DA1 target specificity, DA2 investment commitment, DA3 centrality in narrative | one shared anchor row |

Scoring: anchored 1–5 (anchors at 1/3/5; 2 and 4 intermediate), construct = simple mean, separate confidence grade High / Medium / Low / Insufficient (MT §3.1).

**Three-layer architecture (MT §4).** L1 universal core (codebook, scoring, M1–M5, options, traceability) never changes. L2 context modifiers shift thresholds or reinterpret, never add/remove constructs. L3 case-specific evidence pipeline: intake → extraction → classification → scoring → diagnosis/output.

**Context modifiers (MT §4.2, Table 5).** Regulatory intensity (High lowers SO2/SO3 misfit threshold by 0.5 → "regulated-design constraint"); Duncan uncertainty (+0.5 required SO per step above low-moderate); Size (large: EC1 structural separation expected; small: contextual ambidexterity accepted); Life-cycle (formalization stage: high SO3 formalization expected, misfit only if DA high); Ownership (SOE / subsidiary: SO2 needs parent or ministry evidence); Transformation stage (announced <1 yr: low CA2 = "too early to judge").

**Evidence protocol (MT §5).** Classes F (full weight), C (cannot alone exceed 3), T (full if credible and dated), E (partial, sample rules), I (never evidence). Rules: R1 triangulation (High needs ≥2 independent sources incl. ≥1 F or T); R2 claim ceiling; R3 recency (>36 months → −1 confidence grade; E limited to last 24 months); R4 employee-review discipline (themes across ≥30 reviews, bias disclosure); R5 absence ≠ evidence (Insufficient, list what is missing); R6 contradictions (show both, precedence F > T > E > C, cap at Medium); R7 short quotes with source ID + page/timestamp. Ethics safeguards per MT §5.3.

**Decision rules (MT §6.1, Table 7).** Fire only if involved constructs have ≥ Low confidence, else "Cannot assess – evidence gap".
- M1 Mechanistic misfit: DA ≥ 4 and SO ≤ 2.5 (adjusted)
- M2 Coordination gap: DI1 = reciprocal and DI2 ≤ 2
- M3 Culture say–do gap: CA1 strong claim and mean(CA2, CA3) ≤ 2.5
- M4 Exploration deficit: DA ≥ 4 and EC ≤ 2.5
- M5 Isolated exploration: EC1 separate unit, no integration evidence, and SO ≤ 2.5
- FIT: DA − mean(SO, CA, EC) ≤ 0.5 and no M-rule fires
- Two or more rules → compound tension, which orders recommendations (e.g. M1+M3: culture first or together).

**Options library (MT §6.3, Table 8).** A–G mapped M1: A, B, C; M2: C, D; M3: E; M4: F, G; M5: F. All options shown with benefit, risk, assumption; the tool never picks one.

**Validation (MT §7).** T1–T5 synthetic packs with expected outputs (Table 9); Part B course case + two real firms (one regulated); Part C 20% inter-coder (≥80% within ±1), AI vs manual (any fabricated citation = fail), generalisability (no L1 edits). Sensitivity ±0.5 on thresholds (MT §9).

**Human judgment (MT §8.2, Table 11).** Mandatory at: accepting AI tags; resolving contradictions; marginal context modifiers; choosing options; presenting Low/Insufficient outputs as hypotheses. Every diagnosis ends with an "additional evidence needed" list.

---

## 2. Spec change proposals (SCP)

Each item says what is wrong or under-specified, why it matters for a deterministic build, and a proposed default. **Nothing below will be implemented until the group decides.** "Blocking" = the rule cannot be coded, or a stress test cannot pass, without a decision.

### Blocking

**SCP-01 Claim ceiling vs Digital Ambition (MT §5.2 R2 vs §6.1 M1/M4, Table 9 T1).**
DA indicators (targets, investment, centrality) are mostly sourced from annual reports, investor days and calls, which are largely company claims (C). Under R2, DA could rarely exceed 3, so M1 and M4 (both need DA ≥ 4) could almost never fire, and T1 (DA 4.5) could not be reproduced.
Proposed: DA measures *stated* intent, so C is the appropriate evidence class for DA1–DA3, exactly as for CA1. Exempt DA1–DA3 and CA1 from the claim ceiling. Audited capex/opex figures or board-approved investment tagged F still raise confidence. Keep the ceiling for all other indicators. Theory check: this is consistent with the MT §9 assumption that the declared strategy is taken as the firm's real intent.

**SCP-02 How row-level evidence becomes an indicator score (MT §3.1, §4.3 step 4).**
The midterm says scores are "computed from tagged evidence" but does not say how several rows combine into one indicator score.
Proposed deterministic rule:
1. Each accepted evidence row carries an **anchor level 1–5** for its indicator. The extraction agent *proposes* it with the anchor text quoted; the analyst confirms or edits at Checkpoint 1. The LLM never sets the final indicator score.
2. Indicator score = median of row anchor levels **from the highest-precedence class present** (F > T > E > C, from R6).
3. If only C rows exist, score = min(median, 3) (R2), except indicators exempted by SCP-01.
4. Count-based indicators are computed by formula, not by judgement: SO3 = share of sampled postings coded "autonomy" vs "procedure"; SO4 and CA3 = theme frequency bands from App. A (>30%, 10–30%, <10%).

**SCP-03 Confidence grades below High are not defined (MT §3.1, §5.2).**
Only High is defined (R1). Proposed indicator-level ladder:
- High: ≥2 independent sources, ≥1 is F or T, no contradiction
- Medium: ≥2 independent sources of any class, **or** one F/T source
- Low: one source, C or E only
- Insufficient: no qualifying row
Then apply R3 (−1 grade if all supporting rows are older than 36 months) and R6 (cap at Medium if a contradiction exists).
"Contradiction" (needed for R6): two accepted rows on the same indicator whose anchor levels differ by ≥2 points.
"Independent" (needed for R1): different source IDs from different publishers; documents from the company itself count as one publisher. **Group decision needed:** the stricter version shown here, or "different source IDs" (looser).

**SCP-04 Construct roll-up when some indicators are Insufficient (MT §3.1).**
Proposed: a construct is scored if at least half of its scored indicators are rated (SO ≥2 of 4, DI ≥1 of 2, CA ≥2 of 3, EC ≥2 of 3, DA ≥2 of 3); otherwise the construct is Insufficient. Construct confidence = lowest confidence among its rated indicators, capped at Medium if any indicator is Insufficient. This is what makes T3 produce "SO, CA, EC Insufficient".

**SCP-05 Which indicators enter the DI and CA means (MT Table 4).**
DI1 is "classified, not scored" and CA1 is "recorded as claim". If CA1 entered the CA mean, a firm's own claims would raise its culture score, which defeats the M3 say–do test.
Proposed: DI = mean(DI2, DI3); CA = mean(CA2, CA3, CA4). DI1 and CA1 are stored separately and used only in M2 and M3. Also define "CA1 strong claim" = CA1 anchor level ≥ 4.

**SCP-06 Regulatory modifier: indicator-level text vs construct-level test (MT Table 5 vs Table 9 T4).**
Table 5 says SO2 and SO3 thresholds are lowered by 0.5 (and calls SO2, which is centralization, a "formalization" indicator). But M1 tests the SO *construct*, and T4's paper trace lowers the *M1 SO threshold* from 2.5 to 2.0.
Proposed (matches T4): High regulation lowers the M1 SO threshold by 0.5. If DA ≥ 4 and SO lies between the adjusted and unadjusted thresholds (2.0 < SO ≤ 2.5), the tool raises a "regulated-design constraint" flag instead of M1, and shows the unadjusted result next to it. Medium and Low regulation: no change. Note: the T4 pack must set uncertainty at Low or Low-moderate, otherwise the uncertainty modifier (+0.5) cancels the regulatory one.

**SCP-07 Several modifiers acting at once (MT Table 5).**
Proposed: adjustments are additive on the M1/M5 SO threshold. Base 2.5; High regulation −0.5; uncertainty High-moderate +0.5, High +1.0. Example: a High-regulation firm in a High-uncertainty sector gets 2.5 − 0.5 + 1.0 = 3.0. Every adjustment is printed in the Show Evidence panel. Also proposed: the uncertainty step applies to M1 and M5 (the rules that test SO), not to FIT.

**SCP-08 M5 condition is not mappable to the EC1 anchors (MT Table 7, App. A).**
The EC1 anchors mix "unit exists" and "linked to core" in one 1–5 scale. Proposed: EC1 rows also carry two structured fields, `unit_exists` (yes / no / unknown) and `integration_link` (yes / no / unknown). M5 fires when unit_exists = yes, integration_link ≠ yes, and SO ≤ adjusted threshold. This also enforces T5: EC1 = 1 only if a row explicitly evidences absence; silence gives Insufficient.

**SCP-09 Gap state between FIT and misfit (MT Table 7).**
If DA − mean(SO, CA, EC) > 0.5 but no M-rule fires (e.g. DA 3.8, SO 3.0, CA 3.0, EC 3.0), the spec gives no output. Proposed label: "UNEXPLAINED GAP: ambition exceeds design by X; no specific misfit pattern; investigate". Not mapped to options.

### Clarifications (needed, but a sensible default exists)

**SCP-10 Separate anchors for DA1, DA2, DA3 (App. A).** One combined row exists. Proposed split using the same wording: DA1 targets (none / some targets / specific dated targets), DA2 investment (none disclosed / stated priority without figure / quantified multi-year commitment), DA3 centrality (passing mention / one of several priorities / central organising theme).

**SCP-11 DI1 categorical aggregation.** Proposed: DI1 = the class with the most accepted rows; a tie is resolved by the analyst at Checkpoint 2. DI1 needs ≥ Low confidence for M2 to fire.

**SCP-12 Size modifier vs equal weights (MT Table 5 vs §3.1).** "Weighted as the expected route" would break equal weights. Proposed, with no reweighting: Small firms: an EC1 of Insufficient or 1 is excluded from the EC mean (contextual ambidexterity accepted). Large firms: no numeric change; when M4 fires the options view lists F before G. Medium: no change.

**SCP-13 Life-cycle modifier is numerically empty.** M1 already requires DA ≥ 4. Proposed: in Formalization stage, a low SO3 is annotated "expected for stage" in the Show Evidence panel; no number changes. Collectivity and Elaboration: no effect (the spec names none). Stage classification is a human checkpoint (MT Table 11).

**SCP-14 Ownership modifier.** Proposed: for State-owned and MNC subsidiary firms, SO2 stays "Pending: parent/ministry evidence required" unless an accepted row is tagged `level: parent`. Insufficient otherwise. The analyst may override at Checkpoint 2, and the override is logged.

**SCP-15 Transformation-stage modifier.** Proposed: if stage = Announced and CA2 ≤ 2, CA2 is shown as "too early to judge", excluded from the CA mean, and M3 uses CA3 alone.

**SCP-16 Recency and review sample.** Proposed: the case has a fixed `as_of_date` (so reruns are reproducible). E rows older than 24 months and E rows with stated n < 30 are kept in the register but excluded from scoring, with the reason shown. SO3 needs ≥15 postings (the lower bound in MT Table 4), otherwise Insufficient. This makes T3 (3 postings) give SO3 Insufficient.

**SCP-17 Rules fired at Low confidence.** MT §6.1 lets a rule fire at Low; MT Table 11 says Low outputs must be shown as hypotheses. Proposed: a rule fired on any Low-confidence input is labelled "HYPOTHESIS". Only Medium or High inputs produce "FINDING".

**SCP-18 Score bands.** MT §6.2 prints "2.0 (Low)" without defining bands. Proposed: Low ≤ 2.5; Moderate > 2.5 and < 4; High ≥ 4. These match the rule cut-offs. Comparisons use unrounded scores; display uses 1 decimal place.

### Things to verify (not changes)
- Burns & Stalker mechanistic/organic, Thompson interdependence and coordination, Schein levels, March exploration/exploitation, Duncan uncertainty, structural vs contextual ambidexterity, life-cycle stages: **verify each against Daft & Uppal, chapter to be filled by each framework owner**. I will cite chapters only where you give them to me.

---

## 3. Build-option comparison

Assumptions, since the prompt's placeholders were not filled: basic Python at most among members; near-zero budget; Claude Pro, Google Workspace and Excel available; about 12 working days to the demo.

| | A. Python app (Streamlit + Claude API + YAML config) | B. Spreadsheet engine + Claude Project as agents | C. Hybrid (recommended) |
|---|---|---|---|
| What runs the rules | Python reading YAML | Sheet formulas | Python reading YAML, **plus** an auto-generated Excel scorecard with live formulas as a mirror evaluators can inspect |
| What runs the agents | API calls with JSON schemas | Humans paste into Claude chat, then copy results back | API calls **or** paste-in mode: the app shows each agent prompt, you run it in Claude Pro, and drop the returned JSON file back into the app. The engine does not care which route produced the file |
| Quote verification in code (principle 4) | Yes | Weak: sheet formulas cannot fuzzy-match against a 200-page PDF | Yes, deterministic string matching, no LLM |
| "Agentic" credibility | High | Low: a human is the orchestrator | High; orchestrator, checkpoints and run log are visible |
| Effort (person-days) | ~12–15 | ~6–8 | ~13–16 (I write the code; you mainly assemble sources and review) |
| Demo reliability | Medium: depends on API and network | High | High: **replay mode** runs from cached agent outputs. The live stress demos mostly need only the engine. Deleting sources needs no LLM call; injecting one contradictory source needs one short extraction call, with a pre-extracted backup file |
| Transparency to evaluators | Code is opaque to non-coders | Very high | High: YAML config is readable, the Excel mirror holds formulas, every score has a Show Evidence panel |
| Cost | API usage (probably a few USD for all cases; to be confirmed in Phase 2) | Zero | Zero in paste-in mode; small in API mode |
| Main risk | Team cannot maintain code | Fails principles 1 and 4 in spirit; does not scale to many cases | More moving parts; mitigated by tests and replay mode |

**Recommendation: C (hybrid).** It is the only option that satisfies all seven of your non-negotiable principles together:
- deterministic rules from config
- quote verification in code
- visible human checkpoints
- generalisability shown by a config checksum that stays unchanged across cases
- a demo that survives an API or Wi-Fi failure

It also keeps the midterm's stated plan (MT §4.3: "spreadsheet scoring model … the spreadsheet, not the AI, holds the decision rules"). The Excel mirror is that spreadsheet. The Python engine is the reference implementation, and a test checks that the two agree.

Planned layout (for orientation only; to be built in Phases 1–4):
```
dwo-orgfit/
  config/      codebook.yaml  evidence_rules.yaml  modifiers.yaml  rules.yaml  options.yaml  source_checklist.yaml
  agents/      prompts + JSON schemas for intake, extraction, classification, recommendation, report
  engine/      verify.py  scoring.py  diagnosis.py  orchestrator.py   (no LLM inside)
  app/         Streamlit UI: case run, 3 checkpoints, Show Evidence, cross-case dashboard
  cases/       T1..T5 (SYNTHETIC), course_case/, firm_regulated/, firm_less_regulated/
  runs/        per-run evidence register, run log (JSONL), report (HTML/DOCX), Excel scorecard
  validation/  reliability export + agreement calc, sensitivity ±0.5, AI-vs-manual template, config checksum
```
Human checkpoints: CP1 accept/reject/edit each evidence row and its anchor level; CP2 confirm borderline modifiers, resolve contradictions and DI1 ties; CP3 choose among options. Verifier = deterministic code: fuzzy match of excerpts against the source text, recency, duplicates, contradiction detection.

---

## 4. Cases: what I need from you

- **Course case:** I do not know your course pack. Send the list of cases taught in DWO (or the one you prefer) and its text, which must be your licensed copy.
- **Real firms:** candidates to consider. I have **not** fetched or checked any facts about them; each is listed only because it is commonly cited for a public transformation programme and has listed-company disclosures. The evidence lead should check source availability before choosing.
  - Regulated (banking): DBS Bank (Singapore) or HDFC Bank / ICICI Bank (India). State Bank of India would also exercise the State-owned ownership modifier.
  - Less regulated: Asian Paints, Tata Steel, or Titan (India); or a global consumer or industrial firm.
  - Diversity suggestion: one Indian PSU or regulated firm plus one private, less-regulated firm. Together they exercise the regulation, ownership and size modifiers.

---

## 5. Open questions (decisions that belong to the group)

1. **Guidelines PDF**: it was not attached. Please upload it (and any midterm feedback from the professor). The Phase 6 requirement map and parts of Phase 5 depend on it.
2. **Build option**: confirm C (hybrid)? And may we use the Claude API (needs a small prepaid API credit, separate from Claude Pro), or should the build default to paste-in mode only?
3. **SCP-01 to SCP-18**: accept all defaults, or mark the ones you want changed. SCP-01, -02, -03 (independence definition), -05 and -06 matter most.
4. **Demo date** (7, 8 or 9 Dec) and the laptop OS that will run the demo.
5. **Where the code should live**: this cloud container is temporary. Should I push to a GitHub repo you create, or package a zip at the end of each phase?
