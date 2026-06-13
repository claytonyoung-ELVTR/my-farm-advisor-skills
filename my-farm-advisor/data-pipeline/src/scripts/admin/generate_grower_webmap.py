#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""Generate a lightweight interactive grower web map from pipeline field boundaries.

Produces a single self-contained HTML file per grower with embedded GeoJSON,
Leaflet.js, and a sidebar field list. No embedded rasters or heavy data bundles.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Bootstrap local lib paths
try:
    _LIB = Path(__file__).resolve().parents[2] / "lib"
    sys.path.insert(0, str(_LIB))
    from paths import DATA_ROOT, farm_boundary_path, grower_dir
    from runtime_paths import resolve_runtime_paths
except ImportError:
    # Fallback for runtime paths when imported as top-level
    DATA_ROOT = Path(os.environ.get("DATA_PIPELINE_DATA_ROOT", "")) / "data-pipeline"
    def farm_boundary_path(grower: str, farm: str) -> Path:
        return DATA_ROOT / "growers" / grower / "farms" / farm / "boundary" / "field_boundaries.geojson"
    def grower_dir(grower: str) -> Path:
        return DATA_ROOT / "growers" / grower
    resolve_runtime_paths = None


def _discover_farm(grower_slug: str, farm_slug_hint: str | None) -> tuple[Path, str]:
    g_dir = grower_dir(grower_slug)
    if not g_dir.is_dir():
        raise SystemExit(f"Grower directory not found: {g_dir}")
    farms_dir = g_dir / "farms"
    if not farms_dir.is_dir():
        raise SystemExit(f"No farms directory for grower: {g_dir}")

    if farm_slug_hint:
        candidates = [farms_dir / farm_slug_hint]
    else:
        candidates = sorted(farms_dir.iterdir())

    for farm_dir in candidates:
        if not farm_dir.is_dir():
            continue
        boundaries = farm_dir / "boundary" / "field_boundaries.geojson"
        if boundaries.is_file():
            return boundaries, farm_dir.name
    raise SystemExit(f"No valid farm with boundaries found for grower '{grower_slug}'")


