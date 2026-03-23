from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "sap-o2c-data"
DB_PATH = PROJECT_ROOT / "backend" / "o2c.duckdb"
