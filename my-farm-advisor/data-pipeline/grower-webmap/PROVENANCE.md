# Provenance

## Origin

- **Skill:** `grower-webmap`
- **Location:** `my-farm-advisor/data-pipeline/grower-webmap/`
- **Origin type:** authored in this repository for the Assignment 1 grower web-map deliverable. No upstream package was copied, vendored, or mirrored.
- **Version:** `0.1.0`
- **License:** Apache-2.0 (repository default)

## Upstream and reference sources

| Item | Source | Use |
| --- | --- | --- |
| Basemap tiles | ESRI World Imagery (`server.arcgisonline.com`) | Display only, streamed at view time with Esri attribution |
| Alternate basemap | OpenStreetMap standard tiles (`tile.openstreetmap.org`) | Display only, ODbL attribution |
| Leaflet 1.9.4 | `unpkg.com/leaflet@1.9.4` | Map runtime loaded from CDN; not vendored |
| Subskill layout conventions | `my-farm-advisor/terrain/dem-terrain/` | Folder structure and doc split |
| Leaflet sidebar pattern | `my-farm-advisor/admin/interactive-web-map/` | Interaction model only; no code copied and no embedded-imagery approach reused |

Data consumed by this skill is produced by the existing data pipeline:

- `growers/<grower>/grower.json`
- `growers/<grower>/farms/<farm>/farm.json`
- `growers/<grower>/farms/<farm>/boundary/field_boundaries.geojson`

The default boundary source in this repository is USDA CSB for US farms and OSM `landuse=farmland` elsewhere. Assignment 1 runtimes may instead have OSM-derived boundaries from a local OSM state extract; the manifest records the boundary path and SHA-256 so the actual source is always traceable from the output.

## Dependencies

- Python standard library only (`argparse`, `hashlib`, `json`, `pathlib`, `datetime`, `dataclasses`).
- No geopandas, shapely, folium, or tile download step.
- Browser-side Leaflet from CDN; internet access is required for basemap tiles but not for the polygons.

## Local modifications

- None relative to an upstream source; this skill is new in-repo content.
- One routing line was added to `my-farm-advisor/data-pipeline/README.md` so the subskill is discoverable from its parent.
- The umbrella `my-farm-advisor/SKILL.md`, `my-farm-advisor/INDEX.md`, and `data-pipeline/scripts/install.sh` were intentionally left unchanged.

## Asset policy

- No generated HTML, manifests, tiles, rasters, or GeoJSON payloads are committed.
- Rendering writes only to `DATA_PIPELINE_DATA_ROOT`:
  - `growers/<grower>/derived/maps/<grower>_grower_map.html`
  - `growers/<grower>/manifests/grower_map_manifest.json`
- Installed runtime copy: `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/skills/grower-webmap/`, outside the runtime `src/` tree so `install.sh` source refreshes do not remove it.

## Verification record

- Structural smoke: field counts, popup metadata keys, basemap URLs, no embedded `data:image` payloads, page size guard, and `node --check` on the inline script.
- Repository validation: `./scripts/validate.sh`.
