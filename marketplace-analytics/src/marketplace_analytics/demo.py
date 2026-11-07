"""Генерирует воспроизводимые вымышленные данные маркетплейса для стран СНГ.

Все суммы заданы в RUB как единой расчётной валюте демонстрации.
Распределения городов, цен, оплат и сроков доставки придуманы для проекта.
Это не статистика рынка и не конвертация реальных валют."""
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
from .config import DEMO, FILES


def generate_demo(output_dir: Path = DEMO, n_orders: int = 3600, seed: int = 42) -> Path:
    if n_orders < 10:
        raise ValueError("Количество заказов должно быть не меньше 10")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    n_users = max(10, int(n_orders * 0.68))
    locations = [
        ("Россия", "Москва"), ("Россия", "Санкт-Петербург"), ("Россия", "Казань"),
        ("Беларусь", "Минск"), ("Казахстан", "Алматы"), ("Казахстан", "Астана"),
        ("Армения", "Ереван"), ("Кыргызстан", "Бишкек"), ("Узбекистан", "Ташкент"),
        ("Таджикистан", "Душанбе"), ("Азербайджан", "Баку"),
    ]
    categories = ["Красота и здоровье", "Электроника и аксессуары", "Дом и текстиль",
                  "Спорт и отдых", "Мебель и декор", "Игрушки", "Книги"]
    # Условные уровни цен категорий в RUB; не рыночная оценка.
    category_prices = {"Красота и здоровье": 1200, "Электроника и аксессуары": 4500,
                       "Дом и текстиль": 2200, "Спорт и отдых": 3000,
                       "Мебель и декор": 6500, "Игрушки": 1800, "Книги": 700}
    customer_users = rng.choice(n_users, size=n_orders, replace=True)
    customer_locations = rng.integers(0, len(locations), size=n_users)
    start = datetime(2024, 1, 1)
    offsets = rng.integers(0, 545, size=n_orders)
    order_dates = [start + timedelta(days=int(d), hours=int(rng.integers(8, 22))) for d in offsets]
    n_products = 280
    product_categories = rng.choice(categories, size=n_products)
    products = pd.DataFrame({"product_id": [f"p{i:05d}" for i in range(n_products)],
                             "product_category_name": product_categories})
    customers = pd.DataFrame({"customer_id": [f"c{i:06d}" for i in range(n_orders)],
                              "customer_unique_id": [f"u{u:06d}" for u in customer_users],
                              "country": [locations[customer_locations[u]][0] for u in customer_users],
                              "city": [locations[customer_locations[u]][1] for u in customer_users]})
    orders, items, payments, reviews = [], [], [], []
    for i, date in enumerate(order_dates):
        oid = f"o{i:06d}"
        status = rng.choice(["delivered", "shipped", "canceled"], p=[.92,.055,.025])
        shipping_days = int(rng.integers(3, 28))
        delivered = date + timedelta(days=shipping_days) if status == "delivered" else None
        promised = date + timedelta(days=17)
        orders.append((oid, f"c{i:06d}", status, date, delivered, promised))
        count = int(rng.choice([1, 2, 3], p=[.77, .19, .04]))
        subtotal = 0.0
        freight = 0.0
        for j in range(1, count + 1):
            product = int(rng.integers(n_products))
            base_price = category_prices[product_categories[product]]
            price = round(float(rng.lognormal(np.log(base_price), .55)), 2)
            delivery_fee = round(float(rng.uniform(99, 799)), 2)
            subtotal += price
            freight += delivery_fee
            items.append((oid, j, f"p{product:05d}", f"s{int(rng.integers(50)):03d}", price, delivery_fee))
        payments.append((oid, 1, str(rng.choice(["Банковская карта", "Онлайн-перевод", "При получении", "Электронный кошелёк"],
                              p=[.7,.16,.1,.04])), round(subtotal + freight, 2)))
        # Связь опозданий с низкими оценками искусственно задана генератором.
        late = delivered is not None and delivered.date() > promised.date()
        score = int(rng.choice([1, 2, 3, 4, 5], p=[.15,.13,.2,.32,.2] if late else [.03,.05,.1,.28,.54]))
        if status == "delivered":
            reviews.append((oid, score))
    tables = {
        "orders": pd.DataFrame(orders, columns=["order_id", "customer_id", "order_status",
                    "order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"]),
        "customers": customers,
        "items": pd.DataFrame(items, columns=["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"]),
        "payments": pd.DataFrame(payments, columns=["order_id", "payment_sequential", "payment_type", "payment_value"]),
        "reviews": pd.DataFrame(reviews, columns=["order_id", "review_score"]),
        "products": products,
    }
    for key, frame in tables.items():
        frame.to_csv(output_dir / FILES[key], index=False)
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEMO)
    parser.add_argument("--orders", type=int, default=3600)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(f"Демонстрационные данные созданы в {generate_demo(args.output_dir, args.orders, args.seed)}")


if __name__ == "__main__":
    main()
