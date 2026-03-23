"""
Semantic layer: build validated link tables, dimensions, flow status,
lineage, and graph structures from the raw ingested tables.

Each link table is built and validated independently before being
composed into higher-level structures.
"""

import duckdb

from config import DB_PATH


# ---------------------------------------------------------------------------
# Link tables (pairwise, validated)
# ---------------------------------------------------------------------------

LINK_SO_DELIVERY_SQL = """
CREATE OR REPLACE TABLE link_so_delivery AS
SELECT
    soi.salesOrder              AS sales_order_id,
    CAST(soi.salesOrderItem AS INTEGER) AS so_item_number,
    dli.deliveryDocument        AS delivery_id,
    CAST(dli.deliveryDocumentItem AS INTEGER) AS dl_item_number
FROM raw_sales_order_items soi
JOIN raw_outbound_delivery_items dli
  ON soi.salesOrder = dli.referenceSdDocument
  AND CAST(soi.salesOrderItem AS INTEGER) = CAST(dli.referenceSdDocumentItem AS INTEGER)
"""

LINK_DELIVERY_BILLING_SQL = """
CREATE OR REPLACE TABLE link_delivery_billing AS
SELECT
    bdi.referenceSdDocument     AS delivery_id,
    CAST(bdi.referenceSdDocumentItem AS INTEGER) AS dl_item_number,
    bdi.billingDocument         AS billing_document_id,
    CAST(bdi.billingDocumentItem AS INTEGER) AS bd_item_number,
    bdh.billingDocumentIsCancelled AS is_cancelled,
    bdh.billingDocumentType     AS billing_type
FROM raw_billing_document_items bdi
JOIN raw_billing_document_headers bdh
  ON bdi.billingDocument = bdh.billingDocument
"""

CANCELLATION_PAIRS_SQL = """
CREATE OR REPLACE TABLE cancellation_pairs AS
SELECT DISTINCT
    canc.billing_document_id    AS cancelled_billing_id,
    repl.billing_document_id    AS replacement_billing_id,
    canc.delivery_id,
    canc.dl_item_number
FROM link_delivery_billing canc
JOIN link_delivery_billing repl
  ON canc.delivery_id = repl.delivery_id
  AND canc.dl_item_number = repl.dl_item_number
WHERE canc.is_cancelled = true
  AND repl.is_cancelled = false
  AND canc.billing_type = 'F2'
  AND repl.billing_type = 'S1'
"""

LINK_BILLING_JOURNAL_SQL = """
CREATE OR REPLACE TABLE link_billing_journal AS
SELECT
    je.referenceDocument            AS billing_document_id,
    je.accountingDocument           AS accounting_document_id,
    je.accountingDocumentItem       AS accounting_item,
    CAST(je.amountInTransactionCurrency AS DECIMAL(18,2)) AS amount,
    je.transactionCurrency          AS currency,
    je.glAccount                    AS gl_account,
    je.postingDate                  AS posting_date,
    je.customer                     AS customer_id,
    je.profitCenter                 AS profit_center
FROM raw_journal_entry_items_accounts_receivable je
"""

LINK_JOURNAL_PAYMENT_SQL = """
CREATE OR REPLACE TABLE link_journal_payment AS
SELECT
    je.accountingDocument           AS accounting_document_id,
    je.accountingDocumentItem       AS accounting_item,
    je.referenceDocument            AS billing_document_id,
    CAST(je.amountInTransactionCurrency AS DECIMAL(18,2)) AS amount,
    je.clearingAccountingDocument   AS clearing_document_id,
    je.clearingDate                 AS clearing_date,
    CASE
        WHEN je.clearingAccountingDocument IS NOT NULL
             AND je.clearingAccountingDocument != ''
        THEN true ELSE false
    END AS is_cleared
FROM raw_journal_entry_items_accounts_receivable je
"""

# ---------------------------------------------------------------------------
# Dimension tables
# ---------------------------------------------------------------------------

DIM_CUSTOMER_SQL = """
CREATE OR REPLACE TABLE dim_customer AS
SELECT
    bp.businessPartner              AS customer_id,
    bp.businessPartnerFullName      AS customer_name,
    bp.businessPartnerCategory      AS category,
    bp.creationDate                 AS created_date,
    bp.businessPartnerIsBlocked     AS is_blocked,
    addr.cityName                   AS city,
    addr.country                    AS country,
    addr.region                     AS region,
    addr.postalCode                 AS postal_code,
    addr.streetName                 AS street
FROM raw_business_partners bp
LEFT JOIN raw_business_partner_addresses addr
  ON bp.businessPartner = addr.businessPartner
"""

