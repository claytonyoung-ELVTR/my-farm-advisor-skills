# Grower Web Map

A grower-level interactive map built from the data-pipeline runtime tree. One HTML page is written per grower and contains that grower's farm and field polygons, clickable metadata popups, and a field list that zooms to a field.

This subskill is read-only with respect to the pipeline: it never downloads imagery, re-runs ingest steps, or rewrites boundaries. It has no third-party Python dependencies, so it runs from an installed runtime copy with the data-pipeline virtualenv or plain `python3`.

## What it reads

| Input | Path |
| --- | --- |
| Grower metadata | `growers/<grower>/grower.json` |
| Farm metadata | `growers/<grower>/farms/<farm>/farm.json` |
| Field polygons | `growers/<grower>/farms/<farm>/boundary/field_boundaries.geojson` |

Boundaries are read as-is from the pipeline output, which is WGS84 (`EPSG:4326`). Field display names come from a `field_name` or `name` property when the boundary has one; otherwise the pipeline `field_id` (for example `osm-w1282575240`) is used. The skill never invents names.

## What it writes

| Output | Path |
| --- | --- |
| Map page | `growers/<grower>/derived/maps/<grower>_grower_map.html` |
| Provenance manifest | `growers/<grower>/manifests/grower_map_manifest.json` |

The HTML excludes imagery and rasters; only field geometry and popup metadata are embedded, so a three-field grower page is roughly 20-30 KiB. The manifest records the source boundary paths and SHA-256 digests, field inventory, HTML size and digest, basemap URLs, and attribution.

Map HTML has no timestamp, so re-rendering unchanged data produces a byte-identical page. The manifest is timestamped by design.

## Install into a runtime

The skill is not part of the runtime `src/` tree, because `install.sh` replaces that tree on refresh. Install it beside the runtime instead:

```bash
export DATA_PIPELINE_DATA_ROOT=/absolute/path/to/my-farm-advisor-runtime
cd my-farm-advisor/data-pipeline/grower-webmap
./scripts/install_into_runtime.sh
```

That copies this folder to `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/skills/grower-webmap/`. Generated grower data is not touched.

## Render

Every grower in the runtime:

```bash
"${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python" \
  "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/skills/grower-webmap/scripts/render_growers.py" \
  --data-root "${DATA_PIPELINE_DATA_ROOT}"
```

Selected growers:

```bash
python3 scripts/render_growers.py \
  --data-root ~/my-farm-advisor-runtime \
  --grower il-demo-grower \
  --grower ia-demo-grower
```

`--data-root` accepts either the runtime data root or its `data-pipeline` base, and falls back to `DATA_PIPELINE_DATA_ROOT`. Exit codes: `0` rendered, `1` nothing rendered, `2` bad arguments or missing runtime data.

Output example:

```
il-demo-grower: 3 fields -> .../growers/il-demo-grower/derived/maps/il_demo_grower_grower_map.html (28.4 KiB)
  manifest: .../growers/il-demo-grower/manifests/grower_map_manifest.json
```

## Map behavior

- **Basemap:** ESRI World Imagery by default, with an OpenStreetMap toggle in the layer control. Tiles load from the internet at view time.
- **Fields:** one GeoJSON layer per farm, colored per farm, all fields fitted on load.
- **Popups:** grower, farm, field name, field ID, area in acres, county, and boundary source.
- **Field list:** grouped by farm in the sidebar; clicking an entry zooms to that field and opens its popup. `Fit all fields` restores the grower view.
- **Zoom:** Leaflet zoom controls, scroll-wheel zoom, and a dual-unit scale bar.
- **Small screens:** the sidebar moves below the map under 720 px.

Run it locally by opening the HTML file directly; no server is required. A web server is only needed if the browser blocks local file access in a locked-down profile.

## Attribution and licensing

- Basemap tiles: ESRI World Imagery, displayed with Esri attribution. Toggle layer: OpenStreetMap contributors, ODbL.
- Field boundaries: pipeline output. OSM-derived boundaries carry ODbL 1.0 attribution via the map footer and manifest.

Keep both attributions visible when sharing or publishing a page.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `no growers/ directory under ...` | Wrong `--data-root`, or the pipeline has not run yet. |
| `unknown grower(s): ...` | Check `ls "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/growers"`. |
| `skip: <grower> has no field boundaries` | The grower exists but no farm has `boundary/field_boundaries.geojson`. |
| Map is blank with grey background | Tiles cannot load (offline or blocked); polygons still render once tiles return. |
| Page opens but the sidebar is empty | The boundary GeoJSON had no `Polygon`/`MultiPolygon` features with a `field_id`. |
