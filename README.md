# Olist E-Commerce Analytics

Interactive analytics dashboard for the Olist Brazilian E-Commerce dataset, built on a modern local batch warehouse (DuckDB + dbt).

## Live Site

**Website:** https://saber2164.github.io/olist-dashboard/

**Dashboard:** https://saber2164.github.io/olist-dashboard/dashboard.html

## Data

The raw Olist CSV dataset is **not** included in this repository (it's large). 

Download it from Kaggle: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Extract the CSVs into `olist_data/`, then run:

```bash
python3 ingest_raw.py
```

This loads all CSVs into `olist.duckdb` under the `main_raw` schema.

## KPIs & charts

- **KPI cards:** Total Revenue, Order Items, Customers, On-Time Rate, Avg Delivery Delay, Avg Review Score
- **Revenue by Customer State** (top 15)
- **Monthly Revenue Trend**
- **Revenue by Seller State** (top 10)
- **Revenue by Product Category** (top 10)
- **Delivery Delay Distribution**
- **Review Score Distribution**
- **Delivery Delay vs Review Score** scatter

## Regenerate the dashboard

```bash
python3 dashboard.py --export
```

Requires: `duckdb`, `pandas`, `pyarrow`, `plotly`, `dash`

## Project structure

The data pipeline (DuckDB ingestion + dbt models + tests + docs) lives alongside this dashboard. Run `dbt build --project-dir olist_dbt --full-refresh` to rebuild the warehouse, then re-export the dashboard.

## License

MIT
