"""Deterministic compiler: query plan → parameterized SQL over semantic views.

The LLM never writes SQL. It produces a structured plan. This module
compiles plans into safe, parameterized queries.
"""

from db.connection import get_connection

# Maps entity_type to the semantic table and its queryable columns
TABLE_MAP = {
    "sales_order": {
        "table": "raw_sales_order_headers",
        "columns": {
            "sales_order_id": "salesOrder",
            "customer_id": "soldToParty",
            "order_date": "creationDate",
            "total_amount": "CAST(totalNetAmount AS DECIMAL(18,2))",
            "delivery_status": "overallDeliveryStatus",
            "currency": "transactionCurrency",
        },
        "default_label": "salesOrder",
    },
    "delivery": {
        "table": "raw_outbound_delivery_headers",
        "columns": {
            "delivery_id": "deliveryDocument",
            "creation_date": "creationDate",
            "goods_movement_status": "overallGoodsMovementStatus",
            "goods_movement_date": "actualGoodsMovementDate",
            "picking_status": "overallPickingStatus",
        },
        "default_label": "deliveryDocument",
    },
    "billing": {
        "table": "raw_billing_document_headers",
        "columns": {
            "billing_document_id": "billingDocument",
            "billing_date": "billingDocumentDate",
            "amount": "CAST(totalNetAmount AS DECIMAL(18,2))",
            "type": "billingDocumentType",
            "is_cancelled": "billingDocumentIsCancelled",
            "customer_id": "soldToParty",
            "currency": "transactionCurrency",
        },
        "default_label": "billingDocument",
    },
    "journal_entry": {
        "table": "link_billing_journal",
        "columns": {
            "accounting_document_id": "accounting_document_id",
            "billing_document_id": "billing_document_id",
            "amount": "amount",
            "posting_date": "posting_date",
            "gl_account": "gl_account",
            "customer_id": "customer_id",
            "currency": "currency",
        },
        "default_label": "accounting_document_id",
    },
    "payment": {
        "table": "link_journal_payment",
        "columns": {
            "clearing_document_id": "clearing_document_id",
            "accounting_document_id": "accounting_document_id",
            "billing_document_id": "billing_document_id",
            "clearing_date": "clearing_date",
            "is_cleared": "is_cleared",
            "amount": "amount",
        },
        "default_label": "clearing_document_id",
    },
    "customer": {
        "table": "dim_customer",
        "columns": {
            "customer_id": "customer_id",
            "customer_name": "customer_name",
            "city": "city",
            "country": "country",
            "region": "region",
            "is_blocked": "is_blocked",
        },
        "default_label": "customer_id",
    },
    "product": {
        "table": "dim_product",
        "columns": {
            "product_id": "product_id",
            "product_name": "product_name",
            "product_type": "product_type",
            "product_group": "product_group",
            "weight": "gross_weight",
            "base_unit": "base_unit",
        },
        "default_label": "product_id",
    },
    "plant": {
        "table": "dim_plant",
        "columns": {
            "plant_id": "plant_id",
            "plant_name": "plant_name",
            "sales_organization": "sales_organization",
        },
        "default_label": "plant_id",
    },
    "flow_status": {
        "table": "flow_status",
        "columns": {
            "sales_order_id": "sales_order_id",
            "so_item_number": "so_item_number",
            "product_id": "product_id",
            "customer_id": "customer_id",
            "order_amount": "order_amount",
            "flow_status": "flow_status",
            "has_delivery": "has_delivery",
            "has_billing_active": "has_billing_active",
            "has_journal_entry": "has_journal_entry",
            "is_cleared": "is_cleared",
            "delivery_id": "delivery_id",
            "active_billing_id": "active_billing_id",
        },
        "default_label": "sales_order_id",
    },
    "lineage": {
        "table": "lineage_item_flow",
        "columns": {
            "sales_order_id": "sales_order_id",
            "so_item_number": "so_item_number",
            "customer_id": "customer_id",
            "product_id": "product_id",
            "order_amount": "order_amount",
            "delivery_id": "delivery_id",
            "active_billing_id": "active_billing_id",
            "billed_amount": "billed_amount",
            "accounting_document_id": "accounting_document_id",
            "clearing_document_id": "clearing_document_id",
            "is_cleared": "is_cleared",
        },
        "default_label": "sales_order_id",
    },
}


