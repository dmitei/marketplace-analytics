import tempfile
import unittest
from pathlib import Path
import pandas as pd
from marketplace_analytics.config import FILES
from marketplace_analytics.demo import generate_demo


class CISDemoTests(unittest.TestCase):
    def test_reproducible_cis_data_and_payment_totals(self):
        with tempfile.TemporaryDirectory() as folder:
            a = generate_demo(Path(folder) / 'a', n_orders=120, seed=5)
            b = generate_demo(Path(folder) / 'b', n_orders=120, seed=5)
            for filename in FILES.values():
                self.assertEqual((a / filename).read_bytes(), (b / filename).read_bytes())
            customers = pd.read_csv(a / FILES['customers'])
            self.assertTrue(customers.city.notna().all())
            self.assertNotIn('customer_state', customers.columns)
            self.assertTrue(customers.country.str.contains('Россия|Беларусь|Казахстан|Армения|Кыргызстан|Узбекистан|Таджикистан|Азербайджан').all())
            orders = pd.read_csv(a / FILES['orders'])
            self.assertTrue(orders.order_id.is_unique)
            self.assertTrue((pd.to_datetime(orders.order_purchase_timestamp) >= '2024-01-01').all())
            items = pd.read_csv(a / FILES['items'])
            payments = pd.read_csv(a / FILES['payments'])
            self.assertTrue((items.price > 0).all())
            self.assertTrue(items.freight_value.between(99, 799).all())
            self.assertTrue(set(payments.payment_type) <= {'Банковская карта', 'Онлайн-перевод', 'При получении', 'Электронный кошелёк'})
            totals = items.assign(total=items.price + items.freight_value).groupby('order_id').total.sum()
            for row in payments.itertuples():
                self.assertAlmostEqual(row.payment_value, totals[row.order_id], places=2)
