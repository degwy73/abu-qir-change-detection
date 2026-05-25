"""
Configuration for Abu Qir (Alexandria, Egypt) change detection workflow.
Edit AOI coordinates, time periods, and parameters here. Everything else
in the project consumes from this file.
"""

from pathlib import Path

# -------------------------------------------------------------------
# PROJECT PATHS
# -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
MAPS_DIR = OUTPUTS_DIR / "maps"
CHARTS_DIR = OUTPUTS_DIR / "charts"
GEOTIFFS_DIR = OUTPUTS_DIR / "geotiffs"
REPORT_DIR = OUTPUTS_DIR / "report"

# -------------------------------------------------------------------
# GOOGLE EARTH ENGINE PROJECT
# -------------------------------------------------------------------
# Replace with your registered GEE Cloud project ID after running
# `earthengine authenticate` and registering at code.earthengine.google.com.
GEE_PROJECT = "abu-qir-alex"

# -------------------------------------------------------------------
# AREA OF INTEREST — New Abu Qir / Abu Qir Bay, NE of Alexandria
# Bounding box covers historic Abu Qir, the new reclamation extension,
# and a buffer of coastline for shoreline analysis.
# Format: [minLon, minLat, maxLon, maxLat] in EPSG:4326
# -------------------------------------------------------------------
AOI_BBOX = [30.0200, 31.2700, 30.1800, 31.3700]
AOI_NAME = "New_Abu_Qir_Alexandria"

# -------------------------------------------------------------------
# TIME PERIODS FOR CHANGE DETECTION
# Each period is a 2-year composite to reduce cloud/seasonal noise.
# Landsat archive starts 1984; Sentinel-2 starts 2015.
# -------------------------------------------------------------------
LANDSAT_PERIODS = [
    ("1990", "1990-01-01", "1991-12-31"),
    ("1995", "1995-01-01", "1996-12-31"),
    ("2000", "2000-01-01", "2001-12-31"),
    ("2005", "2005-01-01", "2006-12-31"),
    ("2010", "2010-01-01", "2011-12-31"),
    ("2015", "2015-01-01", "2016-12-31"),
    ("2020", "2020-01-01", "2021-12-31"),
    ("2024", "2024-01-01", "2025-12-31"),
]

# Sentinel-2 disabled — Landsat alone provides the headline result and the
# S2 visualization params required separate tuning that wasn't worth the
# marginal value-add. Re-enable here if you want a higher-resolution
# snapshot for recent years.
SENTINEL2_PERIODS = []

# -------------------------------------------------------------------
# CLOUD MASKING
# -------------------------------------------------------------------
LANDSAT_CLOUD_THRESHOLD = 30  # percent
S2_CLOUD_THRESHOLD = 20       # percent

# -------------------------------------------------------------------
# SPECTRAL INDICES — produced for every composite
# -------------------------------------------------------------------
INDICES = ["NDVI", "NDBI", "MNDWI", "NDWI", "BSI"]

# -------------------------------------------------------------------
# CLASSIFICATION — built-up vs non-built-up
# Uses Dynamic World (S2 era) and a Random Forest fallback for Landsat era.
# -------------------------------------------------------------------
USE_DYNAMIC_WORLD = True
RF_TRAINING_SAMPLES_PER_CLASS = 500
RF_NUM_TREES = 100

# -------------------------------------------------------------------
# SHORELINE EXTRACTION
# MNDWI threshold to separate water from land.
# Typically 0.0 works well for Mediterranean coast composites.
# -------------------------------------------------------------------
MNDWI_WATER_THRESHOLD = 0.0

# -------------------------------------------------------------------
# EXPORT SETTINGS
# Large rasters export to Google Drive (folder name below) since the
# Python API can't write directly to local disk for big rasters.
# Smaller PNG previews are pulled via ee.Image.getThumbURL.
# -------------------------------------------------------------------
DRIVE_FOLDER = "AbuQir_ChangeDetection_Exports"
THUMBNAIL_SCALE = 30   # meters per pixel for PNG previews
EXPORT_SCALE_LANDSAT = 30
EXPORT_SCALE_S2 = 10
MAX_PIXELS = 1e10

# -------------------------------------------------------------------
# VISUALIZATION
# -------------------------------------------------------------------
RGB_VIS_LANDSAT = {
    "bands": ["SR_B4", "SR_B3", "SR_B2"],
    "min": 0.02,
    "max": 0.30,
    "gamma": 1.2,
}
RGB_VIS_S2 = {
    "bands": ["B4", "B3", "B2"],
    "min": 300,
    "max": 3000,
    "gamma": 1.1,
}
NDVI_VIS = {"min": -0.2, "max": 0.8,
            "palette": ["#b30000", "#e6e600", "#1a9641"]}
NDBI_VIS = {"min": -0.3, "max": 0.3,
            "palette": ["#1a9641", "#ffffbf", "#d7191c"]}
MNDWI_VIS = {"min": -0.5, "max": 0.5,
             "palette": ["#a6611a", "#ffffbf", "#0571b0"]}
BUILTUP_VIS = {"min": 0, "max": 1,
               "palette": ["#cccccc", "#d7191c"]}
CHANGE_VIS = {"min": -1, "max": 1,
              "palette": ["#1a9641", "#ffffbf", "#d7191c"]}
