"""Command-line surface for the design atlas."""

from __future__ import annotations

import json
from pathlib import Path

from solutiongraph.design_atlas import (
    REFERENCE_DESIGN_PACKS,
    REFERENCE_DESIGN_QUESTIONS,
    REFERENCE_SOURCES,
    REFERENCE_TASK_ARCHETYPES,
    REFERENCE_TECHNIQUES,
    CapabilityEvidence,
    DecisionAnswer,
    DesignContext,
    DesignPlanner,
    assess_maturity,
    atlas_index,
    normalize_task_type,
)
from solutiongraph.design_atlas.reporting import plan_payload, write_plan_bundle


def add_design_atlas_parser(commands) -> None:
    atlas = commands.add_parser(
        "atlas",
        help="Explore the data-science technique inventory and compile design worklists",
    )
    sub = atlas.add_subparsers(dest="atlas_command", required=True)

    sources = sub.add_parser("sources", help="List primary and official research sources")
    sources.add_argument("--json", action="store_true")

    techniques = sub.add_parser(
        "techniques", help="List the 618 cataloged techniques without implying execution maturity"
    )
    techniques.add_argument("--phase")
    techniques.add_argument("--query")
    techniques.add_argument(
        "--source-claim",
        choices=("reported-implemented", "reported-partial", "reported-designed", "reported-absent"),
    )
    techniques.add_argument("--json", action="store_true")

    packs = sub.add_parser("packs", help="List design-question packs")
    packs.add_argument("--json", action="store_true")

    questions = sub.add_parser("questions", help="List structured design questions")
    questions.add_argument("--pack")
    questions.add_argument("--mode", choices=("deterministic", "llm", "human", "external"))
    questions.add_argument("--json", action="store_true")

    archetypes = sub.add_parser("archetypes", help="List common data/ML task archetypes")
    archetypes.add_argument("--json", action="store_true")

    coverage = sub.add_parser("coverage", help="Show catalog and evidence-maturity coverage")
    coverage.add_argument("--json", action="store_true")

    plan = sub.add_parser("plan", help="Compile an all-visible effort-aware design plan")
    plan.add_argument("--context", type=Path, help="Strict design-context JSON")
    plan.add_argument("--dataset", type=Path, help="Optional CSV/TSV/JSON/JSONL dataset to profile")
    plan.add_argument(
        "--mapping-strategy",
        choices=("exact", "conservative", "broad"),
        default="conservative",
    )
    plan.add_argument("--task-type", help="Task archetype, for example regression or llm-evaluation")
    plan.add_argument("--objective", help="Required real-world outcome")
    plan.add_argument("--modality", action="append", help="Namespaced modality; repeatable")
    plan.add_argument("--signal", action="append", help="Namespaced task signal; repeatable")
    plan.add_argument("--constraint", action="append", help="Namespaced hard constraint; repeatable")
    plan.add_argument("--lifecycle-stage", default="lifecycle.prototype")
    plan.add_argument("--risk-tier", default="risk.medium")
    plan.add_argument("--target-name", default="")
    plan.add_argument("--time-field", default="")
    plan.add_argument("--group-field", default="")
    plan.add_argument("--entity-field", default="")
    plan.add_argument("--row-count", type=int)
    plan.add_argument("--column-count", type=int)
    plan.add_argument("--effort", choices=("E1", "E3", "E5", "E7", "E10"), default="E3")
    plan.add_argument("--mode", action="append", choices=("deterministic", "llm", "human", "external"))
    plan.add_argument("--permission", action="append")
    plan.add_argument("--random-seed", type=int, default=0)
    plan.add_argument("--output-dir", type=Path)
    plan.add_argument("--json", action="store_true")

    resolve = sub.add_parser(
        "resolve", help="Validate structured answers against a freshly compiled plan"
    )
    resolve.add_argument("context", type=Path, help="Strict design-context JSON")
    resolve.add_argument("answers", type=Path, help="JSON array of structured answers")
    resolve.add_argument(
        "--effort", choices=("E1", "E3", "E5", "E7", "E10"), default="E3"
    )
    resolve.add_argument(
        "--mode", action="append", choices=("deterministic", "llm", "human", "external")
    )
    resolve.add_argument("--permission", action="append")
    resolve.add_argument("--random-seed", type=int, default=0)
    resolve.add_argument("--output", type=Path)
    resolve.add_argument("--json", action="store_true")

    maturity = sub.add_parser("maturity", help="Derive C0-C7 maturity from an evidence JSON file")
    maturity.add_argument("evidence", type=Path)
    maturity.add_argument("--json", action="store_true")


