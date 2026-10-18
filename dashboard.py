"""Olist E-Commerce KPI Dashboard - Plotly + Dash

Reads Parquet exports from pbi_export/ and renders an interactive dashboard.
Run:
    python3 dashboard.py
Then open http://localhost:8050

To export as a standalone HTML file for cloud hosting:
    python3 dashboard.py --export
This writes dashboard.html which you can host on GitHub Pages, Netlify, etc.
"""

import argparse
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from dash import Dash, dcc, html, Input, Output, no_update

EXPORT_DIR = Path("pbi_export")
DUCKDB_PATH = Path("olist.duckdb")


def load_data() -> dict[str, pd.DataFrame]:
    """Load Parquet exports (or DuckDB directly if Parquet missing)."""
    data = {}
    tables = [
        "fct_order_items",
        "dim_customers",
        "dim_products",
        "dim_sellers",
        "dim_date",
        "stg_orders",
        "stg_reviews",
        "stg_payments",
    ]
    if all((EXPORT_DIR / f"{t}.parquet").exists() for t in tables):
        for t in tables:
            data[t] = pd.read_parquet(EXPORT_DIR / f"{t}.parquet")
    else:
        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        for t in tables:
            data[t] = con.execute(f"SELECT * FROM main_main.{t}").fetchdf()
        con.close()
    return data


def build_kpi_cards(data: dict[str, pd.DataFrame]) -> str:
    fct = data["fct_order_items"]
    customers = data["dim_customers"]
    reviews = data["stg_reviews"]

    total_revenue = fct["total_item_cost"].sum()
    total_items = len(fct)
    on_time_rate = (fct["delivery_delay_days"].fillna(0) <= 0).mean() * 100
    avg_delay = fct["delivery_delay_days"].mean()
    avg_review = reviews["review_score"].mean()
    total_customers = customers["customer_id"].nunique()

    cards = [
        ("Total Revenue", f"${total_revenue:,.0f}", "Sum of price + freight across all order items"),
        ("Order Items", f"{total_items:,}", "Total number of order line items"),
        ("Customers", f"{total_customers:,}", "Unique customers (customer_unique_id)"),
        ("On-Time Rate", f"{on_time_rate:.1f}%", "Share of items delivered on or before estimated date"),
        ("Avg Delivery Delay", f"{avg_delay:.1f} days", "Negative = delivered early, positive = late"),
        ("Avg Review Score", f"{avg_review:.2f} / 5", "Average customer review score"),
    ]

    card_els = ""
    for title, value, tooltip in cards:
        card_els += (
            '<div class="kpi-card" title="{tooltip}">'
            f'<div class="kpi-title">{title}</div>'
            f'<div class="kpi-value">{value}</div>'
            "</div>"
        ).replace("{tooltip}", tooltip).replace('"', '&quot;')

    return f'<div class="kpi-row">{card_els}</div>'


