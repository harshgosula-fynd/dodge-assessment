"""Graph exploration API endpoints."""

from fastapi import APIRouter, HTTPException, Query

from models.schemas import GraphNode, SubgraphResponse, NodeSearchResult
from services.graph_service import (
    get_node, get_neighbors, search_nodes, get_initial_graph,
    get_sample_flow, get_flow_subgraph, get_focus_subgraph,
)

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/initial", response_model=SubgraphResponse)
def initial_graph():
    """Get the full graph."""
    return get_initial_graph()


@router.get("/sample-flow", response_model=SubgraphResponse)
def sample_flow():
    """Get a single representative complete O2C flow for onboarding."""
    return get_sample_flow()


@router.get("/flow/{sales_order_id}", response_model=SubgraphResponse)
def flow_subgraph(sales_order_id: str):
    """Get the full O2C flow subgraph for a specific sales order."""
    result = get_flow_subgraph(sales_order_id)
    if not result or len(result["nodes"]) == 0:
        raise HTTPException(status_code=404, detail=f"Sales order '{sales_order_id}' not found")
    return result


@router.get("/focus/{node_id:path}", response_model=SubgraphResponse)
def focus_on_node(node_id: str):
    """Get a business-meaningful subgraph focused on a specific entity.

    For transactional docs (billing, delivery, etc.), returns the full O2C
    flow for the related sales order. For customers, returns a curated
    subset of their orders with flows.
    """
    return get_focus_subgraph(node_id)


@router.get("/node/{node_id:path}", response_model=GraphNode)
def read_node(node_id: str):
    """Get details for a single graph node."""
    node = get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return node


@router.get("/neighbors/{node_id:path}", response_model=SubgraphResponse)
def read_neighbors(
    node_id: str,
    depth: int = Query(default=1, ge=1, le=3),
    exclude_types: str = Query(default="product,plant"),
):
    """Get the local subgraph around a node.

    exclude_types: comma-separated node types to exclude (default: product,plant)
    Set to empty string to include all types.
    """
    node = get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    exclude = set(exclude_types.split(",")) if exclude_types else set()
    return get_neighbors(node_id, max_depth=depth, exclude_types=exclude)


@router.get("/search", response_model=list[NodeSearchResult])
def search(
    q: str = Query(default=""),
    node_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Search graph nodes by label or ID. Empty query lists all."""
    return search_nodes(q, node_type=node_type, limit=limit)
