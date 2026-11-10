---
name: grower-webmap
description: >
  Grower-level interactive web map for My Farm Advisor data-pipeline runtimes.
  Use when a request needs a lightweight, shareable HTML map of every field for
  one or more growers, with a satellite basemap, clickable field metadata, and
  zoom-to-field controls.
license: Apache-2.0
metadata:
  author: Clayton Young / Superior Byte Works, LLC (@borealBytes)
  version: "0.1.0"
  skill-author: Clayton Young / Superior Byte Works, LLC (@borealBytes)
  skill-version: "0.1.0"
---

# Grower Web Map

Render one self-contained HTML page per grower from data the pipeline already produced. Each page shows every field polygon for that grower over ESRI World Imagery, with click popups and a field list that zooms to a field.

## Start Here

- Read [README.md](README.md) for the runtime contract, inputs, outputs, and commands.
- Read [INDEX.md](INDEX.md) for file-level navigation.
- Read [PROVENANCE.md](PROVENANCE.md) before changing the renderer, basemaps, or attribution.
- Run [`scripts/render_growers.py`](scripts/render_growers.py) against the runtime data root.
- Install into a runtime with [`scripts/install_into_runtime.sh`](scripts/install_into_runtime.sh).

## Routing Notes

- Use this skill for a grower-wide or multi-grower field overview delivered as a browser map.
- Use the farm HTML report (`data-pipeline/src/scripts/reporting/generate_farm_html.py`) for a per-farm analytical report with embedded charts; use this skill when the deliverable is interactive geography instead.
- Use `data-pipeline/src/scripts/render_field_maps.py` for static per-field PNG composites.
- Do not embed satellite imagery, rasters, or data bundles. Basemap tiles load at view time; geometry is the only payload.
- Generated HTML and manifests stay under `DATA_PIPELINE_DATA_ROOT`; never commit them.
