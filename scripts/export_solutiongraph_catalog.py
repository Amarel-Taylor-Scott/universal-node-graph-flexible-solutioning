#!/usr/bin/env python3
"""Regenerate the checked-in reference node pack and semantic templates."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from solutiongraph.catalog import write_catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("catalog"),
        help="Catalogue directory (default: catalog)",
    )
    args = parser.parse_args()
    written = write_catalog(args.output)
    print(f"wrote {len(written)} catalogue documents to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
