# Decision Log

All design decisions made since the midterm. You asked me to "go with your intuition and document it" (26 Nov 2026), so every Spec Change Proposal in `docs/phase0_spec_digest.md` was **accepted with the proposed default**. Each is recorded below as a decision (D-xx) with the config location that implements it.

**Reversing a decision.** Edit the config file named below, add a dated line under "Change history", and rerun `python -m engine.config_check`. A change gives a new core-config fingerprint. That is expected **between** releases. It must not happen **between cases** in one validation round (generalisability test, MT §7.3).

## Decisions

| ID | Decision | Midterm reference | Implemented in |
|---|---|---|---|
| D-01 | DA1–DA3, CA1 and DI1 are exempt from the claim ceiling, because they measure stated intent or classify announced work. All other indicators keep the ceiling at 3. | MT §5.2 R2 vs §6.1 M1/M4; T1 | `codebook.yaml` `claim_ceiling_exempt` |
| D-02 | Anchored indicators: each evidence row carries an anchor level. The LLM proposes it, the analyst confirms it at CP1, and the engine takes the median of rows from the highest-precedence class present. SO3, SO4 and CA3 are computed from counts using bands. | MT §3.1, §4.3 | `codebook.yaml` `scoring_method`, `bands` |
| D-03 | Confidence ladder: High = ≥2 independent sources, ≥1 F/T, no contradiction. Medium = ≥2 independent sources, or 1 F/T source. Low = one C or E source. Then recency (−1 grade) and contradiction (cap Medium). **Strict independence**: different publishers, and all company documents count as one publisher. A contradiction is two accepted rows ≥2 levels apart. | MT §5.2 R1, R3, R6 | `evidence_rules.yaml` `confidence`, `R1`, `R6` |
| D-04 | A construct is scored only if at least half its scored indicators are rated (SO 2/4, DI 1/2, CA 2/3, EC 2/3, DA 2/3). Construct confidence = lowest indicator grade, capped at Medium if any indicator is Insufficient. | MT §3.1; T3 | `codebook.yaml` `min_rated_indicators`; `evidence_rules.yaml` `confidence.construct` |
| D-05 | DI = mean(DI2, DI3) and CA = mean(CA2, CA3, CA4). DI1 and CA1 are kept apart and used only in M2 and M3. A strong CA1 claim means level ≥ 4. CA1 anchors are new (Appendix A has none). | MT Table 4, Table 7 | `codebook.yaml` |
| D-06 | High regulatory intensity lowers the **construct-level** SO threshold used by M1 and M5 by 0.5. If 2.0 < SO ≤ 2.5 and DA ≥ 4, the result is a "Regulated-design constraint" flag instead of M1, and the unadjusted result is shown next to it. | MT Table 5 vs Table 9 T4 | `modifiers.yaml` `regulatory_intensity` |
| D-07 | Threshold modifiers are additive. Uncertainty adds +0.5 at High-moderate and +1.0 at High. Both apply to the SO threshold of M1 and M5, not to FIT. | MT Table 5 | `modifiers.yaml` `combination`, `environmental_uncertainty` |
| D-08 | EC1 is scored from two structured fields, `unit_exists` and `integration_link`. A score of 1 needs explicit evidence of absence. M5 = unit exists, link not confirmed, and SO ≤ threshold. | MT Table 7 M5, App. A, T5 | `codebook.yaml` `EC1`; `rules.yaml` `M5` |
| D-09 | New outcome **GAP**: DA − mean(SO, CA, EC) > 0.5 and no misfit rule fires. It is reported as "unexplained gap; investigate" and has no options. | MT Table 7 (gap in spec) | `rules.yaml` `outcomes.GAP` |
| D-10 | DA is split into DA1 targets, DA2 investment and DA3 centrality. The anchors reuse the Appendix A wording. | App. A | `codebook.yaml` |
| D-11 | DI1 = the category with the most accepted rows. A tie is resolved by the analyst at CP2. | MT Table 4 | engine (Phase 3), `codebook.yaml` `DI1` |
| D-12 | Size, with no reweighting. Small firms: an EC1 of Insufficient or 1 is excluded from the EC mean. Large firms: when M4 fires, option F is listed before G. | MT Table 5 vs §3.1 | `modifiers.yaml` `size` |
| D-13 | Life-cycle stage: at the Formalization stage, SO3 ≤ 2 is annotated "expected for stage" and no number changes. The stage is always confirmed by the analyst at CP2. | MT Table 5, Table 11 | `modifiers.yaml` `life_cycle_stage` |
| D-14 | Ownership: for State-owned firms and MNC subsidiaries, SO2 needs a row tagged `level_scope: parent`. Without one it is shown as "Pending", which counts as Insufficient. The analyst can override at CP2, and the override is logged. | MT Table 5 | `modifiers.yaml` `ownership` |
| D-15 | Transformation stage Announced: if CA2 ≤ 2 it is shown as "too early to judge", excluded from the CA mean, and M3 uses CA3 alone. The stage is derived from the announcement date. | MT Table 5 | `modifiers.yaml` `transformation_stage` |
| D-16 | Each case has a fixed `as_of_date`. E rows older than 24 months or with n < 30 are kept in the register but excluded from scoring. Recency downgrade applies when the newest supporting row is older than 36 months. SO3 needs ≥15 postings. | MT §5.2 R3, R4; Table 4 | `evidence_rules.yaml` `R3`, `R4`; `codebook.yaml` `SO3` |
| D-17 | A rule fired on any Low-confidence input is labelled **HYPOTHESIS**. It is a **FINDING** only if every input is Medium or High. Below Low, the output is "Cannot assess – evidence gap". | MT §6.1, Table 11 | `evidence_rules.yaml` `rule_firing` |
| D-18 | Score bands: Low ≤ 2.5; Moderate > 2.5 and < 4; High ≥ 4. Displayed to 1 decimal place; comparisons use unrounded values. | MT §6.2 | `codebook.yaml` `score_bands` |
| D-19 | Three compound-tension pairs added beyond the midterm's M1+M3 (M1+M2, M4+M5, M1+M4). Each is marked `source: proposed` and shown with that label. **The group should confirm or delete them.** | MT §6.1 | `rules.yaml` `compound_tensions` |
| D-20 | Anchors 2 and 4, which Appendix A leaves as "intermediate", were written out so coders agree more often. Each one is marked `added: true`. | App. A | `codebook.yaml` |
| D-21 | Build option C (hybrid): a Python deterministic engine with YAML config; a Streamlit UI with checkpoints CP1–CP3; agents run in API mode or paste-in mode; replay mode for the demo; an Excel scorecard mirror with live formulas. | MT §4.3 | whole repo |
| D-22 | Model: the agents use Claude Opus 5.5 (`claude-opus-5-5`) by default. This is set in `config/runtime.yaml`, which is **not** part of the core fingerprint, so changing the model does not break the generalisability test. | n/a | `config/runtime.yaml` (Phase 2) |