def build_figures(data: dict[str, pd.DataFrame]):
    fct = data["fct_order_items"]
    customers = data["dim_customers"]
    products = data["dim_products"]
    sellers = data["dim_sellers"]
    dates = data["dim_date"]
    reviews = data["stg_reviews"]

    # Merge fct with dimensions
    fct_c = fct.merge(customers[["customer_id", "customer_state"]], on="customer_id", how="left")
    fct_p = fct.merge(products[["product_key", "product_category_name_english"]], left_on="product_id", right_on="product_key", how="left")
    fct_s = fct.merge(sellers[["seller_key", "seller_state"]], left_on="seller_id", right_on="seller_key", how="left")
    fct_d = fct.merge(dates[["date_key", "year_month"]], left_on="order_date_key", right_on="date_key", how="left")

    # Reviews live on stg_orders (order_id), join fct.order_id -> reviews.order_id
    fct_r = fct.merge(reviews[["order_id", "review_score"]], on="order_id", how="left")

    # 1. Revenue by customer state
    rev_state = (
        fct_c.groupby("customer_state")["total_item_cost"]
        .sum()
        .reset_index()
        .sort_values("total_item_cost", ascending=False)
        .head(15)
    )
    fig_state = px.bar(
        rev_state,
        x="customer_state",
        y="total_item_cost",
        title="Revenue by Customer State (Top 15)",
        labels={"total_item_cost": "Revenue ($)", "customer_state": "State"},
        color="total_item_cost",
        color_continuous_scale="Blues",
    )
    fig_state.update_layout(showlegend=False, height=400)

    # 2. Monthly revenue trend
    rev_month = (
        fct_d.groupby("year_month")["total_item_cost"]
        .sum()
        .reset_index()
        .sort_values("year_month")
    )
    fig_month = px.line(
        rev_month,
        x="year_month",
        y="total_item_cost",
        title="Monthly Revenue Trend",
        labels={"total_item_cost": "Revenue ($)", "year_month": "Month"},
        markers=True,
    )
    fig_month.update_layout(height=400)

    # 3. Top sellers by revenue
    rev_seller = (
        fct_s.groupby("seller_state")["total_item_cost"]
        .sum()
        .reset_index()
        .sort_values("total_item_cost", ascending=False)
        .head(10)
    )
    fig_seller = px.bar(
        rev_seller,
        x="seller_state",
        y="total_item_cost",
        title="Revenue by Seller State (Top 10)",
        labels={"total_item_cost": "Revenue ($)", "seller_state": "State"},
        color="total_item_cost",
        color_continuous_scale="Greens",
    )
    fig_seller.update_layout(showlegend=False, height=400)

    # 4. Revenue by product category
    rev_cat = (
        fct_p.groupby("product_category_name_english")["total_item_cost"]
        .sum()
        .reset_index()
        .sort_values("total_item_cost", ascending=False)
        .head(10)
    )
    fig_cat = px.bar(
        rev_cat,
        x="total_item_cost",
        y="product_category_name_english",
        orientation="h",
        title="Revenue by Product Category (Top 10)",
        labels={"total_item_cost": "Revenue ($)", "product_category_name_english": "Category"},
        color="total_item_cost",
        color_continuous_scale="Oranges",
    )
    fig_cat.update_layout(showlegend=False, height=400, yaxis={"categoryorder": "total ascending"})

    # 5. Delivery delay distribution
    delay_data = fct["delivery_delay_days"].dropna().astype(int).tolist()
    fig_delay = go.Figure()
    fig_delay.add_trace(
        go.Histogram(
            x=delay_data,
            nbinsx=30,
            marker_color="#ef553b",
            name="Order Items",
        )
    )
    fig_delay.update_layout(
        title="Delivery Delay Distribution (days)",
        xaxis_title="Days Late (negative = early)",
        yaxis_title="Count",
        height=400,
        showlegend=False,
    )

    # 6. Review score distribution
    review_data = reviews["review_score"].dropna().astype(int).tolist()
    fig_review = go.Figure()
    fig_review.add_trace(
        go.Histogram(
            x=review_data,
            marker_color="#00cc96",
            name="Reviews",
        )
    )
    fig_review.update_layout(
        title="Review Score Distribution",
        xaxis_title="Review Score (1-5)",
        yaxis_title="Count",
        height=400,
        showlegend=False,
    )

    # 7. Delay vs Review Score scatter
    delay_review = fct_r.dropna(subset=["delivery_delay_days", "review_score"])[
        ["delivery_delay_days", "review_score"]
    ]
    delay_review["delivery_delay_days"] = delay_review["delivery_delay_days"].astype(int)
    delay_review["review_score"] = delay_review["review_score"].astype(int)
    sample = delay_review.sample(min(5000, len(delay_review)), random_state=42)
    fig_scatter = go.Figure()
    fig_scatter.add_trace(
        go.Scatter(
            x=sample["delivery_delay_days"].tolist(),
            y=sample["review_score"].tolist(),
            marker=dict(color="#636efa", opacity=0.5, size=6),
            name="Order Items",
        )
    )
    fig_scatter.update_layout(
        title="Delivery Delay vs Review Score (sample 5k)",
        xaxis_title="Days Late",
        yaxis_title="Review Score",
        height=400,
        showlegend=False,
    )

    return fig_state, fig_month, fig_seller, fig_cat, fig_delay, fig_review, fig_scatter


def build_app(data: dict[str, pd.DataFrame]) -> Dash:
    fig_state, fig_month, fig_seller, fig_cat, fig_delay, fig_review, fig_scatter = build_figures(data)

    app = Dash(__name__)
    app.title = "Olist E-Commerce KPI Dashboard"

    app.layout = html.Div(
        [
            html.H1("Olist E-Commerce KPI Dashboard", className="header-title"),
            html.P("Modern Local Batch Warehouse (DuckDB + dbt) — Interactive Analytics", className="header-sub"),
            html.Hr(className="header-divider"),
            build_kpi_cards(data),
            html.Div(
                [
                    html.Div(dcc.Graph(figure=fig_state), className="chart-col"),
                    html.Div(dcc.Graph(figure=fig_month), className="chart-col"),
                ],
                className="chart-row",
            ),
            html.Div(
                [
                    html.Div(dcc.Graph(figure=fig_seller), className="chart-col"),
                    html.Div(dcc.Graph(figure=fig_cat), className="chart-col"),
                ],
                className="chart-row",
            ),
            html.Div(
                [
                    html.Div(dcc.Graph(figure=fig_delay), className="chart-col"),
                    html.Div(dcc.Graph(figure=fig_review), className="chart-col"),
                ],
                className="chart-row",
            ),
            html.Div(
                [html.Div(dcc.Graph(figure=fig_scatter), className="chart-col-full")],
                className="chart-row",
            ),
            html.Footer(
                "Built with DuckDB, dbt, Plotly & Dash · Data: Olist Brazilian E-Commerce",
                className="footer",
            ),
        ],
        className="container",
    )

    return app


