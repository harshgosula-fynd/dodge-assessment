"""Flow status API endpoints."""

from fastapi import APIRouter, Query

from models.schemas import FlowStatusOverview, BrokenFlowItem
from services.status_service import get_status_overview, get_broken_flows, get_status_by_customer

router = APIRouter(prefix="/api/status", tags=["status"])


@router.get("/overview", response_model=FlowStatusOverview)
def status_overview():
    """Get aggregate flow status counts across all SO items."""
    return get_status_overview()


@router.get("/broken", response_model=list[BrokenFlowItem])
def broken_flows(
    status: str | None = Query(default=None, description="Filter by specific status"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get items with incomplete / broken flows."""
    return get_broken_flows(status_filter=status, limit=limit)


@router.get("/by-customer")
def status_by_customer():
    """Get flow status breakdown per customer."""
    return get_status_by_customer()
