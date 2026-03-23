"""
Raw ingestion layer: load all JSONL files into DuckDB as raw tables.

All fields are preserved as strings to avoid losing leading zeros
on ERP-style identifiers. The only exception is fields that are
natively boolean or nested objects, which DuckDB infers automatically
from the JSON.

Each subfolder in the data directory becomes one table.
Multiple part files within a folder are concatenated.
"""

import json
from pathlib import Path

import duckdb

from config import DATA_DIR, DB_PATH


# Tables and their expected approximate row counts (for validation).
EXPECTED_TABLES = {
    "billing_document_cancellations": 80,
    "billing_document_headers": 163,
    "billing_document_items": 245,
    "business_partner_addresses": 8,
    "business_partners": 8,
    "customer_company_assignments": 8,
    "customer_sales_area_assignments": 28,
    "journal_entry_items_accounts_receivable": 123,
    "outbound_delivery_headers": 86,
    "outbound_delivery_items": 137,
    "payments_accounts_receivable": 120,
    "plants": 44,
    "product_descriptions": 69,
    "product_plants": 3036,
    "product_storage_locations": 16723,
    "products": 69,
    "sales_order_headers": 100,
    "sales_order_items": 167,
    "sales_order_schedule_lines": 179,
}


def ingest_all(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Load every JSONL folder into a raw DuckDB table.

    Returns a dict of table_name → row_count for validation.
    """
    results = {}

    for folder in sorted(DATA_DIR.iterdir()):
        if not folder.is_dir():
            continue

        table_name = f"raw_{folder.name}"
        jsonl_files = sorted(folder.glob("*.jsonl"))
        if not jsonl_files:
            continue

        # Read all part files and collect rows
        all_rows = []
        for jf in jsonl_files:
            with open(jf) as f:
                for line in f:
                    all_rows.append(json.loads(line.strip()))

        if not all_rows:
            continue

        # Create table from the collected rows.
        # We use read_json_auto with a UNION of all part files for efficiency,
        # but since we already parsed them, we insert via Python for control
        # over type handling.
        con.execute(f"DROP TABLE IF EXISTS {table_name}")

        # Let DuckDB infer schema from the JSON files directly — this is
        # more robust than manual column definitions and handles nested
        # objects (like time fields) correctly.
        file_list = [str(f) for f in jsonl_files]
        con.execute(
            f"""
            CREATE TABLE {table_name} AS
            SELECT * FROM read_json_auto(
                {file_list},
                format='newline_delimited',
                union_by_name=true
            )
            """
        )

        row_count = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
        results[folder.name] = row_count

    return results


def validate_ingestion(results: dict[str, int]) -> list[str]:
    """Check ingested row counts against expectations. Returns list of warnings."""
    warnings = []
    for table_name, expected in EXPECTED_TABLES.items():
        actual = results.get(table_name)
        if actual is None:
            warnings.append(f"MISSING: {table_name} was not ingested")
        elif actual != expected:
            warnings.append(
                f"COUNT MISMATCH: {table_name} expected {expected}, got {actual}"
            )
    for table_name in results:
        if table_name not in EXPECTED_TABLES:
            warnings.append(f"UNEXPECTED: {table_name} ({results[table_name]} rows)")
    return warnings


def run_ingestion():
    """Execute full ingestion pipeline with validation."""
    con = duckdb.connect(str(DB_PATH))
    try:
        print("Ingesting JSONL files into DuckDB...")
        results = ingest_all(con)

        print(f"\nIngested {len(results)} tables:")
        for name, count in sorted(results.items()):
            marker = ""
            expected = EXPECTED_TABLES.get(name)
            if expected and count != expected:
                marker = f"  ⚠ expected {expected}"
            print(f"  {name}: {count} rows{marker}")

        warnings = validate_ingestion(results)
        if warnings:
            print(f"\n⚠ {len(warnings)} validation warnings:")
            for w in warnings:
                print(f"  {w}")
        else:
            print("\n✓ All tables ingested with expected row counts.")

        return results
    finally:
        con.close()


if __name__ == "__main__":
    run_ingestion()
