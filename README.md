# Olist E-Commerce Analytics

Interactive analytics dashboard for the Olist Brazilian E-Commerce dataset, built on a modern local batch warehouse (DuckDB + dbt).

**Live Site:** https://saber2164.github.io/olist-dashboard/
**Dashboard:** https://saber2164.github.io/olist-dashboard/dashboard.html

---

# System Architecture Design Document

## 1. System Architecture

```mermaid
graph TD
    A[Raw CSV Files<br/>Olist Dataset] --> B[Python Ingestion Script<br/>ingest_raw.py]
    B --> C[DuckDB Local Database<br/>olist.duckdb<br/>main_raw Schema]
    C --> D[dbt Core + dbt-duckdb]
    D --> E[Staging Models<br/>stg_* - Views]
    E --> F[Marts<br/>fct_order_items - Fact Table (Incremental)]
    E --> G[dim_customers - Dimension]
    E --> H[dim_sellers - Dimension]
    E --> I[dim_products - Dimension]
    E --> J[dim_date - Dimension]
    F --> K[Data Quality Tests<br/>schema.yml + Custom Tests]
    F --> L[Snapshot: snap_customers<br/>SCD Type 2]
    M[dbt Docs<br/>Lineage & Catalog]
    N[Parquet Exports<br/>pbi_export/]
    O[Power BI / Tableau<br/>Dashboards]
    P[Plotly/Dash Dashboard<br/>dashboard.html]
    K --> M
    N --> O
    N --> P
```

**Data Flow:**
1. Raw Olist CSVs → `ingest_raw.py` → DuckDB `main_raw` schema
2. dbt staging models clean and type-cast raw tables into views
3. dbt mart models build the star schema (fact + dimensions)
4. Data quality tests validate every model
5. Snapshot tracks customer geography changes (SCD Type 2)
6. Parquet exports feed BI tools; dashboard HTML serves standalone analytics

---

## 2. Table Grain Definitions

| Table | Type | Grain | Primary Key |
|-------|------|-------|-------------|
| `fct_order_items` | Fact | 1 row per order item within an order | `order_item_key` (surrogate: order_id + order_item_id) |
| `dim_customers` | Dimension | 1 row per unique customer | `customer_id` |
| `dim_sellers` | Dimension | 1 row per unique seller | `seller_id` |
| `dim_products` | Dimension | 1 row per unique product | `product_id` |
| `dim_date` | Dimension | 1 row per calendar date | `date_key` |
| `stg_*` | Staging | 1:1 with raw source table | Natural key of source |

---

## 3. Incremental Strategy & Late-Arriving Data

The `fct_order_items` fact table uses **incremental materialization** with a **3-day dynamic lookback window**:

```jinja
{% if is_incremental() %}
    WHERE o.order_purchase_timestamp >= (
        SELECT COALESCE(MAX(order_purchase_timestamp), '1900-01-01'::TIMESTAMP) - INTERVAL '3 DAYS'
        FROM {{ this }}
    )
{% endif %}
```

**How it works:**
- On first run: full table build
- On subsequent runs: only rows where `order_purchase_timestamp` is within the last 3 days (relative to max timestamp already in the table) are deleted and re-inserted
- This captures late-arriving order status/delivery updates without a full table refresh
- `on_schema_change='append_new_columns'` handles schema evolution gracefully

---

## 4. SCD Type 2 Implementation

The `snap_customers` snapshot tracks customer geography changes over time using `dbt snapshot` with `strategy='check'`:

```sql
{% snapshot snap_customers %}

{{
    config(
      target_schema='snapshots',
      unique_key='customer_id',
      strategy='check',
      check_cols=['customer_zip_code_prefix', 'customer_city', 'customer_state'],
      invalidate_hard_deletes=True
    )
}}

SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
FROM {{ ref('stg_customers') }}

{% endsnapshot %}
```

**How it works:**
- `unique_key='customer_id'` identifies the business key
- `strategy='check'` compares `check_cols` to detect changes
- When a customer's zip code, city, or state changes, dbt expires the old record (sets `dbt_valid_to`) and inserts a new record (sets `dbt_valid_from`)
- `invalidate_hard_deletes=True` marks records that no longer exist in the source as expired
- dbt adds `dbt_valid_from` and `dbt_valid_to` metadata columns for point-in-time queries

---

## 5. Data Quality Framework

### Schema Tests (`models/schema.yml`)

