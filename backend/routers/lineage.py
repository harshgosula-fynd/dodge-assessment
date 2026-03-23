"""Lineage / flow tracing API endpoints."""

from fastapi import APIRouter, HTTPException

from services.lineage_service import get_lineage_by_sales_order, get_lineage_by_document

router = APIRouter(prefix="/api/lineage", tags=["lineage"])


@router.get("/order/{sales_order_id}")
def trace_order(sales_order_id: str):
    """Trace the full O2C flow for a sales order."""
    result = get_lineage_by_sales_order(sales_order_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Sales order '{sales_order_id}' not found")
    return result


@router.get("/trace/{doc_type}/{doc_id}")
def trace_document(doc_type: str, doc_id: str):
    """Given any document type and ID, trace back to the full sales order flow.

    doc_type must be one of: sales_order, delivery, billing, journal, payment
    """
    valid_types = {"sales_order", "delivery", "billing", "journal", "payment"}
    if doc_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid doc_type '{doc_type}'. Must be one of: {', '.join(sorted(valid_types))}",
        )
    result = get_lineage_by_document(doc_type, doc_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"{doc_type} '{doc_id}' not found in lineage")
    return result