def compile_query(plan: dict) -> tuple[str, list]:
    """Compile a query plan into (sql, params).

    Returns parameterized SQL that is safe to execute.
    """
    intent = plan["intent"]
    entity_type = plan.get("entity_type", "flow_status")

    if intent == "trace_flow":
        return _compile_trace(plan)
    elif intent == "find_broken":
        return _compile_find_broken(plan)
    elif intent == "aggregate":
        return _compile_aggregate(plan)
    elif intent == "list_entities":
        return _compile_list(plan)
    elif intent == "describe_entity":
        return _compile_describe(plan)
    else:
        raise ValueError(f"Unknown intent: {intent}")


def _get_table_info(entity_type: str) -> dict:
    info = TABLE_MAP.get(entity_type)
    if not info:
        raise ValueError(f"Unknown entity_type: {entity_type}")
    return info


def _build_where(info: dict, filters: dict) -> tuple[str, list]:
    """Build WHERE clause from filters. Returns (clause, params)."""
    conditions = []
    params = []
    for field, value in filters.items():
        col = info["columns"].get(field)
        if col is None:
            continue  # skip unknown filters
        conditions.append(f"{col} = ?")
        params.append(value)
    clause = " AND ".join(conditions) if conditions else "1=1"
    return clause, params


def _compile_trace(plan: dict) -> tuple[str, list]:
    """Trace flow: delegate to lineage table."""
    filters = plan.get("filters", {})
    entity_type = plan.get("entity_type", "sales_order")

    # Map the filter to the lineage table column
    lineage_info = TABLE_MAP["lineage"]
    where, params = _build_where(lineage_info, filters)

    # If filtering by a non-lineage field, try the entity's own table
    if not params and filters:
        entity_info = _get_table_info(entity_type)
        for field, value in filters.items():
            col = entity_info["columns"].get(field)
            if col:
                # Find the corresponding lineage column
                lineage_col_map = {
                    "sales_order": "sales_order_id",
                    "delivery": "delivery_id",
                    "billing": "active_billing_id",
                    "journal_entry": "accounting_document_id",
                    "payment": "clearing_document_id",
                }
                lineage_field = lineage_col_map.get(entity_type)
                if lineage_field and lineage_field in lineage_info["columns"]:
                    where = f"{lineage_info['columns'][lineage_field]} = ?"
                    params = [value]
                    break

    sql = f"""
        SELECT * FROM lineage_item_flow
        WHERE {where}
        ORDER BY sales_order_id, so_item_number
        LIMIT 50
    """
    return sql, params


def _compile_find_broken(plan: dict) -> tuple[str, list]:
    """Find broken/incomplete flows."""
    filters = plan.get("filters", {})
    info = TABLE_MAP["flow_status"]
    where, params = _build_where(info, filters)

    # Default: everything not complete
    if "flow_status" not in filters:
        where = "flow_status != 'complete'"
        params = []

    sql = f"""
        SELECT sales_order_id, so_item_number, product_id, customer_id,
               order_amount, flow_status, delivery_id, active_billing_id
        FROM flow_status
        WHERE {where}
        ORDER BY flow_status, sales_order_id, so_item_number
        LIMIT 50
    """
    return sql, params