| Test | Applied To | Purpose |
|------|-----------|---------|
| `unique` | `order_item_key`, `customer_id` | No duplicate primary keys |
| `not_null` | All critical columns | No missing required values |
| `accepted_values` | `order_status` | Value is in allowed domain |
| `relationships` | `product_id`, `seller_id` | Referential integrity to source tables |

### Custom Singular Test (`tests/assert_order_total_matches_items.sql`)

Validates that no order has a non-positive total item cost:

```sql
SELECT
    order_id,
    SUM(price) AS total_price,
    SUM(freight_value) AS total_freight,
    SUM(total_item_cost) AS total_calculated
FROM {{ ref('fct_order_items') }}
GROUP BY order_id
HAVING SUM(total_item_cost) <= 0
```

Returns zero rows on success; any returned row indicates a data quality failure.

---

## 6. Trade-offs & Scalability

### Why DuckDB?

- **Zero cloud cost:** Runs entirely in-process, no server infrastructure
- **Vectorized execution:** Columnar storage optimized for analytical queries
- **Single file:** Entire warehouse in `olist.duckdb` — easy backup and versioning
- **dbt-native:** First-class `dbt-duckdb` adapter with full SQL and dbt standards

### Scalability to 100x Volume

**Transition strategy from local DuckDB:**

| Stage | Storage | Compute | Tooling |
|-------|---------|---------|---------|
| Current (local) | `olist.duckdb` file | Local CPU/memory | dbt + Python |
| Scale-up | AWS S3 (Parquet) | DuckDB + Athena | `httpfs` extension for S3 queries |
| Enterprise | Snowflake / BigQuery | Cloud data warehouse | dbt-snowflake / dbt-bigquery |

**Migration path:** Export marts to Parquet on S3 → query with DuckDB `httpfs` → eventually migrate models to Snowflake/BigQuery with minimal SQL changes (dbt abstraction layer).

---

## 7. CI/CD Pipeline

GitHub Actions (`.github/workflows/dbt_ci.yml`) runs on every PR and push to `main`:

1. Checkout code
2. Set up Python 3.10
3. Install `dbt-duckdb` and `pandas`
4. Install dbt packages (`dbt deps`)
5. Ingest raw CSVs into DuckDB (`python ingest_raw.py`)
6. Run `dbt build` — builds all models and runs all data quality tests

Any test failure blocks the merge/deploy.

---

## 8. Project Structure

```
olist-dashboard/
├── ingest_raw.py              # Python: CSV → DuckDB ingestion
├── dashboard.py               # Python: Plotly/Dash dashboard generator
├── dashboard.html             # Exported standalone dashboard
├── index.html                 # Project website (Apple-inspired design)
├── PROJECT_CONCEPTS.md        # Detailed concept guide (not pushed)
├── .github/workflows/dbt_ci.yml
│   └── CI/CD pipeline
├── olist_dbt/
│   ├── dbt_project.yml        # dbt project configuration
│   ├── packages.yml           # dbt-utils dependency
│   ├── models/
│   │   ├── schema.yml         # Data quality tests
│   │   ├── staging/           # stg_* view models (cleaned, typed)
│   │   └── marts/             # dim_* + fct_order_items
│   ├── snapshots/
│   │   └── snap_customers.sql # SCD Type 2 snapshot
│   ├── tests/
│   │   └── assert_order_total_matches_items.sql
│   ├── macros/
│   │   └── date_macros.sql
│   └── target/                # Compiled output (gitignored)
├── pbi_export/                # Parquet extracts for BI tools (gitignored)
├── olist_data/                # Raw CSVs (gitignored - download from Kaggle)
└── olist.duckdb               # Warehouse database (gitignored)
```

---

## 9. How to Run

```bash
# 1. Clone the repository
git clone https://github.com/saber2164/olist-dashboard.git
cd olist-dashboard

# 2. Download raw data (not in repo - see Kaggle link above)
# Extract into olist_data/

# 3. Ingest raw data
python3 ingest_raw.py

# 4. Install dbt dependencies
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
dbt deps --project-dir olist_dbt

# 5. Build warehouse + run all tests
dbt build --project-dir olist_dbt --full-refresh

# 6. Export Parquet for BI tools
# (run the Python export script)

# 7. Generate dashboard
python3 dashboard.py --export

# 8. View dbt docs
dbt docs generate --project-dir olist_dbt
dbt docs serve --project-dir olist_dbt --port 8080
```

---

## 10. License

MIT
