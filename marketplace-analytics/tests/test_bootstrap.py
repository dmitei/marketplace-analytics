"""Integration checks for a clean first launch and safe subsequent launches."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from marketplace_analytics.bootstrap import ensure_demo_database
from marketplace_analytics.analytics import get_orders, kpis, cohort_retention, rfm_segments
from marketplace_analytics.config import FILES, ROOT


class BootstrapTests(unittest.TestCase):
    def test_clean_launch_and_existing_database(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db, demo = root / 'processed' / 'marketplace.db', root / 'demo'
            ensure_demo_database(db, demo)
            orders = get_orders(db)
            self.assertEqual(len(orders), 3600)
            self.assertTrue(orders.order_id.is_unique)
            items = pd.read_csv(demo / FILES['items'])
            self.assertAlmostEqual(orders.gmv.sum(), items.price.sum(), places=2)
            self.assertGreater(kpis(orders)['gmv'], 0)
            self.assertFalse(cohort_retention(orders).empty)
            self.assertFalse(rfm_segments(orders).empty)
            with sqlite3.connect(db) as conn:
                for report in sorted((ROOT / 'sql').glob('*.sql')):
                    self.assertTrue(conn.execute(report.read_text()).fetchall())
            before = db.read_bytes()
            modified = db.stat().st_mtime_ns
            (demo / FILES['orders']).unlink()
            ensure_demo_database(db, demo)
            self.assertEqual(db.read_bytes(), before)
            self.assertEqual(db.stat().st_mtime_ns, modified)
            self.assertFalse((demo / FILES['orders']).exists())

    def test_incomplete_csvs_without_database_are_regenerated(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            demo = root / 'demo'
            demo.mkdir()
            (demo / FILES['orders']).write_text('incomplete')
            db = root / 'marketplace.db'
            ensure_demo_database(db, demo)
            self.assertTrue(all((demo / name).is_file() for name in FILES.values()))
            self.assertEqual(len(get_orders(db)), 3600)
