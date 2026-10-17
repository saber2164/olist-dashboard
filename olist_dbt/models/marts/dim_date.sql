{{
  config(
    materialized='table',
    schema='main'
  )
}}

-- dim_date: Calendar date spine dimension table.
-- Covers every date between the earliest order purchase date and the latest
-- estimated delivery date in the source data. Includes calendar flags used
-- for time-based analysis.
with date_bounds as (
  select
    cast(min(order_purchase_timestamp) as date) as min_date,
    cast(max(order_estimated_delivery_date) as date) as max_date
  from {{ ref('stg_orders') }}
),
dates as (
  select
    unnest(generate_series(min_date, max_date, interval 1 day)) as date_day
  from date_bounds
)
select
  cast(date_day as date) as date_key,
  extract(year from cast(date_day as date))::int as year,
  extract(month from cast(date_day as date))::int as month,
  extract(day from cast(date_day as date))::int as day,
  extract(dow from cast(date_day as date))::int as day_of_week,
  dayname(cast(date_day as date)) as day_name,
  extract(quarter from cast(date_day as date))::int as quarter,
  concat(extract(year from cast(date_day as date))::int, '-', lpad(extract(month from cast(date_day as date))::int::varchar, 2, '0')) as year_month,
  case when extract(dow from cast(date_day as date))::int in (0, 6) then true else false end as is_weekend
from dates
