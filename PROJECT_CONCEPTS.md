# Olist E-Commerce Data Warehouse — Concept Guide

A detailed explanation of every concept used in this project, with code snippets and rationale. This file is **not** pushed to GitHub.

---

## 1. Project Overview

We built a modern local batch data warehouse for the Olist Brazilian E-Commerce dataset (~100k orders, 112k order items).

**Goal:** Transform raw, unindexed operational data into a high-performance Kimball star-schema data warehouse that business teams can query without hitting the transactional database.

**Architecture (local, zero-cloud):**

```
Raw CSVs  -->  Python (duckdb)  -->  olist.duckdb (main_raw schema)
                                             |
                                     dbt Core (dbt-duckdb)
                                             |
                                 staging -> marts (star schema)
```

- **Storage & engine:** DuckDB (in-process, columnar, OLAP)
- **Transformation & modeling:** dbt Core + dbt-duckdb adapter
- **Ingestion:** Python (`duckdb`, `pandas`)
- **Visualization:** Plotly/Dash dashboard + Power BI/Tableau-ready Parquet exports

---

## 2. DuckDB — The Analytical Engine

DuckDB is an in-process, embedded SQL OLAP database. Unlike client-server databases (Postgres, MySQL), DuckDB runs inside your application process — no separate server to install or manage.

**Why DuckDB for this project:**
- Columnar storage + vectorized execution → fast analytical queries
- Zero configuration, single file (`olist.duckdb`)
- Supports modern PostgreSQL-like SQL
- dbt-duckdb adapter makes it a first-class dbt target

**Snippet — connecting and querying:**

```python
import duckdb

con = duckdb.connect('olist.duckdb', read_only=True)
df = con.execute("SELECT * FROM main_main.fct_order_items LIMIT 5").fetchdf()
con.close()
```

**Key file:** `olist.duckdb` (the entire warehouse lives in this one file).

---

## 3. dbt Core — Transformation Layer

dbt (data build tool) is the transformation layer. It lets us write SQL models, materialize them as views/tables, run tests, generate docs, and manage lineage — all with software-engineering best practices (version control, testing, documentation).

### dbt_project.yml

Controls model paths, materializations, schemas, and project hooks:

```yaml
models:
  olist_dbt:
    staging:
      +materialized: view
      +schema: main
    marts:
      +materialized: table
      +schema: main

on-run-start:
  - "CREATE SCHEMA IF NOT EXISTS main"
  - "CREATE SCHEMA IF NOT EXISTS main_raw"
  - "CREATE SCHEMA IF NOT EXISTS snapshots"
```

**Why schemas matter in DuckDB:** DuckDB uses schema as the catalog level. Our profile points to `schema: main`, so models land under `main_main` (database `main`, schema `main`) when queried via the catalog.

### Profiles

`~/.dbt/profiles.yml` connects dbt to the DuckDB file:

```yaml
olist_dbt:
  outputs:
    dev:
      type: duckdb
      path: /Users/.../olist.duckdb
      schema: main
      threads: 1
  target: dev
```

### Common dbt commands

```bash
# Build all models + run tests + run snapshots
dbt build --project-dir olist_dbt --full-refresh

# Run only tests
dbt test --project-dir olist_dbt

# Generate documentation
dbt docs generate --project-dir olist_dbt

# Serve docs locally
dbt docs serve --project-dir olist_dbt --port 8080
```

---

## 4. Data Modeling — Kimball Star Schema

We modeled the data as a **star schema**: one central fact table surrounded by dimension tables. This is optimized for analytical query performance and is easy for BI tools (Power BI, Tableau) to consume.

### Fact Table: `fct_order_items`

**Grain:** 1 row per order item within an order.

```sql
-- Surrogate key: order_id + order_item_id
concat(order_id, '-', lpad(order_item_id::varchar, 3, '0')) as order_item_key
```

**Metrics:** `price`, `freight_value`, `item_total_cost`, `delivery_delay_days`.

**Foreign keys:** `customer_key`, `product_key`, `seller_key`, `order_date_key`.

**Incremental strategy:** `delete+insert` with a 3-day lookback window. On each run, we delete rows from the last 3 days (relative to max `order_purchase_timestamp`) and re-insert them. This captures late-arriving delivery/status updates without a full refresh.

```jinja
{% if is_incremental() %}
where d.order_purchase_timestamp >= (
  select max(order_purchase_timestamp) - interval 3 days from {{ this }}
)
{% endif %}
```

