# Local Instructions

## Purpose

This folder owns the grower-level interactive web map workflow for the data pipeline. It documents and routes the generator that turns each grower's downloaded field-boundary polygons into one lightweight HTML map.

## Safe edit scope

Edits should stay in this folder, its children, and the two generator files it routes to:

- `../src/scripts/reporting/grower_web_map.py`
- `../src/scripts/reporting/generate_grower_web_map.py`

Do not change the parent `README.md`, `AGENTS.md`, sibling workflows, or root policy from a subskill task unless explicitly requested.

## Read nearby docs first

Read [README.md](README.md) first, then [GUIDE.md](GUIDE.md). For runtime and installer context, read [../README.md](../README.md) and [../AGENTS.md](../AGENTS.md). For related reporting flows, read [../../data-sources/INDEX.md](../../data-sources/INDEX.md).

## Local workflow notes

- The generator runs from the installed runtime source copy, not from the checkout: `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src`.
- Default output is `growers/<grower>/derived/reports/<grower>_web_map.html`.
- The map must use the real `boundary/field_boundaries.geojson` polygons. Do not substitute synthetic or hand-drawn boundaries.
- The satellite basemap is ESRI World Imagery loaded from the internet. Do not embed imagery, rasters, or full JS bundles in the HTML.
- Field display names come from `field-inventory.csv` when a name column exists; otherwise use the stable field ID/slug label.
- Keep the HTML small: simplify polygons, round coordinates, and embed only scalar metadata.

## Local validation

Run the generator for at least one real grower after changes:

```bash
export DATA_PIPELINE_DATA_ROOT=/absolute/path/to/my-farm-advisor-runtime
cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src"
"${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python" \
  scripts/reporting/generate_grower_web_map.py --all
```

Then run `./scripts/validate.sh` from the repository root.

## Local-delta-only reminder

This nested AGENTS.md only records instructions that differ from the parent or root files. Do not duplicate root-wide asset, vendor, or validation policy here except this pointer to `../../../AGENTS.md`.
