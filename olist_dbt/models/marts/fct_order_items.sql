{{
  config(
    materialized='incremental',
    schema='main',
    unique_key='order_item_key',
    incremental_strategy='delete+insert'
  )
}}

-- fct_order_items: Order items fact table.
-- Grain: 1 row per order item within an order.
-- Metrics: price, freight_value, item_total_cost, delivery_delay_days.
-- Foreign Keys: customer_key, product_key, seller_key, order_date_key.
--
-- Incremental strategy: delete+insert with a 3-day lookback window.
-- On each run we delete rows where order_purchase_timestamp is within the
-- last 3 days (relative to the max date already in the table) and re-insert
-- them. This captures late-arriving order status/delivery updates without
-- performing a full refresh.
with order_items as (
  select
    oi.order_id,
    oi.order_item_id,
    oi.product_id,
    oi.seller_id,
    oi.price,
    oi.freight_value,
    (oi.price + oi.freight_value) as item_total_cost,
    o.order_purchase_timestamp,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    o.customer_id
  from {{ ref('stg_order_items') }} oi
  join {{ ref('stg_orders') }} o
    on oi.order_id = o.order_id
),
dated as (
  select
    *,
    cast(order_purchase_timestamp as date) as order_date,
    case
      when order_delivered_customer_date is not null
           and order_estimated_delivery_date is not null
      then date_diff('day', order_estimated_delivery_date, order_delivered_customer_date)
      else null
    end as delivery_delay_days
  from order_items
),
enriched as (
  select
    d.*,
    c.customer_key
  from dated d
  left join {{ ref('dim_customers') }} c
    on d.customer_id = c.customer_id
)
select
  concat(e.order_id, '-', lpad(e.order_item_id::varchar, 3, '0')) as order_item_key,
  e.customer_key,
  e.product_id as product_key,
  e.seller_id as seller_key,
  e.order_date as order_date_key,
  e.price,
  e.freight_value,
  e.item_total_cost,
  e.delivery_delay_days,
  e.order_purchase_timestamp,
  e.order_delivered_customer_date
from enriched e
{% if is_incremental() %}
where e.order_purchase_timestamp >= (
  select max(order_purchase_timestamp) - interval 3 days from {{ this }}
)
{% endif %}
