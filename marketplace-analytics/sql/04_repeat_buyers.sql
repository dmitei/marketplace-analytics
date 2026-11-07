WITH buyer_orders AS (
    SELECT customer_unique_id, COUNT(*) AS n_orders, SUM(gmv) AS lifetime_gmv
    FROM order_mart WHERE is_valid = 1 GROUP BY customer_unique_id
)
SELECT COUNT(*) AS buyers,
       SUM(CASE WHEN n_orders >= 2 THEN 1 ELSE 0 END) AS repeat_buyers,
       ROUND(100.0 * AVG(CASE WHEN n_orders >= 2 THEN 1.0 ELSE 0 END), 2) AS repeat_share_pct
FROM buyer_orders;