def export_html(data: dict[str, pd.DataFrame], output: Path = Path("dashboard.html")):
    """Render all figures to a single standalone HTML file."""
    fig_state, fig_month, fig_seller, fig_cat, fig_delay, fig_review, fig_scatter = build_figures(data)

    kpi = build_kpi_cards(data)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Olist E-Commerce KPI Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background: #f8f9fa; color: #333; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
        .header-title {{ font-size: 28px; font-weight: 700; margin: 0 0 4px 0; color: #1a1a2e; }}
        .header-sub {{ color: #666; margin: 0 0 16px 0; }}
        .header-divider {{ border: none; border-top: 1px solid #ddd; margin: 0 0 24px 0; }}
        .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .kpi-card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-left: 4px solid #1f77b4; }}
        .kpi-title {{ font-size: 13px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }}
        .kpi-value {{ font-size: 26px; font-weight: 700; color: #1a1a2e; }}
        .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }}
        .chart-col-full {{ grid-column: 1 / -1; }}
        .chart-col {{ background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); padding: 16px; }}
        .footer {{ margin-top: 32px; padding: 20px; text-align: center; color: #888; font-size: 13px; border-top: 1px solid #ddd; }}
        @media (max-width: 900px) {{ .chart-row {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <div class="container">
        <h1 class="header-title">Olist E-Commerce KPI Dashboard</h1>
        <p class="header-sub">Modern Local Batch Warehouse (DuckDB + dbt) — Interactive Analytics</p>
        <hr class="header-divider">
        {kpi}
        <div class="chart-row">
            <div class="chart-col" id="chart-state"></div>
            <div class="chart-col" id="chart-month"></div>
        </div>
        <div class="chart-row">
            <div class="chart-col" id="chart-seller"></div>
            <div class="chart-col" id="chart-cat"></div>
        </div>
        <div class="chart-row">
            <div class="chart-col" id="chart-delay"></div>
            <div class="chart-col" id="chart-review"></div>
        </div>
        <div class="chart-row">
            <div class="chart-col-full" id="chart-scatter"></div>
        </div>
        <footer class="footer">Built with DuckDB, dbt, Plotly & Dash · Data: Olist Brazilian E-Commerce</footer>
    </div>
    <script>
        const figState = {fig_state.to_json()};
        const figMonth = {fig_month.to_json()};
        const figSeller = {fig_seller.to_json()};
        const figCat = {fig_cat.to_json()};
        const figDelay = {fig_delay.to_json()};
        const figReview = {fig_review.to_json()};
        const figScatter = {fig_scatter.to_json()};
        Plotly.newPlot('chart-state', figState.data, figState.layout);
        Plotly.newPlot('chart-month', figMonth.data, figMonth.layout);
        Plotly.newPlot('chart-seller', figSeller.data, figSeller.layout);
        Plotly.newPlot('chart-cat', figCat.data, figCat.layout);
        Plotly.newPlot('chart-delay', figDelay.data, figDelay.layout);
        Plotly.newPlot('chart-review', figReview.data, figReview.layout);
        Plotly.newPlot('chart-scatter', figScatter.data, figScatter.layout);
    </script>
</body>
</html>
"""
    output.write_text(html_content, encoding="utf-8")
    print(f"Exported standalone dashboard to {output.resolve()}")


def main():
    parser = argparse.ArgumentParser(description="Olist E-Commerce KPI Dashboard")
    parser.add_argument("--export", action="store_true", help="Export standalone HTML file instead of running server")
    parser.add_argument("--port", type=int, default=8050, help="Port for the Dash server")
    args = parser.parse_args()

    data = load_data()

    if args.export:
        export_html(data)
        return

    app = build_app(data)
    app.run_server(debug=True, port=args.port, host="127.0.0.1")


if __name__ == "__main__":
    main()
