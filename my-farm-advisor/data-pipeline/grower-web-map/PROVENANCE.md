# Provenance

## grower-web-map

- source_repo: N/A (authored in this repository)
- source_local_path: N/A
- source_ref: assignment-1
- source_commit: N/A (original work in this repository)
- source_status: original work
- source_path: `my-farm-advisor/data-pipeline/grower-web-map/`
- destination_path: `my-farm-advisor/data-pipeline/grower-web-map/`
- import_date: 2026-11-03
- exclusions: generated HTML maps, downloaded basemap tiles, and any runtime output under `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/growers/`
- local_modifications: New subskill authored for Assignment 1. The generator lives at `my-farm-advisor/data-pipeline/src/scripts/reporting/generate_grower_web_map.py` and `grower_web_map.py` so the existing installer copies it into the runtime source tree.
- third_party: MapLibre GL JS 4.7.1 (BSD-3-Clause) and ESRI World Imagery / OpenStreetMap tiles are referenced by URL at runtime. No third-party source is vendored.
- update_procedure: Edit the generator and this subskill in place, reinstall the runtime with `data-pipeline/scripts/install.sh --non-interactive --force-refresh --no-install-deps`, regenerate maps with `--all`, and rerun `./scripts/validate.sh`.
