# Assignment 1 Grower Web Map

**Domain:** Agricultural Data Science & Farm Management — Admin Maps
**License:** Apache-2.0
**Attribution:** Superior Byte Works LLC / borealBytes

## What This Subskill Does

Generates a lightweight, interactive, single-file HTML map for each grower in the data pipeline runtime.

- Uses actual downloaded field polygon boundaries (`field_boundaries.geojson`)
- Shows all fields on a generic CartoDB basemap
- Lets users zoom, pan, and click fields
- Sidebar field list with click-to-zoom
- Popup metadata includes grower, farm, and field name
- No embedded imagery, rasters, or full data bundles — keeps HTML small

## Files

- `GUIDE.md` — usage instructions, CLI reference, and runtime notes
- `AGENTS.md` — local safe-edit scope and validation checklist
- `README.md` — this file

## How to Use

See `GUIDE.md` for the full quick-start and CLI reference.

## Integration with Data Pipeline

The runnable script lives in `data-pipeline/src/scripts/admin/generate_grower_webmap.py`. After the checkout installer syncs the runtime source, the script runs from the runtime copy against live grower data.

## Related

- `../interactive-web-map/` — full-featured multi-layer dashboard
- `../../../data-pipeline/` — authoritative runtime and pipeline scripts
