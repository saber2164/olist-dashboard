"""Phase 1: Ingest raw Olist CSVs into DuckDB main_raw schema.

Run:
    python3 ingest_raw.py

This script creates olist.duckdb (in the project root) and loads all raw
CSV datasets into the main_raw schema as DuckDB tables. It is idempotent:
tables are dropped and recreated on each run so you can re-run safely
during iterative development.
"""

from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent
CSV_DIR = PROJECT_ROOT / "olist_data"
DUCKDB_PATH = PROJECT_ROOT / "olist.duckdb"

# Map CSV filenames to raw table names in main_raw schema
RAW_TABLES = {
    "olist_customers_dataset.csv": "raw_customers",
    "olist_geolocation_dataset.csv": "raw_geolocation",
    "olist_order_items_dataset.csv": "raw_order_items",
    "olist_order_payments_dataset.csv": "raw_payments",
    "olist_order_reviews_dataset.csv": "raw_reviews",
    "olist_orders_dataset.csv": "raw_orders",
    "olist_products_dataset.csv": "raw_products",
    "olist_sellers_dataset.csv": "raw_sellers",
    "product_category_name_translation.csv": "raw_product_category_translation",
}


def main() -> None:
    if DUCKDB_PATH.exists():
        DUCKDB_PATH.unlink()

    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS main_raw")
        con.execute("USE main_raw")

        for csv_file, table_name in RAW_TABLES.items():
            csv_path = CSV_DIR / csv_file
            if not csv_path.exists():
                print(f"WARNING: {csv_path} not found, skipping {table_name}")
                continue

            con.execute(f"DROP TABLE IF EXISTS {table_name}")
            con.execute(
                f"""
                CREATE TABLE {table_name} AS
                SELECT * FROM read_csv_auto(
                    '{csv_path}',
                    header = true,
                    ignore_errors = true
                )
                """
            )
            count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            print(f"Loaded {table_name}: {count:,} rows from {csv_file}")

        print(f"\nDone. Raw tables loaded into DuckDB at {DUCKDB_PATH}")
        print("Next step: run `dbt init olist_dbt` to scaffold the dbt project.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
