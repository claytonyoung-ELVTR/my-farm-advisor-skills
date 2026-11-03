#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""Build lightweight, grower-scoped interactive field maps.

The generated document is a single HTML file. Field polygons and scalar field
metadata are embedded as GeoJSON. The map engine (MapLibre GL JS) and the
satellite/street basemap tiles load from public CDNs, so no imagery or raster
data is embedded in the output.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import numbers
import re
import sys
from datetime import datetime, timezone
from html import escape as html_escape
from pathlib import Path
from typing import Any, Iterable

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

_LOCAL_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LOCAL_LIB))

from paths import (  # noqa: E402
    GROWERS_ROOT,
    farm_boundary_path,
    farm_dir,
    farm_manifest_dir,
    grower_dir,
    grower_manifest_path,
    grower_web_map_path,
    validate_path_slug,
)

_SQ_METERS_PER_ACRE = 4046.8564224
_SIMPLIFY_TOLERANCE = 0.000008
_COORDINATE_PRECISION = 6

_STATE_FIPS_TO_USPS = {
    "01": "AL",
    "02": "AK",
    "04": "AZ",
    "05": "AR",
    "06": "CA",
    "08": "CO",
    "09": "CT",
    "10": "DE",
    "11": "DC",
    "12": "FL",
    "13": "GA",
    "15": "HI",
    "16": "ID",
    "17": "IL",
    "18": "IN",
    "19": "IA",
    "20": "KS",
    "21": "KY",
    "22": "LA",
    "23": "ME",
    "24": "MD",
    "25": "MA",
    "26": "MI",
    "27": "MN",
    "28": "MS",
    "29": "MO",
    "30": "MT",
    "31": "NE",
    "32": "NV",
    "33": "NH",
    "34": "NJ",
    "35": "NM",
    "36": "NY",
    "37": "NC",
    "38": "ND",
    "39": "OH",
    "40": "OK",
    "41": "OR",
    "42": "PA",
    "44": "RI",
    "45": "SC",
    "46": "SD",
    "47": "TN",
    "48": "TX",
    "49": "UT",
    "50": "VT",
    "51": "VA",
    "53": "WA",
    "54": "WV",
    "55": "WI",
    "56": "WY",
    "60": "AS",
    "66": "GU",
    "69": "MP",
    "72": "PR",
    "78": "VI",
}

_CROP_COLORS = {
    "alfalfa": "#66bb6a",
    "barley": "#c9a227",
    "corn": "#f2c14e",
    "cotton": "#eceff1",
    "developed": "#8d6e63",
    "fallow": "#9e9e9e",
    "farmland": "#c49a6c",
    "forest": "#2e7d32",
    "hay": "#aed581",
    "meadow": "#7cb342",
    "oats": "#d7b56d",
    "pasture": "#8bc34a",
    "rice": "#4dd0e1",
    "sorghum": "#c1440e",
    "soybean": "#4caf50",
    "soybeans": "#4caf50",
    "unknown": "#90a4ae",
    "water": "#2196f3",
    "wheat": "#d9a441",
}

_FALLBACK_COLORS = (
    "#5c8d89",
    "#8e6c88",
    "#c08552",
    "#4f6d8f",
    "#7a9e5b",
    "#b56576",
    "#6d597a",
    "#3d8b8b",
    "#a37c40",
    "#5e8c61",
)

_BASEMAPS = {
    "imagery": {
        "label": "Satellite",
        "tiles": [
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ],
        "attribution": (
            "Tiles &copy; Esri &mdash; Source: Esri, Maxar, "
            "Earthstar Geographics, and the GIS User Community"
        ),
        "maxzoom": 19,
    },
    "labels": {
        "label": "Place labels",
        "tiles": [
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
        ],
        "attribution": "Labels &copy; Esri",
        "maxzoom": 19,
    },
    "streets": {
        "label": "Streets",
        "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        "attribution": (
            '&copy; <a href="https://www.openstreetmap.org/copyright">'
            "OpenStreetMap</a> contributors"
        ),
        "maxzoom": 19,
    },
}


def humanize_slug(value: str) -> str:
    """Turn a slug such as ``il-grower`` into ``IL Grower``."""
    parts = [part for part in re.split(r"[-_\s]+", str(value).strip()) if part]
    if not parts:
        return str(value)
    if len(parts[0]) == 2 and parts[0].isalpha():
        parts[0] = parts[0].upper()
    for index in range(1, len(parts)):
        parts[index] = parts[index][:1].upper() + parts[index][1:]
    return " ".join(parts)


def discover_grower_slugs() -> list[str]:
    """Return valid grower slugs that have a ``farms/`` directory."""
    if not GROWERS_ROOT.exists():
        return []
    slugs: list[str] = []
    for entry in sorted(GROWERS_ROOT.iterdir()):
        if not entry.is_dir() or not (entry / "farms").is_dir():
            continue
        try:
            slugs.append(validate_path_slug(entry.name, "grower_slug"))
        except ValueError:
            continue
    return slugs


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _fips_code(value: Any, width: int = 2) -> str:
    digits = re.sub(r"\D", "", _clean_text(value))
    return digits.zfill(width) if digits else ""


def _id_digits(value: str) -> str:
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    return re.sub(r"\D", "", text)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _grower_display_name(grower_slug: str) -> str:
    payload = _read_json(grower_dir(grower_slug) / "grower.json")
    name = _clean_text(payload.get("display_name"))
    if name and name.lower() != grower_slug.lower():
        return name
    return humanize_slug(grower_slug)


