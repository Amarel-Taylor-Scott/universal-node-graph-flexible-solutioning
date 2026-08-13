"""Render a portable, self-contained design-atlas report bundle."""

from __future__ import annotations

from typing import Any

from solutiongraph.design_atlas.model import DesignContext, DesignDossier, DesignPlan
from solutiongraph.design_atlas.reporting import plan_payload, render_html, render_markdown


def render_report_node(
    context: dict[str, Any],
    design_plan: dict[str, Any],
    design_dossier: dict[str, Any],
) -> dict[str, Any]:
    """Render JSON, Markdown, and HTML without a filesystem or network effect."""
    parsed_context = DesignContext.from_dict(context)
    parsed_plan = DesignPlan.from_dict(design_plan)
    parsed_dossier = DesignDossier.from_dict(design_dossier)
    if parsed_plan.context_digest != parsed_context.digest:
        raise ValueError("design_plan is not bound to the supplied context")
    if parsed_dossier.plan_digest != parsed_plan.digest:
        raise ValueError("design_dossier is not bound to the supplied plan")
    return {
        "payload": plan_payload(parsed_context, parsed_plan, parsed_dossier),
        "markdown": render_markdown(parsed_context, parsed_plan, parsed_dossier),
        "html": render_html(parsed_context, parsed_plan, parsed_dossier),
    }


__all__ = ["render_report_node"]
