#!/usr/bin/env python3
"""
Root entry point for the AML / Financial Intelligence one-page report.

    # 1) Demo mode — build from a generated synthetic dataset
    python generate_report.py

    # 2) Real data — point it at your Excel statement
    python generate_report.py --excel /path/to/statement.xlsx

    # ...or via environment variables (equivalent):
    AML_INPUT_MODE=excel AML_EXCEL_PATH=/path/statement.xlsx python generate_report.py

Output (in ./output):
    AML_Intelligence_Report.pdf    <- single-page landscape deliverable
    AML_Intelligence_Report.html   <- same report as HTML (for quick preview)
    preview.png                    <- raster snapshot of the sheet
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate the AML intelligence report.")
    ap.add_argument("--excel", help="Path to a real .xlsx/.csv statement to analyse.")
    ap.add_argument("--regen-data", action="store_true",
                    help="Force-regenerate the synthetic demo dataset.")
    args = ap.parse_args()

    if args.excel:
        os.environ["AML_INPUT_MODE"] = "excel"
        os.environ["AML_EXCEL_PATH"] = os.path.abspath(args.excel)
        config.INPUT_MODE = "excel"
        config.EXCEL_PATH = os.path.abspath(args.excel)

    if args.regen_data:
        from data_generator import main as gen
        gen()

    import report
    report.main()


if __name__ == "__main__":
    main()
