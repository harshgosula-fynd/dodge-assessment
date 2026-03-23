"""Graph query logic over DuckDB graph_nodes / graph_edges tables."""

import json

from db.connection import get_connection


def get_node(node_id: str) -> dict | None:
    con = get_connection()
    row = con.execute(
        "SELECT node_id, node_type, label, properties FROM graph_nodes WHERE node_id = ?",
        [node_id],
    ).fetchone()
    if not row:
        return None
    return {
        "node_id": row[0],
        "node_type": row[1],
        "label": row[2],
        "properties": json.loads(row[3]) if isinstance(row[3], str) else row[3],
    }


def get_neighbors(
    node_id: str, max_depth: int = 1, exclude_types: set[str] | None = None
) -> dict:
    """Return the local subgraph around a node up to max_depth hops.

    exclude_types: node types to filter out (e.g., {"product", "plant"})
    """
    con = get_connection()
    visited_nodes = set()
    all_edges = []
    frontier = {node_id}

    for _ in range(max_depth):
        if not frontier:
            break
        placeholders = ", ".join(["?"] * len(frontier))
        frontier_list = list(frontier)

        rows = con.execute(
            f"""
            SELECT source_id, target_id, edge_type, properties
            FROM graph_edges
            WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})
            """,
            frontier_list + frontier_list,
        ).fetchall()

        next_frontier = set()
        for src, tgt, etype, props in rows:
            edge = {
                "source_id": src,
                "target_id": tgt,
                "edge_type": etype,
                "properties": json.loads(props) if isinstance(props, str) else props,
            }
            if edge not in all_edges:
                all_edges.append(edge)
            next_frontier.add(src)
            next_frontier.add(tgt)

        visited_nodes.update(frontier)
        frontier = next_frontier - visited_nodes

    # Collect node IDs
    all_node_ids = {node_id}
    for e in all_edges:
        all_node_ids.add(e["source_id"])
        all_node_ids.add(e["target_id"])

    # Fetch and filter nodes
    if all_node_ids:
        placeholders = ", ".join(["?"] * len(all_node_ids))
        node_rows = con.execute(
            f"SELECT node_id, node_type, label, properties FROM graph_nodes WHERE node_id IN ({placeholders})",
            list(all_node_ids),
        ).fetchall()
    else:
        node_rows = []

    nodes = []
    included_ids = set()
    for r in node_rows:
        if exclude_types and r[1] in exclude_types and r[0] != node_id:
            continue
        nodes.append({
            "node_id": r[0], "node_type": r[1], "label": r[2],
            "properties": json.loads(r[3]) if isinstance(r[3], str) else r[3],
        })
        included_ids.add(r[0])

    # Remove edges that reference excluded nodes
    filtered_edges = [
        e for e in all_edges
        if e["source_id"] in included_ids and e["target_id"] in included_ids
    ]

    return {"nodes": nodes, "edges": filtered_edges}


def get_sample_flow() -> dict:
    """Return a single complete O2C flow for onboarding.

    Picks a sales order that has the full chain: SO → DL → BD → JE → PAY.
    """
    con = get_connection()

    # Find a complete flow
    row = con.execute("""
        SELECT sales_order_id FROM flow_status
        WHERE flow_status = 'complete'
        LIMIT 1
    """).fetchone()

    if not row:
        return {"nodes": [], "edges": []}

    return get_flow_subgraph(row[0])


