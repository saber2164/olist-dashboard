{{
  config(
    materialized='view',
    schema='main'
  )
}}

-- Staging model for raw_geolocation
-- Geolocation is large (~1M rows); used for joining city/state to zip prefixes.
select
  geolocation_zip_code_prefix as zip_code_prefix,
  trim(geolocation_city) as city,
  trim(geolocation_state) as state,
  cast(geolocation_lat as decimal(10,6)) as lat,
  cast(geolocation_lng as decimal(10,6)) as lng
from {{ source('olist_raw', 'raw_geolocation') }}
