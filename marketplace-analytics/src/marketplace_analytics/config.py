"""Project paths and demo CSV schema."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
DEMO = ROOT / "data" / "demo"
DB = ROOT / "data" / "processed" / "marketplace.db"

FILES = {
    "orders": "orders.csv",
    "customers": "customers.csv",
    "items": "items.csv",
    "payments": "payments.csv",
    "reviews": "reviews.csv",
    "products": "products.csv",
}

FIELDS = {
    "orders": ["order_id", "customer_id", "order_status", "order_purchase_timestamp",
               "order_delivered_customer_date", "order_estimated_delivery_date"],
    "customers": ["customer_id", "customer_unique_id", "country", "city"],
    "items": ["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"],
    "payments": ["order_id", "payment_sequential", "payment_type", "payment_value"],
    "reviews": ["order_id", "review_score"],
    "products": ["product_id", "product_category_name"],
}
