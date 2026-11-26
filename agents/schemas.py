"""JSON output schemas for the LLM agents.

Schemas are built at run time from config/codebook.yaml, so the indicator list
and enums always match the theory files (principle 2). The same schema is
(a) sent to the API as output_config.format, and (b) used to validate every
response locally, including paste-mode replies.
"""
from __future__ import annotations


def _nullable(schema: dict) -> dict:
    return {"anyOf": [schema, {"type": "null"}]}


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props,
            "required": required if required is not None else list(props),
            "additionalProperties": False}


def extraction_schema(codebook: dict, source_ids: list[str] | None = None) -> dict:
    inds = sorted(codebook["indicators"])
    di1 = sorted(codebook["indicators"]["DI1"]["categories"])
    ec1 = codebook["indicators"]["EC1"]["fields"]
    themes = ["bureaucracy_approval_delay", "change_resistance", "openness_innovation"]
    structured = _obj({
        "posting_code": _nullable({"type": "string", "enum": ["autonomy", "procedure", "mixed"]}),
        "theme": _nullable({"type": "string", "enum": themes}),
        "theme_count": _nullable({"type": "integer"}),
        "n_reviews": _nullable({"type": "integer"}),
        "period_end": _nullable({"type": "string"}),
        "unit_exists": _nullable({"type": "string", "enum": ec1["unit_exists"]}),
        "integration_link": _nullable({"type": "string", "enum": ec1["integration_link"]}),
    })
    row = _obj({
        "source_id": {"type": "string", "enum": sorted(source_ids)} if source_ids else {"type": "string"},
        "indicator": {"type": "string", "enum": inds},
        "excerpt": {"type": "string"},
        "location": {"type": "string"},
        "proposed_level": _nullable({"type": "integer", "enum": [1, 2, 3, 4, 5]}),
        "proposed_category": _nullable({"type": "string", "enum": di1}),
        "structured_fields": structured,
        "level_scope": {"type": "string", "enum": ["firm", "parent", "business_unit"]},
        "rationale": {"type": "string"},
    })
    return _obj({
        "rows": {"type": "array", "items": row},
        "embedded_instruction_detected": {"type": "boolean"},
        "embedded_instruction_text": _nullable({"type": "string"}),
    })


def classification_schema() -> dict:
    item = _obj({
        "row_key": {"type": "string"},
        "evidence_class": {"type": "string", "enum": ["F", "C", "T", "E"]},
        "class_justification": {"type": "string"},
    })
    return _obj({"items": {"type": "array", "items": item}})


def recommendation_schema() -> dict:
    tailored = _obj({
        "rule_id": {"type": "string"},
        "option_id": {"type": "string"},
        "why_it_matters_here": {"type": "string"},
        "what_would_make_it_fail_here": {"type": "string"},
        "assumption_public_data_cannot_confirm": {"type": "string"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    })
    suggested = _obj({
        "rule_id": {"type": "string"},
        "title": {"type": "string"},
        "rationale": {"type": "string"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    })
    return _obj({
        "tailored_options": {"type": "array", "items": tailored},
        "analyst_suggested": {"type": "array", "items": suggested},
    })


def report_schema() -> dict:
    stmt = _obj({
        "type": {"type": "string", "enum": ["fact", "claim", "third_party", "employee_voice", "inference"]},
        "text": {"type": "string"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "rule_ids": {"type": "array", "items": {"type": "string"}},
    })
    return _obj({
        "executive_summary": {"type": "array", "items": stmt},
        "client_meeting_questions": {"type": "array", "items": {"type": "string"}},
    })
