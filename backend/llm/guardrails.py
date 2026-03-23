"""Domain guardrails: validate questions are about O2C data."""

from llm.client import call_llm
from llm.prompts import DOMAIN_CLASSIFIER_PROMPT


async def is_domain_relevant(question: str) -> bool:
    """Return True if the question is about O2C business data."""
    prompt = DOMAIN_CLASSIFIER_PROMPT.format(question=question)
    response = await call_llm(prompt, temperature=0.0, max_tokens=5)
    return response.strip().upper().startswith("YES")


O2C_KEYWORDS = {
    "order", "sales", "delivery", "billing", "invoice", "payment",
    "customer", "product", "plant", "journal", "posting", "receivable",
    "shipped", "billed", "paid", "cleared", "cancelled", "flow",
    "lineage", "trace", "broken", "incomplete", "status", "amount",
    "material", "goods", "movement", "document",
}


def quick_relevance_check(question: str) -> bool | None:
    """Fast keyword check. Returns True/False if confident, None if unsure."""
    q = question.lower()
    # Check if any keyword appears as a substring (handles plurals, etc.)
    match_count = sum(1 for kw in O2C_KEYWORDS if kw in q)
    if match_count >= 1:
        return True
    # If zero keyword matches and very short, likely off-topic
    if match_count == 0 and len(q.split()) <= 4:
        return False
    return None  # unsure, need LLM