def get_flow_subgraph(sales_order_id: str) -> dict:
    """Build a subgraph representing the full O2C flow for one sales order.

    Returns nodes and edges for the chain:
    Customer → Sales Order → Delivery → Billing → Journal → Payment
    """
    con = get_connection()

    # Get lineage rows for this SO
    rows = con.execute(
        "SELECT * FROM lineage_item_flow WHERE sales_order_id = ?",
        [sales_order_id],
    ).fetchall()

    if not rows:
        return {"nodes": [], "edges": []}

    cols = [d[0] for d in con.execute("SELECT * FROM lineage_item_flow LIMIT 0").description]

    node_ids: set[str] = set()
    edge_set: set[tuple[str, str, str]] = set()

    for row in rows:
        r = dict(zip(cols, row))

        cust = r.get("customer_id")
        so = r.get("sales_order_id")
        prod = r.get("product_id")
        dl = r.get("delivery_id")
        bd = r.get("active_billing_id")
        je = r.get("accounting_document_id")
        pay = r.get("clearing_document_id")

        if cust:
            node_ids.add(f"customer:{cust}")
        if so:
            node_ids.add(f"sales_order:{so}")
            if cust:
                edge_set.add((f"customer:{cust}", f"sales_order:{so}", "PLACED_ORDER"))
        if prod:
            node_ids.add(f"product:{prod}")
            if so:
                edge_set.add((f"sales_order:{so}", f"product:{prod}", "CONTAINS_PRODUCT"))
        if dl:
            node_ids.add(f"delivery:{dl}")
            if so:
                edge_set.add((f"sales_order:{so}", f"delivery:{dl}", "FULFILLED_BY"))
        if bd:
            node_ids.add(f"billing:{bd}")
            if dl:
                edge_set.add((f"delivery:{dl}", f"billing:{bd}", "BILLED_AS"))
        if je:
            node_ids.add(f"journal:{je}")
            if bd:
                edge_set.add((f"billing:{bd}", f"journal:{je}", "POSTED_AS"))
        if pay:
            node_ids.add(f"payment:{pay}")
            if je:
                edge_set.add((f"journal:{je}", f"payment:{pay}", "CLEARED_BY"))

    # Fetch node details
    if not node_ids:
        return {"nodes": [], "edges": []}

    placeholders = ", ".join(["?"] * len(node_ids))
    node_rows = con.execute(
        f"SELECT node_id, node_type, label, properties FROM graph_nodes WHERE node_id IN ({placeholders})",
        list(node_ids),
    ).fetchall()

    nodes = [
        {"node_id": r[0], "node_type": r[1], "label": r[2],
         "properties": json.loads(r[3]) if isinstance(r[3], str) else r[3]}
        for r in node_rows
    ]

    edges = [
        {"source_id": s, "target_id": t, "edge_type": et, "properties": {}}
        for s, t, et in edge_set
    ]

    return {"nodes": nodes, "edges": edges}


def get_focus_subgraph(node_id: str) -> dict:
    """Return a business-meaningful subgraph focused on the given node.

    The behavior is entity-type-aware:
    - billing/delivery/journal/payment: find the related sales order(s)
      and return the full O2C flow, with this node as the focal point.
    - sales_order: return the full flow for this order.
    - customer: return the customer + up to 10 orders with their flows.
    - product: return the product + related orders (capped).
    """
    con = get_connection()
    parts = node_id.split(":")
    node_type = parts[0]
    entity_id = ":".join(parts[1:])

    # Map any transactional document back to its sales order(s)
    col_map = {
        "sales_order": "sales_order_id",
        "delivery": "delivery_id",
        "billing": "active_billing_id",
        "journal": "accounting_document_id",
        "payment": "clearing_document_id",
        "product": "product_id",
        "customer": "customer_id",
    }

    col = col_map.get(node_type)
    if not col:
        # Unknown type — fall back to neighbors
        return get_neighbors(node_id, max_depth=1, exclude_types={"product", "plant"})

    if node_type == "sales_order":
        return get_flow_subgraph(entity_id)

    if node_type in ("delivery", "billing", "journal", "payment"):
        # Find the related sales order and return its full flow
        rows = con.execute(
            f"SELECT DISTINCT sales_order_id FROM lineage_item_flow WHERE {col} = ?",
            [entity_id],
        ).fetchall()
        if not rows:
            return get_neighbors(node_id, max_depth=1, exclude_types={"product", "plant"})

        # Build combined flow for all related SOs (usually 1)
        all_nodes: dict[str, dict] = {}
        all_edges: set[tuple[str, str, str]] = set()
        for r in rows[:3]:  # cap at 3 SOs
            sg = get_flow_subgraph(r[0])
            for n in sg["nodes"]:
                all_nodes[n["node_id"]] = n
            for e in sg["edges"]:
                all_edges.add((e["source_id"], e["target_id"], e["edge_type"]))

        return {
            "nodes": list(all_nodes.values()),
            "edges": [{"source_id": s, "target_id": t, "edge_type": et, "properties": {}} for s, t, et in all_edges],
        }

    if node_type == "customer":
        # Customer + up to 10 orders with flows
        rows = con.execute(
            """SELECT DISTINCT sales_order_id FROM lineage_item_flow
               WHERE customer_id = ? LIMIT 10""",
            [entity_id],
        ).fetchall()
        all_nodes: dict[str, dict] = {}
        all_edges: set[tuple[str, str, str]] = set()
        for r in rows:
            sg = get_flow_subgraph(r[0])
            for n in sg["nodes"]:
                all_nodes[n["node_id"]] = n
            for e in sg["edges"]:
                all_edges.add((e["source_id"], e["target_id"], e["edge_type"]))
        return {
            "nodes": list(all_nodes.values()),
            "edges": [{"source_id": s, "target_id": t, "edge_type": et, "properties": {}} for s, t, et in all_edges],
        }

    if node_type == "product":
        # Product + up to 5 related orders
        rows = con.execute(
            """SELECT DISTINCT sales_order_id FROM lineage_item_flow
               WHERE product_id = ? LIMIT 5""",
            [entity_id],
        ).fetchall()
        all_nodes: dict[str, dict] = {}
        all_edges: set[tuple[str, str, str]] = set()
        # Add the product node itself
        pn = get_node(node_id)
        if pn:
            all_nodes[pn["node_id"]] = pn
        for r in rows:
            sg = get_flow_subgraph(r[0])
            for n in sg["nodes"]:
                all_nodes[n["node_id"]] = n
            for e in sg["edges"]:
                all_edges.add((e["source_id"], e["target_id"], e["edge_type"]))
        return {
            "nodes": list(all_nodes.values()),
            "edges": [{"source_id": s, "target_id": t, "edge_type": et, "properties": {}} for s, t, et in all_edges],
        }

    return get_neighbors(node_id, max_depth=1, exclude_types={"product", "plant"})