DIM_PRODUCT_SQL = """
CREATE OR REPLACE TABLE dim_product AS
SELECT
    p.product                       AS product_id,
    pd.productDescription           AS product_name,
    p.productType                   AS product_type,
    p.productGroup                  AS product_group,
    p.division                      AS division,
    CAST(p.grossWeight AS DECIMAL(18,3)) AS gross_weight,
    CAST(p.netWeight AS DECIMAL(18,3))   AS net_weight,
    p.weightUnit                    AS weight_unit,
    p.baseUnit                      AS base_unit,
    p.productOldId                  AS legacy_id
FROM raw_products p
LEFT JOIN raw_product_descriptions pd
  ON p.product = pd.product
  AND pd.language = 'EN'
"""

DIM_PLANT_SQL = """
CREATE OR REPLACE TABLE dim_plant AS
SELECT
    plant                           AS plant_id,
    plantName                       AS plant_name,
    salesOrganization               AS sales_organization,
    distributionChannel             AS distribution_channel,
    division,
    language
FROM raw_plants
"""

# ---------------------------------------------------------------------------
# Flow status (per sales order item)
# ---------------------------------------------------------------------------

FLOW_STATUS_SQL = """
CREATE OR REPLACE TABLE flow_status AS
WITH so_base AS (
    SELECT
        soi.salesOrder                          AS sales_order_id,
        CAST(soi.salesOrderItem AS INTEGER)     AS so_item_number,
        soi.material                            AS product_id,
        CAST(soi.netAmount AS DECIMAL(18,2))    AS order_amount,
        soi.transactionCurrency                 AS currency,
        soh.soldToParty                         AS customer_id,
        soh.creationDate                        AS order_date
    FROM raw_sales_order_items soi
    JOIN raw_sales_order_headers soh ON soi.salesOrder = soh.salesOrder
),
-- Step through the chain, aggregating per SO item
step_delivery AS (
    SELECT
        lsd.sales_order_id,
        lsd.so_item_number,
        lsd.delivery_id,
        dlh.actualGoodsMovementDate IS NOT NULL AS has_goods_movement
    FROM link_so_delivery lsd
    JOIN raw_outbound_delivery_headers dlh
      ON lsd.delivery_id = dlh.deliveryDocument
),
step_billing AS (
    SELECT
        lsd.sales_order_id,
        lsd.so_item_number,
        MAX(CASE WHEN NOT ldb.is_cancelled THEN ldb.billing_document_id END) AS active_billing_id,
        bool_or(NOT ldb.is_cancelled)           AS has_billing_active,
        bool_or(ldb.is_cancelled)               AS has_billing_cancelled
    FROM link_so_delivery lsd
    JOIN link_delivery_billing ldb
      ON lsd.delivery_id = ldb.delivery_id
      AND lsd.dl_item_number = ldb.dl_item_number
    GROUP BY lsd.sales_order_id, lsd.so_item_number
),
step_journal AS (
    SELECT
        sb.sales_order_id,
        sb.so_item_number,
        lbj.accounting_document_id,
        lbj.amount                              AS posted_amount,
        lbj.posting_date
    FROM step_billing sb
    JOIN link_billing_journal lbj
      ON sb.active_billing_id = lbj.billing_document_id
    WHERE sb.has_billing_active
),
step_payment AS (
    SELECT
        sj.sales_order_id,
        sj.so_item_number,
        ljp.clearing_document_id,
        ljp.clearing_date,
        ljp.is_cleared
    FROM step_journal sj
    JOIN link_journal_payment ljp
      ON sj.accounting_document_id = ljp.accounting_document_id
)
SELECT
    sb.sales_order_id,
    sb.so_item_number,
    sb.product_id,
    sb.order_amount,
    sb.currency,
    sb.customer_id,
    sb.order_date,
    -- Raw boolean indicators
    sd.delivery_id IS NOT NULL                  AS has_delivery,
    COALESCE(sd.has_goods_movement, false)       AS has_goods_movement,
    COALESCE(sbi.has_billing_active, false)      AS has_billing_active,
    COALESCE(sbi.has_billing_cancelled, false)   AS has_billing_cancelled,
    sj.accounting_document_id IS NOT NULL        AS has_journal_entry,
    COALESCE(sp.is_cleared, false)               AS is_cleared,
    -- Key IDs for tracing
    sd.delivery_id,
    sbi.active_billing_id,
    sj.accounting_document_id,
    sp.clearing_document_id,
    sp.clearing_date,
    -- Derived status: furthest stage reached in O2C chain
    -- Goods movement is orthogonal (tracked as separate boolean)
    CASE
        WHEN sd.delivery_id IS NULL
            THEN 'ordered_only'
        WHEN sd.delivery_id IS NOT NULL
             AND NOT COALESCE(sbi.has_billing_active, false)
             AND NOT COALESCE(sbi.has_billing_cancelled, false)
            THEN 'delivered_not_billed'
        WHEN COALESCE(sbi.has_billing_cancelled, false)
             AND NOT COALESCE(sbi.has_billing_active, false)
            THEN 'cancelled'
        WHEN COALESCE(sbi.has_billing_active, false)
             AND sj.accounting_document_id IS NULL
            THEN 'billed_no_posting'
        WHEN sj.accounting_document_id IS NOT NULL
             AND NOT COALESCE(sp.is_cleared, false)
            THEN 'posted_not_paid'
        WHEN COALESCE(sp.is_cleared, false)
            THEN 'complete'
        ELSE 'partial'
    END AS flow_status
FROM so_base sb
LEFT JOIN step_delivery sd
  ON sb.sales_order_id = sd.sales_order_id
  AND sb.so_item_number = sd.so_item_number
LEFT JOIN step_billing sbi
  ON sb.sales_order_id = sbi.sales_order_id
  AND sb.so_item_number = sbi.so_item_number
LEFT JOIN step_journal sj
  ON sb.sales_order_id = sj.sales_order_id
  AND sb.so_item_number = sj.so_item_number
LEFT JOIN step_payment sp
  ON sb.sales_order_id = sp.sales_order_id
  AND sb.so_item_number = sp.so_item_number
"""

