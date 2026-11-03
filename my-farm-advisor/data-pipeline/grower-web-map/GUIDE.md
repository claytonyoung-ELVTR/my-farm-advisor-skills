# Grower Web Map Guide

This guide covers the grower-web-map generator, its inputs, the interactive map behavior, and the checks used to verify the output.

## Why a dedicated generator

The map is a purpose-built grower application, not a reuse of the general `admin/interactive-web-map` template. It is scoped to one grower, reads canonical pipeline boundaries, and renders a farm-grouped field browser with a satellite-first basemap.

## Entrypoint

```text
${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src/scripts/reporting/generate_grower_web_map.py
```

The map builder lives next to it in `grower_web_map.py`. Both files are copied into the runtime by `data-pipeline/scripts/install.sh` because they live under `src/`.

## CLI

| Option | Behavior |
| --- | --- |
| `--grower-slug SLUG` | Render one grower. Repeat the flag to render several. |
| `--all` | Render every directory under `growers/` that has a `farms/` directory. |
| `--output PATH` | Override the output file. Requires exactly one grower. |

`--grower-slug` and `--all` are mutually exclusive and one is required.

## Data flow

1. Validate the grower slug and load `grower.json` for an optional display name.
2. Read `manifests/pipeline_schedule.json` for farm display names, then fall back to `farms/<farm>/farm.json` and finally the farm slug.
3. Iterate every directory under `farms/` and read `boundary/field_boundaries.geojson`.
4. Read `manifests/field-inventory.csv` for `field_id -> field_slug` and optional name columns.
5. Project each farm to its UTM zone to compute reliable centroids and acreage, then reproject the polygons to EPSG:4326.
6. Simplify polygons with a small tolerance and round coordinates to six decimal places.
7. Build one GeoJSON `FeatureCollection` plus farm summaries, bounds, stats, and basemap definitions.
8. Embed the payload as JSON in the HTML and write the file.

## Field naming

The pipeline does not store a separate human field name. The generator uses:

1. `field_name`, `name`, or `display_name` from `field-inventory.csv` when present.
2. Otherwise `Field <digits>` derived from the stable `field_id`/`field_slug` (for example `Field 1288035236`).

The stable `field_slug` and `field_id` are retained in the map metadata.

## Map behavior

- The page opens fitted to all of the grower's fields.
- The sidebar lists farms and their fields; hovering a row highlights the polygon, and clicking a row flies to the field and opens its popup.
- Clicking a polygon opens a popup with field name, farm, grower, crop, acres, location, and field ID. The sidebar also shows a selected-field panel with centroid and slug.
- The search box filters both the field list and the map polygons by field name, slug, ID, farm, or crop.
- "Fit all fields" resets the view. Each farm header has its own zoom button.
- The basemap switcher offers Satellite (ESRI World Imagery), Hybrid (imagery plus ESRI place labels), and Streets (OpenStreetMap).
- Crop colors drive the polygon fill, outline, and legend. The sidebar opacity slider changes the fill opacity without changing the file.
- `Esc` clears the current selection. MapLibre's navigation, scale, fullscreen, and attribution controls are enabled.

## Output contract

```text
growers/<grower>/derived/reports/<grower>_web_map.html
```

- A single HTML file with inline CSS, inline application JavaScript, and an inline JSON payload.
- No external data file, no embedded imagery, no base64 rasters, and no bundled JS library.
- Typical size is tens of KiB for a few fields; the generator is intended to stay well under 250 KiB for normal grower counts.
- MapLibre GL JS and the basemap tiles are fetched from public CDNs, so the page needs internet access for the library and basemap. Field geometry and metadata remain in the file if a tile request fails.

## Basemaps and attribution

- Satellite: `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`
- Hybrid labels: `https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}`
- Streets: `https://tile.openstreetmap.org/{z}/{x}/{y}.png`
- MapLibre GL JS 4.7.1: `https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js`

Attribution is displayed in the map's attribution control and embedded in the raster source definitions. Keep the attribution when changing basemap sources.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `No field boundaries found for grower` | Confirm `farms/<farm>/boundary/field_boundaries.geojson` exists and has features. |
| `No farms directory for grower` | Confirm the grower slug and the `farms/` directory under `growers/`. |
| Blank basemap, visible polygons | The tile service or CDN is unreachable. Field outlines still render. |
| Blank page | Confirm the MapLibre CDN script loads and the browser has JavaScript and WebGL enabled. |
| Missing grower in `--all` | The grower directory must contain a `farms/` directory. |
| `--output` rejected | `--output` is only valid with exactly one `--grower-slug`. |

## Verification

After generating maps, verify the embedded payload:

```bash
python3 - <<'PY'
import json
import re
from pathlib import Path

path = Path("growers/il-grower/derived/reports/il-grower_web_map.html")
text = path.read_text()
match = re.search(
    r'<script id="grower-data" type="application/json">(.*?)</script>',
    text,
    re.S,
)
data = json.loads(match.group(1))
print(data["stats"])
print([(f["properties"]["field_name"], f["properties"]["farm_name"]) for f in data["fields"]["features"]])
PY
```

Run `./scripts/validate.sh` from the repository root after documentation or generator changes.
