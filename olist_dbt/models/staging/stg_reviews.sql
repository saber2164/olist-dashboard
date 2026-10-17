{{
  config(
    materialized='view',
    schema='main'
  )
}}

-- Staging model for raw_reviews
select
  review_id,
  order_id,
  cast(review_score as int) as review_score,
  cast(review_creation_date as timestamp) as review_creation_date,
  cast(review_answer_timestamp as timestamp) as review_answer_timestamp
from {{ source('olist_raw', 'raw_reviews') }}
