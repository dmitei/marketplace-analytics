-- First eligible month per buyer; one buyer counted once per returning month.
WITH customer_months AS (
    SELECT DISTINCT customer_unique_id, order_month
    FROM order_mart WHERE is_valid = 1
), first_month AS (
    SELECT customer_unique_id, MIN(order_month) AS cohort
    FROM customer_months GROUP BY customer_unique_id
), activity AS (
    SELECT f.cohort, m.customer_unique_id,
           (CAST(substr(m.order_month,1,4) AS INTEGER)-CAST(substr(f.cohort,1,4) AS INTEGER))*12
             + CAST(substr(m.order_month,6,2) AS INTEGER)-CAST(substr(f.cohort,6,2) AS INTEGER) AS period
    FROM customer_months m JOIN first_month f USING (customer_unique_id)
), counts AS (
    SELECT cohort, period, COUNT(DISTINCT customer_unique_id) AS active_buyers
    FROM activity GROUP BY cohort, period
), sizes AS (
    SELECT cohort, active_buyers AS cohort_size FROM counts WHERE period = 0
)
SELECT c.cohort, c.period, c.active_buyers, s.cohort_size,
       ROUND(100.0*c.active_buyers/s.cohort_size, 2) AS retention_pct
FROM counts c JOIN sizes s USING (cohort)
ORDER BY cohort, period;
