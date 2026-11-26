"""LLM gateway: one function every agent uses to get a JSON answer.

Modes (config/runtime.yaml → agent_mode):
  api    – Claude API call with a JSON-schema output format; response cached
  paste  – prompt written to a file for manual use in Claude Pro; the run
           pauses until the reply file exists (free)
  replay – cached responses only; never calls the API (demo safety net)

In every mode the reply is validated against the schema before use, and the
call is recorded in the run log with tokens and cost. Cached responses are
keyed by a hash of (model, system prompt, user message, schema). Unchanged
inputs therefore always give the same output, which makes reruns deterministic.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import jsonschema

from engine.common import ROOT, RunLog, read_json, sha, write_json


class PasteRequired(Exception):
    """Raised in paste mode when a prompt is waiting for a manual reply."""

    def __init__(self, prompt_path: Path, reply_path: Path):
        super().__init__(f"Paste mode: run the prompt in {prompt_path} and save the JSON reply as {reply_path}")
        self.prompt_path, self.reply_path = prompt_path, reply_path


class ReplayMiss(Exception):
    pass


class BudgetExceeded(Exception):
    pass


class AgentOutputInvalid(Exception):
    pass


@dataclass
class Gateway:
    runtime: dict
    case_id: str
    run_dir: Path
    log: RunLog

    @property
    def mode(self) -> str:
        return self.runtime["agent_mode"]

    def _cache_path(self, agent: str, key: str) -> Path:
        return ROOT / self.runtime["cache_dir"] / self.case_id / agent / f"{key}.json"

    def call(self, agent: str, call_id: str, system: str, user: str, schema: dict, stage: str) -> dict:
        model = self.runtime["model"]
        key = sha({"model": model, "system": system, "user": user, "schema": schema})[:24]
        cache = self._cache_path(agent, key)

        if cache.exists():
            cached = read_json(cache)
            data = cached["output"]
            self._validate(agent, data, schema)
            self.log.event(stage, agent, "llm_call_cached", detail={"call_id": call_id, "cache_key": key,
                           "origin": cached.get("origin")}, inputs=user, outputs=data, model=cached.get("model"))
            return data

        if self.mode == "replay":
            raise ReplayMiss(f"No cached response for {agent} call {call_id} (key {key}). "
                             f"Run once in api or paste mode first.")
        if self.mode == "paste":
            data = self._paste(agent, call_id, key, system, user, schema)
            origin, usage = "paste", {}
        elif self.mode == "api":
            data, usage = self._api(agent, system, user, schema)
            origin = "api"
        else:
            raise ValueError(f"Unknown agent_mode {self.mode}")

        self._validate(agent, data, schema)
        write_json(cache, {"agent": agent, "model": model if origin == "api" else f"{model} (paste mode, manual)",
                           "origin": origin, "call_id": call_id, "output": data})
        write_json(self.run_dir / "agent_io" / agent / f"{call_id}.json",
                   {"system_sha": sha(system)[:16], "user": user, "output": data, "usage": usage})
        self.log.event(stage, agent, f"llm_call_{origin}", detail={"call_id": call_id, "cache_key": key},
                       inputs=user, outputs=data, model=model, usage=usage)
        return data

    # ------------------------------------------------------------------ api
    def _api(self, agent: str, system: str, user: str, schema: dict) -> tuple[dict, dict]:
        import anthropic  # imported here so paste/replay modes work without the SDK configured

        limit = self.runtime["max_cost_usd_per_run"]
        spent = self.log.total_cost()
        if spent >= limit:
            raise BudgetExceeded(f"Run cost ${spent:.2f} reached the limit ${limit:.2f} (config/runtime.yaml)")

        client = anthropic.Anthropic()
        kwargs = dict(
            model=self.runtime["model"],
            max_tokens=self.runtime["max_tokens"],
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"effort": self.runtime["effort"].get(agent, "medium"),
                           "format": {"type": "json_schema", "schema": schema}},
        )
        if self.runtime.get("fallbacks") not in (None, False, "off", "none"):
            resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                               fallbacks=self.runtime["fallbacks"], **kwargs)
        else:
            resp = client.messages.create(**kwargs)

        if resp.stop_reason == "refusal":
            raise AgentOutputInvalid(f"{agent}: model declined the request (stop_reason=refusal)")
        if resp.stop_reason == "max_tokens":
            raise AgentOutputInvalid(f"{agent}: output truncated at max_tokens; reduce chunk_words or raise max_tokens")
        text = next((b.text for b in resp.content if b.type == "text"), None)
        if text is None:
            raise AgentOutputInvalid(f"{agent}: no text block in response")
        usage = self._usage(resp)
        return json.loads(text), usage

    def _usage(self, resp) -> dict:
        u = resp.usage
        price = self.runtime["prices"].get(resp.model) or self.runtime["prices"].get(self.runtime["model"], {})
        inp = getattr(u, "input_tokens", 0) or 0
        out = getattr(u, "output_tokens", 0) or 0
        cr = getattr(u, "cache_read_input_tokens", 0) or 0
        cw = getattr(u, "cache_creation_input_tokens", 0) or 0
        cost = (inp * price.get("input", 0) + out * price.get("output", 0) + cr * price.get("cache_read", 0)
                + cw * price.get("cache_write", 0)) / 1_000_000
        return {"input_tokens": inp + cr + cw, "output_tokens": out, "cache_read": cr, "cache_write": cw,
                "cost_usd": round(cost, 5), "served_model": resp.model, "request_id": getattr(resp, "_request_id", None)}

    # ---------------------------------------------------------------- paste
    def _paste(self, agent: str, call_id: str, key: str, system: str, user: str, schema: dict) -> dict:
        folder = self.run_dir / "paste"
        prompt_path = folder / f"{call_id}.prompt.md"
        reply_path = folder / f"{call_id}.reply.json"
        if reply_path.exists():
            raw = reply_path.read_text(encoding="utf-8")
            m = re.search(r"\{.*\}", raw, re.S)          # tolerate ```json fences and text around the reply
            if not m:
                raise AgentOutputInvalid(f"{reply_path.name}: no JSON object found. Save only Claude's JSON reply.")
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError as exc:
                raise AgentOutputInvalid(
                    f"{reply_path.name}: reply is not valid JSON ({exc.msg}, line {exc.lineno}). If the reply was cut "
                    "off, ask Claude in the same chat: 'Continue the JSON exactly where you stopped', join the parts, "
                    "and save again.") from exc
        folder.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(
            "# PASTE-MODE PROMPT — attach this file to a NEW claude.ai chat (or paste everything below the line)\n"
            f"# Agent: {agent} | Call: {call_id} | Cache key: {key}\n"
            f"# Save Claude's reply (the JSON only) as: {reply_path.name} in this folder, then resume the run.\n"
            "---\n\n"
            f"## Instructions\n\n{system}\n\n## Input\n\n{user}\n\n"
            "## Required output\n\nReply with ONE JSON object only, no commentary, matching this JSON Schema:\n\n"
            f"```json\n{json.dumps(schema, indent=1)}\n```\n", encoding="utf-8")
        raise PasteRequired(prompt_path, reply_path)

    # ------------------------------------------------------------- validate
    @staticmethod
    def _validate(agent: str, data: dict, schema: dict) -> None:
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as exc:
            raise AgentOutputInvalid(f"{agent}: output does not match schema: {exc.message}") from exc
