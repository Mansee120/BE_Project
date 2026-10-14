"""
report.py
---------
Prints the YojanaBench accuracy report as pandas DataFrames and saves each
table as a CSV under reports/.

Usage:
    python report.py

The tables themselves are produced by backend.report.build_report(), which is
also what the dashboard's /api/report endpoint serves.
"""
import os

import pandas as pd

from backend.report import build_report

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 60)
pd.set_option("display.unicode.east_asian_width", True)

REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def main():
    raw = build_report()
    frames = {name: pd.DataFrame(rows) for name, rows in raw.items()}

    os.makedirs(REPORT_DIR, exist_ok=True)

    print("\n" + "=" * 78)
    print("  YojanaBench - ACCURACY REPORT")
    print("=" * 78)

    for name, df in frames.items():
        print(f"\n### {name.replace('_', ' ').upper()}")
        print(df.to_string(index=False))
        df.to_csv(os.path.join(REPORT_DIR, name + ".csv"), index=False)

    print(f"\nCSV reports written to: {REPORT_DIR}")


if __name__ == "__main__":
    main()
