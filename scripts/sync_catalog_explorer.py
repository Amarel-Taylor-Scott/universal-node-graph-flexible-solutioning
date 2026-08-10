#!/usr/bin/env python3
"""Synchronize inline catalog data in the self-contained template explorer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

def _viewer_data() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    from solutiongraph.reference_nodes import (
        REFERENCE_DESCRIPTORS,
        REFERENCE_NODE_SPECS,
    )
    from solutiongraph.template_library import REFERENCE_TEMPLATES

    templates = [
        {
            "id": template.id,
            "title": template.title,
            "domains": list(template.domains),
            "stages": [
                {
                    "id": stage.id,
                    "title": stage.title,
                    "description": stage.description,
                    "slots": [
                        [slot.id, slot.purpose]
                        for slot in template.program.slots
                        if slot.id in stage.slot_ids
                    ],
                }
                for stage in template.stages
            ],
        }
        for template in REFERENCE_TEMPLATES.templates
    ]
    descriptions = {item.node_id: item for item in REFERENCE_DESCRIPTORS}
    nodes = [
        {
            "id": node.id,
            "capability": node.capabilities[0],
            "effects": list(node.effects),
            "summary": descriptions[node.id].summary,
        }
        for node in REFERENCE_NODE_SPECS
    ]
    return templates, nodes


def sync(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    start_token = "      const templates = "
    start = text.find(start_token)
    end_tokens = (
        "\n\n      const domainSelect",
        "\n\n      const templateSelect",
    )
    end_candidates = [
        position
        for token in end_tokens
        if (position := text.find(token, start)) >= 0
    ]
    end = min(end_candidates, default=-1)
    if start < 0 or end < 0:
        raise ValueError(f"{path}: catalog data anchors not found")
    templates, nodes = _viewer_data()
    generated = (
        "      const templates = "
        + json.dumps(templates, indent=2, ensure_ascii=False)
        + ";\n\n      const nodes = "
        + json.dumps(nodes, indent=2, ensure_ascii=False)
        + ";"
    )
    path.write_text(text[:start] + generated + text[end:], encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "html",
        type=Path,
        nargs="*",
        default=[Path("examples/catalog-template-explorer.html")],
        help="Explorer HTML file(s) to synchronize",
    )
    args = parser.parse_args()
    for path in args.html:
        sync(path)
        print(f"synchronized {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
