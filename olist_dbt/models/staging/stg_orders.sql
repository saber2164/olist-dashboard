{{
  config(
    materialized='view',
    schema='main'
  )
}}

-- Staging model for raw_orders
-- Purpose: Standardize column names, cast data types, and handle trivial nulls.
-- This is a 1:1 mapping to the raw orders table with cleaned columns.
select
  order_id,
  customer_id,
  order_status,
  cast(order_purchase_timestamp as timestamp) as order_purchase_timestamp,
  cast(order_approved_at as timestamp) as order_approved_at,
  cast(order_delivered_carrier_date as timestamp) as order_delivered_carrier_date,
  cast(order_delivered_customer_date as timestamp) as order_delivered_customer_date,
  cast(order_estimated_delivery_date as timestamp) as order_estimated_delivery_date
from {{ source('olist_raw', 'raw_orders') }}
