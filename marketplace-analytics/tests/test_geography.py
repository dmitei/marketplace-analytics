import sqlite3
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from marketplace_analytics.analytics import filter_orders, get_orders
from marketplace_analytics.bootstrap import ensure_demo_database
from marketplace_analytics.config import FILES
from marketplace_analytics.demo import generate_demo
from marketplace_analytics.etl import load_csvs


class GeographyTests(unittest.TestCase):
    def test_filters(self):
        df = pd.DataFrame({'country': ['Россия', 'Казахстан', 'Казахстан'],
                           'city': ['Москва', 'Алматы', 'Астана'],
                           'order_date': ['2024-01-01', '2024-02-01', '2024-03-01']})
        self.assertEqual(len(filter_orders(df, countries=['Казахстан'])), 2)
        self.assertEqual(filter_orders(df, countries=['Казахстан'], cities=['Алматы']).city.tolist(), ['Алматы'])
        self.assertTrue(filter_orders(df, countries=['Россия'], cities=['Алматы']).empty)
        self.assertTrue(filter_orders(df, countries=[]).empty)
        self.assertTrue(filter_orders(df, cities=[]).empty)
        self.assertEqual(len(filter_orders(df, start='2024-03-01', countries=['Казахстан'])), 1)

    def test_csv_to_mart_geography(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            demo = generate_demo(root / 'demo', n_orders=120)
            db = root / 'db.sqlite'
            load_csvs(demo, db)
            mart = get_orders(db)
            customers = pd.read_csv(demo / FILES['customers'])
            orders = pd.read_csv(demo / FILES['orders'])
            expected = orders.merge(customers, on='customer_id')[['order_id', 'country', 'city']].sort_values('order_id').reset_index(drop=True)
            pd.testing.assert_frame_equal(mart[['order_id', 'country', 'city']].sort_values('order_id').reset_index(drop=True), expected)
            self.assertNotIn('customer_state', mart.columns)

    def test_legacy_database_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'legacy.db'
            with sqlite3.connect(db) as conn:
                conn.execute('CREATE TABLE order_mart (order_id TEXT, customer_state TEXT)')
                conn.execute("INSERT INTO order_mart VALUES ('1', 'Казахстан · Алматы')")
            before = db.read_bytes()
            with self.assertRaisesRegex(ValueError, 'marketplace-demo'):
                ensure_demo_database(db, Path(folder) / 'demo')
            self.assertEqual(before, db.read_bytes())