def _compile_aggregate(plan: dict) -> tuple[str, list]:
    """Aggregate query: count, sum, etc."""
    entity_type = plan.get("entity_type", "flow_status")
    info = _get_table_info(entity_type)
    filters = plan.get("filters", {})
    agg = plan.get("aggregation", "count")
    count_field = plan.get("count_field")
    group_by = plan.get("group_by")
    order_by = plan.get("order_by")
    order_dir = (plan.get("order_dir") or "desc").upper()
    limit = plan.get("limit")
    if not isinstance(limit, int) or limit < 1 or limit > 200:
        limit = 20

    if order_dir not in ("ASC", "DESC"):
        order_dir = "DESC"

    where, params = _build_where(info, filters)

    # If count_field is specified, filter out NULLs and count distinct
    count_col_expr = None
    if count_field and count_field in info["columns"]:
        count_col_real = info["columns"][count_field]
        count_col_expr = count_col_real
        # Add NOT NULL filter for the counted column
        if where == "1=1":
            where = f"{count_col_real} IS NOT NULL"
        else:
            where = f"{where} AND {count_col_real} IS NOT NULL"

    if group_by and group_by in info["columns"]:
        group_col = info["columns"][group_by]

        # Build aggregation expression
        if agg == "count":
            if count_col_expr:
                agg_expr = f"count(DISTINCT {count_col_expr}) AS count"
            else:
                agg_expr = "count(*) AS count"
            sort_col = "count"
        elif agg in ("sum", "avg", "min", "max"):
            # Find a numeric column to aggregate
            amount_col = info["columns"].get("amount") or info["columns"].get("order_amount") or info["columns"].get("total_amount")
            if amount_col:
                agg_expr = f"{agg}({amount_col}) AS {agg}_value"
                sort_col = f"{agg}_value"
            else:
                agg_expr = "count(*) AS count"
                sort_col = "count"
        else:
            agg_expr = "count(*) AS count"
            sort_col = "count"

        # Resolve order_by
        if order_by == agg or order_by == "count":
            order_col = sort_col
        elif order_by and order_by in info["columns"]:
            order_col = info["columns"][order_by]
        else:
            order_col = sort_col

        sql = f"""
            SELECT {group_col} AS {group_by}, {agg_expr}
            FROM {info['table']}
            WHERE {where}
            GROUP BY {group_col}
            ORDER BY {order_col} {order_dir}
            LIMIT {limit}
        """
    else:
        # No group by — simple aggregate
        if agg == "count":
            if count_col_expr:
                agg_expr = f"count(DISTINCT {count_col_expr}) AS count"
            else:
                agg_expr = "count(*) AS count"
        elif agg in ("sum", "avg", "min", "max"):
            amount_col = info["columns"].get("amount") or info["columns"].get("order_amount") or info["columns"].get("total_amount")
            if amount_col:
                agg_expr = f"{agg}({amount_col}) AS {agg}_value"
            else:
                agg_expr = "count(*) AS count"
        else:
            agg_expr = "count(*) AS count"

        sql = f"""
            SELECT {agg_expr}
            FROM {info['table']}
            WHERE {where}
        """

    return sql, params


def _compile_list(plan: dict) -> tuple[str, list]:
    """List/filter entities."""
    entity_type = plan.get("entity_type", "flow_status")
    info = _get_table_info(entity_type)
    filters = plan.get("filters", {})
    limit = plan.get("limit")
    if not isinstance(limit, int) or limit < 1 or limit > 200:
        limit = 20

    where, params = _build_where(info, filters)

    # Select key columns
    select_cols = ", ".join(f"{v} AS {k}" for k, v in info["columns"].items())

    sql = f"""
        SELECT {select_cols}
        FROM {info['table']}
        WHERE {where}
        ORDER BY {info['default_label']}
        LIMIT {limit}
    """
    return sql, params


def _compile_describe(plan: dict) -> tuple[str, list]:
    """Describe a specific entity."""
    entity_type = plan.get("entity_type", "sales_order")
    info = _get_table_info(entity_type)
    filters = plan.get("filters", {})
    where, params = _build_where(info, filters)

    select_cols = ", ".join(f"{v} AS {k}" for k, v in info["columns"].items())

    sql = f"""
        SELECT {select_cols}
        FROM {info['table']}
        WHERE {where}
        LIMIT 5
    """
    return sql, params


def execute_query(sql: str, params: list) -> list[dict]:
    """Execute compiled SQL and return results as list of dicts."""
    con = get_connection()
    result = con.execute(sql, params)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    return [
        {col: _serialize(val) for col, val in zip(columns, row)}
        for row in rows
    ]


def _serialize(val):
    """Convert DuckDB values to JSON-safe types."""
    if val is None:
        return None
    if isinstance(val, (int, float, bool, str)):
        return val
    return str(val)
