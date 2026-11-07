-- SQLite syntax. Mart grain: exactly one row per order.
-- GMV = sum of item prices, excludes freight and canceled/unavailable orders.
SELECT COUNT(*) AS eligible_orders,
       ROUND(SUM(gmv), 2) AS gmv_rub,
       ROUND(AVG(gmv), 2) AS average_order_value_rub,
       COUNT(DISTINCT customer_unique_id) AS unique_buyers
FROM order_mart
WHERE is_valid = 1;
