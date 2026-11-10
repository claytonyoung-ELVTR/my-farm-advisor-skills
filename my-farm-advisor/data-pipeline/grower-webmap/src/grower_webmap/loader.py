"""Read-only loaders for grower, farm, and field boundary runtime data.

Every path resolved here lives under ``DATA_PIPELINE_DATA_ROOT``. Nothing is
downloaded, cached, or written by this module.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FIELD_NAME_KEYS = ("field_name", "name", "display_name")
DISPLAY_NAME_KEYS = ("display_name", "name")


class GrowerWebMapError(RuntimeError):
    """Raised when runtime grower data is missing or unreadable."""


@dataclass(frozen=True)
class FieldRecord:
    """One field polygon with the metadata needed for a map popup."""

    farm_slug: str
    farm_name: str
    field_id: str
    field_name: str
    properties: dict[str, Any]
    geometry: dict[str, Any]


@dataclass
class FarmRecord:
    """One farm under a grower, including its boundary source path."""

    slug: str
    name: str
    state: str | None
    boundary_path: Path
    fields: list[FieldRecord] = field(default_factory=list)


@dataclass
class GrowerRecord:
    """One grower and all farms/fields found in the runtime data tree."""

    slug: str
    name: str
    root: Path
    runtime_base: Path
    farms: list[FarmRecord] = field(default_factory=list)

    @property
    def fields(self) -> list[FieldRecord]:
        return [field for farm in self.farms for field in farm.fields]


def resolve_runtime_base(data_root: str | Path | None = None) -> Path:
    """Resolve the runtime base (``<root>/data-pipeline``) from an explicit path or env."""
    raw = str(data_root) if data_root else os.environ.get("DATA_PIPELINE_DATA_ROOT", "")
    if not raw.strip():
        raise GrowerWebMapError(
            "pass --data-root or set DATA_PIPELINE_DATA_ROOT to the runtime data root"
        )

    root = Path(raw).expanduser().resolve(strict=False)
    for candidate in (root, root / "data-pipeline"):
        if (candidate / "growers").is_dir():
            return candidate
    raise GrowerWebMapError(
        f"no growers/ directory under {root} or {root / 'data-pipeline'}; "
        "run the data pipeline first"
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GrowerWebMapError(f"cannot read {path}: {exc}") from exc
    except ValueError as exc:
        raise GrowerWebMapError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise GrowerWebMapError(f"{path} must contain a JSON object")
    return payload


def _first_non_empty(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _field_name(properties: dict[str, Any], field_id: str) -> str:
    return _first_non_empty(properties, FIELD_NAME_KEYS) or field_id


def _state_code(metadata: dict[str, Any]) -> str | None:
    value = metadata.get("state")
    if isinstance(value, str) and value.strip():
        return value.strip().upper()
    return None


def load_farm(farm_dir: Path) -> FarmRecord:
    """Load one farm directory. Missing boundary files yield a farm with no fields."""
    metadata_path = farm_dir / "farm.json"
    metadata = _read_json(metadata_path) if metadata_path.exists() else {}

    farm = FarmRecord(
        slug=str(metadata.get("farm_slug") or farm_dir.name),
        name=_first_non_empty(metadata, DISPLAY_NAME_KEYS) or farm_dir.name,
        state=_state_code(metadata),
        boundary_path=farm_dir / "boundary" / "field_boundaries.geojson",
    )
    if not farm.boundary_path.exists():
        return farm

    payload = _read_json(farm.boundary_path)
    features = payload.get("features")
    if not isinstance(features, list):
        return farm

    for feature in features:
        if not isinstance(feature, dict):
            continue
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") not in {
            "Polygon",
            "MultiPolygon",
        }:
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        field_id = _first_non_empty(properties, ("field_id", "field_slug"))
        if field_id is None:
            continue
        farm.fields.append(
            FieldRecord(
                farm_slug=farm.slug,
                farm_name=farm.name,
                field_id=field_id,
                field_name=_field_name(properties, field_id),
                properties=dict(properties),
                geometry=geometry,
            )
        )

    farm.fields.sort(key=lambda item: item.field_id)
    return farm


def load_grower(grower_dir: Path, runtime_base: Path) -> GrowerRecord:
    """Load one grower directory with every farm that has a farm.json."""
    metadata_path = grower_dir / "grower.json"
    metadata = _read_json(metadata_path) if metadata_path.exists() else {}

    grower = GrowerRecord(
        slug=str(metadata.get("grower_slug") or grower_dir.name),
        name=_first_non_empty(metadata, DISPLAY_NAME_KEYS) or grower_dir.name,
        root=grower_dir,
        runtime_base=runtime_base,
    )

    farms_root = grower_dir / "farms"
    if not farms_root.is_dir():
        return grower

    for farm_dir in sorted(path for path in farms_root.iterdir() if path.is_dir()):
        if not (farm_dir / "farm.json").exists() and not (
            farm_dir / "boundary" / "field_boundaries.geojson"
        ).exists():
            continue
        grower.farms.append(load_farm(farm_dir))

    grower.farms.sort(key=lambda item: item.slug)
    return grower


def discover_growers(
    runtime_base: Path, grower_slugs: list[str] | None = None
) -> list[GrowerRecord]:
    """Load the requested grower slugs, or every grower in the runtime tree."""
    growers_root = runtime_base / "growers"
    if not growers_root.is_dir():
        raise GrowerWebMapError(f"growers/ directory not found: {growers_root}")

    if grower_slugs:
        grower_dirs = [growers_root / slug for slug in grower_slugs]
        missing = [
            path.name
            for path in grower_dirs
            if not path.is_dir() or not (path / "grower.json").exists()
        ]
        if missing:
            raise GrowerWebMapError(
                "unknown grower(s): "
                + ", ".join(sorted(missing))
                + f"; available: {', '.join(sorted(p.name for p in growers_root.iterdir() if p.is_dir()))}"
            )
    else:
        grower_dirs = sorted(
            path
            for path in growers_root.iterdir()
            if path.is_dir() and (path / "grower.json").exists()
        )

    return [load_grower(path, runtime_base) for path in grower_dirs]