### Dimension Tables

| Table | Grain | Key | Purpose |
|-------|-------|-----|---------|
| `dim_customers` | 1 per customer | `customer_key` (= `customer_unique_id`) | Latest customer geography |
| `dim_sellers` | 1 per seller | `seller_key` (= `seller_id`) | Seller location |
| `dim_products` | 1 per product | `product_key` (= `product_id`) | Category (PT + EN), dimensions, weight |
| `dim_date` | 1 per calendar date | `date_key` | Year, month, quarter, day-of-week, weekend flag |

**dim_date** is a generated date spine covering every date between the earliest order and latest estimated delivery. It enables time-based grouping without complex date math in every query.

**dim_products** joins to `stg_product_category_translation` to get English category names alongside the original Portuguese names.

---

## 5. SCD Type 2 — Tracking Historical Changes

**SCD (Slowly Changing Dimension) Type 2** preserves history by adding version rows with validity periods instead of overwriting.

We use a **dbt snapshot** (`snapshots/snapshot_customers.sql`) to track changes in customer zip code, city, and state over time:

```jinja
{{
  config(
    target_schema='snapshots',
    unique_key='customer_unique_id',
    strategy='timestamp',
    updated_at='customer_unique_id'
  )
}}

select
  customer_unique_id,
  customer_id,
  customer_zip_code_prefix,
  customer_city,
  customer_state
from {{ ref('stg_customers') }}
```

dbt adds `dbt_valid_from` and `dbt_valid_to` metadata columns. Historical reports can join to the snapshot as-of a specific order date to see the customer's location at that time.

> **Note:** `dbt snapshot` discovery had an issue in this dbt version (0 snapshot nodes found). The snapshot SQL is correct; invoke it explicitly if needed.

---

## 6. Staging Layer

Each raw table has a 1:1 staging view (`stg_*`) that:
- Casts data types explicitly (timestamps, decimals, ints)
- Trims/cleans dirty string fields
- Standardizes column names to snake_case

**Example — `stg_orders.sql`:**

```sql
select
  order_id,
  customer_id,
  order_status,
  cast(order_purchase_timestamp as timestamp) as order_purchase_timestamp,
  cast(order_approved_at as timestamp) as order_approved_at,
  cast(order_delivered_customer_date as timestamp) as order_delivered_customer_date,
  cast(order_estimated_delivery_date as timestamp) as order_estimated_delivery_date
from {{ source('olist_raw', 'raw_orders') }}
```

**Example — `stg_order_items.sql`:**

```sql
cast(price as decimal(18,2)) as price,
cast(freight_value as decimal(18,2)) as freight_value
```

---

## 7. Sources

`sources.yml` declares the raw tables in DuckDB's `main_raw` schema:

```yaml
sources:
  - name: olist_raw
    schema: main_raw
    tables:
      - name: raw_orders
      - name: raw_order_items
      - name: raw_customers
      - name: raw_products
      - name: raw_sellers
      - name: raw_payments
      - name: raw_reviews
      - name: raw_product_category_translation
      - name: raw_geolocation
```

**Important:** In DuckDB, sources should **not** specify a `database:` key — DuckDB uses the schema as the catalog. Specifying `database: main_raw` caused "Catalog 'main_raw' does not exist" errors.

---

## 8. Data Quality Framework

### Schema Tests (`models/schema.yml`)

Generic dbt tests applied to columns:

```yaml
models:
  - name: stg_orders
    columns:
      - name: order_id
        tests:
          - unique
          - not_null
      - name: order_status
        tests:
          - not_null
          - accepted_values:
              values: ['delivered', 'shipped', 'invoiced', 'created', 'approved', 'canceled', 'unavailable', 'processing']
  - name: fct_order_items
    columns:
      - name: order_item_key
        tests:
          - unique
          - not_null
      - name: customer_key
        tests:
          - relationships:
              to: ref('dim_customers')
              field: customer_key
```

| Test | What it checks |
|------|---------------|
| `unique` | No duplicate values in column |
| `not_null` | No NULL values |
| `accepted_values` | Value is in allowed list |
| `relationships` | Referential integrity (FK → PK) |

### Custom Singular Test (`tests/test_order_item_consistency.sql`)

Custom SQL that returns zero rows on success:

```sql
select
  order_item_key,
  price,
  freight_value,
  item_total_cost
from {{ ref('fct_order_items') }}
where item_total_cost is null
   or item_total_cost <> price + freight_value
```