def _farm_name_lookup(grower_slug: str) -> dict[str, str]:
    names: dict[str, str] = {}
    schedule = _read_json(grower_manifest_path(grower_slug))
    farms = schedule.get("farms")
    if isinstance(farms, list):
        for item in farms:
            if not isinstance(item, dict):
                continue
            farm_slug = _clean_text(item.get("farm_slug"))
            farm_name = _clean_text(item.get("farm_name"))
            if farm_slug and farm_name:
                names[farm_slug] = farm_name
    return names


def _farm_display_name(grower_slug: str, farm_slug: str, names: dict[str, str]) -> str:
    if farm_slug in names:
        return names[farm_slug]
    payload = _read_json(farm_dir(grower_slug, farm_slug) / "farm.json")
    name = _clean_text(payload.get("display_name"))
    if name:
        return name
    return humanize_slug(farm_slug)


def _load_inventory(grower_slug: str, farm_slug: str) -> tuple[dict[str, str], dict[str, str]]:
    """Return ``field_id -> field_slug`` and ``field_id -> display name`` maps."""
    slug_by_id: dict[str, str] = {}
    name_by_id: dict[str, str] = {}
    path = farm_manifest_dir(grower_slug, farm_slug) / "field-inventory.csv"
    if not path.exists():
        return slug_by_id, name_by_id
    try:
        handle = path.open(newline="", encoding="utf-8")
    except OSError:
        return slug_by_id, name_by_id
    with handle:
        reader = csv.DictReader(handle)
        for row in reader:
            field_id = _clean_text(row.get("field_id"))
            if not field_id:
                continue
            slug_by_id[field_id] = _clean_text(row.get("field_slug")) or field_id
            for key in ("field_name", "name", "display_name"):
                name = _clean_text(row.get(key))
                if name:
                    name_by_id[field_id] = name
                    break
    return slug_by_id, name_by_id


def _field_display_name(field_id: str, field_slug: str, inventory_name: str) -> str:
    if inventory_name:
        return inventory_name
    digits = _id_digits(field_id) or _id_digits(field_slug)
    if digits:
        return f"Field {digits}"
    return humanize_slug(field_slug or field_id)


def _crop_label(value: Any) -> str:
    text = _clean_text(value)
    if not text or text.lower() in {"nan", "none", "null"}:
        return "Unknown"
    return text.replace("_", " ").replace("-", " ").title()


def _crop_color(crop_label: str) -> str:
    key = crop_label.lower()
    if key in _CROP_COLORS:
        return _CROP_COLORS[key]
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return _FALLBACK_COLORS[int(digest[:8], 16) % len(_FALLBACK_COLORS)]


def _location_label(county_name: str, state_code: str) -> str:
    county = county_name.strip()
    if county and not county.lower().endswith("county"):
        county = f"{county} County"
    return ", ".join(part for part in (county, state_code) if part)


def _round_coordinates(value: Any, ndigits: int = _COORDINATE_PRECISION) -> Any:
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        return round(float(value), ndigits)
    if isinstance(value, (list, tuple)):
        return [_round_coordinates(item, ndigits) for item in value]
    return value


def _iter_positions(coords: Any) -> Iterable[tuple[float, float]]:
    if not coords:
        return
    head = coords[0]
    if isinstance(head, numbers.Real) and not isinstance(head, bool):
        yield float(coords[0]), float(coords[1])
        return
    for item in coords:
        yield from _iter_positions(item)


def _feature_bounds(features: list[dict[str, Any]]) -> list[list[float]] | None:
    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    for feature in features:
        for x, y in _iter_positions(feature["geometry"]["coordinates"]):
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if not math.isfinite(min_x):
        return None
    return [
        [round(min_x, _COORDINATE_PRECISION), round(min_y, _COORDINATE_PRECISION)],
        [round(max_x, _COORDINATE_PRECISION), round(max_y, _COORDINATE_PRECISION)],
    ]


def _load_farm_features(
    grower_slug: str,
    grower_name: str,
    farm_slug: str,
    farm_name: str,
    slug_by_id: dict[str, str],
    name_by_id: dict[str, str],
) -> list[dict[str, Any]]:
    boundary_path = farm_boundary_path(grower_slug, farm_slug)
    if not boundary_path.exists():
        return []

    frame = gpd.read_file(boundary_path)
    if frame.empty:
        return []
    if frame.crs is None:
        frame = frame.set_crs("EPSG:4326")
    frame = frame.to_crs("EPSG:4326")

    try:
        projected_crs = frame.estimate_utm_crs()
    except Exception:  # pragma: no cover - defensive fallback for odd extents
        projected_crs = "EPSG:5070"
    projected = frame.to_crs(projected_crs)
    centroids = gpd.GeoSeries(
        projected.geometry.centroid, crs=projected_crs
    ).to_crs("EPSG:4326")
    computed_acres = projected.geometry.area / _SQ_METERS_PER_ACRE

    features: list[dict[str, Any]] = []
    for idx, row in frame.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
            if geometry.is_empty:
                continue
        simplified = geometry.simplify(_SIMPLIFY_TOLERANCE, preserve_topology=True)
        if simplified.is_empty:
            simplified = geometry

        field_id = _clean_text(row.get("field_id"))
        field_slug = slug_by_id.get(field_id, "") or field_id
        if not field_id and not field_slug:
            field_id = f"field-{idx}"
            field_slug = field_id

        crop_name = _clean_text(row.get("crop_name"))
        crop_label = _crop_label(crop_name)
        county_name = _clean_text(row.get("county_name"))
        county_fips = _fips_code(row.get("county_fips"), 3)
        state_fips = _fips_code(row.get("state_fips"), 2)
        state_code = _STATE_FIPS_TO_USPS.get(state_fips, "")

        acres = _to_float(row.get("area_acres"))
        if acres is None or acres <= 0:
            acres = float(computed_acres.loc[idx])

        centroid = centroids.loc[idx]
        latitude = round(float(centroid.y), _COORDINATE_PRECISION)
        longitude = round(float(centroid.x), _COORDINATE_PRECISION)

        field_name = _field_display_name(
            field_id, field_slug, name_by_id.get(field_id, "")
        )
        properties = {
            "field_key": f"{grower_slug}:{farm_slug}:{field_id}",
            "field_id": field_id,
            "field_slug": field_slug,
            "field_name": field_name,
            "farm_slug": farm_slug,
            "farm_name": farm_name,
            "grower_slug": grower_slug,
            "grower_name": grower_name,
            "crop_name": crop_name,
            "crop_label": crop_label,
            "area_acres": round(float(acres), 2),
            "county_name": county_name,
            "county_fips": county_fips,
            "state_fips": state_fips,
            "state_code": state_code,
            "location_label": _location_label(county_name, state_code),
            "lat": latitude,
            "lon": longitude,
            "color": _crop_color(crop_label),
        }
        features.append(
            {
                "type": "Feature",
                "geometry": _round_coordinates(mapping(simplified)),
                "properties": properties,
            }
        )
    return features


