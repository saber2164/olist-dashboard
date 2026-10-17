-- Custom singular test: returns rows where the order item total cost is inconsistent
-- (null or not equal to price + freight). Returns zero rows when all items are consistent.
select
  order_item_key,
  price,
  freight_value,
  item_total_cost
from {{ ref('fct_order_items') }}
where item_total_cost is null
   or item_total_cost <> price + freight_value
