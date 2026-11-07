SELECT order_month, COUNT(*) AS eligible_orders,
       ROUND(SUM(gmv), 2) AS gmv_brl,
       ROUND(AVG(gmv), 2) AS aov_brl
FROM order_mart
WHERE is_valid = 1
GROUP BY order_month
ORDER BY order_month;
