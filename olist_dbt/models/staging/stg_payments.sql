{{
  config(
    materialized='view',
    schema='main'
  )
}}

-- Staging model for raw_payments
-- Casts payment_value to decimal and payment_installments to int.
select
  order_id,
  payment_sequential,
  payment_type,
  cast(payment_installments as int) as payment_installments,
  cast(payment_value as decimal(18,2)) as payment_value
from {{ source('olist_raw', 'raw_payments') }}