def _emit(rows, as_json: bool, columns: tuple[str, ...]) -> int:
    if as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    print("\t".join(column.upper() for column in columns))
    for row in rows:
        print("\t".join(str(row[column]) for column in columns))
    return 0


def _context(args) -> DesignContext:
    if args.context and args.dataset:
        raise ValueError("--context and --dataset are mutually exclusive")
    if args.context:
        return DesignContext.from_dict(json.loads(args.context.read_text(encoding="utf-8")))
    if not args.task_type or not args.objective:
        raise ValueError("--task-type and --objective are required when --context is absent")
    modalities = tuple(args.modality or ("modality.tabular",))
    task_type = normalize_task_type(args.task_type)
    if args.dataset:
        from solutiongraph.design_atlas.profiling import context_from_records
        from solutiongraph.interrogation.io import load_records

        context, _, _ = context_from_records(
            load_records(args.dataset),
            task_type=task_type,
            objective=args.objective,
            mapping_strategy=args.mapping_strategy,
            source_id="source.design-atlas-cli-dataset",
            target_name=args.target_name,
            group_field=args.group_field,
            entity_field=args.entity_field,
            lifecycle_stage=args.lifecycle_stage,
            risk_tier=args.risk_tier,
            modalities=modalities,
            signals=tuple(args.signal or ()),
            constraints=tuple(args.constraint or ()),
        )
        return context
    return DesignContext(
        id=f"context.cli.{task_type.removeprefix('task.')}",
        task_type=task_type,
        objective=args.objective,
        modalities=modalities,
        lifecycle_stage=args.lifecycle_stage,
        risk_tier=args.risk_tier,
        signals=tuple(args.signal or ()),
        constraints=tuple(args.constraint or ()),
        row_count=args.row_count,
        column_count=args.column_count,
        target_name=args.target_name,
        time_field=args.time_field,
        group_field=args.group_field,
        entity_field=args.entity_field,
    )


def _evidence(path: Path) -> CapabilityEvidence:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("design_atlas_model_version", None)
    tuple_fields = (
        "monitoring_evidence",
        "security_evidence",
        "privacy_evidence",
        "rollback_evidence",
        "slo_evidence",
        "artifact_refs",
    )
    for field in tuple_fields:
        data[field] = tuple(data.get(field, ()))
    return CapabilityEvidence(**data)


