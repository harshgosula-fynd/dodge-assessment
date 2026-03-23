"""Lineage query logic: trace the full O2C flow for a document."""

from db.connection import get_connection


def get_lineage_by_sales_order(sales_order_id: str) -> dict | None:
    """Return the full item-level flow for a sales order."""
    con = get_connection()
    rows = con.execute(
        """
        SELECT
            sales_order_id, so_item_number, customer_id, product_id,
            ordered_qty, order_amount, currency, plant_id, order_date,
            delivery_id, dl_item_number, delivery_date,
            delivered_qty, goods_movement_date, gm_status,
            active_billing_id, active_billing_type, billing_date,
            billed_amount, cancelled_billing_id,
            accounting_document_id, posted_amount, posting_date, gl_account,
            clearing_document_id, clearing_date, is_cleared
        FROM lineage_item_flow
        WHERE sales_order_id = ?
        ORDER BY so_item_number
        """,
        [sales_order_id],
    ).fetchall()

    if not rows:
        return None

    customer_id = rows[0][2]
    items = []

    for r in rows:
        steps = []

        # Order step (always present)
        steps.append({
            "stage": "sales_order",
            "document_id": r[0],
            "item_number": r[1],
            "amount": float(r[5]) if r[5] else None,
            "date": str(r[8]) if r[8] else None,
            "status": "created",
        })

        # Delivery step
        if r[9]:  # delivery_id
            steps.append({
                "stage": "delivery",
                "document_id": r[9],
                "item_number": r[10],
                "amount": float(r[12]) if r[12] else None,
                "date": str(r[11]) if r[11] else None,
                "status": r[14] or "unknown",  # gm_status
            })

        # Billing step
        if r[15]:  # active_billing_id
            steps.append({
                "stage": "billing",
                "document_id": r[15],
                "item_number": None,
                "amount": float(r[18]) if r[18] else None,
                "date": str(r[17]) if r[17] else None,
                "status": f"rebilled (was {r[19]})" if r[19] else r[16],  # type, note if it replaced a cancelled doc
            })

        # Journal entry step
        if r[20]:  # accounting_document_id
            steps.append({
                "stage": "journal_entry",
                "document_id": r[20],
                "item_number": None,
                "amount": float(r[21]) if r[21] else None,
                "date": str(r[22]) if r[22] else None,
                "status": r[23],  # gl_account
            })

        # Payment step
        if r[24]:  # clearing_document_id
            steps.append({
                "stage": "payment",
                "document_id": r[24],
                "item_number": None,
                "amount": None,
                "date": str(r[25]) if r[25] else None,
                "status": "cleared" if r[26] else "open",
            })

        # Determine flow status from flow_status table
        fs_row = con.execute(
            "SELECT flow_status FROM flow_status WHERE sales_order_id = ? AND so_item_number = ?",
            [sales_order_id, r[1]],
        ).fetchone()
        flow_status = fs_row[0] if fs_row else "unknown"

        items.append({
            "so_item_number": r[1],
            "product_id": r[3],
            "order_amount": float(r[5]) if r[5] else None,
            "steps": steps,
            "flow_status": flow_status,
        })

    return {
        "sales_order_id": sales_order_id,
        "customer_id": customer_id,
        "items": items,
    }


def get_lineage_by_document(doc_type: str, doc_id: str) -> dict | None:
    """Given any document type and ID, find the related sales order and return full lineage."""
    con = get_connection()

    column_map = {
        "sales_order": "sales_order_id",
        "delivery": "delivery_id",
        "billing": "active_billing_id",
        "journal": "accounting_document_id",
        "payment": "clearing_document_id",
    }

    column = column_map.get(doc_type)
    if not column:
        return None

    row = con.execute(
        f"SELECT DISTINCT sales_order_id FROM lineage_item_flow WHERE {column} = ?",
        [doc_id],
    ).fetchone()

    if not row:
        return None

    return get_lineage_by_sales_order(row[0])
