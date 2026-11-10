"""Grower-level interactive field map for My Farm Advisor.

The package reads only runtime pipeline outputs (grower metadata, farm metadata,
and field boundary GeoJSON) and writes one lightweight HTML page per grower.
It has no third-party dependencies so it can run from an installed runtime copy
without the data-pipeline virtualenv.
"""

from __future__ import annotations

SKILL_NAME = "grower-webmap"
__version__ = "0.1.0"

__all__ = ["SKILL_NAME", "__version__"]
