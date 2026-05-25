"""
Abu Qir (Alexandria, Egypt) — multi-decadal change detection workflow on
Google Earth Engine.

Pipeline:
  1. Authenticate & initialize Earth Engine
  2. Build harmonized Landsat 5/7/8/9 + Sentinel-2 composites per period
  3. Compute spectral indices (NDVI, NDBI, MNDWI, NDWI, BSI)
  4. Classify built-up area (Dynamic World for S2 era, Random Forest for
     Landsat era)
  5. Detect change: image differencing + post-classification comparison
  6. Extract shoreline (MNDWI threshold) per period
  7. Compute time-series statistics over the AOI
  8. Export GeoTIFFs to Google Drive + PNG previews locally
  9. Hand off stats to the report generator

Run:  python abu_qir_workflow.py
Pre-req:  earthengine authenticate  (one-time)
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import ee

import config


# =====================================================================
# 1. EE INITIALIZATION
# =====================================================================
def initialize_ee() -> None:
    """Initialize Earth Engine with the user's registered Cloud project."""
    try:
        ee.Initialize(project=config.GEE_PROJECT)
        print(f"[OK] EE initialized with project: {config.GEE_PROJECT}")
    except Exception:
        print("[INFO] Running ee.Authenticate() — follow the browser prompt.")
        ee.Authenticate()
        ee.Initialize(project=config.GEE_PROJECT)


def get_aoi() -> ee.Geometry:
    """Return the AOI as an ee.Geometry rectangle."""
    return ee.Geometry.Rectangle(config.AOI_BBOX)


# =====================================================================
# 2. LANDSAT HARMONIZATION & COMPOSITES
# =====================================================================
# Landsat Collection 2 Level-2 surface reflectance band mapping.
# We rename to common names so L5/L7/L8/L9 can be merged.
L578_BANDS_FROM = ["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7",
                   "QA_PIXEL"]
L578_BANDS_TO = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7",
                 "QA_PIXEL"]
L89_BANDS_FROM = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7",
                  "QA_PIXEL"]
L89_BANDS_TO = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7",
                "QA_PIXEL"]


def mask_landsat_clouds(image: ee.Image) -> ee.Image:
    """Cloud + cloud-shadow mask from Landsat C2 QA_PIXEL."""
    qa = image.select("QA_PIXEL")
    # bits 3 = cloud, 4 = cloud shadow, 5 = snow, 1 = dilated cloud
    cloud_mask = (
        qa.bitwiseAnd(1 << 3).eq(0)
        .And(qa.bitwiseAnd(1 << 4).eq(0))
        .And(qa.bitwiseAnd(1 << 5).eq(0))
        .And(qa.bitwiseAnd(1 << 1).eq(0))
    )
    return image.updateMask(cloud_mask)


def scale_landsat(image: ee.Image) -> ee.Image:
    """Apply Collection 2 scale + offset to surface reflectance bands."""
    optical = image.select("SR_B.").multiply(0.0000275).add(-0.2)
    return image.addBands(optical, overwrite=True)


def get_landsat_collection(start: str, end: str,
                           aoi: ee.Geometry) -> ee.ImageCollection:
    """Merge Landsat 5/7/8/9 SR collections for the date range, harmonized."""
    l5 = (ee.ImageCollection("LANDSAT/LT05/C02/T1_L2")
          .filterDate(start, end).filterBounds(aoi)
          .filter(ee.Filter.lt("CLOUD_COVER", config.LANDSAT_CLOUD_THRESHOLD))
          .select(L578_BANDS_FROM, L578_BANDS_TO))
    l7 = (ee.ImageCollection("LANDSAT/LE07/C02/T1_L2")
          .filterDate(start, end).filterBounds(aoi)
          .filter(ee.Filter.lt("CLOUD_COVER", config.LANDSAT_CLOUD_THRESHOLD))
          .select(L578_BANDS_FROM, L578_BANDS_TO))
    l8 = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
          .filterDate(start, end).filterBounds(aoi)
          .filter(ee.Filter.lt("CLOUD_COVER", config.LANDSAT_CLOUD_THRESHOLD))
          .select(L89_BANDS_FROM, L89_BANDS_TO))
    l9 = (ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
          .filterDate(start, end).filterBounds(aoi)
          .filter(ee.Filter.lt("CLOUD_COVER", config.LANDSAT_CLOUD_THRESHOLD))
          .select(L89_BANDS_FROM, L89_BANDS_TO))
    return (l5.merge(l7).merge(l8).merge(l9)
            .map(mask_landsat_clouds).map(scale_landsat))


