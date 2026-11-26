"""Orchestrator: runs one case end to end, tracks state, pauses at human
checkpoints and writes the run log.

    INTAKE → EXTRACT → VERIFY_QUOTES → CLASSIFY → VERIFY_FULL → [CP1]
           → [CP2] → SCORE → DIAGNOSE → RECOMMEND → [CP3] → REPORT → DONE

Usage (from the repository root):
    python -m engine.orchestrator run    --case cases/T1_coherent_misfit [--mode api|paste|replay] [--exclude S03,S04]
    python -m engine.orchestrator resume --run runs/<case>/<run_id> --analyst "Name"
    python -m engine.orchestrator accept-verified --run runs/<case>/<run_id> --analyst "Name"
    python -m engine.orchestrator status --run runs/<case>/<run_id>

Every stage is idempotent: resuming after an error re-enters the failed stage.
Agent calls are cached, so a resumed or repeated run makes no repeat API calls
for inputs that have not changed. For the live stress demo, --exclude drops
sources; only a newly injected source costs a new extraction call.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from agents import agents
from agents.llm import AgentOutputInvalid, BudgetExceeded, Gateway, PasteRequired, ReplayMiss
from engine import checkpoints as cp
from engine import verify
from engine.common import ROOT, RUNS_DIR, RunLog, load_config, load_runtime, read_json, write_json
from engine.config_check import check as config_check, fingerprint
from engine.intake import load_case, run_intake
from engine.sources import batch_chunks, chunk_pages, load_source, prefilter_pages

STAGES = ["INTAKE", "EXTRACT", "VERIFY_QUOTES", "CLASSIFY", "VERIFY_FULL", "CP1", "CP2",
          "SCORE", "DIAGNOSE", "RECOMMEND", "CP3", "REPORT", "DONE"]


class Paused(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status, self.message = status, message


class Run:
    def __init__(self, run_dir: Path):
        self.dir = run_dir
        self.state = read_json(run_dir / "state.json")
        self.cfg = load_config()
        self.runtime = self.state["runtime"]
        self.case_dir = ROOT / self.state["case_dir"]
        self.case, register = load_case(self.case_dir)
        excl = set(self.state.get("excluded_sources", []))
        self.register = {k: v for k, v in register.items() if k not in excl}
        self.log = RunLog(run_dir / "run_log.jsonl", self.state["run_id"], self.state["case_id"])
        self.gw = Gateway(self.runtime, self.state["case_id"], run_dir, self.log)

    # ------------------------------------------------------------ helpers
    def save(self):
        write_json(self.dir / "state.json", self.state)

    def advance(self, to: str):
        self.state["history"].append({"stage": self.state["stage"], "completed": datetime.now().isoformat(timespec="seconds")})
        self.state["stage"] = to
        self.state["status"] = "running"
        self.save()

    @property
    def rows(self) -> list[dict]:
        p = self.dir / "evidence_register.json"
        return read_json(p) if p.exists() else []

    def save_rows(self, rows: list[dict]):
        write_json(self.dir / "evidence_register.json", rows)

    def docs(self) -> dict:
        return {sid: load_source(sid, self.case_dir / "sources" / s["file"]) for sid, s in self.register.items()}

    # ------------------------------------------------------------- stages
    def INTAKE(self):
        fp = fingerprint()
        if fp != self.state["config_fingerprint"]:
            raise RuntimeError("Core config changed since this run started; start a new run.")
        errs = config_check(self.cfg)
        if errs:
            raise RuntimeError(f"Config check failed: {errs}")
        report = run_intake(self.case_dir, self.case, self.register, self.cfg)
        write_json(self.dir / "intake_report.json", report)
        self.log.event("intake", "intake_agent", "validated", detail={k: report[k] for k in ("ok", "errors", "warnings", "derived")}
                       | {"gaps": [g["source_type"] for g in report["checklist_gaps"]]})
        if not report["ok"]:
            raise Paused("intake_failed", "Intake errors (fix case files, then resume):\n  - " + "\n  - ".join(report["errors"]))
        self.advance("EXTRACT")

    def _mode_value(self, key: str):
        v = self.runtime[key]
        return v[self.runtime["agent_mode"] if self.runtime["agent_mode"] in v else "api"] if isinstance(v, dict) else v

    def _pause_for_paste(self, stage: str, pending: list[PasteRequired]):
        """Paste mode: all prompts of a stage are written at once so several members can work in parallel."""
        plan = self.dir / "paste" / "PASTE_PLAN.md"
        lines = [f"# Paste plan: {stage} ({len(pending)} prompts)", "",
                 "For each prompt: open a NEW chat in claude.ai, attach or paste the .prompt.md file, and save Claude's",
                 "JSON reply in this folder under the reply name shown. When all replies are saved, run `resume`.",
                 "Prompts are independent, so members can do them in parallel. Suggested split:", "",
                 "| # | Prompt file | Save reply as | Member | Done |", "|---|---|---|---|---|"]
        members = [f"M{i}" for i in range(1, 8)]
        for i, p in enumerate(pending):
            done = "yes" if p.reply_path.exists() else ""
            lines.append(f"| {i + 1} | {p.prompt_path.name} | {p.reply_path.name} | {members[i % 7]} | {done} |")
        plan.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.log.event(stage, "orchestrator", "paste_prompts_written", detail={"n": len(pending), "plan": str(plan)})
        raise Paused("awaiting_paste", f"PASTE MODE: {len(pending)} prompt(s) for {stage} are waiting. "
                     f"See {plan}. Save every reply, then resume.")

    def EXTRACT(self):
        pf = self.cfg["prefilter"]
        all_chunks, filt = [], []
        for sid, doc in self.docs().items():
            kept, skipped = prefilter_pages(doc, pf)
            chunks = chunk_pages(doc, kept, self.runtime["chunk_words"])
            all_chunks.extend(chunks)
            filt.append({"source_id": sid, "pages": len(doc.pages), "kept": len(kept), "skipped_pages": skipped,
                         "words": doc.word_count, "chunks": len(chunks)})
        write_json(self.dir / "prefilter_report.json", filt)
        self.log.event("extraction", "orchestrator", "prefiltered_and_chunked", detail=filt)
        batches = batch_chunks(all_chunks, self._mode_value("extraction_batch_words"))
        rows: list[dict] = []
        injections, pending = [], []
        for bi, batch in enumerate(batches):
            try:
                new, meta = agents.extract_batch(self.gw, self.cfg, f"b{bi:03d}", batch, self.register)
            except PasteRequired as p:
                pending.append(p)
                continue
            hits = [h for ch in batch for h in verify.detect_injection(ch.text)]
            if hits or meta["embedded_instruction_detected"]:
                injections.append({"batch": bi, "sources": sorted({c.source_id for c in batch}), "patterns": hits,
                                   "agent_report": meta["embedded_instruction_text"]})
                for r in new:
                    r["flags"] = ["embedded_instruction"]
            rows.extend(new)
        if pending:
            self._pause_for_paste("EXTRACT", pending)
        for i, r in enumerate(rows, start=1):
            r["evidence_id"] = f"E{i:03d}"
            r["source_date"] = self.register[r["source_id"]].get("date")
            r["analyst_decision"] = "pending"
        if injections:
            self.log.event("extraction", "verifier", "embedded_instructions_detected", detail=injections)
        write_json(self.dir / "embedded_instructions.json", injections)
        self.save_rows(rows)
        self.log.event("extraction", "extraction_agent", "rows_proposed", detail={"n_rows": len(rows)}, outputs=rows)
        self.advance("VERIFY_QUOTES")

    def VERIFY_QUOTES(self):
        rows = verify.verify_rows(self.rows, self.docs(), self.register, self.case, self.cfg)
        self.save_rows(rows)
        rej = [r for r in rows if r["analyst_decision"] == "auto_rejected"]
        self.log.event("verification", "verifier", "quotes_checked",
                       detail={"checked": len(rows), "rejected": len(rej),
                               "rejections": [{"evidence_id": r["evidence_id"], "reason": r["reject_reason"]} for r in rej]})
        self.advance("CLASSIFY")

    def CLASSIFY(self):
        rows = self.rows
        todo = [r for r in rows if r["analyst_decision"] != "auto_rejected"]
        pending = agents.classify_rows(self.gw, todo, self.register, self._mode_value("classification_batch_rows"))
        if pending:
            self._pause_for_paste("CLASSIFY", pending)
        self.save_rows(rows)
        self.advance("VERIFY_FULL")

    def VERIFY_FULL(self):
        rows = verify.verify_rows(self.rows, self.docs(), self.register, self.case, self.cfg)
        for r in rows:
            if r["analyst_decision"] != "auto_rejected":
                r["analyst_decision"] = "pending"
        self.save_rows(rows)
        cp.write_cp1(self.dir / "cp1_review.csv", rows)
        self.log.event("verification", "verifier", "full_check", detail={
            "verified": sum(r["analyst_decision"] == "pending" for r in rows),
            "rejected": sum(r["analyst_decision"] == "auto_rejected" for r in rows),
            "flagged": {f: sum(f in r["flags"] for r in rows) for f in
                        ("contradiction", "duplicate", "stale_36m", "e_older_24m", "e_sample_below_30", "embedded_instruction", "unclassified")}})
        self.advance("CP1")
        raise Paused("awaiting_CP1", f"CP1: review evidence in {self.dir / 'cp1_review.csv'}: set analyst_decision to "
                     "accepted / rejected / edited for every pending row, then resume with --analyst NAME.")

    def CP1(self):
        analyst = self.state.get("analyst")
        if not analyst:
            raise Paused("awaiting_CP1", "Resume with --analyst NAME so CP1 decisions are attributed.")
        rows, problems = cp.read_cp1(self.dir / "cp1_review.csv", self.rows, analyst)
        pending = [r["evidence_id"] for r in rows if r.get("analyst_decision") == "pending"]
        if pending:
            problems.append(f"{len(pending)} rows still pending: {pending[:10]}{' …' if len(pending) > 10 else ''}")
        if problems:
            raise Paused("awaiting_CP1", "CP1 incomplete:\n  - " + "\n  - ".join(problems))
        self.save_rows(rows)
        for r in rows:
            if r["analyst_decision"] in ("accepted", "rejected", "edited"):
                self.log.event("CP1", "analyst", f"row_{r['analyst_decision']}", detail={
                    "evidence_id": r["evidence_id"], "by": analyst, "level": cp.final_level(r),
                    "class": cp.final_class(r), "note": r.get("analyst_note")})
        cp2 = cp.build_cp2(read_json(self.dir / "intake_report.json"), rows, self.cfg)
        cp.write_yaml(self.dir / "cp2_review.yaml", cp2)
        self.advance("CP2")
        if cp2["items"]:
            raise Paused("awaiting_CP2", f"CP2: answer the {len(cp2['items'])} judgement calls in {self.dir / 'cp2_review.yaml'}, then resume.")

    def CP2(self):
        path = self.dir / "cp2_review.yaml"
        data = cp.yaml.safe_load(path.read_text(encoding="utf-8"))
        if data["items"]:
            data, problems = cp.read_cp2(path)
            if problems:
                raise Paused("awaiting_CP2", "CP2 incomplete:\n  - " + "\n  - ".join(problems))
            for it in data["items"]:
                self.log.event("CP2", "analyst", "judgement", detail={"id": it["id"], "answer": it["answer"],
                               "reason": it.get("reason"), "by": data["analyst"]})
        write_json(self.dir / "cp2_decisions.json", data)
        self.advance("SCORE")

    def _phase3(self, module: str, func: str):
        try:
            mod = __import__(f"engine.{module}", fromlist=[func])
            return getattr(mod, func)
        except (ImportError, AttributeError):
            raise Paused("awaiting_phase3", f"Stage needs engine/{module}.py:{func}(), built in Phase 3. "
                         "Everything up to here is complete and saved.")

    def SCORE(self):
        score = self._phase3("scoring", "score_case")
        result = score(self.rows, read_json(self.dir / "intake_report.json"), read_json(self.dir / "cp2_decisions.json"),
                       self.case, self.cfg)
        write_json(self.dir / "scores.json", result)
        self.log.event("scoring", "scoring_engine", "scored", outputs=result)
        self.advance("DIAGNOSE")

    def DIAGNOSE(self):
        diagnose = self._phase3("diagnosis", "diagnose")
        result = diagnose(read_json(self.dir / "scores.json"), self.cfg)
        write_json(self.dir / "diagnosis.json", result)
        self.log.event("diagnosis", "diagnosis_engine", "diagnosed", outputs=result)
        self.advance("RECOMMEND")

    def RECOMMEND(self):
        dx = read_json(self.dir / "diagnosis.json")
        accepted = [dict(r, evidence_class=cp.final_class(r)) for r in self.rows if r["analyst_decision"] in ("accepted", "edited")]
        if dx["fired"]:
            rec = agents.tailor_options(self.gw, self.cfg, dx["fired"], accepted, dx.get("compound_tensions", []), self.case)
        else:
            rec = {"options": [], "analyst_suggested": [], "missing_tailoring": []}
        write_json(self.dir / "recommendations.json", rec)
        cp.write_yaml(self.dir / "cp3_selection.yaml", cp.build_cp3(rec))
        self.advance("CP3")
        if rec["options"]:
            raise Paused("awaiting_CP3", f"CP3: choose options in {self.dir / 'cp3_selection.yaml'}, then resume.")

    def CP3(self):
        path = self.dir / "cp3_selection.yaml"
        data = cp.yaml.safe_load(path.read_text(encoding="utf-8"))
        if data["items"]:
            data, problems = cp.read_cp3(path)
            if problems:
                raise Paused("awaiting_CP3", "CP3 incomplete:\n  - " + "\n  - ".join(problems))
            for it in data["items"]:
                self.log.event("CP3", "analyst", "options_chosen", detail={"rule_id": it["rule_id"], "chosen": it["chosen"],
                               "rationale": it["rationale"], "by": data["analyst"]})
        write_json(self.dir / "cp3_decisions.json", data)
        self.advance("REPORT")

    def REPORT(self):
        build = self._phase3("report", "build_report")
        build(self)
        self.advance("DONE")

    # -------------------------------------------------------------- driver
    def drive(self) -> str:
        try:
            while self.state["stage"] != "DONE":
                getattr(self, self.state["stage"])()
            self.state["status"] = "done"
            self.save()
            msg = f"Run complete: {self.dir}"
        except Paused as p:
            self.state["status"] = p.status
            self.save()
            self.log.event(self.state["stage"], "orchestrator", "paused", detail=p.status)
            msg = p.message
        except PasteRequired as p:          # single-prompt stages (recommendation, report)
            self.state["status"] = "awaiting_paste"
            self.save()
            msg = (f"PASTE MODE: open {p.prompt_path} in a new claude.ai chat (attach or paste it), save the JSON reply as "
                   f"{p.reply_path}, then resume.")
        except (ReplayMiss, BudgetExceeded, AgentOutputInvalid) as e:
            self.state["status"] = "error"
            self.save()
            self.log.event(self.state["stage"], "orchestrator", "error", detail=str(e))
            msg = f"ERROR at {self.state['stage']}: {e}"
        cost = self.log.total_cost()
        return f"[{self.state['case_id']} | {self.state['run_id']} | stage {self.state['stage']} | {self.state['status']} | API cost so far ${cost:.4f}]\n{msg}"


def new_run(case_dir: Path, mode: str | None, exclude: list[str]) -> Run:
    runtime = load_runtime()
    if mode:
        runtime["agent_mode"] = mode
    case_id = case_dir.name
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + (f"-minus-{'-'.join(exclude)}" if exclude else "")
    run_dir = RUNS_DIR / case_id / run_id
    run_dir.mkdir(parents=True)
    shutil.copy(ROOT / "config" / "runtime.yaml", run_dir / "runtime_snapshot.yaml")
    write_json(run_dir / "state.json", {
        "run_id": run_id, "case_id": case_id, "case_dir": str(case_dir.resolve().relative_to(ROOT)),
        "stage": "INTAKE", "status": "new", "history": [], "config_fingerprint": fingerprint(),
        "runtime": runtime, "excluded_sources": exclude, "analyst": None})
    run = Run(run_dir)
    run.log.event("start", "orchestrator", "run_created", detail={"mode": runtime["agent_mode"], "model": runtime["model"],
                  "config_fingerprint": fingerprint(), "excluded_sources": exclude})
    return run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine.orchestrator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("run"); a.add_argument("--case", required=True); a.add_argument("--mode", choices=["api", "paste", "desktop", "replay"])
    a.add_argument("--exclude", default="", help="comma-separated source IDs to leave out (live stress demo)")
    a.add_argument("--analyst", default=None)
    b = sub.add_parser("resume"); b.add_argument("--run", required=True); b.add_argument("--analyst", default=None)
    b.add_argument("--mode", choices=["api", "paste", "desktop", "replay"])
    c = sub.add_parser("accept-verified"); c.add_argument("--run", required=True); c.add_argument("--analyst", required=True)
    d = sub.add_parser("status"); d.add_argument("--run", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "run":
        run = new_run(Path(args.case), args.mode, [s for s in args.exclude.split(",") if s])
        if args.analyst:
            run.state["analyst"] = args.analyst
        print(run.drive())
    elif args.cmd == "resume":
        run = Run(Path(args.run))
        if args.analyst:
            run.state["analyst"] = args.analyst
        if args.mode:
            run.state["runtime"]["agent_mode"] = args.mode
            run.runtime = run.state["runtime"]
            run.gw.runtime = run.runtime
        print(run.drive())
    elif args.cmd == "accept-verified":
        run = Run(Path(args.run))
        if run.state["stage"] != "CP1":
            print(f"Run is at stage {run.state['stage']}, not CP1."); return 1
        rows, _ = cp.read_cp1(run.dir / "cp1_review.csv", run.rows, args.analyst)
        n, left = cp.bulk_accept_verified(rows)
        run.save_rows(rows)
        cp.write_cp1(run.dir / "cp1_review.csv", rows)
        run.log.event("CP1", "analyst", "bulk_accept_unflagged_verified_rows", detail={"by": args.analyst, "accepted": n, "left_for_review": left})
        print(f"Accepted {n} verified, unflagged rows. {left} flagged rows still need an individual decision in cp1_review.csv.")
    elif args.cmd == "status":
        run = Run(Path(args.run))
        print({k: run.state[k] for k in ("case_id", "run_id", "stage", "status", "excluded_sources")}, f"cost ${run.log.total_cost():.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