def build_grower_payload(grower_slug: str) -> dict[str, Any]:
    """Collect all farms and fields for one grower into a map payload."""
    grower_slug = validate_path_slug(grower_slug, "grower_slug")
    grower_name = _grower_display_name(grower_slug)
    farm_names = _farm_name_lookup(grower_slug)

    grower_root = grower_dir(grower_slug)
    farms_root = grower_root / "farms"
    if not farms_root.is_dir():
        raise FileNotFoundError(f"No farms directory for grower {grower_slug!r}")

    farms: list[dict[str, Any]] = []
    all_features: list[dict[str, Any]] = []
    for entry in sorted(farms_root.iterdir()):
        if not entry.is_dir():
            continue
        farm_slug = entry.name
        try:
            farm_slug = validate_path_slug(farm_slug, "farm_slug")
        except ValueError:
            continue

        farm_name = _farm_display_name(grower_slug, farm_slug, farm_names)
        slug_by_id, name_by_id = _load_inventory(grower_slug, farm_slug)
        features = _load_farm_features(
            grower_slug,
            grower_name,
            farm_slug,
            farm_name,
            slug_by_id,
            name_by_id,
        )
        if not features:
            continue

        bounds = _feature_bounds(features)
        farms.append(
            {
                "slug": farm_slug,
                "name": farm_name,
                "field_count": len(features),
                "area_acres": round(
                    sum(feature["properties"]["area_acres"] for feature in features), 1
                ),
                "bounds": bounds,
            }
        )
        all_features.extend(features)

    if not all_features:
        raise ValueError(f"No field boundaries found for grower {grower_slug!r}")

    for index, feature in enumerate(all_features, start=1):
        feature["id"] = index

    bounds = _feature_bounds(all_features)
    total_acres = round(
        sum(feature["properties"]["area_acres"] for feature in all_features), 1
    )
    return {
        "grower": {"slug": grower_slug, "name": grower_name},
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "crs": "EPSG:4326",
        "basemaps": _BASEMAPS,
        "bounds": bounds,
        "farms": farms,
        "fields": {"type": "FeatureCollection", "features": all_features},
        "stats": {
            "farm_count": len(farms),
            "field_count": len(all_features),
            "area_acres": total_acres,
        },
    }


