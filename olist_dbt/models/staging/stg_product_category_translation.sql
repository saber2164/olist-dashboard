{{
  config(
    materialized='view',
    schema='main'
  )
}}

-- Staging model for raw_product_category_translation
select
  product_category_name,
  trim(product_category_name_english) as product_category_name_english
from {{ source('olist_raw', 'raw_product_category_translation') }}
