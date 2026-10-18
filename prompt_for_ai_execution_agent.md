# Prompt for AI Agent: Upgrade Olist DuckDB + dbt Data Warehouse

Act as a Senior Data Engineer. You are tasked with upgrading an existing local batch data warehouse (`olist-dashboard` repository) built with **DuckDB** and **dbt Core**. 

The goal is to elevate this project from a standard dbt setup to a **Senior DE-Grade Production Warehouse** that demonstrates advanced modeling, data quality assertions, late-arriving data handling, and automated CI/CD pipelines.

---

## Task Requirements & File Deliverables

Please generate or update the exact file structures, dbt configurations, SQL models, and CI/CD pipelines detailed below.

---

### 1. Snapshot Layer: Implement SCD Type 2 (`snapshots/snap_customers.sql`)

Create a dbt snapshot to track customer geography changes over time using timestamp-based change tracking.

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

---

### 2. Incremental Fact Modeling with Dynamic Lookback (`models/marts/fct_order_items.sql`)

Refactor `fct_order_items` to use incremental materialization with a **3-day dynamic lookback window** to gracefully ingest late-arriving order status updates without full table refreshes.

```sql
{{
    config(
        materialized='incremental',
        unique_key='order_item_key',
        on_schema_change='append_new_columns'
    )
}}

WITH order_items AS (
    SELECT * FROM {{ ref('stg_order_items') }}
),
orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
)

SELECT
    -- Surrogate key construction
    {{ dbt_utils.generate_surrogate_key(['oi.order_id', 'oi.order_item_id']) }} AS order_item_key,
    oi.order_id,
    oi.order_item_id,
    o.customer_id,
    oi.product_id,
    oi.seller_id,
    o.order_purchase_timestamp,
    o.order_status,
    oi.price,
    oi.freight_value,
    (oi.price + oi.freight_value) AS total_item_cost,
    DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date) AS delivery_delay_days
FROM order_items oi
INNER JOIN orders o ON oi.order_id = o.order_id

{% if is_incremental() %}
    -- Lookback window for late-arriving records updated/purchased in the last 3 days
    WHERE o.order_purchase_timestamp >= (
        SELECT COALESCE(MAX(order_purchase_timestamp), '1900-01-01'::TIMESTAMP) - INTERVAL '3 DAYS'
        FROM {{ this }}
    )
{% endif %}
```

---

### 3. Comprehensive Data Quality Framework (`models/marts/schema.yml`)

Implement column-level data assertions, referential integrity tests, and value domain checks across staging and core marts.

```yaml
version: 2

models:
  - name: fct_order_items
    description: "Fact table recording individual order items with pricing, delivery SLAs, and key foreign keys."
    columns:
      - name: order_item_key
        description: "Surrogate primary key for each order item record."
        tests:
          - unique
          - not_null

      - name: order_id
        description: "Foreign key reference to orders."
        tests:
          - not_null

      - name: product_id
        description: "Foreign key reference to products."
        tests:
          - not_null
          - relationships:
              to: ref('stg_products')
              field: product_id

      - name: order_status
        tests:
          - accepted_values:
              values: ['delivered', 'shipped', 'canceled', 'invoiced', 'processing', 'created', 'approved', 'unavailable']

      - name: price
        tests:
          - not_null

  - name: dim_customers
    description: "Dimension table containing customer demographic and geography details."
    columns:
      - name: customer_id
        tests:
          - unique
          - not_null
```

---

### 4. Custom Singular Integrity Test (`tests/assert_order_total_matches_items.sql`)

Create a custom singular test verifying that the sum of item prices and freight in `fct_order_items` matches the aggregate transaction amounts.

```sql
-- Singular Test: Assert that no order item has a negative or zero price when freight is added
-- Returns records that FAIL the assertion condition.

SELECT
    order_id,
    SUM(price) AS total_price,
    SUM(freight_value) AS total_freight,
    SUM(total_item_cost) AS total_calculated
FROM {{ ref('fct_order_items') }}
GROUP BY order_id
HAVING SUM(total_item_cost) <= 0
```

---

### 5. Automated CI/CD Pipeline (`.github/workflows/dbt_ci.yml`)

Configure GitHub Actions to automatically run `dbt build` and execute data quality tests on every pull request to `main`.

```yaml
name: dbt Data Quality CI

on:
  pull_request:
    branches: [ "main" ]
  push:
    branches: [ "main" ]

jobs:
  dbt-ci:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python 3.10
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install dbt-duckdb pandas

      - name: Ingest Raw Data into DuckDB
        run: |
          python load_raw_olist.py

      - name: Run dbt Build and Tests
        run: |
          dbt deps
          dbt build --profiles-dir .
```

---

### 6. Production Architecture Documentation (`README.md`)

Update the repository `README.md` to structure it as an **Engineering System Architecture Design Document**.

Sections to include:
1. **System Architecture Diagram** (ASCII or MerMaid line rendering data flow from Raw CSVs -> DuckDB -> dbt Staging -> Marts).
2. **Table Grain Definitions**: Expressly state the grain for every fact (`fct_order_items`: 1 row per item in an order) and dimension (`dim_customers`: 1 row per unique customer ID).
3. **Incremental Strategy & Late-Arriving Data**: Explain the dynamic 3-day lookback window used in `fct_order_items`.
4. **SCD Type 2 Implementation**: Document the snapshot process for customer geography tracking.
5. **Trade-offs & Scalability**:
   - *Why DuckDB?* Fast in-process vectorized execution for small-to-medium analytical workloads without cloud infrastructure overhead.
   - *Scalability to 100x Volume:* Transition strategy from local DuckDB + local storage to **Snowflake / BigQuery** or **AWS S3 (Parquet) + DuckDB/Athena**.

---

## Instructions to Agent:
Execute these file additions and refactors directly into the local repository directory. Verify syntax validity with `dbt compile` and run `dbt build` to ensure all tests pass cleanly.