def _embedded_json(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        text.replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def build_grower_html(payload: dict[str, Any]) -> str:
    grower_name = payload["grower"]["name"]
    title = f"{grower_name} Field Map"
    document = _HTML_TEMPLATE.replace("__MAP_TITLE__", html_escape(title))
    return document.replace("__GROWER_DATA__", _embedded_json(payload))


def write_grower_map(grower_slug: str, output_path: Path | None = None) -> Path:
    payload = build_grower_payload(grower_slug)
    html = build_grower_html(payload)
    path = Path(output_path) if output_path is not None else grower_web_map_path(grower_slug)
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>__MAP_TITLE__</title>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet" />
<style>
  :root {
    --ink: #17251b;
    --muted: #5d6f61;
    --line: #dde5da;
    --panel: #ffffff;
    --panel-soft: #f4f7f2;
    --accent: #2f7d4f;
    --accent-soft: #e6f2e8;
    --shadow: 0 12px 34px rgba(8, 25, 15, 0.18);
    --radius: 14px;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0;
    color: var(--ink);
    background: #0b1410;
    font-family: "Avenir Next", "Segoe UI", system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  [hidden] { display: none !important; }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
  #app { display: flex; height: 100vh; height: 100dvh; overflow: hidden; }
  #sidebar {
    width: 356px;
    flex: none;
    display: flex;
    flex-direction: column;
    min-height: 0;
    background: var(--panel);
    border-right: 1px solid var(--line);
    z-index: 2;
  }
  .sidebar-header {
    padding: 18px 18px 15px;
    color: #fff;
    background: linear-gradient(150deg, #0f2c1b 0%, #1d5a34 62%, #2f7d4f 100%);
  }
  .eyebrow {
    margin: 0;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    opacity: 0.72;
  }
  .sidebar-header h1 {
    margin: 5px 0 6px;
    font-size: 22px;
    line-height: 1.15;
    letter-spacing: -0.01em;
  }
  .subtitle { margin: 0 0 14px; font-size: 12.5px; line-height: 1.45; opacity: 0.82; }
  .primary-button {
    width: 100%;
    padding: 9px 12px;
    border: 1px solid rgba(255, 255, 255, 0.28);
    border-radius: 9px;
    background: rgba(255, 255, 255, 0.14);
    color: #fff;
    font: inherit;
    font-size: 12.5px;
    font-weight: 650;
    cursor: pointer;
    transition: background 0.15s ease;
  }
  .primary-button:hover { background: rgba(255, 255, 255, 0.24); }
  .search-row { padding: 13px 15px 6px; }
  #field-search {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: #fbfcfa;
    color: var(--ink);
    font: inherit;
    font-size: 13.5px;
  }
  #field-search:focus {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
    background: #fff;
  }
  #selection {
    margin: 8px 14px 2px;
    padding: 12px 13px;
    border: 1px solid #cfe2d1;
    border-radius: 12px;
    background: var(--accent-soft);
  }
  .selection-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
  .selection-eyebrow {
    margin: 0 0 2px;
    color: var(--accent);
    font-size: 9.5px;
    font-weight: 750;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }
  .selection-head h2 { margin: 0; font-size: 15.5px; line-height: 1.2; }
  .selection-sub { margin: 3px 0 9px; color: var(--muted); font-size: 11.5px; }
  .icon-button {
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    flex: none;
    border: 1px solid #c4d9c6;
    border-radius: 8px;
    background: #fff;
    color: var(--muted);
    font-size: 16px;
    line-height: 1;
    cursor: pointer;
  }
  .icon-button:hover { color: var(--ink); border-color: var(--accent); }
  .chips { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 9px; }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    border: 1px solid #cfe2d1;
    border-radius: 999px;
    background: #fff;
    font-size: 10.5px;
    font-weight: 650;
  }
  .chip::before {
    content: "";
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--chip, var(--accent));
  }
  .fact-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px 10px;
    margin: 0 0 10px;
    font-size: 11px;
  }
  .fact-grid dt { color: var(--muted); font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.08em; }
  .fact-grid dd { margin: 1px 0 0; font-weight: 600; word-break: break-word; }
  .selection-actions { display: flex; gap: 7px; }
  .secondary-button, .ghost-button {
    flex: 1;
    padding: 7px 9px;
    border-radius: 8px;
    font: inherit;
    font-size: 11.5px;
    font-weight: 650;
    cursor: pointer;
  }
  .secondary-button { border: 1px solid var(--accent); background: var(--accent); color: #fff; }
  .secondary-button:hover { background: #276844; }
  .ghost-button { border: 1px solid #c4d9c6; background: #fff; color: var(--muted); }
  .ghost-button:hover { color: var(--ink); border-color: var(--accent); }
  .farm-list { flex: 1; min-height: 0; overflow-y: auto; padding: 2px 9px 16px; }
  .farm-group { margin: 7px 0 11px; }
  .farm-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 7px 5px;
  }
  .farm-header h2 { margin: 0; font-size: 12.5px; letter-spacing: -0.005em; }
  .farm-header p { margin: 2px 0 0; color: var(--muted); font-size: 10.5px; }
  .farm-zoom {
    padding: 4px 8px;
    border: 1px solid var(--line);
    border-radius: 7px;
    background: #fff;
    color: var(--accent);
    font: inherit;
    font-size: 10.5px;
    font-weight: 700;
    cursor: pointer;
  }
  .farm-zoom:hover { border-color: var(--accent); background: var(--accent-soft); }
  .field-list { margin: 0; padding: 0; list-style: none; }
  .field-row {
    display: flex;
    align-items: center;
    gap: 9px;
    width: 100%;
    padding: 8px 8px;
    border: 0;
    border-radius: 9px;
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
    transition: background 0.12s ease, box-shadow 0.12s ease;
  }
  .field-row:hover, .field-row.is-hover { background: var(--panel-soft); }
  .field-row.is-selected {
    background: var(--accent-soft);
    box-shadow: inset 3px 0 0 var(--accent);
  }
  .field-row:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .swatch {
    width: 11px;
    height: 11px;
    flex: none;
    border-radius: 3px;
    border: 1px solid rgba(0, 0, 0, 0.18);
  }
  .field-meta { display: flex; flex-direction: column; min-width: 0; }
  .field-name {
    overflow: hidden;
    font-size: 12.5px;
    font-weight: 650;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .field-sub { color: var(--muted); font-size: 10.5px; }
  .empty-state { padding: 20px 14px; color: var(--muted); font-size: 12px; text-align: center; }
  .sidebar-footer {
    padding: 9px 16px 13px;
    border-top: 1px solid var(--line);
    background: #fbfcfa;
    color: var(--muted);
    font-size: 10.5px;
  }
  .sidebar-footer label { display: block; margin-bottom: 3px; font-weight: 650; color: var(--ink); }
  #opacity { width: 100%; margin: 0 0 5px; accent-color: var(--accent); }
  .footer-hint { margin: 0; line-height: 1.35; }
  #map-wrap { position: relative; flex: 1; min-width: 0; min-height: 0; background: #0b1410; }
  #map { position: absolute; inset: 0; }
  #basemap-switcher {
    position: absolute;
    top: 14px;
    left: 14px;
    z-index: 2;
    display: flex;
    gap: 3px;
    padding: 4px;
    border-radius: 11px;
    background: rgba(255, 255, 255, 0.96);
    box-shadow: var(--shadow);
    backdrop-filter: blur(8px);
  }
  #basemap-switcher button {
    padding: 7px 11px;
    border: 0;
    border-radius: 7px;
    background: transparent;
    color: var(--muted);
    font: inherit;
    font-size: 11.5px;
    font-weight: 650;
    cursor: pointer;
  }
  #basemap-switcher button:hover { color: var(--ink); background: var(--panel-soft); }
  #basemap-switcher button.active { background: var(--accent); color: #fff; }
  #legend {
    position: absolute;
    right: 14px;
    bottom: 52px;
    z-index: 2;
    max-width: 196px;
    padding: 10px 12px;
    border: 1px solid rgba(221, 229, 218, 0.9);
    border-radius: 11px;
    background: rgba(255, 255, 255, 0.95);
    box-shadow: var(--shadow);
    backdrop-filter: blur(8px);
    font-size: 10.5px;
  }
  #legend h3 {
    margin: 0 0 6px;
    color: var(--muted);
    font-size: 9.5px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .legend-item { display: flex; align-items: center; gap: 6px; margin: 3px 0; }
  #status {
    position: absolute;
    top: 14px;
    left: 50%;
    z-index: 3;
    padding: 7px 13px;
    border-radius: 999px;
    background: rgba(15, 26, 20, 0.88);
    color: #fff;
    font-size: 11.5px;
    font-weight: 600;
    pointer-events: none;
    transform: translateX(-50%);
    transition: opacity 0.25s ease;
  }
  #status.is-hidden { opacity: 0; }
  #status.is-error { background: #8a2b2b; }
  .maplibregl-ctrl-group { border-radius: 10px !important; box-shadow: var(--shadow) !important; }
  .maplibregl-ctrl-attrib { font-size: 10px; }
  .maplibregl-popup-content {
    padding: 11px 13px;
    border-radius: 11px;
    box-shadow: var(--shadow);
    font-family: inherit;
  }
  .popup-title { font-size: 13.5px; font-weight: 750; line-height: 1.2; }
  .popup-sub { margin: 2px 0 8px; color: var(--muted); font-size: 10.5px; }
  .popup-grid { display: grid; grid-template-columns: auto 1fr; gap: 3px 10px; margin: 0; font-size: 11.5px; }
  .popup-grid dt { color: var(--muted); }
  .popup-grid dd { margin: 0; font-weight: 650; }
  @media (max-width: 760px) {
    #app { flex-direction: column; }
    #map-wrap { order: 1; flex: 1; min-height: 54vh; }
    #sidebar { order: 2; width: 100%; max-height: 46vh; border-top: 1px solid var(--line); border-right: 0; overflow-y: auto; }
    .farm-list { flex: none; overflow: visible; }
    .sidebar-header { padding: 13px 16px 12px; }
    .sidebar-header h1 { font-size: 18px; }
    .subtitle { margin-bottom: 10px; }
    #legend { display: none; }
    #basemap-switcher { top: 10px; left: 10px; }
    #status { top: 10px; max-width: 52vw; text-align: center; }
    .maplibregl-ctrl-top-right { top: 4px; right: 4px; }
  }
