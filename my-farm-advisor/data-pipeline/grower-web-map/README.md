# grower-web-map

Generate one lightweight, self-contained interactive HTML field map per grower from the pipeline's downloaded field-boundary polygons.

The map embeds field polygons and scalar metadata in the HTML file. The MapLibre GL JS library and the satellite/street basemap tiles load from public CDNs, so no imagery, rasters, or full data bundles are stored inside the output.

## Output

```text
${DATA_PIPELINE_DATA_ROOT}/data-pipeline/growers/<grower>/derived/reports/<grower>_web_map.html
```

## Run

Install or refresh the runtime source copy after the generator changes:

```bash
export DATA_PIPELINE_DATA_ROOT=/absolute/path/to/my-farm-advisor-runtime
cd my-farm-advisor/data-pipeline
./scripts/install.sh --non-interactive --force-refresh --no-install-deps
```

Render every grower that has a `farms/` directory:

```bash
cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src"
"${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python" \
  scripts/reporting/generate_grower_web_map.py --all
```

Render one grower, or write to an explicit path:

```bash
cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src"
"${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python" \
  scripts/reporting/generate_grower_web_map.py \
  --grower-slug il-grower

"${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python" \
  scripts/reporting/generate_grower_web_map.py \
  --grower-slug il-grower \
  --output /tmp/il-grower-web-map.html
```

`--grower-slug` is repeatable. `--output` requires exactly one grower.

## What the map shows

- Every farm and field belonging to the grower, using the actual field polygons from `boundary/field_boundaries.geojson`.
- ESRI World Imagery satellite tiles by default, with hybrid labels and OpenStreetMap street alternatives.
- Click-to-inspect metadata: grower, farm, field name, crop, acres, county/state, field ID, and centroid.
- A searchable, farm-grouped field list that flies to a field and opens its popup.
- Crop colors, a legend, adjustable fill opacity, per-farm zoom, fit-to-grower, scale bar, and fullscreen.
- Zoom, pan, and responsive desktop/mobile layouts.

## Inputs

- `growers/<grower>/grower.json` for the optional grower display name.
- `growers/<grower>/manifests/pipeline_schedule.json` or each `farms/<farm>/farm.json` for farm display names.
- `growers/<grower>/farms/<farm>/manifests/field-inventory.csv` for field slugs and optional field names.
- `growers/<grower>/farms/<farm>/boundary/field_boundaries.geojson` for polygons, crop names, area, and county/state fields.

## Output contract

- One HTML file per grower, normally well under 250 KiB for typical grower field counts.
- Field polygons are simplified and coordinate-rounded to keep the file small.
- No external data file is required; the page works from `file://` when the CDN tiles and library are reachable.
- The embedded GeoJSON keeps `field_id`, `field_slug`, `farm_slug`, `grower_slug`, crop, acres, and county/state metadata.

See [GUIDE.md](GUIDE.md) for the data contract, map behavior, and troubleshooting. See [AGENTS.md](AGENTS.md) for local edit rules.