# ---------------------------------------------------------------------------
# Lineage item flow (composed from validated links)
# ---------------------------------------------------------------------------

LINEAGE_ITEM_FLOW_SQL = """
CREATE OR REPLACE TABLE lineage_item_flow AS
SELECT
    soi.salesOrder                              AS sales_order_id,
    CAST(soi.salesOrderItem AS INTEGER)         AS so_item_number,
    soh.soldToParty                             AS customer_id,
    soi.material                                AS product_id,
    CAST(soi.requestedQuantity AS DECIMAL(18,2)) AS ordered_qty,
    CAST(soi.netAmount AS DECIMAL(18,2))        AS order_amount,
    soi.transactionCurrency                     AS currency,
    soi.productionPlant                         AS plant_id,
    soh.creationDate                            AS order_date,

    lsd.delivery_id,
    lsd.dl_item_number,
    dlh.creationDate                            AS delivery_date,
    CAST(dli.actualDeliveryQuantity AS DECIMAL(18,2)) AS delivered_qty,
    dlh.actualGoodsMovementDate                 AS goods_movement_date,
    dlh.overallGoodsMovementStatus              AS gm_status,

    ldb_active.billing_document_id              AS active_billing_id,
    ldb_active.billing_type                     AS active_billing_type,
    bdh_active.billingDocumentDate              AS billing_date,
    CAST(bdh_active.totalNetAmount AS DECIMAL(18,2)) AS billed_amount,

    cp.cancelled_billing_id,

    lbj.accounting_document_id,
    lbj.amount                                  AS posted_amount,
    lbj.posting_date,
    lbj.gl_account,

    ljp.clearing_document_id,
    ljp.clearing_date,
    ljp.is_cleared

FROM raw_sales_order_items soi
JOIN raw_sales_order_headers soh
  ON soi.salesOrder = soh.salesOrder
LEFT JOIN link_so_delivery lsd
  ON soi.salesOrder = lsd.sales_order_id
  AND CAST(soi.salesOrderItem AS INTEGER) = lsd.so_item_number
LEFT JOIN raw_outbound_delivery_headers dlh
  ON lsd.delivery_id = dlh.deliveryDocument
LEFT JOIN raw_outbound_delivery_items dli
  ON lsd.delivery_id = dli.deliveryDocument
  AND lsd.dl_item_number = CAST(dli.deliveryDocumentItem AS INTEGER)
LEFT JOIN link_delivery_billing ldb_active
  ON lsd.delivery_id = ldb_active.delivery_id
  AND lsd.dl_item_number = ldb_active.dl_item_number
  AND ldb_active.is_cancelled = false
LEFT JOIN raw_billing_document_headers bdh_active
  ON ldb_active.billing_document_id = bdh_active.billingDocument
LEFT JOIN cancellation_pairs cp
  ON ldb_active.delivery_id = cp.delivery_id
  AND ldb_active.dl_item_number = cp.dl_item_number
LEFT JOIN link_billing_journal lbj
  ON ldb_active.billing_document_id = lbj.billing_document_id
LEFT JOIN link_journal_payment ljp
  ON lbj.accounting_document_id = ljp.accounting_document_id
  AND lbj.accounting_item = ljp.accounting_item
"""

