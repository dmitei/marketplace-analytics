import pandas as pd
import pytest
from marketplace_analytics.analytics import (kpis, cohort_retention, rfm_segments, delivery_summary)
from marketplace_analytics.demo import generate_demo
from marketplace_analytics.etl import load_csvs
from marketplace_analytics.analytics import get_orders


def test_order_grain_and_gmv_no_join_inflation(tmp_path):
    input_dir = generate_demo(tmp_path / "demo", n_orders=120, seed=5)
    db = tmp_path / "test.sqlite"
    load_csvs(input_dir, db)
    mart = get_orders(db)
    items = pd.read_csv(input_dir / "items.csv")
    assert len(mart) == 120
    assert mart.order_id.is_unique
    assert mart.gmv.sum() == pytest.approx(items.price.sum(), abs=.02)
    assert mart.items_count.sum() == len(items)


def test_filter_and_kpis(tmp_path):
    folder = generate_demo(tmp_path / "d", n_orders=60)
    db = tmp_path / "db.sqlite"
    load_csvs(folder, db)
    mart = get_orders(db)
    m = kpis(mart)
    assert m["orders"] <= 60
    assert m["gmv"] > 0
    assert 0 <= m["repeat_share"] <= 1


def test_retention_excludes_same_month_double_count():
    df = pd.DataFrame({
        "customer_unique_id": ["a", "a", "a", "b", "b"],
        "order_month": ["2024-01", "2024-01", "2024-02", "2024-01", "2024-03"],
        "is_valid": [1, 1, 1, 1, 1],
    })
    result = cohort_retention(df)
    assert result[(result.cohort == "2024-01") & (result.period == 0)].iloc[0].cohort_size == 2
    assert result[(result.cohort == "2024-01") & (result.period == 1)].iloc[0].retention == .5
    assert result[(result.cohort == "2024-01") & (result.period == 2)].iloc[0].retention == .5


def test_rfm_and_delivery():
    df = pd.DataFrame({
        "customer_unique_id": ["a", "a", "b"],
        "order_id": ["1", "2", "3"],
        "order_date": ["2024-01-01", "2024-01-15", "2024-02-01"],
        "is_valid": [1, 1, 1],
        "gmv": [100., 200., 50.],
        "is_late": [0., 1., None],
        "review_score": [5., 1., None],
    })
    rfm = rfm_segments(df, "2024-03-01")
    assert rfm.loc[rfm.customer_unique_id.eq("a"), "frequency"].iloc[0] == 2
    deliv = delivery_summary(df)
    assert deliv.orders.sum() == 2
    assert deliv.loc[deliv.delivery_group.eq("Late"), "low_rating_share"].iloc[0] == 1
