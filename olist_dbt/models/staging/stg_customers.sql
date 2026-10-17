{{
  config(
    materialized='view',
    schema='main'
  )
}}

-- Staging model for raw_customers
-- Cleans string fields and standardizes customer location attributes.
select
  customer_id,
  customer_unique_id,
  customer_zip_code_prefix,
  trim(customer_city) as customer_city,
  trim(customer_state) as customer_state
from {{ source('olist_raw', 'raw_customers') }}
