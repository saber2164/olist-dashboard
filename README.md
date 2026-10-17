# Olist E-Commerce Analytics

Interactive analytics dashboard for the Olist Brazilian E-Commerce dataset, built on a modern local batch warehouse (DuckDB + dbt).

## Live Site

**Website:** https://saber2164.github.io/olist-dashboard/

**Dashboard:** https://saber2164.github.io/olist-dashboard/dashboard.html

## What's included

| File | Description |
|------|-------------|
| `index.html` | Sleek, minimal website (Apple-inspired design) |
| `dashboard.html` | Standalone interactive KPI dashboard |
| `dashboard.py` | Python source to regenerate the dashboard |
| `pbi_export/` | Parquet exports of all dbt mart models |

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
