#!/usr/bin/env python3
"""Fail when package/import/tag versions disagree."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", pyproject)
    version = re.search(
        r'(?m)^version\s*=\s*"([^"]+)"\s*$',
        project.group(1) if project else "",
    )
    if version is None:
        print("release version error: [project].version is missing", file=sys.stderr)
        return 1
    distribution_version = version.group(1)
    from solutiongraph import __version__

    problems = []
    if distribution_version != __version__:
        problems.append(
            f"pyproject version {distribution_version} != solutiongraph {__version__}"
        )
    ref_type = os.environ.get("GITHUB_REF_TYPE", "")
    ref_name = os.environ.get("GITHUB_REF_NAME", "")
    if ref_type == "tag" and ref_name != f"v{distribution_version}":
        problems.append(
            f"tag {ref_name!r} must equal v{distribution_version}"
        )
    if problems:
        for problem in problems:
            print(f"release version error: {problem}", file=sys.stderr)
        return 1
    print(f"release version verified: {distribution_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
