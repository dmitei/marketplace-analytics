"""Run a provided SQL report against the built SQLite database."""
import argparse
import sqlite3
from pathlib import Path
import pandas as pd
from marketplace_analytics.config import DB, ROOT


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", nargs="?", default="01_business_kpis.sql")
    p.add_argument("--db", type=Path, default=DB)
    args = p.parse_args()
    query_path = ROOT / "sql" / args.report
    if not query_path.is_file():
        p.error(f"SQL report not found: {query_path}")
    with sqlite3.connect(args.db) as conn:
        print(pd.read_sql_query(query_path.read_text(encoding="utf-8"), conn).to_string(index=False))


if __name__ == "__main__":
    main()
