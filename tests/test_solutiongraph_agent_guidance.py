from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
SKILL = ROOT / ".agents" / "skills" / "model-solution-graph" / "SKILL.md"


def test_workspace_skill_has_minimal_frontmatter_and_selective_references():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: model-solution-graph\ndescription:")
    assert text.count("\n---\n") == 1
    references = {
        "node-authoring.md",
        "registry-discovery.md",
        "template-instantiation.md",
        "experiments.md",
    }
    assert all(f"references/{name}" in text for name in references)
    reference_root = SKILL.parent / "references"
    assert references == {path.name for path in reference_root.glob("*.md")}
    assert all(path.read_text(encoding="utf-8").strip() for path in reference_root.glob("*.md"))


def test_focused_workspace_skills_are_triggerable_and_progressively_disclosed():
    skill_root = ROOT / ".agents" / "skills"
    expected = {
        "author-node-pack",
        "author-structured-workflow",
        "benchmark-solution-graph",
        "create-solution-template",
        "design-autoresearch-campaign",
        "design-topology-family",
        "execute-solution-graph",
        "model-solution-graph",
        "solve-universal-dag",
    }
    assert expected == {path.parent.name for path in skill_root.glob("*/SKILL.md")}
    for name in expected:
        text = (skill_root / name / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith(f"---\nname: {name}\ndescription:")
        assert text.count("\n---\n") == 1
        assert len(text.encode("utf-8")) < 8 * 1024
    create_skill = (skill_root / "create-solution-template" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "references/blueprint-authoring.md" in create_skill
    assert "solutiongraph templates validate" in create_skill


def test_root_instructions_stay_compact_and_vendor_files_point_to_one_source():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert len(agents.encode("utf-8")) < 16 * 1024
    assert "NODE_REPOSITORY_PROTOCOL.md" in agents
    assert "SOLUTION_TEMPLATE_PROTOCOL.md" in agents
    assert "EXECUTION_PROTOCOL.md" in agents
    assert "optional discovery sidecars" in agents
    assert "seeded-sprout" in agents
    assert "@AGENTS.md" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "@./AGENTS.md" in (ROOT / "GEMINI.md").read_text(encoding="utf-8")
    assert "AGENTS.md" in (ROOT / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")


def test_protocols_explicitly_reject_prompt_only_or_similarity_based_validity():
    node_protocol = (ROOT / "NODE_REPOSITORY_PROTOCOL.md").read_text(encoding="utf-8")
    template_protocol = (ROOT / "SOLUTION_TEMPLATE_PROTOCOL.md").read_text(encoding="utf-8")
    playbook = (ROOT / "AGENT_PLAYBOOK.md").read_text(encoding="utf-8")
    assert "only compiler admission" in node_protocol
    assert "dimensions do not imply compatibility" in node_protocol
    assert "Open-world discovery, closed-world compilation" in node_protocol
    assert "Prompt-only contract" in template_protocol
    assert "Embedding similarity used as type safety" in playbook
