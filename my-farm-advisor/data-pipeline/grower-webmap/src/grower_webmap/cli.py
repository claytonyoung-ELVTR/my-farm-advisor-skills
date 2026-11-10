"""Command line entry point for the grower web map skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import SKILL_NAME, __version__
from .loader import GrowerRecord, GrowerWebMapError, discover_growers, resolve_runtime_base
from .render import BASEMAPS, build_payload, render_html

HTML_SUFFIX = "_grower_map.html"
MANIFEST_NAME = "grower_map_manifest.json"


def html_basename(grower_slug: str) -> str:
    """Runtime-safe HTML name, mirroring the ``<farm>_farm_report.html`` convention."""
    return grower_slug.replace("-", "_") + HTML_SUFFIX


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, runtime_base: Path) -> str:
    try:
        return str(path.resolve().relative_to(runtime_base))
    except ValueError:
        return str(path)


def _manifest(
    grower: GrowerRecord, html_path: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    farms = []
    for farm in grower.farms:
        entry: dict[str, Any] = {
            "farm_slug": farm.slug,
            "farm_name": farm.name,
            "state": farm.state,
            "boundary_path": _relative(farm.boundary_path, grower.runtime_base),
            "field_count": len(farm.fields),
        }
        if farm.boundary_path.exists():
            entry["boundary_sha256"] = _sha256(farm.boundary_path)
        farms.append(entry)

    return {
        "skill": SKILL_NAME,
        "skill_version": __version__,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "grower_slug": grower.slug,
        "grower_name": grower.name,
        "grower_metadata": _relative(grower.root / "grower.json", grower.runtime_base),
        "html_path": _relative(html_path, grower.runtime_base),
        "html_bytes": html_path.stat().st_size,
        "html_sha256": _sha256(html_path),
        "farm_count": len(farms),
        "field_count": payload["meta"]["fieldCount"],
        "farms": farms,
        "fields": [
            {
                "farm_slug": field.farm_slug,
                "field_id": field.field_id,
                "field_name": field.field_name,
                "area_acres": field.properties.get("area_acres"),
            }
            for field in grower.fields
        ],
        "output_crs": "EPSG:4326",
        "basemaps": {
            name: {"name": basemap["name"], "url": basemap["url"]}
            for name, basemap in BASEMAPS.items()
        },
        "attribution": {
            "imagery": BASEMAPS["imagery"]["attribution"],
            "boundaries": "Pipeline output (OpenStreetMap ODbL 1.0 where source=OpenStreetMap)",
        },
        "notes": [
            "No imagery, rasters, or data bundles are embedded; basemap tiles load at view time.",
            "Field geometry is copied verbatim from the farm boundary GeoJSON.",
        ],
    }


def render_grower(grower: GrowerRecord) -> tuple[Path, Path]:
    """Render one grower map plus its manifest and return both paths."""
    payload = build_payload(grower)
    html = render_html(payload)

    html_path = grower.root / "derived" / "maps" / html_basename(grower.slug)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")

    manifest_path = grower.root / "manifests" / MANIFEST_NAME
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = _manifest(grower, html_path, payload)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return html_path, manifest_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="render_growers.py",
        description=(
            "Render a lightweight interactive HTML field map for each grower in the "
            "My Farm Advisor runtime data tree."
        ),
    )
    parser.add_argument(
        "--data-root",
        default=None,
        metavar="PATH",
        help="Runtime data root (defaults to DATA_PIPELINE_DATA_ROOT).",
    )
    parser.add_argument(
        "--grower",
        action="append",
        default=None,
        metavar="SLUG",
        help="Grower slug to render. Repeat for several growers. Defaults to all growers.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print errors.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        runtime_base = resolve_runtime_base(args.data_root)
        growers = discover_growers(runtime_base, args.grower)
    except GrowerWebMapError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = 0
    for grower in growers:
        if not grower.fields:
            print(f"skip: {grower.slug} has no field boundaries", file=sys.stderr)
            continue
        html_path, manifest_path = render_grower(grower)
        rendered += 1
        if not args.quiet:
            print(
                f"{grower.slug}: {len(grower.fields)} fields -> "
                f"{html_path} ({html_path.stat().st_size / 1024:.1f} KiB)"
            )
            print(f"  manifest: {manifest_path}")

    if rendered == 0:
        print("error: nothing rendered", file=sys.stderr)
        return 1
    return 0
