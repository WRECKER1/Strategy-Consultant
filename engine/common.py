"""Shared helpers: config loading, paths, dates, run log (register_schema.yaml → run_log_event)."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
CASES_DIR = ROOT / "cases"
RUNS_DIR = ROOT / "runs"
PROMPTS_DIR = ROOT / "agents" / "prompts"


def load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_config() -> dict:
    names = ["codebook", "evidence_rules", "modifiers", "rules", "options", "source_checklist", "register_schema", "prefilter"]
    return {n: load_yaml(CONFIG_DIR / f"{n}.yaml") for n in names}


def load_runtime() -> dict:
    return load_yaml(CONFIG_DIR / "runtime.yaml")


def to_date(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            d = datetime.strptime(s, fmt).date()
            return d
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date: {v!r} (use YYYY-MM-DD)")


def months_between(earlier: date, later: date) -> float:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month) + (later.day - earlier.day) / 30.0


def sha(obj: Any) -> str:
    data = obj if isinstance(obj, (bytes, str)) else json.dumps(obj, sort_keys=True, default=str)
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class RunLog:
    """Append-only JSON Lines log. One event per line (register_schema.yaml)."""

    def __init__(self, path: Path, run_id: str, case_id: str):
        self.path, self.run_id, self.case_id = path, run_id, case_id
        path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, stage: str, actor: str, action: str, detail: Any = None, inputs: Any = None,
              outputs: Any = None, model: str | None = None, usage: dict | None = None) -> None:
        usage = usage or {}
        rec = {
            "timestamp": now_iso(), "run_id": self.run_id, "case_id": self.case_id,
            "stage": stage, "actor": actor, "action": action,
            "inputs_hash": sha(inputs)[:16] if inputs is not None else None,
            "outputs_hash": sha(outputs)[:16] if outputs is not None else None,
            "detail": detail, "model": model,
            "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
            "cost_usd": usage.get("cost_usd"),
        }
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    def events(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def total_cost(self) -> float:
        return round(sum(e.get("cost_usd") or 0 for e in self.events()), 4)