| D-23 | Pipeline order: extraction → quote verification → classification (verified rows only, to save cost) → full verification → CP1 → CP2 → scoring. CP2 comes **before** scoring, because its answers (modifiers, contradiction resolution, DI1 tie, ownership) are scoring inputs. | MT §4.3, Table 11 | `engine/orchestrator.py` |
| D-24 | The intake agent and the verifier are rule-based code, not LLM agents. Both are checks with right answers, so code is more reliable and fully auditable. | MT §4.3 steps 1, 3 | `engine/intake.py`, `engine/verify.py` |
| D-25 | Only flagged rows are excluded from bulk acceptance at CP1. The bulk action is logged with the analyst's name, so the demo can show both the quick path and individual review. | MT Table 11 row 1 | `engine/checkpoints.py` |
| D-26 | A source passage that looks like an instruction to the tool is flagged by a code pattern check **and** by the extraction agent's own report. Every row from that chunk carries `embedded_instruction` and needs individual review. | MT §5.3 | `engine/verify.py`, `agents/prompts/extraction.md` |
| D-27 | Agent responses are cached by a hash of (model, prompt, input, schema). Reruns with unchanged inputs are free and identical. Replay mode is the demo fallback. | demo reliability | `agents/llm.py` |

## Assumptions

| ID | Assumption | Why | How to change |
|---|---|---|---|
| A-01 | No separate guidelines PDF exists. Per your 26 Nov message, the midterm draft is the guidelines. Requirement references (Section 5 components 1–6, Section 10 A–G) will be mapped in Phase 6 to the midterm's acceptance criteria (MT §1.3) and to the requirement labels the QC guide cites. If the brief text becomes available, paste Sections 5, 10 and 11 into `docs/brief_excerpt.md` and I will redo the map. | Requirement text not available | — |
| A-02 | Demo date is not fixed ("sometime in December"). The plan assumes the earliest likely date, 7 Dec 2026: feature freeze 2 Dec, full rehearsal 4–5 Dec. | Safer to plan early | Tell me the date |
| A-03 | Maximum excerpt length is 60 words (R7 says "short"). | Copyright discipline | `evidence_rules.yaml` |
| A-04 | Quote verification accepts a near-exact match at ≥ 0.92 normalized similarity. Anything below is rejected and logged. | PDF text extraction alters hyphens, quotes and line breaks | `evidence_rules.yaml` `verification` |
| A-05 | Demo laptop runs Windows 11 with Python 3.12 from python.org. | Your 26 Nov message | README |
| A-06 | The GitHub repo `WRECKER1/Strategy-Consultant` is **public**. The midterm text, course case texts and copyrighted source documents are therefore **not committed**; real-firm source files stay local (`cases/*/sources/` is git-ignored except for SYNTHETIC packs). Consider making the repo private until grading is done. | Copyright and academic integrity | `.gitignore` |