def landsat_composite(start: str, end: str,
                      aoi: ee.Geometry) -> ee.Image:
    """Median composite over the date range, clipped to AOI."""
    coll = get_landsat_collection(start, end, aoi)
    composite = coll.median().clip(aoi)
    return composite.set({"period_start": start, "period_end": end,
                          "sensor": "Landsat"})


# =====================================================================
# 3. SENTINEL-2 COMPOSITES
# =====================================================================
S2_REFLECTANCE_BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]


def mask_s2_clouds(image: ee.Image) -> ee.Image:
    """
    Sentinel-2 SCL-based cloud mask. Returns only the reflectance bands we
    use (scaled to 0–1), guaranteeing a homogeneous ImageCollection — some
    S2 scenes have different band orderings of auxiliary masks, which
    breaks .median() across the archive otherwise.
    """
    scl = image.select("SCL")
    # Keep: 4=vegetation, 5=bare soil, 6=water, 7=unclassified, 11=snow
    # Drop: 3=cloud shadow, 8=cloud medium prob, 9=cloud high prob, 10=cirrus
    mask = (scl.neq(3)
            .And(scl.neq(8))
            .And(scl.neq(9))
            .And(scl.neq(10)))
    return (image.select(S2_REFLECTANCE_BANDS)
                 .divide(10000)
                 .updateMask(mask))


def s2_composite(start: str, end: str, aoi: ee.Geometry) -> ee.Image:
    coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(start, end).filterBounds(aoi)
            .filter(ee.Filter.lt(
                "CLOUDY_PIXEL_PERCENTAGE", config.S2_CLOUD_THRESHOLD))
            .map(mask_s2_clouds))
    return coll.median().clip(aoi).set(
        {"period_start": start, "period_end": end, "sensor": "Sentinel-2"})


# =====================================================================
# 4. SPECTRAL INDICES
# =====================================================================
def add_indices_landsat(image: ee.Image) -> ee.Image:
    """
    Add NDVI, NDBI, MNDWI, NDWI, BSI to a harmonized Landsat composite.
    Harmonized band convention used here:
      Blue=SR_B2, Green=SR_B3, Red=SR_B4, NIR=SR_B5, SWIR1=SR_B6, SWIR2=SR_B7
    """
    ndvi = image.normalizedDifference(["SR_B5", "SR_B4"]).rename("NDVI")
    ndbi = image.normalizedDifference(["SR_B6", "SR_B5"]).rename("NDBI")
    mndwi = image.normalizedDifference(["SR_B3", "SR_B6"]).rename("MNDWI")
    ndwi = image.normalizedDifference(["SR_B3", "SR_B5"]).rename("NDWI")
    bsi = image.expression(
        "((SWIR1 + RED) - (NIR + BLUE)) / ((SWIR1 + RED) + (NIR + BLUE))",
        {"SWIR1": image.select("SR_B6"), "RED": image.select("SR_B4"),
         "NIR": image.select("SR_B5"), "BLUE": image.select("SR_B2")}
    ).rename("BSI")
    return image.addBands([ndvi, ndbi, mndwi, ndwi, bsi])


def add_indices_s2(image: ee.Image) -> ee.Image:
    """S2 bands: B2=Blue, B3=Green, B4=Red, B8=NIR, B11=SWIR1, B12=SWIR2."""
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndbi = image.normalizedDifference(["B11", "B8"]).rename("NDBI")
    mndwi = image.normalizedDifference(["B3", "B11"]).rename("MNDWI")
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")
    bsi = image.expression(
        "((SWIR1 + RED) - (NIR + BLUE)) / ((SWIR1 + RED) + (NIR + BLUE))",
        {"SWIR1": image.select("B11"), "RED": image.select("B4"),
         "NIR": image.select("B8"), "BLUE": image.select("B2")}
    ).rename("BSI")
    return image.addBands([ndvi, ndbi, mndwi, ndwi, bsi])


# =====================================================================
# 5. BUILT-UP CLASSIFICATION
# =====================================================================
def builtup_from_dynamic_world(start: str, end: str,
                               aoi: ee.Geometry) -> ee.Image:
    """Dynamic World 'built' probability mode for the period (>= 2015)."""
    dw = (ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
          .filterDate(start, end).filterBounds(aoi))
    # 'label' band: 0=water, 1=trees, 2=grass, 3=flooded_veg, 4=crops,
    # 5=shrub, 6=built, 7=bare, 8=snow
    mode = dw.select("label").mode().clip(aoi)
    builtup = mode.eq(6).rename("builtup")
    return builtup


