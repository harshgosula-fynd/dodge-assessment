"""Pydantic models for API request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    node_id: str
    node_type: str
    label: str
    properties: dict


class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    edge_type: str
    properties: dict


class SubgraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class NodeSearchResult(BaseModel):
    node_id: str
    node_type: str
    label: str


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

class LineageStep(BaseModel):
    stage: str
    document_id: str | None
    item_number: int | None = None
    amount: float | None = None
    date: str | None = None
    status: str | None = None


class LineageFlow(BaseModel):
    sales_order_id: str
    customer_id: str
    items: list[LineageItemFlow]


class LineageItemFlow(BaseModel):
    so_item_number: int
    product_id: str
    order_amount: float | None
    steps: list[LineageStep]
    flow_status: str


# Rebuild model to resolve forward reference
LineageFlow.model_rebuild()


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class FlowStatusSummary(BaseModel):
    status: str
    count: int


class FlowStatusOverview(BaseModel):
    total_items: int
    summary: list[FlowStatusSummary]


class BrokenFlowItem(BaseModel):
    sales_order_id: str
    so_item_number: int
    product_id: str
    customer_id: str
    order_amount: float | None
    flow_status: str
    delivery_id: str | None
    active_billing_id: str | None


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class QueryPlan(BaseModel):
    model_config = {"extra": "allow"}

    intent: str
    entity_type: str | None = None
    filters: dict = {}
    aggregation: str | None = None
    count_field: str | None = None
    group_by: str | None = None
    order_by: str | None = None
    order_dir: str | None = None
    limit: int | None = None


class ChatResponse(BaseModel):
    answer: str
    query_plan: QueryPlan | None = None
    executed_sql: str | None = None
    data: list[dict] | None = None
    result_count: int | None = None
    highlighted_nodes: list[str] | None = None
    rejected: bool = False
