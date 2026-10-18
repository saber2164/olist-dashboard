# Project 1 Architecture & Design Doc: Modern Local Batch Warehouse (DuckDB + dbt)

## 1. Project Overview & Business Value

### **Project Title**

**Scalable Modern Data Warehouse & Analytics Engine for E-Commerce Operations**

### **Business Problem / Value Proposition**

In many growing e-commerce platforms, operational transactional databases (OLTP) store raw order, seller, payment, and customer logistics data across un-indexed, highly normalized, or loosely structured schemas. When business teams (e.g., Logistics, Finance, Customer Retention) attempt to run reporting directly on transactional tables or poorly organized data lakes:

* **Analytic queries stall transactional applications** (locking / resource contention).

* **Inconsistent definitions** arise (e.g., Finance calculates "Revenue" on order creation, while Operations calculates it on delivery).

* **Lack of point-in-time auditability** makes tracking changes in seller or customer location/status over time inaccurate.

### **The Solution & Impact**

This project transforms raw operational e-commerce data into a **high-performance, audited Dimensional Data Warehouse (Kimball Star Schema)** using **DuckDB** (an open-source, fast, in-process columnar OLAP database) and **dbt Core**.

**Key Business Improvements:**

1. **SLA Breach & Delivery Delay Reduction:** Identifies specific seller/logistics hubs causing delivery delays and tracks their impact on customer review scores.

2. **Point-in-Time Historical Accuracy (SCD Type 2):** Tracks customer geography and seller status changes over time so historical sales reports accurately reflect customer location at the exact time of order placement.

3. **Automated Data Quality & Pipeline SLA:** Enforces strict data quality assertions (`unique`, `not_null`, foreign key referential integrity) and builds late-arriving data handling into incremental models, preventing pipeline failures when upstream data feeds arrive out of order.

4. **Zero-Cost, Zero-Cloud Footprint:** Built on DuckDB, enabling rapid local iterative development, 100% data privacy, and zero cloud platform maintenance costs while maintaining enterprise-grade SQL and dbt standards.

---

## 2. Technical Stack & Architecture

```
+------------------+         +-----------------------------------------------------------+
| Raw Data Layer   |         | DuckDB Local Analytical Database (olist.duckdb)           |
| (Olist CSVs)     |         |                                                           |
| - Orders         |         |  +--------------------+   +----------------------------+  |
| - Customers      | READ    |  | main_raw Schema    |   | main Schema                |  |
| - Products       | CSV     |  | (Raw ingested CSVs)|-->| - Staging (stg_)           |  |
| - Payments/Items | ------> |  +--------------------+   | - Intermediate (int_)      |  |
+------------------+         |                           | - Marts (fct_ / dim_)      |  |
                               +---------------------------+----------------------------+  |
                                                                   ^                     |
                                                                   | dbt build           |
                                                            +--------------+             |
                                                            | dbt-duckdb   |             |
                                                            +--------------+             |

```

* **Storage & Analytical Engine:** DuckDB (In-process C++ SQL OLAP Database engine)

* **Transformation & Modeling:** dbt Core (`dbt-duckdb`)

* **Ingestion Scripting:** Python (`duckdb`, `pandas`)

* **CI/CD & Documentation:** GitHub Actions (for automated `dbt build` & `dbt test`), `dbt docs`

---

## 3. Data Schema & Modeling Plan

### **A. Raw Layer (`main_raw` Schema)**

Direct landing of Olist raw CSV datasets into DuckDB:

* `raw_orders`, `raw_order_items`, `raw_customers`, `raw_products`, `raw_sellers`, `raw_payments`, `raw_reviews`.

### **B. Staging Layer (`stg_`)**

1-to-1 with raw tables. Responsibilities:

* Standardize column names (snake_case).

* Cast data types explicitly (timestamps, decimals, booleans).

* Handle trivial nulls and clean dirty string fields.

### **C. Intermediate Layer (`int_`)**

Pre-joins or complex business logic calculations (e.g., order item level price/freight calculations, aggregating multi-item orders).

### **D. Core Marts Layer (`marts`)**

Kimball Star Schema optimized for analytical performance:

