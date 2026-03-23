"""Run the full data pipeline: ingest raw JSONL, build semantic layer."""

import sys
sys.path.insert(0, ".")

from db.ingest import run_ingestion
from db.semantic import run_semantic_build


def main():
    print("=" * 60)
    print("PHASE 1: Raw Ingestion")
    print("=" * 60)
    run_ingestion()

    print()
    print("=" * 60)
    print("PHASE 2: Semantic Layer")
    print("=" * 60)
    run_semantic_build()

    print()
    print("=" * 60)
    print("Pipeline complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