</style>
</head>
<body>
<div id="app">
  <aside id="sidebar" aria-label="Grower field navigation">
    <header class="sidebar-header">
      <p class="eyebrow">Grower field map</p>
      <h1 id="grower-name">Grower</h1>
      <p class="subtitle" id="grower-summary">Loading fields&hellip;</p>
      <button id="fit-grower" class="primary-button" type="button">Fit all fields</button>
    </header>
    <div class="search-row">
      <label class="sr-only" for="field-search">Search fields</label>
      <input id="field-search" type="search" placeholder="Search field, farm, or crop" autocomplete="off" />
    </div>
    <section id="selection" aria-live="polite" hidden></section>
    <div id="farm-list" class="farm-list"></div>
    <footer class="sidebar-footer">
      <label for="opacity">Field fill opacity</label>
      <input id="opacity" type="range" min="0" max="80" value="28" />
      <p class="footer-hint">Click a field on the map or in the list. Satellite imagery &copy; Esri.</p>
    </footer>
  </aside>
  <main id="map-wrap">
    <div id="map"></div>
    <div id="basemap-switcher" role="group" aria-label="Basemap">
      <button type="button" data-basemap="imagery" class="active">Satellite</button>
      <button type="button" data-basemap="hybrid">Hybrid</button>
      <button type="button" data-basemap="streets">Streets</button>
    </div>
    <div id="legend" aria-label="Crop legend"></div>
    <div id="status" role="status">Loading satellite map&hellip;</div>
    <noscript><p style="position:absolute;bottom:16px;left:16px;background:#fff;padding:10px 14px;border-radius:10px;">This map needs JavaScript to display field boundaries.</p></noscript>
  </main>
