"""Validate marketplace CSVs, load them into SQLite, and build an order-grain analytical mart."""
import argparse
import sqlite3
from pathlib import Path
import pandas as pd
from .config import DB, DEMO, RAW, FILES, FIELDS

SCHEMA = """
CREATE TABLE customers (customer_id TEXT PRIMARY KEY, customer_unique_id TEXT NOT NULL, country TEXT NOT NULL, city TEXT NOT NULL);
CREATE TABLE orders (order_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, order_status TEXT,
    order_purchase_timestamp TEXT, order_delivered_customer_date TEXT, order_estimated_delivery_date TEXT);
CREATE TABLE items (order_id TEXT, order_item_id INTEGER, product_id TEXT, seller_id TEXT,
    price REAL, freight_value REAL, PRIMARY KEY(order_id, order_item_id));
CREATE TABLE payments (order_id TEXT, payment_sequential INTEGER, payment_type TEXT, payment_value REAL);
CREATE TABLE reviews (order_id TEXT, review_score INTEGER);
CREATE TABLE products (product_id TEXT PRIMARY KEY, product_category_name TEXT);
CREATE INDEX idx_orders_date ON orders(order_purchase_timestamp);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_customers_unique ON customers(customer_unique_id);
CREATE INDEX idx_items_order ON items(order_id);
CREATE INDEX idx_reviews_order ON reviews(order_id);
"""

MART_SQL = """
CREATE TABLE order_mart AS
WITH item_totals AS (
 SELECT order_id, ROUND(SUM(price),2) AS gmv, ROUND(SUM(freight_value),2) AS freight,
        COUNT(*) AS items_count
 FROM items GROUP BY order_id
), review_totals AS (
 SELECT order_id, AVG(review_score) AS review_score FROM reviews GROUP BY order_id
), payment_totals AS (
 SELECT order_id, ROUND(SUM(payment_value),2) AS paid_amount FROM payments GROUP BY order_id
)
SELECT o.order_id, c.customer_unique_id, c.country, c.city, o.order_status,
       substr(o.order_purchase_timestamp,1,10) AS order_date,
       substr(o.order_purchase_timestamp,1,7) AS order_month,
       substr(o.order_delivered_customer_date,1,10) AS delivered_date,
       substr(o.order_estimated_delivery_date,1,10) AS estimated_date,
       COALESCE(i.gmv,0.0) AS gmv, COALESCE(i.freight,0.0) AS freight,
       COALESCE(i.items_count,0) AS items_count, p.paid_amount, r.review_score,
       CASE WHEN o.order_status='delivered' AND o.order_delivered_customer_date IS NOT NULL
                 AND o.order_estimated_delivery_date IS NOT NULL
                 AND date(o.order_delivered_customer_date)>date(o.order_estimated_delivery_date)
            THEN 1 WHEN o.order_status='delivered' AND o.order_delivered_customer_date IS NOT NULL
                 AND o.order_estimated_delivery_date IS NOT NULL THEN 0 ELSE NULL END AS is_late,
       CASE WHEN o.order_status='delivered' AND o.order_delivered_customer_date IS NOT NULL
            THEN CAST(julianday(date(o.order_delivered_customer_date)) -
                      julianday(date(o.order_purchase_timestamp)) AS INTEGER)
            ELSE NULL END AS delivery_days,
       CASE WHEN o.order_status NOT IN ('canceled','unavailable') AND i.order_id IS NOT NULL THEN 1 ELSE 0 END AS is_valid
FROM orders o
JOIN customers c ON c.customer_id=o.customer_id
LEFT JOIN item_totals i ON i.order_id=o.order_id
LEFT JOIN payment_totals p ON p.order_id=o.order_id
LEFT JOIN review_totals r ON r.order_id=o.order_id;
CREATE UNIQUE INDEX idx_mart_order ON order_mart(order_id);
CREATE INDEX idx_mart_date ON order_mart(order_date);
CREATE INDEX idx_mart_customer ON order_mart(customer_unique_id);
CREATE INDEX idx_mart_country ON order_mart(country);
CREATE INDEX idx_mart_city ON order_mart(country, city);
"""


def load_csvs(source_dir: Path, db_path: Path = DB) -> dict[str, int]:
    source_dir, db_path = Path(source_dir), Path(db_path)
    frames: dict[str, pd.DataFrame] = {}
    for table, filename in FILES.items():
        file = source_dir / filename
        if not file.is_file():
            raise FileNotFoundError(f"Missing required file: {file}")
        df = pd.read_csv(file, low_memory=False)
        missing = set(FIELDS[table]) - set(df.columns)
        if missing:
            raise ValueError(f"{filename} missing columns: {sorted(missing)}")
        df = df[FIELDS[table]].copy()
        if table in ("orders", "customers", "products"):
            primary = {"orders":"order_id", "customers":"customer_id", "products":"product_id"}[table]
            if df[primary].isna().any() or df[primary].duplicated().any():
                raise ValueError(f"{filename}: invalid or duplicate {primary}")
        if table == "customers":
            for column in ("country", "city"):
                if df[column].isna().any() or df[column].astype(str).str.strip().eq("").any():
                    raise ValueError(f"{filename}: missing {column}")
        if table == "items" and (df[["order_id", "order_item_id"]].duplicated().any()):
            raise ValueError(f"{filename}: duplicate item keys")
        if table == "items":
            for col in ("price", "freight_value"):
                df[col] = pd.to_numeric(df[col], errors="coerce")
                if df[col].isna().any() or (df[col] < 0).any():
                    raise ValueError(f"{filename}: invalid {col}")
        frames[table] = df
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = db_path.with_name(db_path.name + ".tmp")
    temp_path.unlink(missing_ok=True)
    try:
        with sqlite3.connect(temp_path) as conn:
            conn.executescript(SCHEMA)
            for table in ("customers", "orders", "items", "payments", "reviews", "products"):
                frames[table].to_sql(table, conn, if_exists="append", index=False, chunksize=2000)
            conn.executescript(MART_SQL)
            count_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            count_mart = conn.execute("SELECT COUNT(*) FROM order_mart").fetchone()[0]
            if count_orders != count_mart:
                raise ValueError(f"Order mart lost orders: {count_orders} -> {count_mart}")
        temp_path.replace(db_path)
    finally:
        temp_path.unlink(missing_ok=True)
    return {table: len(df) for table, df in frames.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["demo", "raw"], default="demo")
    parser.add_argument("--input-dir", type=Path, help="Custom directory containing six marketplace CSVs")
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()
    source = args.input_dir or (DEMO if args.source == "demo" else RAW)
    if args.source == "demo" and not args.input_dir and not all((DEMO / f).exists() for f in FILES.values()):
        from .demo import generate_demo
        generate_demo()
    print(f"Loading from {source} ...")
    print("Rows:", load_csvs(source, args.db))
    print(f"SQLite database ready: {args.db}")


if __name__ == "__main__":
    main()
