"""Flow status query logic."""

from db.connection import get_connection


def get_status_overview() -> dict:
    """Return aggregate flow status counts."""
    con = get_connection()
    rows = con.execute(
        "SELECT flow_status, count(*) AS n FROM flow_status GROUP BY 1 ORDER BY n DESC"
    ).fetchall()

    total = sum(r[1] for r in rows)
    return {
        "total_items": total,
        "summary": [{"status": r[0], "count": r[1]} for r in rows],
    }


def get_broken_flows(status_filter: str | None = None, limit: int = 50) -> list[dict]:
    """Return items with incomplete flows.

    'Broken' means any status other than 'complete'.
    Optionally filter by a specific status.
    """
    con = get_connection()

    if status_filter:
        rows = con.execute(
            """
            SELECT sales_order_id, so_item_number, product_id, customer_id,
                   order_amount, flow_status, delivery_id, active_billing_id
            FROM flow_status
            WHERE flow_status = ?
            ORDER BY sales_order_id, so_item_number
            LIMIT ?
            """,
            [status_filter, limit],
        ).fetchall()
    else:
        rows = con.execute(
            """
            SELECT sales_order_id, so_item_number, product_id, customer_id,
                   order_amount, flow_status, delivery_id, active_billing_id
            FROM flow_status
            WHERE flow_status != 'complete'
            ORDER BY flow_status, sales_order_id, so_item_number
            LIMIT ?
            """,
            [limit],
        ).fetchall()

    return [
        {
            "sales_order_id": r[0],
            "so_item_number": r[1],
            "product_id": r[2],
            "customer_id": r[3],
            "order_amount": float(r[4]) if r[4] else None,
            "flow_status": r[5],
            "delivery_id": r[6],
            "active_billing_id": r[7],
        }
        for r in rows
    ]


def get_status_by_customer() -> list[dict]:
    """Return flow status breakdown per customer."""
    con = get_connection()
    rows = con.execute(
        """
        SELECT
            fs.customer_id,
            dc.customer_name,
            fs.flow_status,
            count(*) AS item_count,
            sum(fs.order_amount) AS total_amount
        FROM flow_status fs
        LEFT JOIN dim_customer dc ON fs.customer_id = dc.customer_id
        GROUP BY fs.customer_id, dc.customer_name, fs.flow_status
        ORDER BY fs.customer_id, fs.flow_status
        """
    ).fetchall()

    return [
        {
            "customer_id": r[0],
            "customer_name": r[1],
            "flow_status": r[2],
            "item_count": r[3],
            "total_amount": float(r[4]) if r[4] else None,
        }
        for r in rows
    ]