# ---------------------------------------------------------------------------
# Graph nodes and edges
# ---------------------------------------------------------------------------

GRAPH_NODES_SQL = """
CREATE OR REPLACE TABLE graph_nodes AS

-- Customer nodes
SELECT
    'customer:' || customer_id      AS node_id,
    'customer'                      AS node_type,
    customer_name                   AS label,
    json_object(
        'city', city,
        'country', country,
        'region', region,
        'is_blocked', is_blocked
    ) AS properties
FROM dim_customer

UNION ALL

-- Product nodes
SELECT
    'product:' || product_id        AS node_id,
    'product'                       AS node_type,
    COALESCE(product_name, product_id) AS label,
    json_object(
        'type', product_type,
        'group', product_group,
        'weight', gross_weight,
        'unit', base_unit
    ) AS properties
FROM dim_product

UNION ALL

-- Plant nodes
SELECT
    'plant:' || plant_id            AS node_id,
    'plant'                         AS node_type,
    plant_name                      AS label,
    json_object(
        'sales_org', sales_organization
    ) AS properties
FROM dim_plant

UNION ALL

-- Sales order nodes
SELECT DISTINCT
    'sales_order:' || salesOrder    AS node_id,
    'sales_order'                   AS node_type,
    'SO ' || salesOrder             AS label,
    json_object(
        'date', creationDate,
        'amount', totalNetAmount,
        'currency', transactionCurrency,
        'delivery_status', overallDeliveryStatus,
        'customer', soldToParty
    ) AS properties
FROM raw_sales_order_headers

UNION ALL

-- Delivery nodes
SELECT DISTINCT
    'delivery:' || deliveryDocument AS node_id,
    'delivery'                      AS node_type,
    'DL ' || deliveryDocument       AS label,
    json_object(
        'date', creationDate,
        'gm_status', overallGoodsMovementStatus,
        'gm_date', actualGoodsMovementDate,
        'picking_status', overallPickingStatus
    ) AS properties
FROM raw_outbound_delivery_headers

UNION ALL

-- Billing document nodes
SELECT DISTINCT
    'billing:' || billingDocument   AS node_id,
    'billing'                       AS node_type,
    CASE WHEN billingDocumentIsCancelled THEN 'CANC ' ELSE 'INV ' END || billingDocument AS label,
    json_object(
        'date', billingDocumentDate,
        'amount', totalNetAmount,
        'currency', transactionCurrency,
        'type', billingDocumentType,
        'is_cancelled', billingDocumentIsCancelled,
        'company_code', companyCode
    ) AS properties
FROM raw_billing_document_headers

UNION ALL

-- Journal entry nodes
SELECT DISTINCT
    'journal:' || accounting_document_id AS node_id,
    'journal'                       AS node_type,
    'JE ' || accounting_document_id AS label,
    json_object(
        'amount', amount,
        'currency', currency,
        'posting_date', posting_date,
        'gl_account', gl_account
    ) AS properties
FROM link_billing_journal

UNION ALL

-- Payment/clearing nodes (only distinct clearing docs)
SELECT DISTINCT
    'payment:' || clearing_document_id AS node_id,
    'payment'                       AS node_type,
    'PAY ' || clearing_document_id  AS label,
    json_object(
        'clearing_date', clearing_date
    ) AS properties
FROM link_journal_payment
WHERE is_cleared = true
"""

