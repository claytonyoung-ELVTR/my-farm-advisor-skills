"""Build the inline map payload and render the single-file HTML page.

The rendered page embeds only field geometry and popup metadata. Basemap tiles
are streamed by Leaflet at view time, so no imagery is embedded or downloaded.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import SKILL_NAME, __version__
from .loader import GrowerRecord

TEMPLATE_PATH = Path(__file__).with_name("template.html")
DATA_PLACEHOLDER = "__GROWER_MAP_DATA__"

FARM_COLORS = (
    "#f59e0b",
    "#38bdf8",
    "#a3e635",
    "#f472b6",
    "#c084fc",
    "#2dd4bf",
    "#fb7185",
    "#facc15",
)

BASEMAPS: dict[str, dict[str, Any]] = {
    "imagery": {
        "name": "ESRI World Imagery",
        "url": (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ),
        "maxZoom": 19,
        "attribution": (
            "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, "
            "and the GIS User Community"
        ),
    },
    "osm": {
        "name": "OpenStreetMap",
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "maxZoom": 19,
        "attribution": (
            '&copy; <a href="https://www.openstreetmap.org/copyright">'
            "OpenStreetMap</a> contributors"
        ),
    },
}

# Properties copied into the page. Anything else stays in the runtime GeoJSON.
POPUP_PROPERTIES = (
    "field_id",
    "field_name",
    "area_acres",
    "county_name",
    "state_fips",
    "county_fips",
    "crop_name",
    "source",
)


def _json_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def build_payload(grower: GrowerRecord) -> dict[str, Any]:
    """Assemble the JSON payload embedded in the HTML page."""
    farms: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []

    for index, farm in enumerate(grower.farms):
        color = FARM_COLORS[index % len(FARM_COLORS)]
        farms.append(
            {
                "slug": farm.slug,
                "name": farm.name,
                "state": farm.state,
                "color": color,
                "fieldCount": len(farm.fields),
            }
        )
        for field in farm.fields:
            properties = {
                "farm_slug": farm.slug,
                "farm_name": farm.name,
                "field_id": field.field_id,
                "field_name": field.field_name,
            }
            for key in POPUP_PROPERTIES:
                value = field.properties.get(key)
                if key in ("area_acres", "state_fips", "county_fips"):
                    value = _json_number(value)
                elif isinstance(value, str):
                    value = value.strip() or None
                if value is not None:
                    properties[key] = value
            features.append(
                {
                    "type": "Feature",
                    "geometry": field.geometry,
                    "properties": properties,
                }
            )

    return {
        "grower": {"slug": grower.slug, "name": grower.name},
        "farms": farms,
        "fields": features,
        "basemaps": BASEMAPS,
        "meta": {
            "skill": SKILL_NAME,
            "version": __version__,
            "crs": "EPSG:4326",
            "farmCount": len(farms),
            "fieldCount": len(features),
        },
    }


def payload_json(payload: dict[str, Any]) -> str:
    """Serialize the payload, escaping ``</`` so ``</script>`` cannot break the page."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).replace(
        "</", "<\\/"
    )


def render_html(payload: dict[str, Any]) -> str:
    """Return the complete HTML document for one grower payload."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if DATA_PLACEHOLDER not in template:
        raise RuntimeError(f"map template is missing {DATA_PLACEHOLDER}: {TEMPLATE_PATH}")
    return template.replace(DATA_PLACEHOLDER, payload_json(payload))