def search_nodes(query: str, node_type: str | None = None, limit: int = 20) -> list[dict]:
    """Search nodes by label or ID substring. Empty query lists by type."""
    con = get_connection()

    if not query:
        # Empty query: list nodes, optionally filtered by type
        if node_type:
            rows = con.execute(
                "SELECT node_id, node_type, label FROM graph_nodes WHERE node_type = ? ORDER BY label LIMIT ?",
                [node_type, limit],
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT node_id, node_type, label FROM graph_nodes ORDER BY label LIMIT ?",
                [limit],
            ).fetchall()
    else:
        search_term = f"%{query}%"
        if node_type:
            rows = con.execute(
                """
                SELECT node_id, node_type, label
                FROM graph_nodes
                WHERE node_type = ? AND (label ILIKE ? OR node_id ILIKE ?)
                ORDER BY label
                LIMIT ?
                """,
                [node_type, search_term, search_term, limit],
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT node_id, node_type, label
                FROM graph_nodes
                WHERE label ILIKE ? OR node_id ILIKE ?
                ORDER BY label
                LIMIT ?
                """,
                [search_term, search_term, limit],
            ).fetchall()

    return [{"node_id": r[0], "node_type": r[1], "label": r[2]} for r in rows]


def get_initial_graph() -> dict:
    """Return the complete O2C flow graph for all customers.

    Includes all customers, sales orders, deliveries, active billings,
    journals, and payments. Excludes products, plants, cancelled billings.
    """
    con = get_connection()

    # Get ALL lineage rows
    rows = con.execute("SELECT * FROM lineage_item_flow").fetchall()
    cols = [d[0] for d in con.execute("SELECT * FROM lineage_item_flow LIMIT 0").description]

    node_ids: set[str] = set()
    edge_set: set[tuple[str, str, str]] = set()

    for row in rows:
        r = dict(zip(cols, row))
        cust = r.get("customer_id")
        so = r.get("sales_order_id")
        prod = r.get("product_id")
        dl = r.get("delivery_id")
        bd = r.get("active_billing_id")
        je = r.get("accounting_document_id")
        pay = r.get("clearing_document_id")

        if cust: node_ids.add(f"customer:{cust}")
        if so:
            node_ids.add(f"sales_order:{so}")
            if cust: edge_set.add((f"customer:{cust}", f"sales_order:{so}", "PLACED_ORDER"))
        if prod:
            node_ids.add(f"product:{prod}")
            if so: edge_set.add((f"sales_order:{so}", f"product:{prod}", "CONTAINS_PRODUCT"))
        if dl:
            node_ids.add(f"delivery:{dl}")
            if so: edge_set.add((f"sales_order:{so}", f"delivery:{dl}", "FULFILLED_BY"))
        if bd:
            node_ids.add(f"billing:{bd}")
            if dl: edge_set.add((f"delivery:{dl}", f"billing:{bd}", "BILLED_AS"))
        if je:
            node_ids.add(f"journal:{je}")
            if bd: edge_set.add((f"billing:{bd}", f"journal:{je}", "POSTED_AS"))
        if pay:
            node_ids.add(f"payment:{pay}")
            if je: edge_set.add((f"journal:{je}", f"payment:{pay}", "CLEARED_BY"))

    if not node_ids:
        return {"nodes": [], "edges": []}

    # Fetch node details
    ph = ", ".join(["?"] * len(node_ids))
    node_rows = con.execute(
        f"SELECT node_id, node_type, label, properties FROM graph_nodes WHERE node_id IN ({ph})",
        list(node_ids),
    ).fetchall()

    nodes = [
        {"node_id": r[0], "node_type": r[1], "label": r[2],
         "properties": json.loads(r[3]) if isinstance(r[3], str) else r[3]}
        for r in node_rows
    ]

    edges = [
        {"source_id": s, "target_id": t, "edge_type": et, "properties": {}}
        for s, t, et in edge_set
    ]

    return {"nodes": nodes, "edges": edges}