GRAPH_EDGES_SQL = """
CREATE OR REPLACE TABLE graph_edges AS

-- Customer → Sales Order (PLACED_ORDER)
SELECT DISTINCT
    'customer:' || soh.soldToParty  AS source_id,
    'sales_order:' || soh.salesOrder AS target_id,
    'PLACED_ORDER'                  AS edge_type,
    json_object('date', soh.creationDate) AS properties
FROM raw_sales_order_headers soh

UNION ALL

-- Sales Order → Product (CONTAINS_PRODUCT)
SELECT DISTINCT
    'sales_order:' || soi.salesOrder AS source_id,
    'product:' || soi.material      AS target_id,
    'CONTAINS_PRODUCT'              AS edge_type,
    json_object(
        'quantity', soi.requestedQuantity,
        'amount', soi.netAmount
    ) AS properties
FROM raw_sales_order_items soi

UNION ALL

-- Sales Order → Delivery (FULFILLED_BY)
SELECT DISTINCT
    'sales_order:' || lsd.sales_order_id AS source_id,
    'delivery:' || lsd.delivery_id  AS target_id,
    'FULFILLED_BY'                  AS edge_type,
    '{}' AS properties
FROM link_so_delivery lsd

UNION ALL

-- Sales Order → Plant (SHIPS_FROM)
SELECT DISTINCT
    'sales_order:' || soi.salesOrder AS source_id,
    'plant:' || soi.productionPlant AS target_id,
    'SHIPS_FROM'                    AS edge_type,
    '{}' AS properties
FROM raw_sales_order_items soi
WHERE soi.productionPlant IS NOT NULL AND soi.productionPlant != ''

UNION ALL

-- Delivery → Billing (BILLED_AS) — active billing only
SELECT DISTINCT
    'delivery:' || ldb.delivery_id  AS source_id,
    'billing:' || ldb.billing_document_id AS target_id,
    'BILLED_AS'                     AS edge_type,
    json_object('type', ldb.billing_type) AS properties
FROM link_delivery_billing ldb
WHERE ldb.is_cancelled = false

UNION ALL

-- Cancelled billing → Replacement billing (CANCELLED_BY)
SELECT DISTINCT
    'billing:' || cp.cancelled_billing_id AS source_id,
    'billing:' || cp.replacement_billing_id AS target_id,
    'CANCELLED_BY'                  AS edge_type,
    '{}' AS properties
FROM cancellation_pairs cp

UNION ALL

-- Billing → Journal Entry (POSTED_AS)
SELECT DISTINCT
    'billing:' || lbj.billing_document_id AS source_id,
    'journal:' || lbj.accounting_document_id AS target_id,
    'POSTED_AS'                     AS edge_type,
    json_object('amount', lbj.amount) AS properties
FROM link_billing_journal lbj

UNION ALL

-- Journal Entry → Payment (CLEARED_BY)
SELECT DISTINCT
    'journal:' || ljp.accounting_document_id AS source_id,
    'payment:' || ljp.clearing_document_id AS target_id,
    'CLEARED_BY'                    AS edge_type,
    json_object('clearing_date', ljp.clearing_date) AS properties
FROM link_journal_payment ljp
WHERE ljp.is_cleared = true
"""

# ---------------------------------------------------------------------------
# Validation queries
# ---------------------------------------------------------------------------

VALIDATIONS = {
    "link_so_delivery_count": (
        "SELECT count(*) FROM link_so_delivery",
        137,
        "expected 137 rows (1:1 SO item to delivery item)"
    ),
    "link_so_delivery_cardinality": (
        """SELECT count(*) FROM (
            SELECT sales_order_id, so_item_number, count(*)
            FROM link_so_delivery
            GROUP BY 1, 2
            HAVING count(*) > 1
        )""",
        0,
        "expected 0 duplicates (strict 1:1)"
    ),
    "link_delivery_billing_count": (
        "SELECT count(*) FROM link_delivery_billing",
        245,
        "expected 245 rows (124 deliveries × ~2 billing docs)"
    ),
    "link_delivery_billing_active_count": (
        "SELECT count(*) FROM link_delivery_billing WHERE is_cancelled = false",
        124,
        "expected 124 active billing items (245 total - 121 cancelled)"
    ),
    "cancellation_pairs_count": (
        "SELECT count(*) FROM cancellation_pairs",
        121,
        "expected ~121 cancelled-replacement pairs"
    ),
    "link_billing_journal_count": (
        "SELECT count(*) FROM link_billing_journal",
        123,
        "expected 123 journal entries"
    ),
    "link_journal_payment_cleared": (
        "SELECT count(*) FROM link_journal_payment WHERE is_cleared = true",
        120,
        "expected 120 cleared payments"
    ),
    "link_journal_payment_open": (
        "SELECT count(*) FROM link_journal_payment WHERE is_cleared = false",
        3,
        "expected 3 open receivables"
    ),
    "dim_customer_count": (
        "SELECT count(*) FROM dim_customer",
        8,
        "expected 8 customers"
    ),
    "dim_product_count": (
        "SELECT count(*) FROM dim_product",
        69,
        "expected 69 products"
    ),
    "dim_plant_count": (
        "SELECT count(*) FROM dim_plant",
        44,
        "expected 44 plants"
    ),
    "flow_status_total": (
        "SELECT count(*) FROM flow_status",
        167,
        "expected 167 rows (one per SO item)"
    ),
    "lineage_item_flow_total": (
        "SELECT count(*) FROM lineage_item_flow",
        167,
        "expected 167 rows (one per SO item)"
    ),
    "graph_nodes_nonzero": (
        "SELECT count(*) FROM graph_nodes",
        None,  # just check > 0
        "expected non-zero graph nodes"
    ),
    "graph_edges_nonzero": (
        "SELECT count(*) FROM graph_edges",
        None,
        "expected non-zero graph edges"
    ),
    "graph_nodes_no_duplicates": (
        "SELECT count(*) FROM (SELECT node_id FROM graph_nodes GROUP BY node_id HAVING count(*) > 1)",
        0,
        "expected 0 duplicate node_ids in graph_nodes"
    ),
    "graph_edges_no_duplicates": (
        "SELECT count(*) FROM (SELECT source_id, target_id, edge_type FROM graph_edges GROUP BY 1,2,3 HAVING count(*) > 1)",
        0,
        "expected 0 duplicate edges in graph_edges"
    ),
}


