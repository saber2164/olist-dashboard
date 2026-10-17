{{
  config(
    materialized='view',
    schema='main'
  )
}}

-- Staging model for raw_order_items
-- Casts price and freight_value to decimal for monetary precision.
select
  order_id,
  order_item_id,
  product_id,
  seller_id,
  cast(shipping_limit_date as timestamp) as shipping_limit_date,
  cast(price as decimal(18,2)) as price,
  cast(freight_value as decimal(18,2)) as freight_value
from {{ source('olist_raw', 'raw_order_items') }}
