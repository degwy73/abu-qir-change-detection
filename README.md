# Multi-Decadal Change Detection — New Abu Qir, Alexandria

Multi-sensor, multi-decadal satellite change detection of the New Abu Qir
coastline on the Mediterranean shore of Alexandria, Egypt. Built entirely on
Google Earth Engine using Landsat 5/7/8/9, Sentinel-2, and Google's Dynamic
World land-cover product. End-to-end reproducible in Python.

![Built-up area time-series](outputs/charts/builtup_timeseries.png)

---

## Headline Findings (1990 → 2024)

| Metric | 1990 | 2024 | Change |
|---|---|---|---|
| Built-up area (Landsat, 30 m) | 9.20 km² | **22.06 km²** | **+140%** |
| Open-water area in AOI | 139.99 km² | 128.46 km² | −11.53 km² (reclamation) |
| Mean NDBI (built-up index) | −0.28 | **+0.23** | Sign flip — full urban substrate transition |
| Mean NDVI | −0.04 | −0.20 | Vegetation suppressed by construction |

**The most interesting finding is not the magnitude — it's the timing.**
NDBI flipped from negative to positive between 2015 and 2020, five years
*before* the built-up area surged. The satellite captured the surface
preparation phase (bare construction substrate replacing vegetation) before
the structures were visible. The 2020–2024 window then shows the active
build-out, with ~12 km² of new urban footprint and an equivalent reduction
in open water from reclamation.

---

## What the Repository Contains

- **End-to-end Python pipeline** for Google Earth Engine
- **Multi-sensor harmonization** across Landsat 5/7/8/9 + Sentinel-2
- **Five spectral indices**: NDVI, NDBI, MNDWI, NDWI, BSI
- **Built-up classification** using Dynamic World (post-2015) and a
  transparent NDBI/NDVI/MNDWI threshold rule for the pre-Dynamic-World era
- **Two change-detection methods**: image differencing and
  post-classification comparison
- **Auto-generated Markdown report** populated with the computed statistics
- **Time-lapse animations**, time-series charts, and an interactive notebook

The full methodology and per-period table is in
[`outputs/report/Abu_Qir_Change_Detection_Report.md`](outputs/report/Abu_Qir_Change_Detection_Report.md).

---

## Visual Highlights

![Landsat RGB time-lapse 1990–2024](outputs/maps/timelapse_landsat.gif)

![Change-class map: stable / new built / lost](outputs/maps/change_1990_to_2024.png)

Legend: grey = stable non-built · dark grey = stable built · red = new built (gain) · blue = lost built (rare).

---

## Reproducibility

The pipeline is fully reproducible by anyone with a free Earth Engine account.
All inputs are open public archives (Landsat, Sentinel-2, Dynamic World).

### Quickstart

```bash
# 1. Clone
git clone https://github.com/<your-handle>/abu-qir-change-detection.git
cd abu-qir-change-detection

# 2. Install (Python 3.11 or 3.12)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Authenticate Earth Engine
python -c "import ee; ee.Authenticate()"

# 4. Set your registered GEE project ID in config.py
#    GEE_PROJECT = "your-gee-project-id"

# 5. Run end-to-end
python run_all.py
```

Run time: ~5–10 minutes on the previews and stats; GeoTIFF exports run
asynchronously on Google's servers and land in your Google Drive folder
`AbuQir_ChangeDetection_Exports`.

### Adapt to a different location

Edit one line in `config.py`:

```python
AOI_BBOX = [minLon, minLat, maxLon, maxLat]   # EPSG:4326
```

Everything else — time periods, cloud thresholds, indices, classification,
report — re-runs unchanged.

---

## File Map

| File | Role |
|---|---|
| `config.py` | AOI, time periods, thresholds, visualisation styles |
| `abu_qir_workflow.py` | Main GEE pipeline (composites → indices → classification → change → exports) |
| `visualize_and_report.py` | Charts, time-lapses, interactive map, Markdown report |
| `run_all.py` | End-to-end orchestrator |
| `abu_qir_explorer.ipynb` | Interactive Jupyter notebook |
| `requirements.txt` | Python dependencies |
| `outputs/` | Generated artifacts (charts, maps, report, stats.json) |

---

## Methodology in One Paragraph

For every configured time window, the pipeline merges harmonised Landsat
5/7/8/9 surface reflectance collections (filtered to <30 % scene cloud cover,
QA-masked for cloud/shadow/snow), produces a median composite, and computes
five spectral indices. Built-up area is classified using Google's Dynamic
World V1 mode label for the 2015–present era; for earlier periods, a
transparent threshold rule (`NDBI > 0 AND NDVI < 0.2 AND MNDWI < 0`) is
applied as a reproducible fallback. Change detection runs in parallel via
NDBI image differencing and post-classification comparison of built-up
rasters between the first and last periods. Zonal statistics over the AOI
produce time-series of built-up km², open-water km², and mean indices,
which drive the auto-generated report and charts. Full-resolution GeoTIFFs
are exported to Google Drive in EPSG:32636 (UTM 36N).

---

## Limitations

1. The pre-2015 built-up classifier is an unsupervised threshold rule, not
   a trained model. Class boundaries are reproducible but not validated
   against ground truth. For production work, swap in a trained Random
   Forest using locally collected labelled points.
2. Cloud thresholds and median compositing handle residual noise but
   cannot fully eliminate cross-sensor radiometric drift.
3. The AOI is a rectangle. For applied work, use a precise municipal
   boundary polygon.
4. Shoreline extraction at 30 m (Landsat) carries sub-pixel positional
   uncertainty. For engineering-grade shoreline-change rate analysis,
   prefer Sentinel-2 (10 m) or commercial high-resolution imagery.

---

## About the Author

**Yasser Aldegwy, MSc.** — Geospatial Engineer based in Riyadh, originally
from Alexandria. 30+ years of geospatial industry experience across the
Middle East. Currently Executive Director at GeoSystems (النظم المكانية)
and Senior Project Manager on a large-scale national Digital Twin
initiative covering five Saudi cities.

LinkedIn: <https://www.linkedin.com/in/yasserdegwy/>

This study is a personal project applying open-data remote sensing
techniques to my hometown coastline.

---

## License

Released under the [MIT License](LICENSE). Public satellite data is
© ESA / © USGS / © Google as applicable.
