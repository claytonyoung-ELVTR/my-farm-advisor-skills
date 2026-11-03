#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""Generate lightweight, grower-scoped interactive field maps.

Each grower receives one self-contained HTML file that embeds field polygons and
scalar metadata. Satellite and street basemaps load from public tile services.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LOCAL_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LOCAL_LIB))

from runtime_paths import resolve_runtime_paths  # noqa: E402

_RUNTIME_PATHS = resolve_runtime_paths()
_SCRIPTS = _RUNTIME_PATHS.runtime_scripts
_LIB = _RUNTIME_PATHS.runtime_scripts / "lib"
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_LIB))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grower_web_map import (  # noqa: E402
    discover_grower_slugs,
    write_grower_map,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate one lightweight interactive HTML field map per grower "
            "from the pipeline field boundaries."
        )
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--grower-slug",
        action="append",
        metavar="SLUG",
        help="Grower slug to render. Repeat for multiple growers.",
    )
    target.add_argument(
        "--all",
        action="store_true",
        help="Render every grower under growers/ that has a farms/ directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional output HTML path. Requires exactly one grower. "
            "Defaults to growers/<grower>/derived/reports/<grower>_web_map.html."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.all:
        if args.output is not None:
            print("--output can only be used with a single --grower-slug", file=sys.stderr)
            return 2
        growers = discover_grower_slugs()
        if not growers:
            print(f"No growers found under {_RUNTIME_PATHS.runtime_base / 'growers'}", file=sys.stderr)
            return 1
    else:
        growers = list(args.grower_slug)
        if args.output is not None and len(growers) != 1:
            print("--output can only be used with a single --grower-slug", file=sys.stderr)
            return 2

    print("=" * 60)
    print("Grower Web Map")
    print("=" * 60)

    failures = 0
    for grower_slug in growers:
        try:
            output_path = write_grower_map(grower_slug, output_path=args.output)
        except Exception as exc:  # pragma: no cover - surfaced as a CLI failure
            failures += 1
            print(f"FAIL  {grower_slug}: {exc}", file=sys.stderr)
            continue
        size_kb = output_path.stat().st_size / 1024
        print(f"OK    {grower_slug}: {output_path} ({size_kb:.1f} KiB)")

    if failures:
        print(f"{failures} grower map(s) failed", file=sys.stderr)
        return 1
    print(f"Generated {len(growers)} grower map(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
