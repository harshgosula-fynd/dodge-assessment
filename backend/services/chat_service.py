"""Chat service: orchestrates the full NL → query → answer pipeline.

Pipeline:
1. Guardrail check (keyword pre-filter + LLM classifier)
2. Query planner (LLM → structured JSON plan)
3. SQL compiler (deterministic plan → parameterized SQL)
4. Execute (DuckDB)
5. Summarizer (LLM → natural language answer)
6. Extract highlighted graph node IDs from results
"""

import json
import logging
import re

from llm.guardrails import is_domain_relevant, quick_relevance_check
from llm.query_planner import generate_query_plan
from llm.sql_compiler import compile_query, execute_query
from llm.client import call_llm
from llm.prompts import SUMMARIZER_PROMPT

logger = logging.getLogger(__name__)

REJECTION_MESSAGE = (
    "I can only answer questions about the Order-to-Cash dataset, "
    "including sales orders, deliveries, billing documents, payments, "
    "customers, products, and business flow analysis. "
    "Please ask a question related to this data."
)

# Columns in query results that map to graph node IDs
NODE_ID_COLUMNS = {
    "sales_order_id": "sales_order",
    "customer_id": "customer",
    "delivery_id": "delivery",
    "billing_document_id": "billing",
    "active_billing_id": "billing",
    "accounting_document_id": "journal",
    "clearing_document_id": "payment",
    "product_id": "product",
    "plant_id": "plant",
}


def _sanitize_sql(sql: str, params: list) -> str:
    """Return a human-readable version of the SQL with params inlined as literals.

    This is for display only — never executed.
    """
    clean = re.sub(r'\s+', ' ', sql).strip()
    for p in params:
        clean = clean.replace("?", repr(str(p)), 1)
    return clean


def _extract_highlighted_nodes(data: list[dict], plan: dict) -> list[str]:
    """Extract graph node IDs from query results.

    Scans result columns for known ID fields and maps them to graph node IDs
    like 'customer:320000083', 'sales_order:740509', etc.
    """
    node_ids: list[str] = []
    seen: set[str] = set()

    for row in data[:30]:  # cap scanning to avoid huge lists
        for col, node_type in NODE_ID_COLUMNS.items():
            val = row.get(col)
            if val is not None and val != "" and str(val) != "None":
                nid = f"{node_type}:{val}"
                if nid not in seen:
                    seen.add(nid)
                    node_ids.append(nid)

    return node_ids[:50]  # cap to prevent UI overload


async def handle_chat(message: str) -> dict:
    """Process a chat message through the full pipeline."""

    # Step 1: Guardrail check
    quick = quick_relevance_check(message)
    if quick is False:
        return _response(answer=REJECTION_MESSAGE, rejected=True)
    if quick is None:
        try:
            relevant = await is_domain_relevant(message)
            if not relevant:
                return _response(answer=REJECTION_MESSAGE, rejected=True)
        except Exception as e:
            logger.warning(f"Guardrail LLM call failed, proceeding anyway: {e}")

    # Step 2: Generate query plan
    try:
        plan = await generate_query_plan(message)
    except Exception as e:
        logger.error(f"Query planning failed: {e}")
        return _response(
            answer="I understood your question but couldn't process it right now. Please try again.",
            query_plan=None,
        )

    # Step 3: Compile to SQL
    try:
        sql, params = compile_query(plan)
    except Exception as e:
        logger.error(f"SQL compilation failed: {e}")
        return _response(
            answer=f"I created a query plan but couldn't compile it. Error: {e}",
            query_plan=plan,
        )

    # Step 4: Execute
    try:
        data = execute_query(sql, params)
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return _response(
            answer=f"Query execution failed. Error: {e}",
            query_plan=plan,
            executed_sql=_sanitize_sql(sql, params),
        )

    result_count = len(data)
    display_sql = _sanitize_sql(sql, params)

    # Step 5: Summarize
    try:
        data_str = json.dumps(data[:30], indent=2, default=str)
        prompt = SUMMARIZER_PROMPT.format(question=message, data=data_str)
        answer = await call_llm(prompt, temperature=0.1, max_tokens=1024)
    except Exception as e:
        logger.warning(f"Summarizer failed: {e}")
        answer = f"Query returned {result_count} result(s)."

    # Step 6: Extract highlighted nodes
    highlighted = _extract_highlighted_nodes(data, plan)

    return _response(
        answer=answer,
        query_plan=plan,
        executed_sql=display_sql,
        data=data[:50],
        result_count=result_count,
        highlighted_nodes=highlighted if highlighted else None,
    )


def _response(
    answer: str,
    query_plan: dict | None = None,
    executed_sql: str | None = None,
    data: list[dict] | None = None,
    result_count: int | None = None,
    highlighted_nodes: list[str] | None = None,
    rejected: bool = False,
) -> dict:
    return {
        "answer": answer,
        "query_plan": query_plan,
        "executed_sql": executed_sql,
        "data": data,
        "result_count": result_count,
        "highlighted_nodes": highlighted_nodes,
        "rejected": rejected,
    }
