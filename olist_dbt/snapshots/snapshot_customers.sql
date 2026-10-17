{{
  config(
    target_schema='snapshots',
    unique_key='customer_unique_id',
    strategy='timestamp',
    updated_at='customer_unique_id'
  )
}}
select customer_unique_id, customer_id, customer_zip_code_prefix, customer_city, customer_state
from {{ ref('stg_customers') }}
