{{
    config(
        materialized='incremental',
        unique_key='order_item_key',
        on_schema_change='append_new_columns',
        incremental_strategy='delete+insert'
    )
}}

WITH order_items AS (
    SELECT * FROM {{ ref('stg_order_items') }}
),
orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
)

SELECT
    -- Surrogate key construction using dbt-utils
    {{ dbt_utils.generate_surrogate_key(['oi.order_id', 'oi.order_item_id']) }} AS order_item_key,
    oi.order_id,
    oi.order_item_id,
    o.customer_id,
    oi.product_id,
    oi.seller_id,
    CAST(o.order_purchase_timestamp AS DATE) AS order_date_key,
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
