{{
  config(
    materialized='view',
    schema='main'
  )
}}

-- Staging model for raw_sellers
select
  seller_id,
  seller_zip_code_prefix,
  trim(seller_city) as seller_city,
  trim(seller_state) as seller_state
from {{ source('olist_raw', 'raw_sellers') }}
