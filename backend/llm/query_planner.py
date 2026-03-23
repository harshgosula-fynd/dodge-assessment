"""Translate natural language questions into structured query plans."""

import json
import re

from llm.client import call_llm
from llm.prompts import QUERY_PLANNER_PROMPT

VALID_INTENTS = {"trace_flow", "list_entities", "aggregate", "find_broken", "describe_entity"}
VALID_ENTITY_TYPES = {
    "sales_order", "delivery", "billing", "journal_entry",
    "payment", "customer", "product", "plant", "flow_status", "lineage",
}


async def generate_query_plan(question: str) -> dict:
    """Use the LLM to generate a structured query plan from a question."""
    prompt = QUERY_PLANNER_PROMPT.format(question=question)
    response = await call_llm(prompt, temperature=0.0, max_tokens=512)

    # Extract JSON from response (handle markdown code fences)
    json_str = response.strip()

    # Try to find JSON block between ```json ... ``` first
    code_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', json_str, re.DOTALL)
    if code_match:
        json_str = code_match.group(1)
    else:
        # Fall back to finding first complete JSON object
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_str, re.DOTALL)
        if json_match:
            json_str = json_match.group()

    try:
        plan = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}. Raw response: {json_str[:200]}")

    # Validate and normalize
    if plan.get("intent") not in VALID_INTENTS:
        raise ValueError(f"Invalid intent: {plan.get('intent')}. Must be one of: {VALID_INTENTS}")

    if plan.get("entity_type") and plan["entity_type"] not in VALID_ENTITY_TYPES:
        raise ValueError(f"Invalid entity_type: {plan.get('entity_type')}")

    # Normalize null-like values
    for key in ["aggregation", "order_by", "order_dir", "group_by", "count_field"]:
        if plan.get(key) in (None, "null", ""):
            plan[key] = None

    if not isinstance(plan.get("filters"), dict):
        plan["filters"] = {}

    return plan
