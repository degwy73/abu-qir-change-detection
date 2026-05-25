"""
End-to-end orchestrator for the Abu Qir change detection workflow.

Sequence:
  1. abu_qir_workflow.run()   -> queues GeoTIFF exports, writes PNGs + stats.json
  2. visualize_and_report.run() -> charts, time-lapse GIFs, interactive map, MD report

Usage:
    python run_all.py
"""

from __future__ import annotations
import time

import abu_qir_workflow
import visualize_and_report


def main() -> None:
    t0 = time.time()
    print("\n##### STEP 1/2 — Earth Engine analysis #####")
    abu_qir_workflow.run()

    print("\n##### STEP 2/2 — Local visualization & report #####")
    visualize_and_report.run()

    print(f"\n[ALL DONE] Total wall time: {time.time() - t0:.1f} s")
    print("Outputs in: ./outputs/")
    print("Final report: ./outputs/report/Abu_Qir_Change_Detection_Report.md")
    print("Drive exports: monitor at "
          "https://code.earthengine.google.com/tasks")


if __name__ == "__main__":
    main()
