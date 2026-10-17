{{
  config(
    materialized='table',
    schema='main'
  )
}}

-- dim_sellers: Seller dimension table.
-- One row per seller with location and derived performance tier placeholder.
select
  s.seller_id as seller_key,
  s.seller_zip_code_prefix,
  s.seller_city,
  s.seller_state
from {{ ref('stg_sellers') }} s