def builtup_from_rf(image_with_indices: ee.Image,
                    aoi: ee.Geometry) -> ee.Image:
    """
    Simple unsupervised proxy for Landsat era: classify built-up via
    NDBI > 0 AND NDVI < 0.2 AND MNDWI < 0. Good enough for relative
    change analysis at 30 m. Replace with a trained RF if you have
    labeled samples.
    """
    ndbi = image_with_indices.select("NDBI")
    ndvi = image_with_indices.select("NDVI")
    mndwi = image_with_indices.select("MNDWI")
    builtup = (ndbi.gt(0).And(ndvi.lt(0.2)).And(mndwi.lt(0)))
    return builtup.rename("builtup").clip(aoi)


# =====================================================================
# 6. SHORELINE EXTRACTION
# =====================================================================
def extract_shoreline(image_with_indices: ee.Image,
                      aoi: ee.Geometry) -> ee.Image:
    """Water mask from MNDWI, then reduce to coastline raster."""
    mndwi = image_with_indices.select("MNDWI")
    water = mndwi.gt(config.MNDWI_WATER_THRESHOLD).rename("water")
    # Edge detection: difference between water and its 1-pixel dilation
    shoreline = water.subtract(water.focal_min(1)).abs().rename("shoreline")
    return water.addBands(shoreline).clip(aoi)


# =====================================================================
# 7. CHANGE DETECTION
# =====================================================================
def index_difference(img_a: ee.Image, img_b: ee.Image,
                     band: str) -> ee.Image:
    """Per-pixel change in an index between two periods (B - A)."""
    return img_b.select(band).subtract(img_a.select(band)).rename(
        f"{band}_change")


def post_classification_change(builtup_a: ee.Image,
                               builtup_b: ee.Image) -> ee.Image:
    """
    0 = no-change non-built, 1 = stable built, 2 = new built (gain),
    3 = lost built (rare on this coast but tracked for completeness).
    """
    a = builtup_a.select("builtup")
    b = builtup_b.select("builtup")
    stable_nonbuilt = a.eq(0).And(b.eq(0)).multiply(0)
    stable_built = a.eq(1).And(b.eq(1)).multiply(1)
    gain = a.eq(0).And(b.eq(1)).multiply(2)
    loss = a.eq(1).And(b.eq(0)).multiply(3)
    return stable_nonbuilt.add(stable_built).add(gain).add(loss).rename(
        "change_class")


# =====================================================================
# 8. ZONAL STATISTICS (drives the time-series report)
# =====================================================================
def builtup_area_km2(builtup: ee.Image, aoi: ee.Geometry,
                     scale: int) -> float:
    """Sum built-up pixels * pixel area, return km²."""
    pixel_area_km2 = ee.Image.pixelArea().divide(1_000_000)
    area = builtup.select("builtup").multiply(pixel_area_km2)
    stat = area.reduceRegion(
        reducer=ee.Reducer.sum(), geometry=aoi,
        scale=scale, maxPixels=config.MAX_PIXELS)
    return stat.getInfo().get("builtup", 0.0)


def water_area_km2(image_with_indices: ee.Image, aoi: ee.Geometry,
                   scale: int) -> float:
    water = image_with_indices.select("MNDWI").gt(
        config.MNDWI_WATER_THRESHOLD).rename("water")
    pixel_area_km2 = ee.Image.pixelArea().divide(1_000_000)
    area = water.multiply(pixel_area_km2)
    stat = area.reduceRegion(
        reducer=ee.Reducer.sum(), geometry=aoi,
        scale=scale, maxPixels=config.MAX_PIXELS)
    return stat.getInfo().get("water", 0.0)


def mean_index(image_with_indices: ee.Image, band: str,
               aoi: ee.Geometry, scale: int) -> float:
    stat = image_with_indices.select(band).reduceRegion(
        reducer=ee.Reducer.mean(), geometry=aoi,
        scale=scale, maxPixels=config.MAX_PIXELS)
    return stat.getInfo().get(band, None)