## API credit estimate (D-22)

This is an estimate, not a measurement. The run log will record actual tokens and cost from each API response (`usage` field), so you will see real spend after the first run.

Prices used (Claude API list prices, per million tokens): Opus 5.5 $4 input / $20 output; Sonnet 5.5 $2 / $10. Batch API is 50% cheaper. Cached system-prompt reads are about $0.20 per million.

| Run | Token assumption | Opus 5.5 cost |
|---|---|---|
| One real firm, full pipeline | About 350k tokens of source text (2 annual reports' relevant sections, 4 calls, deck, 30 postings, news, review aggregate), read in about 45 chunks; about 90k output tokens for extraction incl. thinking; classification, recommendation and report about 110k in and 40k out | about $4–5 |
| Course case | about 20–30k tokens | about $0.50 |
| One synthetic pack (T1–T5) | about 5–10k tokens | about $0.20–0.30 |

| Budget line | Runs | Estimate |
|---|---|---|
| Real firms (2 firms × about 4 runs: development, prompt fixes, final, AI-vs-manual) | 8 | $40 |
| Course case | 4 | $2 |
| T1–T5 regression runs | about 30 | $9 |
| Prompt development on small samples | — | $10 |
| Rehearsals and live stress demo (one short extraction each) | about 10 | $3 |
| **Total** | | **about $65** |

**Recommendation:** buy **$50** of API credit now and set a spend limit in the Anthropic Console. Top up $25 only if the run-log meter shows you need it. To halve the cost, either:
- switch extraction to Sonnet 5.5 (one line in `config/runtime.yaml`), or
- run the final extraction passes through the Batch API.

If you buy no credit at all, the tool still runs completely in **paste-in mode**: you run each agent prompt in Claude Pro and upload the returned JSON.

## Defects found and fixed during the build
| Date | Defect | Found by | Fix |
|---|---|---|---|
| 2026-11-26 | YAML 1.1 read the unquoted EC1 values `yes` / `no` as true / false, so every EC1 row failed schema validation. | Phase 2 pipeline test | Values quoted in `codebook.yaml`. The core fingerprint changed (pre-release). |
| 2026-11-26 | A word hyphenated across a line break in the source (`sign-\noff`) did not match the excerpt `sign-off`. | Verifier unit test | Hyphens are ignored when matching. |
| 2026-11-26 | Identical boilerplate in different job postings was flagged as duplicate SO3 evidence. | Pipeline test | For SO3, the duplicate key includes the posting label. |

## Change history
- 2026-11-26: D-01 to D-22 and A-01 to A-06 recorded. Phase 1 config v1.0.0.
- 2026-11-26: Phase 2. D-23 to D-27 added, three defects fixed, `config/runtime.yaml` added (outside the fingerprint).