# ---------------------------------------------------------------------------
# Build all
# ---------------------------------------------------------------------------

BUILD_ORDER = [
    ("link_so_delivery", LINK_SO_DELIVERY_SQL),
    ("link_delivery_billing", LINK_DELIVERY_BILLING_SQL),
    ("cancellation_pairs", CANCELLATION_PAIRS_SQL),
    ("link_billing_journal", LINK_BILLING_JOURNAL_SQL),
    ("link_journal_payment", LINK_JOURNAL_PAYMENT_SQL),
    ("dim_customer", DIM_CUSTOMER_SQL),
    ("dim_product", DIM_PRODUCT_SQL),
    ("dim_plant", DIM_PLANT_SQL),
    ("flow_status", FLOW_STATUS_SQL),
    ("lineage_item_flow", LINEAGE_ITEM_FLOW_SQL),
    ("graph_nodes", GRAPH_NODES_SQL),
    ("graph_edges", GRAPH_EDGES_SQL),
]


def build_semantic_layer(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Build all semantic tables in dependency order. Returns table→row_count."""
    results = {}
    for name, sql in BUILD_ORDER:
        print(f"  Building {name}...")
        con.execute(sql)
        count = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        results[name] = count
        print(f"    → {count} rows")
    return results


def validate_semantic_layer(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Run all validation checks. Returns list of failures."""
    failures = []
    for check_name, (sql, expected, desc) in VALIDATIONS.items():
        actual = con.execute(sql).fetchone()[0]
        if expected is not None:
            if actual != expected:
                failures.append(
                    f"FAIL {check_name}: got {actual}, {desc}"
                )
        else:
            if actual == 0:
                failures.append(f"FAIL {check_name}: got 0, {desc}")
    return failures


def run_semantic_build():
    """Execute full semantic layer build with validation."""
    con = duckdb.connect(str(DB_PATH))
    try:
        print("Building semantic layer...")
        results = build_semantic_layer(con)

        print("\nRunning validation checks...")
        failures = validate_semantic_layer(con)
        if failures:
            print(f"\n⚠ {len(failures)} validation failures:")
            for f in failures:
                print(f"  {f}")
        else:
            print("\n✓ All validation checks passed.")

        # Print flow status distribution
        print("\nFlow status distribution:")
        rows = con.execute(
            "SELECT flow_status, count(*) AS n FROM flow_status GROUP BY 1 ORDER BY n DESC"
        ).fetchall()
        for status, count in rows:
            print(f"  {status}: {count}")

        # Print graph summary
        print("\nGraph summary:")
        node_types = con.execute(
            "SELECT node_type, count(*) FROM graph_nodes GROUP BY 1 ORDER BY 1"
        ).fetchall()
        for t, c in node_types:
            print(f"  Nodes - {t}: {c}")
        edge_types = con.execute(
            "SELECT edge_type, count(*) FROM graph_edges GROUP BY 1 ORDER BY 1"
        ).fetchall()
        for t, c in edge_types:
            print(f"  Edges - {t}: {c}")

        return results
    finally:
        con.close()


if __name__ == "__main__":
    run_semantic_build()