def _load_geojson(boundary_path: Path) -> dict:
    with boundary_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_html(grower_slug: str, farm_slug: str, geojson: dict) -> str:
    features = geojson.get("features", [])
    # Clean features to only include lightweight properties
    cleaned_features = []
    for feat in features:
        props = feat.get("properties", {})
        fid = props.get("field_id", "unknown")
        cleaned = {
            "type": "Feature",
            "geometry": feat.get("geometry", {}),
            "properties": {
                "field_id": fid,
                "field_name": props.get("field_name", fid),
                "area_acres": round(float(props.get("area_acres", 0)), 2),
                "county_name": props.get("county_name", ""),
                "crop_name": props.get("crop_name", ""),
                "source": props.get("source", ""),
            }
        }
        cleaned_features.append(cleaned)

    cleaned_geojson = {
        "type": "FeatureCollection",
        "features": cleaned_features
    }

    geojson_str = json.dumps(cleaned_geojson, separators=(",", ":"))

    # Compute bounds
    lats = []
    lons = []
    for feat in cleaned_features:
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if geom.get("type") == "Polygon":
            for ring in coords:
                for pt in ring:
                    lons.append(pt[0])
                    lats.append(pt[1])
        elif geom.get("type") == "MultiPolygon":
            for poly in coords:
                for ring in poly:
                    for pt in ring:
                        lons.append(pt[0])
                        lats.append(pt[1])

    if lats and lons:
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
    else:
        center_lat, center_lon = 40.0, -95.0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{grower_slug} — Field Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{height:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}}
  #app{{display:flex;height:100vh}}
  #sidebar{{width:260px;min-width:220px;background:#fff;border-right:1px solid #ddd;box-shadow:2px 0 8px rgba(0,0,0,0.06);z-index:1000;display:flex;flex-direction:column}}
  #sidebar-header{{padding:14px 16px;border-bottom:1px solid #eee;background:#f8f9fa}}
  #sidebar-header h1{{font-size:1.05em;color:#1B5E20;margin:0;font-weight:600}}
  #sidebar-header .subtitle{{font-size:0.75em;color:#666;margin-top:3px}}
  #sidebar-content{{flex:1;overflow-y:auto;padding:10px 14px}}
  .section-title{{font-size:0.7em;color:#888;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;margin-top:12px;font-weight:600}}
  .field-card{{background:#fff;border:1px solid #e0e0e0;border-radius:6px;padding:8px 12px;margin-bottom:6px;cursor:pointer;transition:all 0.15s}}
  .field-card:hover{{border-color:#2E7D32;box-shadow:0 2px 6px rgba(46,125,50,0.12)}}
  .field-card.active{{border-color:#2E7D32;background:#f0f7f0;box-shadow:0 2px 6px rgba(46,125,50,0.15)}}
  .field-card .fid{{font-size:0.8em;font-weight:600;color:#333;margin-bottom:1px}}
  .field-card .meta{{font-size:0.7em;color:#888}}
  .field-card .area{{font-size:0.78em;color:#2E7D32;font-weight:600}}
  #map{{flex:1;position:relative}}
  .legend{{background:#fff;padding:8px 10px;border-radius:4px;box-shadow:0 0 10px rgba(0,0,0,0.15);font-size:0.8em;line-height:1.4}}
  .legend-title{{font-weight:600;margin-bottom:4px;color:#333}}
  .legend-item{{display:flex;align-items:center;gap:6px;margin:3px 0}}
  .legend-swatch{{width:14px;height:14px;border-radius:2px;border:1px solid rgba(0,0,0,0.15)}}
</style>
</head>
<body>
<div id="app">
  <div id="sidebar">
    <div id="sidebar-header">
      <h1>{grower_slug}</h1>
      <div class="subtitle">{farm_slug}</div>
    </div>
    <div id="sidebar-content">
      <div class="section-title">Fields</div>
      <div id="field-list"></div>
      <div class="section-title">Legend</div>
      <div class="legend">
        <div class="legend-item"><span class="legend-swatch" style="background:#2E7D32"></span>Field boundary</div>
        <div class="legend-item"><span class="legend-swatch" style="background:#1565C0"></span>Selected</div>
      </div>
    </div>
  </div>
  <div id="map"></div>
</div>
<script>
const GEOJSON = {geojson_str};
const GROWER = "{grower_slug}";
const FARM = "{farm_slug}";

// Initialize map
const map = L.map('map').setView([{center_lat}, {center_lon}], 12);

// Add satellite basemap
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
  attribution: 'Esri, Maxar, Earthstar Geographics, and the GIS User Community',
  maxZoom: 20
}}).addTo(map);

// Add labels overlay for roads and places
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
  attribution: 'Esri',
  maxZoom: 20,
  pane: 'tilePane'
}}).addTo(map);

// Layer group for fields
const fieldGroup = L.layerGroup().addTo(map);
const fieldLayers = {{}};

// Render fields
for (const feat of GEOJSON.features) {{
  const fid = feat.properties.field_id;
  const layer = L.geoJSON(feat, {{
    style: {{
      color: '#1a1a1a',
      weight: 2,
      fillColor: '#2E7D32',
      fillOpacity: 0.25,
      opacity: 1
    }}
  }}).addTo(fieldGroup);

  layer.on('click', function(e) {{
    L.DomEvent.stopPropagation(e);
    selectField(fid);
  }});
  layer.on('mouseover', function(e) {{
    this.setStyle({{ fillOpacity: 0.45, weight: 3 }});
  }});
  layer.on('mouseout', function(e) {{
    this.setStyle({{ fillOpacity: 0.25, weight: 2 }});
  }});

  const popupHtml = '<b>' + fid + '</b><br/>' +
    'Grower: ' + GROWER + '<br/>' +
    'Farm: ' + FARM + '<br/>' +
    'Area: ' + (feat.properties.area_acres || 0) + ' acres<br/>' +
    (feat.properties.county_name ? 'County: ' + feat.properties.county_name + '<br/>' : '') +
    (feat.properties.crop_name ? 'Crop: ' + feat.properties.crop_name : '');
  layer.bindPopup(popupHtml);

  layer.bindTooltip('<b>' + fid + '</b>', {{
    permanent: false, direction: 'top', offset: [0, -8]
  }});

  fieldLayers[fid] = layer;
}}

// Fit to all fields
if (GEOJSON.features.length > 0) {{
  const group = new L.featureGroup(Object.values(fieldLayers));
  map.fitBounds(group.getBounds(), {{ padding: [40, 40] }});
}}

// Build sidebar field list
function buildSidebar() {{
  const el = document.getElementById('field-list');
  el.innerHTML = '';
  for (const feat of GEOJSON.features) {{
    const fid = feat.properties.field_id;
    const div = document.createElement('div');
    div.className = 'field-card';
    div.dataset.fid = fid;
    div.innerHTML = '<div class="fid">' + fid + '</div>' +
      '<div class="area">' + (feat.properties.area_acres || 0) + ' acres</div>' +
      '<div class="meta">' + (feat.properties.county_name || '') + ' | ' + (feat.properties.crop_name || '') + '</div>';
    div.addEventListener('click', function() {{
      selectField(fid);
    }});
    el.appendChild(div);
  }}
}}

function selectField(fid) {{
  // Highlight sidebar
  document.querySelectorAll('.field-card').forEach(c => c.classList.remove('active'));
  const card = document.querySelector('.field-card[data-fid="' + fid + '"]');
  if (card) card.classList.add('active');

  // Highlight map layer
  for (const key in fieldLayers) {{
    fieldLayers[key].setStyle({{ fillColor: '#2E7D32', weight: 2 }});
  }}
  const layer = fieldLayers[fid];
  if (layer) {{
    layer.setStyle({{ fillColor: '#1565C0', weight: 3 }});
    const b = layer.getBounds();
    map.fitBounds(b, {{ padding: [60, 60], maxZoom: 16 }});
    layer.openPopup();
  }}
}}

// Close popups on background click
map.on('click', function() {{
  map.closePopup();
  document.querySelectorAll('.field-card').forEach(c => c.classList.remove('active'));
  for (const key in fieldLayers) {{
    fieldLayers[key].setStyle({{ fillColor: '#2E7D32', weight: 2 }});
  }}
}});

buildSidebar();
</script>
</body>
</html>
"""
    return html


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a lightweight interactive grower web map from pipeline field boundaries"
    )
    parser.add_argument("--grower-slug", required=True, help="Grower slug (e.g. illinois-grower)")
    parser.add_argument("--farm-slug", default=None, help="Optional farm slug (auto-detected if omitted)")
    parser.add_argument("--output", default=None, help="Output HTML path (default: growers/<grower>/derived/grower_webmap.html)")
    args = parser.parse_args()

    boundary_path, farm_slug = _discover_farm(args.grower_slug, args.farm_slug)
    print(f"Discovered farm: {farm_slug}")
    print(f"Loading boundaries from: {boundary_path}")

    geojson = _load_geojson(boundary_path)
    n_fields = len(geojson.get("features", []))
    print(f"Found {n_fields} field(s)")

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = grower_dir(args.grower_slug) / "derived" / "grower_webmap.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    html = _build_html(args.grower_slug, farm_slug, geojson)
    out_path.write_text(html, encoding="utf-8")

    size_kb = len(html) / 1024
    print(f"✓ Created: {out_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
