-- Singular Test: Assert that no order item has a negative or zero total_item_cost when freight is added
-- Returns records that FAIL the assertion condition.
-- The test passes if zero rows are returned.

SELECT
    order_id,
    SUM(price) AS total_price,
    SUM(freight_value) AS total_freight,
    SUM(total_item_cost) AS total_calculated
FROM {{ ref('fct_order_items') }}
GROUP BY order_id
HAVING SUM(total_item_cost) <= 0
