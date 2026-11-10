# Grower Web Map Index

File-level navigation for the `grower-webmap` subskill.

## Documents

- [SKILL.md](SKILL.md) - routing entrypoint and scope.
- [README.md](README.md) - runtime contract, inputs, outputs, commands, map behavior, attribution, troubleshooting.
- [PROVENANCE.md](PROVENANCE.md) - origin, dependency, and asset-policy record.

## Code

- [`src/grower_webmap/__init__.py`](src/grower_webmap/__init__.py) - package name and version.
- [`src/grower_webmap/loader.py`](src/grower_webmap/loader.py) - runtime base resolution and grower/farm/field loading.
- [`src/grower_webmap/render.py`](src/grower_webmap/render.py) - payload assembly, basemap definitions, template rendering.
- [`src/grower_webmap/template.html`](src/grower_webmap/template.html) - Leaflet page template with the data placeholder.
- [`src/grower_webmap/cli.py`](src/grower_webmap/cli.py) - argument parsing, HTML and manifest writing.
- [`src/grower_webmap/__main__.py`](src/grower_webmap/__main__.py) - `python -m grower_webmap` entry.
- [`scripts/render_growers.py`](scripts/render_growers.py) - runnable wrapper used from a checkout or runtime copy.
- [`scripts/install_into_runtime.sh`](scripts/install_into_runtime.sh) - copies the subskill into `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/skills/`.

## Where outputs land

- HTML map: `growers/<grower>/derived/maps/<grower>_grower_map.html`
- Manifest: `growers/<grower>/manifests/grower_map_manifest.json`

Both paths are under `DATA_PIPELINE_DATA_ROOT` and never under this checkout.