</div>
<script id="grower-data" type="application/json">__GROWER_DATA__</script>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script>
(function () {
  "use strict";

  var DATA = JSON.parse(document.getElementById("grower-data").textContent);
  var FEATURES = DATA.fields.features;
  var FIELD_BY_ID = new Map(FEATURES.map(function (feature) { return [feature.id, feature]; }));
  var ROWS = new Map();
  var selectedId = null;
  var hoverId = null;
  var popup = null;
  var baseOpacity = 0.28;
  var statusTimer = null;

  var statusEl = document.getElementById("status");
  var selectionEl = document.getElementById("selection");
  var farmListEl = document.getElementById("farm-list");
  var searchEl = document.getElementById("field-search");
  var opacityEl = document.getElementById("opacity");

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
    });
  }

  function setStatus(text, options) {
    options = options || {};
    clearTimeout(statusTimer);
    if (options.hide || !text) {
      statusEl.classList.add("is-hidden");
      statusEl.textContent = "";
      return;
    }
    statusEl.textContent = text;
    statusEl.classList.toggle("is-error", Boolean(options.error));
    statusEl.classList.remove("is-hidden");
    var timeout = options.timeout || 0;
    if (timeout) {
      statusTimer = setTimeout(function () {
        statusEl.classList.add("is-hidden");
      }, timeout);
    }
  }

  document.getElementById("grower-name").textContent = DATA.grower.name;
  document.getElementById("grower-summary").textContent =
    DATA.stats.farm_count + (DATA.stats.farm_count === 1 ? " farm" : " farms") +
    " \u00b7 " + DATA.stats.field_count +
    (DATA.stats.field_count === 1 ? " field" : " fields") +
    " \u00b7 " + DATA.stats.area_acres.toFixed(1) + " acres";
  document.title = DATA.grower.name + " Field Map";

  function fieldBounds(feature) {
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    function walk(coords) {
      if (!coords || !coords.length) return;
      if (typeof coords[0] === "number") {
        minX = Math.min(minX, coords[0]); minY = Math.min(minY, coords[1]);
        maxX = Math.max(maxX, coords[0]); maxY = Math.max(maxY, coords[1]);
        return;
      }
      coords.forEach(walk);
    }
    walk(feature.geometry.coordinates);
    return [[minX, minY], [maxX, maxY]];
  }

  function popupHtml(feature) {
    var p = feature.properties;
    return '<div class="popup-title">' + escapeHtml(p.field_name) + "</div>" +
      '<div class="popup-sub">' + escapeHtml(p.farm_name) + " \u00b7 " +
      escapeHtml(p.grower_name) + "</div>" +
      '<dl class="popup-grid">' +
      "<dt>Crop</dt><dd>" + escapeHtml(p.crop_label) + "</dd>" +
      "<dt>Acres</dt><dd>" + p.area_acres.toFixed(2) + "</dd>" +
      "<dt>Location</dt><dd>" + escapeHtml(p.location_label || "n/a") + "</dd>" +
      "<dt>Field ID</dt><dd>" + escapeHtml(p.field_id) + "</dd>" +
      "</dl>";
  }

  function showPopup(feature) {
    if (popup) popup.remove();
    var p = feature.properties;
    popup = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: false,
      maxWidth: "310px",
      offset: 12
    })
      .setLngLat([p.lon, p.lat])
      .setHTML(popupHtml(feature))
      .addTo(map);
  }

  function renderSelection(feature) {
    var p = feature.properties;
    selectionEl.hidden = false;
    selectionEl.innerHTML =
      '<div class="selection-head">' +
      '<div><p class="selection-eyebrow">Selected field</p><h2>' +
      escapeHtml(p.field_name) + "</h2></div>" +
      '<button type="button" class="icon-button" data-action="clear" aria-label="Clear selection">\u00d7</button>' +
      "</div>" +
      '<p class="selection-sub">' + escapeHtml(p.farm_name) + " \u00b7 " +
      escapeHtml(p.grower_name) + "</p>" +
      '<div class="chips">' +
      '<span class="chip" style="--chip:' + escapeHtml(p.color) + '">' + escapeHtml(p.crop_label) + "</span>" +
      '<span class="chip">' + p.area_acres.toFixed(2) + " ac</span>" +
      "</div>" +
      '<dl class="fact-grid">' +
      "<div><dt>County</dt><dd>" + escapeHtml(p.location_label || "n/a") + "</dd></div>" +
      "<div><dt>Field ID</dt><dd>" + escapeHtml(p.field_id) + "</dd></div>" +
      "<div><dt>Centroid</dt><dd>" + p.lat.toFixed(5) + ", " + p.lon.toFixed(5) + "</dd></div>" +
      "<div><dt>Slug</dt><dd>" + escapeHtml(p.field_slug) + "</dd></div>" +
      "</dl>" +
      '<div class="selection-actions">' +
      '<button type="button" class="secondary-button" data-action="zoom">Zoom to field</button>' +
      '<button type="button" class="ghost-button" data-action="clear">Clear</button>' +
      "</div>";
  }

  function setHover(id) {
    if (hoverId === id) return;
    if (hoverId !== null && map.getSource("fields")) {
      map.setFeatureState({ source: "fields", id: hoverId }, { hover: false });
    }
    hoverId = id;
    if (id !== null && map.getSource("fields")) {
      map.setFeatureState({ source: "fields", id: id }, { hover: true });
    }
    ROWS.forEach(function (row, rowId) {
      row.classList.toggle("is-hover", rowId === id);
    });
  }

  function clearSelection() {
    if (selectedId !== null && map.getSource("fields")) {
      map.setFeatureState({ source: "fields", id: selectedId }, { selected: false });
    }
    selectedId = null;
    selectionEl.hidden = true;
    selectionEl.innerHTML = "";
    ROWS.forEach(function (row) { row.classList.remove("is-selected"); });
    if (popup) { popup.remove(); popup = null; }
  }

  function flyToFeature(feature) {
    map.fitBounds(fieldBounds(feature), {
      padding: 90,
      maxZoom: 17,
      duration: 900
    });
  }

  function selectField(id, options) {
    options = options || {};
    var feature = FIELD_BY_ID.get(id);
    if (!feature) return;
    if (selectedId !== null && selectedId !== id && map.getSource("fields")) {
      map.setFeatureState({ source: "fields", id: selectedId }, { selected: false });
    }
    selectedId = id;
    if (map.getSource("fields")) {
      map.setFeatureState({ source: "fields", id: id }, { selected: true });
    }
    ROWS.forEach(function (row, rowId) {
      row.classList.toggle("is-selected", rowId === id);
    });
    var row = ROWS.get(id);
    if (row) row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    renderSelection(feature);
    if (window.matchMedia && window.matchMedia("(max-width: 760px)").matches) {
      selectionEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
    if (options.fly) flyToFeature(feature);
    if (options.popup) showPopup(feature);
  }

  function renderSidebar() {
    farmListEl.innerHTML = "";
    DATA.farms.forEach(function (farm) {
      var fields = FEATURES.filter(function (feature) {
        return feature.properties.farm_slug === farm.slug;
      });
      var section = document.createElement("section");
      section.className = "farm-group";
      section.dataset.farmSlug = farm.slug;
      section.innerHTML =
        '<div class="farm-header">' +
        "<div><h2>" + escapeHtml(farm.name) + "</h2><p>" +
        farm.field_count + (farm.field_count === 1 ? " field" : " fields") +
        " \u00b7 " + farm.area_acres.toFixed(1) + " ac</p></div>" +
        '<button type="button" class="farm-zoom" data-farm-slug="' +
        escapeHtml(farm.slug) + '" aria-label="Zoom to ' + escapeHtml(farm.name) + '">Zoom</button>' +
        "</div>" +
        '<ul class="field-list"></ul>';
      var list = section.querySelector(".field-list");
      fields.forEach(function (feature) {
        var p = feature.properties;
        var item = document.createElement("li");
        var button = document.createElement("button");
        button.type = "button";
        button.className = "field-row";
        button.dataset.fieldId = String(feature.id);
        button.innerHTML =
          '<span class="swatch" style="background:' + escapeHtml(p.color) + '"></span>' +
          '<span class="field-meta"><span class="field-name">' +
          escapeHtml(p.field_name) + '</span><span class="field-sub">' +
          escapeHtml(p.crop_label) + " \u00b7 " + p.area_acres.toFixed(2) +
          " ac</span></span>";
        button.addEventListener("click", function () {
          selectField(feature.id, { fly: true, popup: true });
        });
        button.addEventListener("mouseenter", function () { setHover(feature.id); });
        button.addEventListener("mouseleave", function () { setHover(null); });
        button.addEventListener("focus", function () { setHover(feature.id); });
        button.addEventListener("blur", function () { setHover(null); });
        item.appendChild(button);
        list.appendChild(item);
        ROWS.set(feature.id, button);
      });
      farmListEl.appendChild(section);
    });
  }

  function renderLegend() {
    var legendEl = document.getElementById("legend");
    var seen = new Map();
    FEATURES.forEach(function (feature) {
      var p = feature.properties;
      if (!seen.has(p.crop_label)) seen.set(p.crop_label, p.color);
    });
    var items = Array.from(seen.keys()).sort().map(function (label) {
      return '<div class="legend-item"><span class="swatch" style="background:' +
        escapeHtml(seen.get(label)) + '"></span>' + escapeHtml(label) + "</div>";
    });
    legendEl.innerHTML = "<h3>Crops</h3>" + items.join("");
  }

  farmListEl.addEventListener("click", function (event) {
    var button = event.target.closest(".farm-zoom");
    if (!button) return;
    var farm = DATA.farms.find(function (entry) {
      return entry.slug === button.dataset.farmSlug;
    });
    if (farm && farm.bounds) {
      map.fitBounds(farm.bounds, { padding: 60, maxZoom: 16, duration: 900 });
    }
  });

  selectionEl.addEventListener("click", function (event) {
    var button = event.target.closest("button[data-action]");
    if (!button) return;
    if (button.dataset.action === "clear") clearSelection();
    if (button.dataset.action === "zoom" && selectedId !== null) {
      flyToFeature(FIELD_BY_ID.get(selectedId));
    }
  });

  document.getElementById("fit-grower").addEventListener("click", function () {
    if (DATA.bounds) {
      map.fitBounds(DATA.bounds, { padding: 56, maxZoom: 16, duration: 900 });
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") clearSelection();
  });

  function opacityExpression() {
    return [
      "case",
      ["boolean", ["feature-state", "selected"], false], Math.min(0.85, baseOpacity + 0.3),
      ["boolean", ["feature-state", "hover"], false], Math.min(0.75, baseOpacity + 0.15),
      baseOpacity
    ];
  }

  opacityEl.addEventListener("input", function () {
    baseOpacity = Number(opacityEl.value) / 100;
    if (map.getLayer("fields-fill")) {
      map.setPaintProperty("fields-fill", "fill-opacity", opacityExpression());
    }
  });

  function applySearch() {
    var query = searchEl.value.trim().toLowerCase();
    var visible = 0;
    var keys = [];
    document.querySelectorAll(".farm-group").forEach(function (group) {
      var groupVisible = 0;
      group.querySelectorAll(".field-row").forEach(function (row) {
        var feature = FIELD_BY_ID.get(Number(row.dataset.fieldId));
        var p = feature.properties;
        var haystack = [
          p.field_name, p.field_slug, p.field_id, p.farm_name, p.crop_label
        ].join(" ").toLowerCase();
        var match = !query || haystack.indexOf(query) !== -1;
        row.parentElement.hidden = !match;
        if (match) {
          groupVisible += 1;
          keys.push(p.field_key);
        }
      });
      group.hidden = groupVisible === 0;
      visible += groupVisible;
    });

    if (map.getLayer("fields-fill")) {
      if (query) {
        map.setFilter("fields-fill", ["in", ["get", "field_key"], ["literal", keys]]);
        map.setFilter("fields-outline", ["in", ["get", "field_key"], ["literal", keys]]);
      } else {
        map.setFilter("fields-fill", null);
        map.setFilter("fields-outline", null);
      }
    }
    if (selectedId !== null) {
      var selected = FIELD_BY_ID.get(selectedId);
      if (query && keys.indexOf(selected.properties.field_key) === -1) clearSelection();
    }
    if (query) {
      setStatus(visible + (visible === 1 ? " field matches" : " fields match") + " \u201c" + searchEl.value.trim() + "\u201d", { timeout: 2200 });
    } else {
      setStatus("", { hide: true });
    }
  }
  searchEl.addEventListener("input", applySearch);

  renderSidebar();
  renderLegend();

  if (!window.maplibregl) {
    setStatus("Map library failed to load. Check the internet connection and reload.", { error: true });
    return;
  }

  var style = {
    version: 8,
    sources: {
      imagery: {
        type: "raster",
        tiles: DATA.basemaps.imagery.tiles,
        tileSize: 256,
        maxzoom: DATA.basemaps.imagery.maxzoom,
        attribution: DATA.basemaps.imagery.attribution
      },
      labels: {
        type: "raster",
        tiles: DATA.basemaps.labels.tiles,
        tileSize: 256,
        maxzoom: DATA.basemaps.labels.maxzoom,
        attribution: DATA.basemaps.labels.attribution
      },
      streets: {
        type: "raster",
        tiles: DATA.basemaps.streets.tiles,
        tileSize: 256,
        maxzoom: DATA.basemaps.streets.maxzoom,
        attribution: DATA.basemaps.streets.attribution
      }
    },
    layers: [
      { id: "basemap-imagery", type: "raster", source: "imagery" },
      { id: "basemap-labels", type: "raster", source: "labels", layout: { visibility: "none" } },
      { id: "basemap-streets", type: "raster", source: "streets", layout: { visibility: "none" } }
    ]
  };

  var map;
  try {
    map = new maplibregl.Map({
      container: "map",
      style: style,
      bounds: DATA.bounds,
      fitBoundsOptions: { padding: 52, maxZoom: 16 },
      maxZoom: 20,
      attributionControl: false
    });
  } catch (error) {
    setStatus("This browser could not start the map engine. WebGL may be unavailable.", {
      error: true
    });
    return;
  }

  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new maplibregl.FullscreenControl(), "top-right");
  map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "imperial" }), "bottom-right");
  map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");

  var BASEMAP_VISIBILITY = {
    imagery: { imagery: true, labels: false, streets: false },
    hybrid: { imagery: true, labels: true, streets: false },
    streets: { imagery: false, labels: false, streets: true }
  };

  document.querySelectorAll("#basemap-switcher button").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelectorAll("#basemap-switcher button").forEach(function (other) {
        other.classList.toggle("active", other === button);
      });
      var visibility = BASEMAP_VISIBILITY[button.dataset.basemap];
      Object.keys(visibility).forEach(function (key) {
        var layerId = "basemap-" + key;
        if (map.getLayer(layerId)) {
          map.setLayoutProperty(layerId, "visibility", visibility[key] ? "visible" : "none");
        }
      });
    });
  });

  var tileErrorShown = false;
  map.on("error", function (event) {
    if (tileErrorShown) return;
    var message = String((event && event.error && event.error.message) || "");
    if (/tile|fetch|network|load/i.test(message)) {
      tileErrorShown = true;
      setStatus("Basemap tiles could not load. Field outlines are still available.", { error: true, timeout: 7000 });
    }
  });

  map.on("load", function () {
    map.addSource("fields", { type: "geojson", data: DATA.fields });
    map.addLayer({
      id: "fields-fill",
      type: "fill",
      source: "fields",
      paint: {
        "fill-color": ["get", "color"],
        "fill-opacity": opacityExpression()
      }
    });
    map.addLayer({
      id: "fields-halo",
      type: "line",
      source: "fields",
      paint: {
        "line-color": "#ffffff",
        "line-width": [
          "case",
          ["boolean", ["feature-state", "selected"], false], 6,
          ["boolean", ["feature-state", "hover"], false], 4,
          0
        ],
        "line-opacity": [
          "case",
          ["boolean", ["feature-state", "selected"], false], 0.9,
          ["boolean", ["feature-state", "hover"], false], 0.55,
          0
        ]
      }
    });
    map.addLayer({
      id: "fields-outline",
      type: "line",
      source: "fields",
      paint: {
        "line-color": ["get", "color"],
        "line-width": [
          "case",
          ["boolean", ["feature-state", "selected"], false], 3.4,
          ["boolean", ["feature-state", "hover"], false], 2.6,
          1.6
        ],
        "line-opacity": 0.95
      }
    });

    map.on("mousemove", "fields-fill", function (event) {
      if (!event.features || !event.features.length) return;
      map.getCanvas().style.cursor = "pointer";
      setHover(event.features[0].id);
    });
    map.on("mouseleave", "fields-fill", function () {
      map.getCanvas().style.cursor = "";
      setHover(null);
    });
    map.on("click", "fields-fill", function (event) {
      if (!event.features || !event.features.length) return;
      selectField(event.features[0].id, { popup: true });
    });
    map.on("click", function (event) {
      var hits = map.queryRenderedFeatures(event.point, { layers: ["fields-fill"] });
      if (!hits.length) clearSelection();
    });

    if (selectedId !== null) {
      map.setFeatureState({ source: "fields", id: selectedId }, { selected: true });
    }
    applySearch();
    setStatus("", { hide: true });
  });

  map.on("idle", function () {
    if (!tileErrorShown) setStatus("", { hide: true });
  });
})();
</script>
</body>
</html>
"""