def _answers(path: Path) -> tuple[DecisionAnswer, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("design answers must be a JSON array")
    answers = []
    for item in payload:
        data = dict(item)
        data.pop("design_atlas_model_version", None)
        data["evidence_refs"] = tuple(data.get("evidence_refs", ()))
        data["assumptions"] = tuple(data.get("assumptions", ()))
        answers.append(DecisionAnswer(**data))
    return tuple(answers)


def run_design_atlas_command(args) -> int:
    command = args.atlas_command
    if command == "sources":
        rows = [source.to_dict() for source in REFERENCE_SOURCES]
        return _emit(rows, args.json, ("id", "kind", "title", "url"))
    if command == "techniques":
        techniques = REFERENCE_TECHNIQUES
        if args.phase:
            phase = args.phase
            techniques = tuple(
                item for item in techniques
                if item.phase_id == phase or item.phase_id.startswith(f"phase.{phase}.")
            )
        if args.query:
            query = args.query.casefold()
            techniques = tuple(
                item for item in techniques
                if query in f"{item.title} {item.examples} {item.family}".casefold()
            )
        if args.source_claim:
            techniques = tuple(item for item in techniques if item.source_claim == args.source_claim)
        rows = [item.to_dict() for item in techniques]
        return _emit(rows, args.json, ("id", "phase_id", "source_claim", "title"))
    if command == "packs":
        rows = [
            {"id": pack.id, "stage": pack.stage, "questions": len(pack.questions), "title": pack.title}
            for pack in REFERENCE_DESIGN_PACKS
        ]
        return _emit(rows, args.json, ("id", "stage", "questions", "title"))
    if command == "questions":
        questions = REFERENCE_DESIGN_QUESTIONS
        if args.pack:
            pack_id = args.pack if args.pack.startswith("design-pack.") else f"design-pack.{args.pack}"
            questions = tuple(item for item in questions if item.pack_id == pack_id)
        if args.mode:
            questions = tuple(item for item in questions if args.mode in item.response_modes)
        rows = [item.to_dict() for item in questions]
        return _emit(rows, args.json, ("id", "pack_id", "cost_tier", "title"))
    if command == "archetypes":
        rows = [item.to_dict() for item in REFERENCE_TASK_ARCHETYPES]
        return _emit(rows, args.json, ("id", "outcome_artifact", "title"))
    if command == "coverage":
        index = atlas_index()
        if args.json:
            print(json.dumps(index, indent=2, sort_keys=True))
        else:
            print(
                f"techniques={index['technique_count']} phases={index['phase_count']} "
                f"packs={index['pack_count']} questions={index['question_count']} "
                f"archetypes={index['task_archetype_count']}"
            )
            print("machine maturity: C1=618; C2-C7 require separate implementation evidence")
            print("claim boundary: " + index["claim_boundary"])
        return 0
    if command == "plan":
        context = _context(args)
        modes = tuple(args.mode or ("human",))
        permissions = tuple(args.permission or (("human.review",) if modes == ("human",) else ()))
        plan = DesignPlanner().plan(
            context,
            effort=args.effort,
            available_modes=modes,
            granted_permissions=permissions,
            random_seed=args.random_seed,
        )
        paths = write_plan_bundle(context, plan, args.output_dir) if args.output_dir else ()
        if args.json:
            print(json.dumps(plan_payload(context, plan), indent=2, sort_keys=True))
        else:
            summary = plan.to_dict()["summary"]
            print(
                f"{plan.id}: visible={len(plan.items)} "
                + " ".join(f"{key}={value}" for key, value in summary.items())
            )
            for item in plan.items:
                if item.status == "selected":
                    question = next(q for q in REFERENCE_DESIGN_QUESTIONS if q.id == item.question_id)
                    print(f"{item.priority:.3f}\t{item.question_id}\t{question.prompt}")
            if paths:
                print("reports: " + ", ".join(str(path) for path in paths))
        return 0
    if command == "resolve":
        context = DesignContext.from_dict(
            json.loads(args.context.read_text(encoding="utf-8"))
        )
        modes = tuple(args.mode or ("human",))
        permissions = tuple(
            args.permission or (("human.review",) if modes == ("human",) else ())
        )
        planner = DesignPlanner()
        plan = planner.plan(
            context,
            effort=args.effort,
            available_modes=modes,
            granted_permissions=permissions,
            random_seed=args.random_seed,
        )
        dossier = planner.resolve(plan, _answers(args.answers))
        payload = dossier.to_dict()
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(
                f"{dossier.id}: decisions={len(dossier.decisions)} "
                f"unanswered={len(dossier.unanswered_question_ids)} "
                f"blocked={len(dossier.blocked_question_ids)}"
            )
            if args.output:
                print(f"wrote {args.output}")
        return 0
    if command == "maturity":
        assessment = assess_maturity(_evidence(args.evidence))
        if args.json:
            print(json.dumps(assessment.to_dict(), indent=2, sort_keys=True))
        else:
            print(
                f"{assessment.capability_id}: {assessment.overall_level} "
                f"({assessment.level_name}); next={assessment.next_gate}"
            )
        return 0
    raise ValueError(f"unknown atlas command {command!r}")


__all__ = ["add_design_atlas_parser", "run_design_atlas_command"]
