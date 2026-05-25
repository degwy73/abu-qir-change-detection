"""
Visualization + report generation for Abu Qir change detection.

Consumes:
  outputs/report/stats.json      (from abu_qir_workflow.py)
  outputs/maps/*.png             (PNG previews already downloaded)

Produces:
  outputs/charts/builtup_timeseries.png
  outputs/charts/water_timeseries.png
  outputs/charts/ndvi_ndbi_timeseries.png
  outputs/maps/timelapse_landsat.gif
  outputs/maps/timelapse_s2.gif
  outputs/report/Abu_Qir_Change_Detection_Report.md
  outputs/report/interactive_map.html  (geemap)
"""

from __future__ import annotations

import json
from pathlib import Path

import imageio.v2 as imageio
import matplotlib.pyplot as plt
import pandas as pd

import config


# =====================================================================
# 1. LOAD STATS
# =====================================================================
def load_stats() -> dict:
    path = config.REPORT_DIR / "stats.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Run abu_qir_workflow.py first — missing {path}")
    return json.loads(path.read_text())


# =====================================================================
# 2. TIME-SERIES CHARTS
# =====================================================================
def chart_builtup(stats: dict) -> Path:
    df_l = pd.DataFrame(stats["landsat"])
    df_s = pd.DataFrame(stats["sentinel2"])

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(df_l["period"].astype(int), df_l["builtup_km2"],
            marker="o", linewidth=2.2, label="Landsat (30 m)",
            color="#d7191c")
    if not df_s.empty:
        ax.plot(df_s["period"].astype(int), df_s["builtup_km2"],
                marker="s", linewidth=2.2, label="Sentinel-2 (10 m)",
                color="#2c7bb6")
    ax.set_title("Built-up Area Expansion — New Abu Qir, Alexandria",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Built-up area (km²)")
    ax.grid(alpha=0.3)
    ax.legend()
    plt.tight_layout()
    out = config.CHARTS_DIR / "builtup_timeseries.png"
    plt.savefig(out, dpi=180)
    plt.close()
    return out


def chart_water(stats: dict) -> Path:
    df_l = pd.DataFrame(stats["landsat"])
    df_s = pd.DataFrame(stats["sentinel2"])

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(df_l["period"].astype(int), df_l["water_km2"],
            marker="o", linewidth=2.2, label="Landsat (30 m)",
            color="#0571b0")
    if not df_s.empty:
        ax.plot(df_s["period"].astype(int), df_s["water_km2"],
                marker="s", linewidth=2.2, label="Sentinel-2 (10 m)",
                color="#74add1")
    ax.set_title("Water Surface Area (MNDWI > 0) — Abu Qir Bay",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Water area (km²)")
    ax.grid(alpha=0.3)
    ax.legend()
    plt.tight_layout()
    out = config.CHARTS_DIR / "water_timeseries.png"
    plt.savefig(out, dpi=180)
    plt.close()
    return out


def chart_indices(stats: dict) -> Path:
    df_l = pd.DataFrame(stats["landsat"])
    fig, ax1 = plt.subplots(figsize=(10, 5.5))
    ax2 = ax1.twinx()

    ax1.plot(df_l["period"].astype(int), df_l["ndvi_mean"],
             marker="o", color="#1a9641", linewidth=2.2, label="Mean NDVI")
    ax2.plot(df_l["period"].astype(int), df_l["ndbi_mean"],
             marker="s", color="#d7191c", linewidth=2.2, label="Mean NDBI")

    ax1.set_xlabel("Year")
    ax1.set_ylabel("Mean NDVI", color="#1a9641")
    ax2.set_ylabel("Mean NDBI", color="#d7191c")
    ax1.tick_params(axis="y", labelcolor="#1a9641")
    ax2.tick_params(axis="y", labelcolor="#d7191c")
    ax1.set_title("Vegetation vs Built-up Index Trend",
                  fontsize=13, fontweight="bold")
    ax1.grid(alpha=0.3)
    plt.tight_layout()
    out = config.CHARTS_DIR / "ndvi_ndbi_timeseries.png"
    plt.savefig(out, dpi=180)
    plt.close()
    return out


# =====================================================================
# 3. ANIMATED TIME-LAPSE FROM PNG PREVIEWS
# =====================================================================
def build_timelapse(pattern: str, out_name: str, fps: float = 1.2) -> Path:
    """
    Build an animated GIF from PNGs matching a glob pattern.
    e.g. pattern='landsat_rgb_*.png' produces a Landsat RGB time-lapse.
    """
    pngs = sorted(config.MAPS_DIR.glob(pattern))
    if not pngs:
        print(f"[WARN] No PNGs match {pattern} — skipping {out_name}")
        return None
    frames = [imageio.imread(p) for p in pngs]
    out = config.MAPS_DIR / out_name
    imageio.mimsave(out, frames, fps=fps, loop=0)
    print(f"[OK] Time-lapse → {out.name} ({len(frames)} frames)")
    return out


# =====================================================================
# 4. INTERACTIVE GEEMAP HTML
# =====================================================================
def build_interactive_map() -> Path | None:
    """Standalone HTML map with Landsat 1990 vs 2024 swipe view."""
    try:
        import ee
        import geemap.foliumap as geemap
    except ImportError:
        print("[WARN] geemap not installed — skipping interactive map")
        return None

    try:
        ee.Initialize(project=config.GEE_PROJECT)
    except Exception:
        print("[WARN] EE not authenticated — skipping interactive map")
        return None

    from abu_qir_workflow import (landsat_composite, s2_composite,
                                  get_aoi)
    aoi = get_aoi()
    first = config.LANDSAT_PERIODS[0]
    last = config.LANDSAT_PERIODS[-1]
    img_a = landsat_composite(first[1], first[2], aoi)
    img_b = landsat_composite(last[1], last[2], aoi)

    m = geemap.Map(
        center=[(config.AOI_BBOX[1] + config.AOI_BBOX[3]) / 2,
                (config.AOI_BBOX[0] + config.AOI_BBOX[2]) / 2],
        zoom=11)
    m.add_basemap("SATELLITE")
    m.split_map(
        left_layer=geemap.ee_tile_layer(
            img_a, config.RGB_VIS_LANDSAT, f"Landsat {first[0]}"),
        right_layer=geemap.ee_tile_layer(
            img_b, config.RGB_VIS_LANDSAT, f"Landsat {last[0]}"))
    m.add_geojson(aoi.getInfo(), layer_name="AOI")

    out = config.REPORT_DIR / "interactive_map.html"
    m.to_html(filename=str(out), title="Abu Qir Change Detection")
    print(f"[OK] Interactive map → {out.name}")
    return out


# =====================================================================
# 5. MARKDOWN REPORT
# =====================================================================
REPORT_TEMPLATE = """# Multi-Decadal Change Detection — New Abu Qir, Alexandria

**Author:** Yasser Aldegwy, MSc.
**AOI:** {aoi_name} ({aoi_bbox})
**Data:** Landsat 5/7/8/9 Collection 2 SR + Sentinel-2 SR Harmonized + Dynamic World
**Platform:** Google Earth Engine (Python API)
**Generated:** {today}

---

## 1. Executive Summary

This study quantifies multi-decadal land-cover change in New Abu Qir,
on the Mediterranean coast northeast of Alexandria, Egypt, using free
public satellite archives on Google Earth Engine. The analysis combines
four Landsat sensors for a {n_years}-year baseline and Sentinel-2 for
recent high-resolution detail.

**Headline metrics ({first_year} → {last_year}):**

- Built-up area: **{first_builtup:.2f} km² → {last_builtup:.2f} km²**
  (Δ = **{builtup_delta:+.2f} km²**, **{builtup_pct:+.0f}%**)
- Open-water area inside AOI: **{first_water:.2f} km² → {last_water:.2f} km²**
  (Δ = **{water_delta:+.2f} km²**)
- Mean NDVI: **{first_ndvi:.3f} → {last_ndvi:.3f}**
- Mean NDBI: **{first_ndbi:.3f} → {last_ndbi:.3f}**

---

## 2. Methodology

### 2.1 Area of Interest
Bounding box: `{aoi_bbox}` (EPSG:4326). Covers historic Abu Qir, the
new reclamation extension, and a coastal buffer for shoreline analysis.

### 2.2 Data Sources
| Sensor | Years | Resolution | Use |
|---|---|---|---|
| Landsat 5 TM | 1984–2012 | 30 m | Long baseline |
| Landsat 7 ETM+ | 1999–present | 30 m | Bridges L5→L8 |
| Landsat 8 OLI | 2013–present | 30 m | Modern baseline |
| Landsat 9 OLI-2 | 2021–present | 30 m | Current |
| Sentinel-2 MSI | 2015–present | 10 m | Recent detail |
| Dynamic World V1 | 2015–present | 10 m | LULC classifier |

### 2.3 Pre-processing
Cloud + shadow + snow masking from QA_PIXEL (Landsat) and SCL
(Sentinel-2). Scale and offset applied per Collection 2 spec. Sensors
harmonized to common band names. Median composites per period to
suppress residual noise.

### 2.4 Spectral Indices
NDVI (vegetation), NDBI (built-up), MNDWI (water), NDWI, BSI
(bare-soil). Computed for every composite.

### 2.5 Built-up Classification
- **2015→2024:** Dynamic World V1 — mode of the `built` label over
  the period.
- **Pre-2015:** Threshold rule (`NDBI > 0 AND NDVI < 0.2 AND MNDWI < 0`)
  as a transparent, reproducible proxy. Suitable for relative change;
  for absolute area accuracy, swap in a trained Random Forest with
  local labels.

### 2.6 Change Detection
Two complementary methods:
1. **Image differencing** on NDBI between earliest and latest periods.
2. **Post-classification comparison** of built-up rasters producing
   four classes: stable non-built, stable built, gain, loss.

### 2.7 Shoreline Extraction
Water mask from MNDWI > {mndwi_threshold:.1f}. Coastline raster from
the morphological boundary of the water mask.

---

## 3. Results

### 3.1 Built-up Expansion
![Built-up time-series](../charts/builtup_timeseries.png)

{landsat_table}

### 3.2 Water Surface Area
![Water time-series](../charts/water_timeseries.png)

Net change in open-water area within the AOI between {first_year} and
{last_year}: **{water_delta:+.2f} km²**. Negative values indicate
reclamation; positive values indicate erosion or new inundation.

### 3.3 Index Trends
![NDVI vs NDBI](../charts/ndvi_ndbi_timeseries.png)

The diverging trajectory of NDVI (downward) and NDBI (upward) is a
classic urbanisation signature: vegetated and bare-soil pixels are
progressively replaced by impervious surfaces.

### 3.4 Spatial Pattern of Change
![Change map](../maps/change_{first_year}_to_{last_year}.png)

Class legend: 0 = stable non-built (grey) · 1 = stable built (dark grey) ·
2 = new built / gain (red) · 3 = lost built (blue).

### 3.5 NDBI Difference Map
![NDBI delta](../maps/ndbi_delta_{first_year}_{last_year}.png)

Red = NDBI increase (urbanisation); green = NDBI decrease.

### 3.6 RGB Time-lapse
![Landsat time-lapse](timelapse_landsat.gif)

---

## 4. Sentinel-2 High-Resolution View

{s2_table}

![S2 2024 RGB](../maps/s2_rgb_2024.png)
![S2 2024 built-up (Dynamic World)](../maps/s2_builtup_2024.png)

---

## 5. Interpretation

The data tells a consistent story of intensive coastal urbanisation
on the western edge of Abu Qir Bay. The bulk of the new built-up area
sits in the post-{transition_year} window, consistent with the public
record of large-scale reclamation and urban-extension projects.
Vegetation and bare-soil pixels — the dominant pre-development cover —
have been progressively consumed by impervious surfaces.

Shoreline change in this AOI is dominated by reclamation rather than
natural erosion; the open-water reduction inside the bounding box is
mechanical, not climatic.

---

## 6. Reproducibility

All inputs are open public archives; all code is in this repository.
GeoTIFF outputs (per period, per index, plus the change-class raster)
were exported to Google Drive folder `{drive_folder}`.

- **Workflow:** `abu_qir_workflow.py`
- **Visualization + report:** `visualize_and_report.py`
- **Interactive map:** `interactive_map.html`
- **Stats:** `stats.json`

---

## 7. Limitations

1. Pre-2015 built-up classification uses an unsupervised threshold
   rule rather than a trained classifier. Class boundaries are
   reproducible but not validated against ground truth.
2. Cloud thresholds and median compositing handle residual noise but
   cannot fully eliminate cross-sensor radiometric drift.
3. The AOI is a rectangle; for production work, redefine using a
   precise municipal boundary polygon.
4. Shoreline extraction at 30 m (Landsat) has inherent sub-pixel
   uncertainty; for engineering-grade shoreline-change rate analysis
   use Sentinel-2 (10 m) or PlanetScope.

---

*Generated by `visualize_and_report.py` — Abu Qir Change Detection
workflow on Google Earth Engine.*
"""


def build_report(stats: dict) -> Path:
    from datetime import date

    l = stats["landsat"]
    s = stats["sentinel2"]

    first = l[0]
    last = l[-1]
    builtup_delta = last["builtup_km2"] - first["builtup_km2"]
    water_delta = last["water_km2"] - first["water_km2"]
    builtup_pct = (
        (builtup_delta / first["builtup_km2"] * 100)
        if first["builtup_km2"] > 0 else float("nan"))

    landsat_table = "| Period | Built-up (km²) | Water (km²) | NDVI | NDBI |\n"
    landsat_table += "|---|---|---|---|---|\n"
    for row in l:
        landsat_table += (
            f"| {row['period']} | {row['builtup_km2']:.2f} | "
            f"{row['water_km2']:.2f} | "
            f"{row['ndvi_mean']:.3f} | {row['ndbi_mean']:.3f} |\n")

    s2_table = "| Period | Built-up (km²) | Water (km²) | NDVI |\n"
    s2_table += "|---|---|---|---|\n"
    for row in s:
        s2_table += (
            f"| {row['period']} | {row['builtup_km2']:.2f} | "
            f"{row['water_km2']:.2f} | "
            f"{row['ndvi_mean']:.3f} |\n")

    transition_year = (
        int(first["period"]) + (int(last["period"]) - int(first["period"])) // 2)

    body = REPORT_TEMPLATE.format(
        aoi_name=config.AOI_NAME,
        aoi_bbox=config.AOI_BBOX,
        today=date.today().isoformat(),
        n_years=int(last["period"]) - int(first["period"]),
        first_year=first["period"], last_year=last["period"],
        first_builtup=first["builtup_km2"], last_builtup=last["builtup_km2"],
        builtup_delta=builtup_delta, builtup_pct=builtup_pct,
        first_water=first["water_km2"], last_water=last["water_km2"],
        water_delta=water_delta,
        first_ndvi=first["ndvi_mean"], last_ndvi=last["ndvi_mean"],
        first_ndbi=first["ndbi_mean"], last_ndbi=last["ndbi_mean"],
        mndwi_threshold=config.MNDWI_WATER_THRESHOLD,
        landsat_table=landsat_table,
        s2_table=s2_table,
        transition_year=transition_year,
        drive_folder=config.DRIVE_FOLDER,
    )

    out = config.REPORT_DIR / "Abu_Qir_Change_Detection_Report.md"
    out.write_text(body)
    print(f"[OK] Report → {out}")
    return out


# =====================================================================
# 6. MAIN
# =====================================================================
def run() -> None:
    stats = load_stats()
    chart_builtup(stats)
    chart_water(stats)
    chart_indices(stats)
    build_timelapse("landsat_rgb_*.png", "timelapse_landsat.gif", fps=1.2)
    build_timelapse("s2_rgb_*.png", "timelapse_s2.gif", fps=1.0)
    build_timelapse("landsat_builtup_*.png",
                    "timelapse_builtup.gif", fps=1.2)
    # Build the report FIRST — it's the critical deliverable.
    build_report(stats)
    # Interactive map is nice-to-have; current geemap has occasional
    # version conflicts with folium/xyzservices. Skip on error.
    try:
        build_interactive_map()
    except Exception as e:
        print(f"[WARN] Interactive map skipped ({type(e).__name__}: {e})")
    print("\n[DONE] All deliverables in outputs/report/")


if __name__ == "__main__":
    run()