* **`fct_order_items`** *(Fact Table)*:

  * **Grain:** 1 row per order item within an order.

  * **Metrics:** `price`, `freight_value`, `item_total_cost`, `delivery_delay_days`.

  * **Foreign Keys:** `customer_key`, `product_key`, `seller_key`, `order_date_key`.

  * **Pattern:** Incremental model with a 3-day lookback window for late-arriving data.

* **`dim_customers`** *(Dimension Table)*:

  * **Pattern:** SCD Type 2 tracking customer zip code and location changes over time via dbt Snapshots (`dbt snapshot`).

* **`dim_sellers`** *(Dimension Table)*: Seller location, onboard date, performance tier.

* **`dim_products`** *(Dimension Table)*: Product category, weight, dimensions.

* **`dim_date`** *(Dimension Table)*: Generated date spine macro covering all dates with calendar flags (day of week, month, quarter, holiday).

---

## 4. Key Engineering Deliverables & Design Patterns

1. **Incremental Loading Strategy:**

   * Construct `fct_order_items` using `materialized='incremental'`.

   * Implement a dynamic lookback window using `is_incremental()` macro logic to ingest late-arriving order status updates without running a full refresh.

2. **SCD Type 2 Implementation:**

   * Configure dbt snapshots with `strategy='timestamp'` or `strategy='check'` tracking changes in customer address fields stored directly in the DuckDB snapshot schema.

3. **Data Quality Framework:**

   * **Schema Tests:** `not_null`, `unique`, `relationships` (referential integrity), `accepted_values`.

   * **Custom Singular Tests:** Custom SQL assertions verifying that order header total equals the sum of order item prices + freight.

4. **Documentation & Lineage:**

   * `dbt docs generate` showcasing full upstream-to-downstream lineage DAGs.

---

## 5. Execution Guidelines & Agent Prompt Instructions

> **Instructions for the AI Assistant / Execution Agent:**
> Act as an expert Data Engineering Lead guiding a developer building this batch warehouse project hands-on. Follow these exact principles when assisting:

### **Agent Operating Principles**

1. **Code Generation Guidelines:**

   * Provide complete, copy-paste-ready scripts with clear file paths (e.g., `models/staging/stg_orders.sql`).

   * Use standard DuckDB SQL dialect (which supports modern PostgreSQL-like syntax and vectorized execution) and modern dbt Core syntax.

   * Include inline documentation explaining *why* a specific pattern (e.g., lookback window, surrogate key) was chosen.

2. **Debugging & Interactive Troubleshooting Mode:**

   * When the user pastes runtime errors (e.g., database file locking errors, dbt model compilation errors, missing column errors), explain the **root cause** first before providing the corrected code.

   * Guide the user to inspect underlying state tables (e.g., `dbt snapshot` metadata columns `dbt_valid_from` and `dbt_valid_to`).

3. **System Design Extraction:**

   * After each successful build milestone, prompt the user with 1–2 system design questions related to what was just built (e.g., *"How does DuckDB's in-process columnar engine differ from Snowflake's virtual warehouse architecture?"* or *"Why prefer star schema over One Big Table (OBT) in DuckDB?"*).

---

## 6. Step-by-Step Roadmap for Weekend Sprint

* **Phase 1: DuckDB Infrastructure & Ingestion Setup**

  * Initialize local DuckDB database (`olist.duckdb`).

  * Write a Python ingestion script (`load_raw_olist.py`) using `duckdb` to read local Olist CSVs and ingest them into the `main_raw` schema.

* **Phase 2: dbt Project Setup & Staging**

  * Run `dbt init olist_dbt`, configure `profiles.yml` with the `duckdb` adapter target.

  * Write `sources.yml` and staging models (`stg_orders.sql`, `stg_customers.sql`, etc.).

* **Phase 3: Core Marts & Incremental Modeling**

  * Build `fct_order_items` with incremental logic and dynamic lookback windows.

  * Implement `dim_date` date spine macro.

* **Phase 4: Snapshots (SCD2) & Data Quality**

  * Create dbt snapshot for customer geography changes.

  * Configure `schema.yml` assertions and run `dbt test`.

* **Phase 5: Documentation & Lineage**

  * Generate dbt docs (`dbt docs generate` & `dbt docs serve`) and review data lineage graph.