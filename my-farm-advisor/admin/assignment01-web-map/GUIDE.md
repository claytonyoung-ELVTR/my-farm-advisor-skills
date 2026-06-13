---
name: assignment01-web-map
description: Generate a lightweight, grower-level interactive web map for each existing grower using actual downloaded field polygon boundaries from the data pipeline. Produces a single self-contained HTML file per grower with zoom, pan, clickable fields, and a sidebar field list.
version: 1.0.0
author: Boreal Bytes
tags: [web-map, leaflet, geospatial, interactive, grower, assignment-1]
---

# Assignment 1 Grower Web Map

## Purpose

This subskill generates a single, lightweight, self-contained HTML web map for each grower in the data pipeline runtime. It uses the actual downloaded field polygon boundaries, shows all fields on a generic basemap, and lets users click fields to see basic metadata and zoom via a sidebar field list.

## Output

- One HTML file per grower: `growers/<grower>/derived/grower_webmap.html`
- Reasonably small (~30–100 KB depending on field count) — no embedded rasters or imagery
- Opens directly in any modern web browser
- Requires internet only for the basemap tiles

## When to Use

- When you want a quick, shareable interactive map of a grower’s fields
- When you need to verify field boundaries visually after pipeline seeding
- As a lightweight alternative to the full-featured `generate_grower_map.py` admin map

## Prerequisites

The data pipeline runtime must already contain field boundaries for the target grower:

```bash
growers/<grower>/farms/<farm>/boundary/field_boundaries.geojson
```

## Quick Start

From the runtime source copy:

```bash
export DATA_PIPELINE_DATA_ROOT=/absolute/path/to/my-farm-advisor-runtime
cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src"
"${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python" \
  scripts/admin/generate_grower_webmap.py \
  --grower-slug illinois-grower
```

The script discovers the first valid farm for the grower, reads its boundary GeoJSON, and writes the HTML map to:

```
growers/<grower>/derived/grower_webmap.html
```

## CLI Reference

```
usage: generate_grower_webmap.py [-h] --grower-slug GROWER_SLUG [--farm-slug FARM_SLUG] [--output OUTPUT]

optional arguments:
  -h, --help            show this help message and exit
  --grower-slug GROWER_SLUG
                        Grower slug (e.g. illinois-grower)
  --farm-slug FARM_SLUG
                        Optional farm slug (auto-detected if omitted)
  --output OUTPUT       Output HTML path (defaults to growers/<grower>/derived/grower_webmap.html)
```

## Runtime Notes

- Run the data-pipeline installer (`scripts/install.sh`) after adding or modifying the script in the checkout so the runtime copy stays in sync.
- The script uses `scripts/lib/paths.py` and `scripts/lib/runtime_paths.py` for canonical runtime discovery.
- The generated HTML uses Leaflet.js and CartoDB Voyager basemap tiles loaded from the internet.

## Local validation

After generating the map, open the HTML file in a browser and verify:

1. All fields are visible on the map
2. The sidebar lists all fields with area and name
3. Clicking a field in the sidebar zooms to it
4. Clicking a polygon on the map opens a popup with grower, farm, and field name
5. The file size is under 500 KB

## Related

- [Interactive Web Map Guide](../interactive-web-map/GUIDE.md) — full-featured multi-layer dashboard
- [Data Pipeline README](../../../data-pipeline/README.md) — runtime setup and farm seeding
- [Admin Index](../INDEX.md) — admin workflow overview
