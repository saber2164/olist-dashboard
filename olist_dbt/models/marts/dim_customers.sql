{{
  config(
    materialized='table',
    schema='main'
  )
}}

-- dim_customers: Customer dimension table.
-- One row per customer (customer_unique_id). Stores current location attributes.
-- SCD Type 2 history is maintained in snapshots/snapshot_customers.sql;
-- this dim reflects the latest customer geography for joins.
select
  c.customer_unique_id as customer_key,
  c.customer_id,
  c.customer_zip_code_prefix,
  c.customer_city,
  c.customer_state
from {{ ref('stg_customers') }} c
qualify row_number() over (partition by c.customer_unique_id order by c.customer_id) = 1