**Important:** dbt custom tests fail if the query returns **any rows**. So we select the failing rows directly, not a `count(*)`.

> **Note:** Generic test arguments should be nested under `arguments:` in newer dbt versions (deprecation warning otherwise), but top-level arguments still work.

---

## 9. Ingestion Script (`ingest_raw.py`)

Reads all Olist CSVs and loads them into DuckDB's `main_raw` schema. Idempotent — drops and recreates tables on each run.

```python
import duckdb
from pathlib import Path

RAW_TABLES = {
    "olist_orders_dataset.csv": "raw_orders",
    "olist_order_items_dataset.csv": "raw_order_items",
    "olist_customers_dataset.csv": "raw_customers",
    # ... etc
}

con = duckdb.connect(str(DUCKDB_PATH))
con.execute("CREATE SCHEMA IF NOT EXISTS main_raw")
con.execute("USE main_raw")

for csv_file, table_name in RAW_TABLES.items():
    con.execute(f"DROP TABLE IF EXISTS {table_name}")
    con.execute(f"""
        CREATE TABLE {table_name} AS
        SELECT * FROM read_csv_auto('{csv_path}', header = true, ignore_errors = true)
    """)
```

Run with: `python3 ingest_raw.py`

---

## 10. Dashboard & Visualization

### Plotly/Dash (`dashboard.py`)

A Python web dashboard that reads Parquet exports and renders interactive charts:

- KPI cards: Total Revenue, Order Items, Customers, On-Time Rate, Avg Delivery Delay, Avg Review Score
- Revenue by Customer State, Monthly Revenue Trend
- Revenue by Seller State, Revenue by Product Category
- Delivery Delay Distribution, Review Score Distribution
- Delivery Delay vs Review Score scatter

Export to a standalone HTML file:

```bash
python3 dashboard.py --export
```

This creates `dashboard.html` — a self-contained file (Plotly loaded from CDN) that opens in any browser, no server needed.

### Parquet Exports (`pbi_export/`)

All mart tables are exported to Parquet for import into Power BI Desktop or Tableau:

```
pbi_export/
  dim_customers.parquet
  dim_date.parquet
  dim_products.parquet
  dim_sellers.parquet
  fct_order_items.parquet
  stg_orders.parquet
  stg_reviews.parquet
  stg_payments.parquet
```

### Power BI

- Free: Power BI Desktop (Windows)
- Connect: Get Data → Parquet → select files in `pbi_export/`
- Relationships: `fct_order_items.customer_key` → `dim_customers.customer_key`, etc.
- Measures use DAX: `SUM(fct_order_items[item_total_cost])`, `DISTINCTCOUNT(stg_orders[order_id])`

### Tableau

- Free option: Tableau Public (saves to cloud)
- Connect: To a File → Parquet
- Build calculated fields and dashboard sheets, publish to Tableau Public

---

## 11. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| DuckDB over Postgres/Snowflake | Zero cloud cost, local-first, single-file, in-process |
| Star schema over One Big Table | Better query performance, BI-tool friendly, dimensional modeling best practice |
| Incremental fact with lookback | Handles late-arriving delivery updates without full refresh |
| Snapshot for SCD2 | Preserves customer geography history for point-in-time accuracy |
| Parquet export for BI | Universal format, readable by Power BI/Tableau/Python/R |
| `delete+insert` incremental | Simple, reliable late-arriving data handling in DuckDB |

---

## 12. How to Run the Full Pipeline

```bash
# 1. (Re)load raw CSVs into DuckDB
python3 ingest_raw.py

# 2. Rebuild all dbt models + run tests
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
dbt build --project-dir olist_dbt --full-refresh

# 3. Export Parquet files for BI tools
mkdir -p pbi_export
python3 -c "
import duckdb, pandas as pd
con = duckdb.connect('olist.duckdb', read_only=True)
for t in ['dim_customers','dim_date','dim_products','dim_sellers','fct_order_items','stg_orders','stg_reviews','stg_payments']:
    con.execute(f'select * from main_main.{t}').fetchdf().to_parquet(f'pbi_export/{t}.parquet', index=False)
"

# 4. Generate & view dbt docs
dbt docs generate --project-dir olist_dbt
dbt docs serve --project-dir olist_dbt --port 8080

# 5. Export and open the dashboard
python3 dashboard.py --export
open dashboard.html
```

---

## 13. File Summary

