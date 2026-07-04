from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ValidationError, field_validator

from app.config import get_settings
from app.models import AgentRecommendation, LLMAgentNote, ResupplyOption


class LLMResponse(BaseModel):
    reasoning_summary: list[str]
    proposed_action: str

    @field_validator("reasoning_summary", mode="before")
    @classmethod
    def normalize_reasoning_summary(cls, value):
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("proposed_action", mode="before")
    @classmethod
    def normalize_proposed_action(cls, value):
        if isinstance(value, dict):
            action = value.get("action")
            if action:
                return action
            return json.dumps(value, separators=(",", ":"))
        return value


SYSTEM_PROMPT = """You are an Ebola test kit resupply agent.
Use only the JSON payload provided by the backend. Do not use outside knowledge.
Do not invent stock counts, clinics, warehouses, routes, delivery times, risk
levels, or transfer quantities. The deterministic backend recommendation is the
source of truth. Your role is to give a concise operational reasoning summary
and action proposal based only on that payload. Do not reveal hidden chain of
thought. Return valid JSON with keys reasoning_summary and proposed_action."""


def build_llm_payload(
    clinic: dict[str, Any],
    options: list[ResupplyOption],
    deterministic: AgentRecommendation,
) -> dict[str, Any]:
    return {
        "data_contract": (
            "All factual inputs are from Neo4j Clinic nodes, Neo4j Warehouse "
            "nodes, Neo4j Warehouse-to-Clinic CAN_SUPPLY relationships, and "
            "deterministic backend calculations. Clinic-to-clinic stock is not "
            "allowed for resupply proposals."
        ),
        "activation_rule": "LLM note is requested only because clinic risk is critical.",
        "clinic": {
            key: clinic.get(key)
            for key in [
                "id",
                "name",
                "test_kits_available",
                "people_waiting",
                "nurses_available",
                "threshold_min_kits",
                "testing_capacity_per_hour",
                "queue_delay_hours",
                "operations_remaining_hours",
                "risk_level",
            ]
        },
        "deterministic_recommendation": {
            "reasoning": deterministic.reasoning,
            "recommendation": deterministic.recommendation,
        },
        "warehouse_only_options": [option.model_dump() for option in options],
        "instruction": (
            "Explain the critical stock situation and propose the same action "
            "supported by the deterministic recommendation. If no warehouse "
            "option exists, say no warehouse route is available."
        ),
    }


def parse_llm_response_content(content: str) -> LLMResponse:
    stripped = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    elif not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            stripped = stripped[start : end + 1]
    return LLMResponse.model_validate_json(stripped)


def unavailable_llm_note(reason: str, include_reason: bool = False) -> LLMAgentNote:
    return LLMAgentNote(
        available=False,
        provider="mistral-openai-compatible",
        proposed_action=reason,
        reasoning_summary=[reason] if include_reason else [],
        data_sources=[
            "neo4j:Clinic",
            "neo4j:Warehouse",
            "neo4j:CAN_SUPPLY:warehouse_only",
            "backend:deterministic_recommendation",
        ],
    )


def generate_critical_llm_note(
    clinic: dict[str, Any],
    options: list[ResupplyOption],
    deterministic: AgentRecommendation,
) -> LLMAgentNote | None:
    if clinic["risk_level"] != "critical":
        return None

    settings = get_settings()
    if not settings.llm_api_key:
        return unavailable_llm_note(
            "Set LLM_API_KEY to enable the critical-case LLM agent."
        )

    payload = build_llm_payload(clinic, options, deterministic)
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    try:
        completion = client.chat.completions.create(
            model=settings.llm_model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(payload, separators=(",", ":")),
                },
            ],
        )
        content = completion.choices[0].message.content or "{}"
        parsed = parse_llm_response_content(content)
    except (ValidationError, json.JSONDecodeError, Exception):
        return unavailable_llm_note(
            "LLM agent could not generate a validated response. Deterministic recommendation remains the source of truth.",
            include_reason=True,
        )

    return LLMAgentNote(
        available=True,
        provider="mistral-openai-compatible",
        model=settings.llm_model,
        reasoning_summary=parsed.reasoning_summary,
        proposed_action=parsed.proposed_action,
        data_sources=[
            "neo4j:Clinic",
            "neo4j:Warehouse",
            "neo4j:CAN_SUPPLY:warehouse_only",
            "backend:deterministic_recommendation",
        ],
    )
