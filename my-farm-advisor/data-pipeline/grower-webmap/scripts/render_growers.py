#!/usr/bin/env python3
"""Render grower-level interactive field maps from the runtime data tree.

Run from the checkout or from an installed runtime copy; the script only adds
its sibling ``src/`` directory to ``sys.path``.

Examples:
    python3 scripts/render_growers.py --data-root ~/my-farm-advisor-runtime
    python3 scripts/render_growers.py --grower il-demo-grower
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grower_webmap.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
