"""Connector test: an in-process MCP client plays the Claude desktop app.

The client's 'answers' are the scripted TEST DOUBLE rows from
test_phase2_pipeline (hand-written, not model output). The test checks the
protocol: tasks are served, results are schema-checked, submissions are final,
quotes are previewed, the run resumes by itself, and the run stops at CP1 with
no tool for the AI to pass it.
"""
from __future__ import annotations

import json
import re

import anyio
import pytest
from mcp import Client

from agents import llm
from engine import orchestrator
from mcp_server import server
from tests.test_phase2_pipeline import SCRIPT


def _data(r):
    sc = r.structured_content
    if sc is not None:
        return sc.get("result", sc)
    return json.loads(r.content[0].text)


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(orchestrator, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(llm.Gateway, "_cache_path", lambda self, a, k: tmp_path / "cache" / a / f"{k}.json")
    return tmp_path


def test_desktop_flow_to_cp1(isolated):
    async def flow():
        async with Client(server.mcp) as c:
            names = {t.name for t in (await c.list_tools()).tools}
            assert not any(("accept" in n) or ("cp1" in n) or ("choose" in n) for n in names)   # no checkpoint tools

            st = _data(await c.call_tool("start_run", {"case_id": "T1_coherent_misfit"}))
            run_id = st["run_id"]
            assert st["status"] == "awaiting_paste" and st["pending_tasks"]

            first = True
            while True:
                tasks = _data(await c.call_tool("list_pending_tasks", {"run_id": run_id}))
                if not tasks:
                    break
                for t in tasks:
                    text = (await c.call_tool("get_task", {"run_id": run_id, "task_id": t["task_id"]})).content[0].text
                    if t["agent"] == "extraction_agent":
                        sids = sorted(set(re.findall(r'source_id="(S\d+)"', text)))
                        result = {"rows": [dict(r, source_id=s) for s in sids for r in SCRIPT.get(s, [])],
                                  "embedded_instruction_detected": False, "embedded_instruction_text": None}
                    else:
                        items = json.loads(re.search(r"```json\n(\[.*?\])\n```", text, re.S).group(1))
                        cls = {"annual_report": "F", "news_article": "T", "job_postings": "F",
                               "employee_review_aggregate": "E", "earnings_call_transcript": "C"}
                        result = {"items": [{"row_key": i["row_key"], "evidence_class": cls[i["source_type"]],
                                             "class_justification": "test double"} for i in items]}
                    if first:   # a malformed result is refused with a reason, and nothing is saved
                        bad = _data(await c.call_tool("submit_result", {"run_id": run_id, "task_id": t["task_id"], "result": {"rows": "x"}}))
                        assert bad["accepted"] is False and "schema" in bad["error"]
                        first = False
                    out = _data(await c.call_tool("submit_result", {"run_id": run_id, "task_id": t["task_id"], "result": result}))
                    assert out["accepted"] is True
                    if t["agent"] == "extraction_agent" and "S01" in text:
                        assert any(m["excerpt_start"].startswith("The Technology Council has del")
                                   for m in out["quote_check_preview"]["quotes_not_found"])
                    again = await c.call_tool("submit_result", {"run_id": run_id, "task_id": t["task_id"], "result": result})
                    assert again.is_error                                     # submissions are final

            st = _data(await c.call_tool("run_status", {"run_id": run_id}))
            assert st["status"] == "awaiting_CP1" and "HUMAN CHECKPOINT CP1" in st["next_step"]
            # resuming without the analyst's decisions does not get past CP1
            st = _data(await c.call_tool("resume_run", {"run_id": run_id, "analyst_name": "M7"}))
            assert st["stage"] == "CP1" and "pending" in st["orchestrator_message"]

    anyio.run(flow)

    reg = json.loads(next((isolated / "runs").glob("*/*/evidence_register.json")).read_text())
    fab = next(r for r in reg if r["excerpt"].startswith("The Technology Council has del"))
    assert fab["analyst_decision"] == "auto_rejected"
    cache = json.loads(next((isolated / "cache" / "extraction_agent").glob("*.json")).read_text())
    assert "desktop app" in cache["model"]
