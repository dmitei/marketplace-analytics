-- Only completed deliveries with observed review scores.
SELECT CASE WHEN is_late = 1 THEN 'Late' ELSE 'On time' END AS delivery_group,
       COUNT(*) AS rated_deliveries,
       ROUND(AVG(review_score), 2) AS avg_review_score,
       ROUND(100.0 * AVG(CASE WHEN review_score <= 2 THEN 1.0 ELSE 0 END), 2) AS low_rating_pct
FROM order_mart
WHERE is_late IS NOT NULL AND review_score IS NOT NULL
GROUP BY is_late
ORDER BY is_late;