| File | Purpose |
|------|---------|
| `ingest_raw.py` | CSV → DuckDB ingestion |
| `olist.duckdb` | The warehouse database |
| `olist_dbt/dbt_project.yml` | dbt project config |
| `~/.dbt/profiles.yml` | dbt connection profile |
| `olist_dbt/models/sources.yml` | Raw source declarations |
| `olist_dbt/models/staging/*.sql` | Cleaned staging views |
| `olist_dbt/models/marts/*.sql` | Fact + dimension tables |
| `olist_dbt/models/schema.yml` | Data quality tests |
| `olist_dbt/tests/test_order_item_consistency.sql` | Custom singular test |
| `olist_dbt/snapshots/snapshot_customers.sql` | SCD Type 2 snapshot |
| `olist_dbt/macros/date_macros.sql` | dbt macros |
| `dashboard.py` | Plotly/Dash dashboard |
| `dashboard.html` | Exported standalone dashboard |
| `pbi_export/*.parquet` | BI-tool-ready extracts |
| `index.html` | Project website (hosted on GitHub Pages) |

---

## 13. Alternative Technologies Considered (and Why Not Used)

| Component | What we used | Alternatives considered | Why not used |
|-----------|-------------|------------------------|--------------|
| **Analytical engine** | DuckDB | MySQL, PostgreSQL, Snowflake, BigQuery, ClickHouse | MySQL/PostgreSQL are row-oriented OLTP — slow on large scans/aggregations, need server setup. Snowflake/BigQuery are cloud data warehouses — cost money, need accounts, against zero-cloud goal. ClickHouse is great OLAP but heavier to run locally and dbt support is less mature than DuckDB. |
| **Transformation** | dbt Core | Apache Airflow, Prefect, Dagster, plain Python scripts | Airflow/Prefect/Dagster are orchestrators, not transformation frameworks — they schedule tasks but don't give you SQL models, lineage, tests, or docs out of the box. Plain Python scripts lack testing, documentation, and lineage tracking. |
| **Orchestration** | Manual (`dbt build`) | Apache Airflow, Prefect, Dagster, cron | Not needed yet — single local batch run. Adding an orchestrator adds infrastructure complexity for a weekend sprint. Can add cron/Airflow later for scheduled refreshes. |
| **Storage format** | Parquet + DuckDB file | CSV, JSON, SQLite, PostgreSQL | CSV/JSON have no schema enforcement or compression. SQLite is row-oriented and slow for analytics. PostgreSQL needs a server and is weaker at columnar scans. Parquet is compressed, columnar, and readable by every BI tool. |
| **BI / Dashboard** | Plotly/Dash (exported HTML) | Tableau Desktop, Power BI Desktop, Looker, Metabase | Tableau/Power BI are excellent but require desktop installs and (for sharing) paid cloud plans. Looker/Metabase need a running server. Plotly/Dash gives a zero-server, single-file HTML dashboard that runs anywhere. |
| **Query language** | SQL | Pandas, Polars, Spark | Pandas/Polars are Python-native and great, but SQL is the lingua franca of analytics, works with dbt, and is readable by BI tools. Spark is overkill for ~100k rows and needs a cluster. |
| **Deployment** | GitHub Pages (static HTML) | Netlify, Vercel, AWS S3, Tableau Cloud, Power BI Service | GitHub Pages is free, requires no build step for a static HTML file, and is already integrated with the repo. Others are also fine but add account setup. |

### Why not MySQL specifically?

MySQL is an **OLTP** (online transaction processing) database — optimized for inserting one order at a time, updating a single row, and serving a live website. It uses row-oriented storage and B-tree indexes.

This project is **OLAP** (online analytical processing) — scanning millions of rows, computing `SUM(price)`, joining fact to dimensions, grouping by date/state. DuckDB's columnar, vectorized engine does this orders of magnitude faster than MySQL on the same hardware, with zero server setup.

Use MySQL to run the e-commerce store. Use DuckDB to analyze it.

---

## 14. Future Considerations

- **Cloud storage:** As the database grows, move `olist.duckdb` and Parquet exports to S3-compatible storage (Cloudflare R2, AWS S3, GCS). DuckDB can query Parquet directly from S3 via the `httpfs` extension.
- **Incremental snapshots:** Schedule `dbt snapshot` runs to maintain SCD2 history over time.
- **Orchestration:** Wrap `ingest_raw.py` + `dbt build` in Airflow, Prefect, or a simple cron job for scheduled refreshes.
- **Authentication:** Never commit R2/AWS keys to git — use environment variables or a secrets manager.