# =====================================================================
# 9. THUMBNAIL DOWNLOAD (PNG previews to local disk)
# =====================================================================
def download_thumbnail(image: ee.Image, vis_params: dict,
                       aoi: ee.Geometry, out_path: Path,
                       dimensions: int = 1024) -> None:
    """Download a styled PNG preview of the image clipped to AOI."""
    url = image.getThumbURL({
        **vis_params,
        "region": aoi,
        "dimensions": dimensions,
        "format": "png",
    })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, out_path)
    print(f"[OK] Saved preview: {out_path.name}")


# =====================================================================
# 10. EXPORT GEOTIFFS TO GOOGLE DRIVE
# =====================================================================
def export_to_drive(image: ee.Image, description: str,
                    aoi: ee.Geometry, scale: int) -> ee.batch.Task:
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder=config.DRIVE_FOLDER,
        fileNamePrefix=description,
        region=aoi,
        scale=scale,
        crs="EPSG:32636",  # UTM 36N — appropriate for NE Egypt
        maxPixels=config.MAX_PIXELS,
        fileFormat="GeoTIFF",
    )
    task.start()
    print(f"[QUEUED] Drive export: {description}")
    return task


# =====================================================================
# 11. MAIN ORCHESTRATION
# =====================================================================
def run() -> dict:
    initialize_ee()
    aoi = get_aoi()

    # Ensure output dirs
    for d in (config.MAPS_DIR, config.CHARTS_DIR,
              config.GEOTIFFS_DIR, config.REPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    stats = {"landsat": [], "sentinel2": []}
    export_tasks = []

    # -----------------------------------------------------------------
    # LANDSAT TIME-SERIES (1990–2025, 30 m)
    # -----------------------------------------------------------------
    print("\n========== LANDSAT TIME-SERIES ==========")
    landsat_builtup_imgs = {}
    for label, start, end in config.LANDSAT_PERIODS:
        print(f"\n--- Period {label} ({start} → {end}) ---")
        composite = landsat_composite(start, end, aoi)
        with_idx = add_indices_landsat(composite)
        builtup = builtup_from_rf(with_idx, aoi)
        landsat_builtup_imgs[label] = builtup

        # Zonal stats
        builtup_km2 = builtup_area_km2(
            builtup, aoi, config.EXPORT_SCALE_LANDSAT)
        water_km2 = water_area_km2(
            with_idx, aoi, config.EXPORT_SCALE_LANDSAT)
        ndvi_mean = mean_index(
            with_idx, "NDVI", aoi, config.EXPORT_SCALE_LANDSAT)
        ndbi_mean = mean_index(
            with_idx, "NDBI", aoi, config.EXPORT_SCALE_LANDSAT)
        stats["landsat"].append({
            "period": label, "start": start, "end": end,
            "builtup_km2": round(builtup_km2, 3),
            "water_km2": round(water_km2, 3),
            "ndvi_mean": round(ndvi_mean, 4) if ndvi_mean else None,
            "ndbi_mean": round(ndbi_mean, 4) if ndbi_mean else None,
        })
        print(f"  built-up = {builtup_km2:.2f} km²,  water = "
              f"{water_km2:.2f} km²,  NDVI = {ndvi_mean}")

        # Local PNG previews
        download_thumbnail(
            composite, config.RGB_VIS_LANDSAT, aoi,
            config.MAPS_DIR / f"landsat_rgb_{label}.png")
        download_thumbnail(
            with_idx, {**config.NDVI_VIS, "bands": ["NDVI"]}, aoi,
            config.MAPS_DIR / f"landsat_ndvi_{label}.png")
        download_thumbnail(
            with_idx, {**config.MNDWI_VIS, "bands": ["MNDWI"]}, aoi,
            config.MAPS_DIR / f"landsat_mndwi_{label}.png")
        download_thumbnail(
            builtup, config.BUILTUP_VIS, aoi,
            config.MAPS_DIR / f"landsat_builtup_{label}.png")

        # Queue GeoTIFF exports to Drive
        export_tasks.append(export_to_drive(
            composite.select(["SR_B2", "SR_B3", "SR_B4", "SR_B5",
                              "SR_B6", "SR_B7"]),
            f"landsat_sr_{label}", aoi, config.EXPORT_SCALE_LANDSAT))
        export_tasks.append(export_to_drive(
            with_idx.select(config.INDICES),
            f"landsat_indices_{label}", aoi, config.EXPORT_SCALE_LANDSAT))
        export_tasks.append(export_to_drive(
            builtup, f"landsat_builtup_{label}",
            aoi, config.EXPORT_SCALE_LANDSAT))

    # -----------------------------------------------------------------
    # POST-CLASSIFICATION CHANGE (first vs last Landsat period)
    # -----------------------------------------------------------------
    first_label = config.LANDSAT_PERIODS[0][0]
    last_label = config.LANDSAT_PERIODS[-1][0]
    change_img = post_classification_change(
        landsat_builtup_imgs[first_label],
        landsat_builtup_imgs[last_label])
    download_thumbnail(
        change_img,
        {"min": 0, "max": 3,
         "palette": ["#dddddd", "#7f7f7f", "#d7191c", "#2c7bb6"]},
        aoi, config.MAPS_DIR / f"change_{first_label}_to_{last_label}.png")
    export_tasks.append(export_to_drive(
        change_img, f"change_class_{first_label}_to_{last_label}",
        aoi, config.EXPORT_SCALE_LANDSAT))

    # NDBI delta (first → last)
    ndbi_a = add_indices_landsat(
        landsat_composite(config.LANDSAT_PERIODS[0][1],
                          config.LANDSAT_PERIODS[0][2], aoi))
    ndbi_b = add_indices_landsat(
        landsat_composite(config.LANDSAT_PERIODS[-1][1],
                          config.LANDSAT_PERIODS[-1][2], aoi))
    ndbi_delta = index_difference(ndbi_a, ndbi_b, "NDBI")
    download_thumbnail(
        ndbi_delta, {"min": -0.3, "max": 0.3,
                     "palette": ["#1a9641", "#ffffbf", "#d7191c"]},
        aoi, config.MAPS_DIR / f"ndbi_delta_{first_label}_{last_label}.png")

    # -----------------------------------------------------------------
    # SENTINEL-2 TIME-SERIES (2018, 2021, 2024 — 10 m)
    # -----------------------------------------------------------------
    print("\n========== SENTINEL-2 TIME-SERIES ==========")
    for label, start, end in config.SENTINEL2_PERIODS:
        print(f"\n--- S2 Period {label} ({start} → {end}) ---")
        composite = s2_composite(start, end, aoi)
        with_idx = add_indices_s2(composite)

        if config.USE_DYNAMIC_WORLD:
            builtup = builtup_from_dynamic_world(start, end, aoi)
        else:
            builtup = builtup_from_rf(with_idx, aoi)

        builtup_km2 = builtup_area_km2(
            builtup, aoi, config.EXPORT_SCALE_S2)
        water_km2 = water_area_km2(
            with_idx, aoi, config.EXPORT_SCALE_S2)
        ndvi_mean = mean_index(
            with_idx, "NDVI", aoi, config.EXPORT_SCALE_S2)
        stats["sentinel2"].append({
            "period": label, "start": start, "end": end,
            "builtup_km2": round(builtup_km2, 3),
            "water_km2": round(water_km2, 3),
            "ndvi_mean": round(ndvi_mean, 4) if ndvi_mean else None,
        })
        print(f"  built-up = {builtup_km2:.2f} km²,  water = "
              f"{water_km2:.2f} km²")

        download_thumbnail(
            composite, config.RGB_VIS_S2, aoi,
            config.MAPS_DIR / f"s2_rgb_{label}.png", dimensions=1536)
        download_thumbnail(
            builtup, config.BUILTUP_VIS, aoi,
            config.MAPS_DIR / f"s2_builtup_{label}.png", dimensions=1536)

        export_tasks.append(export_to_drive(
            composite.select(["B2", "B3", "B4", "B8", "B11", "B12"]),
            f"s2_sr_{label}", aoi, config.EXPORT_SCALE_S2))
        export_tasks.append(export_to_drive(
            with_idx.select(config.INDICES),
            f"s2_indices_{label}", aoi, config.EXPORT_SCALE_S2))

    # -----------------------------------------------------------------
    # PERSIST STATS JSON (consumed by the report generator)
    # -----------------------------------------------------------------
    stats_path = config.REPORT_DIR / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2))
    print(f"\n[OK] Stats written → {stats_path}")

    print(f"\n[INFO] {len(export_tasks)} GeoTIFF export tasks queued to "
          f"Google Drive folder: {config.DRIVE_FOLDER}")
    print("       Monitor at https://code.earthengine.google.com/tasks")

    return stats


if __name__ == "__main__":
    t0 = time.time()
    run()
    print(f"\n[DONE] Total runtime: {time.time() - t0:.1f} s")
