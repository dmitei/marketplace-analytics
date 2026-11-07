"""Pure analytical functions reusable by dashboard, tests, and notebook."""
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
from .config import DB


def get_orders(db_path: Path = DB) -> pd.DataFrame:
    if not Path(db_path).is_file():
        raise FileNotFoundError(f"Database not found: {db_path}. Run marketplace-build --source demo first.")
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM order_mart", conn)


def filter_orders(df: pd.DataFrame, start=None, end=None, countries=None, cities=None) -> pd.DataFrame:
    out = df.copy()
    if start is not None:
        out = out[out.order_date >= str(start)[:10]]
    if end is not None:
        out = out[out.order_date <= str(end)[:10]]
    if countries is not None:
        out = out[out.country.isin(countries)]
    if cities is not None:
        out = out[out.city.isin(cities)]
    return out


def valid_orders(df: pd.DataFrame) -> pd.DataFrame:
    return df[df.is_valid.eq(1)].copy()


def kpis(df: pd.DataFrame) -> dict:
    valid = valid_orders(df)
    total_gmv = float(valid.gmv.sum())
    count = len(valid)
    unique = valid.customer_unique_id.nunique()
    # Repeat purchase share among customers within the selected period.
    counts = valid.groupby("customer_unique_id").size()
    return {
        "gmv": total_gmv,
        "orders": count,
        "aov": total_gmv / count if count else 0.0,
        "customers": int(unique),
        "repeat_share": float((counts >= 2).mean()) if unique else 0.0,
        "late_share": float(df.loc[df.is_late.notna(), "is_late"].mean()) if df.is_late.notna().any() else np.nan,
    }


def monthly_sales(df: pd.DataFrame) -> pd.DataFrame:
    valid = valid_orders(df)
    result = valid.groupby("order_month", as_index=False).agg(gmv=("gmv", "sum"), orders=("order_id", "count"))
    return result.sort_values("order_month")


def cohort_retention(df: pd.DataFrame) -> pd.DataFrame:
    """Month 0 = first observed eligible purchase; retention = distinct buyers returning in M+n.

    Use the full data history for interpretable cohorts, not a dashboard date-filtered slice.
    """
    valid = valid_orders(df)[["customer_unique_id", "order_month"]].drop_duplicates()
    if valid.empty:
        return pd.DataFrame(columns=["cohort", "period", "customers", "cohort_size", "retention"])
    valid["month"] = pd.to_datetime(valid.order_month + "-01")
    first = valid.groupby("customer_unique_id").month.transform("min")
    valid["cohort"] = first.dt.strftime("%Y-%m")
    valid["period"] = ((valid.month.dt.year - first.dt.year)*12 +
                       valid.month.dt.month - first.dt.month)
    sizes = valid[valid.period.eq(0)].groupby("cohort").customer_unique_id.nunique().rename("cohort_size")
    counts = valid.groupby(["cohort", "period"]).customer_unique_id.nunique().rename("customers").reset_index()
    counts = counts.merge(sizes, on="cohort")
    counts["retention"] = counts.customers / counts.cohort_size
    return counts.sort_values(["cohort", "period"]).reset_index(drop=True)


def rfm_segments(df: pd.DataFrame, as_of=None) -> pd.DataFrame:
    valid = valid_orders(df).copy()
    if valid.empty:
        return pd.DataFrame(columns=["customer_unique_id", "recency", "frequency", "monetary", "segment"])
    valid["date"] = pd.to_datetime(valid.order_date)
    ref = pd.Timestamp(as_of) if as_of else valid.date.max() + pd.Timedelta(days=1)
    if (valid.date > ref).any():
        raise ValueError("as_of date precedes some purchases")
    result = valid.groupby("customer_unique_id").agg(
        last_order=("date", "max"), frequency=("order_id", "nunique"), monetary=("gmv", "sum")
    ).reset_index()
    result["recency"] = (ref - result.last_order).dt.days
    # Rank with pct instead of qcut, which fails when frequency is mostly 1.
    r_pct = result.recency.rank(pct=True, ascending=False)
    f_pct = result.frequency.rank(pct=True)
    m_pct = result.monetary.rank(pct=True)
    result["rfm_score"] = (np.ceil(r_pct * 5).clip(1, 5).astype(int) +
                           np.ceil(f_pct * 5).clip(1, 5).astype(int) +
                           np.ceil(m_pct * 5).clip(1, 5).astype(int))
    result["segment"] = np.select(
        [result.rfm_score >= 12, result.rfm_score >= 9, result.rfm_score >= 6],
        ["Champions", "Loyal / potential", "Needs attention"], default="At risk"
    )
    return result.drop(columns=["last_order"])


def delivery_summary(df: pd.DataFrame) -> pd.DataFrame:
    delivered = df[df.is_late.notna() & df.review_score.notna()].copy()
    if delivered.empty:
        return pd.DataFrame(columns=["delivery_group", "orders", "average_review", "low_rating_share"])
    delivered["delivery_group"] = np.where(delivered.is_late.eq(1), "Late", "On time")
    delivered["low_rating"] = delivered.review_score <= 2
    return delivered.groupby("delivery_group", as_index=False).agg(
        orders=("order_id", "count"), average_review=("review_score", "mean"),
        low_rating_share=("low_rating", "mean")
    )
