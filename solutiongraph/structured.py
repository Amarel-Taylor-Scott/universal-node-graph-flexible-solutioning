"""Deterministic lowering for composite and bounded-loop graph structure.

The core compiler intentionally accepts only acyclic executable programs.  This
module preserves that invariant by expanding structured semantic slots into an
ordinary, compiler-valid DAG before candidate admission.  Expansion is content
addressed and inspectable; it is never an executor-side hidden rewrite.

A bounded loop executes at most ``max_iterations`` copies of its body.  Early
convergence is represented inside the body with an explicit active/pass-through
state, so later unrolled copies have no side effects once the state is inactive.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from solutiongraph.compiler import Compiler
from solutiongraph.errors import Diagnostic, ValidationError
from solutiongraph.model import (
    ID_RE,
    Edge,
    GraphInput,
    GraphOutput,
    ProgramGraph,
    SemanticSlot,
    SlotKind,
    sha256_digest,
)

STRUCTURED_MODEL_VERSION = "0.1"


@dataclass(frozen=True)
class SubgraphCatalog:
    """Closed collection of semantic child graphs addressable by id or digest."""

    id: str
    version: str
    graphs: tuple[ProgramGraph, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def resolve(self, reference: str) -> ProgramGraph:
        matches = tuple(
            graph
            for graph in self.graphs
            if reference in (graph.id, graph.digest)
        )
        if len(matches) != 1:
            raise ValueError(
                f"subgraph reference {reference!r} resolved to {len(matches)} graphs"
            )
        return matches[0]

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.version.strip():
            problems.append("subgraph catalog id and version are invalid")
        ids = [graph.id for graph in self.graphs]
        digests = [graph.digest for graph in self.graphs]
        if len(ids) != len(set(ids)):
            problems.append("subgraph catalog graph ids must be unique")
        if len(digests) != len(set(digests)):
            problems.append("subgraph catalog graph digests must be unique")
        compiler = Compiler()
        for graph in self.graphs:
            for diagnostic in compiler.validate_program(graph):
                problems.append(
                    f"subgraph {graph.id}: {diagnostic.code}: {diagnostic.message}"
                )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "structured_model_version": STRUCTURED_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "graphs": [
                {"id": graph.id, "version": graph.version, "digest": graph.digest}
                for graph in self.graphs
            ],
        }


@dataclass(frozen=True)
class LoopPolicy:
    """Explicit compile-time bound and feedback wiring for one loop slot."""

    slot_id: str
    max_iterations: int
    feedback: tuple[tuple[str, str], ...]

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.slot_id):
            problems.append("loop policy slot_id is invalid")
        if self.max_iterations <= 0:
            problems.append("loop max_iterations must be positive")
        outputs = [output for output, _ in self.feedback]
        inputs = [input_ for _, input_ in self.feedback]
        if not self.feedback:
            problems.append("loop policy must declare at least one feedback mapping")
        if len(outputs) != len(set(outputs)) or len(inputs) != len(set(inputs)):
            problems.append("loop feedback ports must be unique")
        return problems


@dataclass(frozen=True)
class ExpansionRecord:
    slot_id: str
    kind: str
    subgraph_id: str
    subgraph_digest: str
    expanded_slot_ids: tuple[str, ...]
    iterations: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "kind": self.kind,
            "subgraph_id": self.subgraph_id,
            "subgraph_digest": self.subgraph_digest,
            "expanded_slot_ids": list(self.expanded_slot_ids),
            "iterations": self.iterations,
        }


@dataclass(frozen=True)
class LoweringReceipt:
    source_program_digest: str
    lowered_program_digest: str
    catalog_digest: str
    expansions: tuple[ExpansionRecord, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "structured_model_version": STRUCTURED_MODEL_VERSION,
            "source_program_digest": self.source_program_digest,
            "lowered_program_digest": self.lowered_program_digest,
            "catalog_digest": self.catalog_digest,
            "expansions": [item.to_dict() for item in self.expansions],
        }


@dataclass(frozen=True)
class LoweredProgram:
    program: ProgramGraph
    receipt: LoweringReceipt


def _graph_inputs(graph: ProgramGraph) -> dict[str, GraphInput]:
    return {item.name: item for item in graph.inputs}


def _graph_outputs(graph: ProgramGraph) -> dict[str, GraphOutput]:
    return {item.name: item for item in graph.outputs}


def _namespaced_slot(slot: SemanticSlot, prefix: str, group: tuple[str, ...]) -> SemanticSlot:
    activation_slot = f"{prefix}/{slot.activation_slot}" if slot.activation_slot else ""
    return replace(
        slot,
        id=f"{prefix}/{slot.id}",
        group=group + slot.group,
        activation_slot=activation_slot,
    )


def _namespaced_edge(edge: Edge, prefix: str) -> Edge:
    return Edge(
        f"{prefix}/{edge.source_slot}",
        edge.source_port,
        f"{prefix}/{edge.target_slot}",
        edge.target_port,
    )


def _validate_boundary(parent: SemanticSlot, child: ProgramGraph) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    child_inputs = _graph_inputs(child)
    child_outputs = _graph_outputs(child)
    parent_inputs = {port.name: port for port in parent.inputs}
    parent_outputs = {port.name: port for port in parent.outputs}
    if set(parent_inputs) != set(child_inputs):
        diagnostics.append(Diagnostic(
            "UNG-STRUCTURE-002",
            "parent input port names must exactly match child graph input names",
            f"program.slots.{parent.id}",
        ))
    if set(parent_outputs) != set(child_outputs):
        diagnostics.append(Diagnostic(
            "UNG-STRUCTURE-003",
            "parent output port names must exactly match child graph output names",
            f"program.slots.{parent.id}",
        ))
    for name in sorted(set(parent_inputs) & set(child_inputs)):
        if not parent_inputs[name].value_type.is_assignable_to(child_inputs[name].value_type):
            diagnostics.append(Diagnostic(
                "UNG-STRUCTURE-004",
                f"parent input {name} is incompatible with the child graph input",
                f"program.slots.{parent.id}.inputs.{name}",
            ))
    for name in sorted(set(parent_outputs) & set(child_outputs)):
        if not child_outputs[name].value_type.is_assignable_to(parent_outputs[name].value_type):
            diagnostics.append(Diagnostic(
                "UNG-STRUCTURE-005",
                f"child graph output {name} is incompatible with the parent output",
                f"program.slots.{parent.id}.outputs.{name}",
            ))
    if not set(child.allowed_effects).issubset(parent.allowed_effects):
        diagnostics.append(Diagnostic(
            "UNG-STRUCTURE-006",
            "child graph effects exceed the composite or loop slot authority",
            f"program.slots.{parent.id}.allowed_effects",
        ))
    if parent.activation_slot:
        diagnostics.append(Diagnostic(
            "UNG-STRUCTURE-007",
            "activated composite/loop slots must be lowered inside an activated parent graph",
            f"program.slots.{parent.id}.activation",
        ))
    return diagnostics


class StructuredCompiler:
    """Expand composites and bounded loops, then validate the resulting plain DAG."""

    def __init__(self, compiler: Compiler | None = None) -> None:
        self.compiler = compiler or Compiler()

    def lower(
        self,
        program: ProgramGraph,
        catalog: SubgraphCatalog,
        *,
        loop_policies: tuple[LoopPolicy, ...] = (),
    ) -> LoweredProgram:
        problems = catalog.validate()
        if problems:
            raise ValueError("invalid subgraph catalog: " + "; ".join(problems))
        source_diagnostics = self.compiler.validate_program(program)
        if source_diagnostics:
            raise ValidationError("cannot lower an invalid program", source_diagnostics)
        policy_map = {policy.slot_id: policy for policy in loop_policies}
        if len(policy_map) != len(loop_policies):
            raise ValueError("loop policies must name unique slots")
        policy_problems = [
            problem
            for policy in loop_policies
            for problem in policy.validate()
        ]
        if policy_problems:
            raise ValueError("invalid loop policies: " + "; ".join(policy_problems))

        current = program
        expansions: list[ExpansionRecord] = []
        while True:
            structured = next(
                (
                    slot
                    for slot in current.slots
                    if slot.kind in (SlotKind.COMPOSITE, SlotKind.LOOP)
                ),
                None,
            )
            if structured is None:
                break
            child = catalog.resolve(structured.subgraph_ref)
            boundary = _validate_boundary(structured, child)
            if boundary:
                raise ValidationError("invalid structured slot boundary", boundary)
            if structured.kind == SlotKind.COMPOSITE:
                current, record = self._expand_composite(current, structured, child)
            else:
                try:
                    policy = policy_map[structured.id]
                except KeyError as exc:
                    raise ValueError(
                        f"loop slot {structured.id} requires an explicit LoopPolicy"
                    ) from exc
                current, record = self._expand_loop(current, structured, child, policy)
            expansions.append(record)

        unused = sorted(set(policy_map) - {item.slot_id for item in expansions})
        if unused:
            raise ValueError("loop policies reference non-loop slots: " + ", ".join(unused))
        lowered_diagnostics = self.compiler.validate_program(current)
        if lowered_diagnostics:
            raise ValidationError("structured lowering produced an invalid DAG", lowered_diagnostics)
        receipt = LoweringReceipt(
            source_program_digest=program.digest,
            lowered_program_digest=current.digest,
            catalog_digest=catalog.digest,
            expansions=tuple(expansions),
        )
        return LoweredProgram(current, receipt)

    @staticmethod
    def _expand_composite(
        program: ProgramGraph,
        parent: SemanticSlot,
        child: ProgramGraph,
    ) -> tuple[ProgramGraph, ExpansionRecord]:
        prefix = parent.id
        child_inputs = _graph_inputs(child)
        child_outputs = _graph_outputs(child)
        expanded_slots = tuple(
            _namespaced_slot(slot, prefix, parent.group + (parent.id,))
            for slot in child.slots
        )
        internal_edges = tuple(_namespaced_edge(edge, prefix) for edge in child.edges)

        edges: list[Edge] = list(internal_edges)
        for edge in program.edges:
            if edge.target_slot == parent.id:
                target = child_inputs[edge.target_port]
                edges.append(Edge(
                    edge.source_slot,
                    edge.source_port,
                    f"{prefix}/{target.target_slot}",
                    target.target_port,
                ))
            elif edge.source_slot == parent.id:
                source = child_outputs[edge.source_port]
                edges.append(Edge(
                    f"{prefix}/{source.source_slot}",
                    source.source_port,
                    edge.target_slot,
                    edge.target_port,
                ))
            else:
                edges.append(edge)

        inputs = tuple(
            GraphInput(
                item.name,
                item.value_type,
                (
                    f"{prefix}/{child_inputs[item.target_port].target_slot}"
                    if item.target_slot == parent.id
                    else item.target_slot
                ),
                (
                    child_inputs[item.target_port].target_port
                    if item.target_slot == parent.id
                    else item.target_port
                ),
            )
            for item in program.inputs
        )
        outputs = tuple(
            GraphOutput(
                item.name,
                item.value_type,
                (
                    f"{prefix}/{child_outputs[item.source_port].source_slot}"
                    if item.source_slot == parent.id
                    else item.source_slot
                ),
                (
                    child_outputs[item.source_port].source_port
                    if item.source_slot == parent.id
                    else item.source_port
                ),
            )
            for item in program.outputs
        )
        slots: list[SemanticSlot] = []
        for slot in program.slots:
            slots.extend(expanded_slots if slot.id == parent.id else (slot,))
        lowered = replace(
            program,
            slots=tuple(slots),
            edges=tuple(edges),
            inputs=inputs,
            outputs=outputs,
        )
        return lowered, ExpansionRecord(
            slot_id=parent.id,
            kind=parent.kind.value,
            subgraph_id=child.id,
            subgraph_digest=child.digest,
            expanded_slot_ids=tuple(slot.id for slot in expanded_slots),
        )

    @staticmethod
    def _expand_loop(
        program: ProgramGraph,
        parent: SemanticSlot,
        child: ProgramGraph,
        policy: LoopPolicy,
    ) -> tuple[ProgramGraph, ExpansionRecord]:
        child_inputs = _graph_inputs(child)
        child_outputs = _graph_outputs(child)
        feedback = dict(policy.feedback)
        diagnostics: list[Diagnostic] = []
        for output_name, input_name in policy.feedback:
            output = child_outputs.get(output_name)
            input_ = child_inputs.get(input_name)
            if output is None or input_ is None:
                diagnostics.append(Diagnostic(
                    "UNG-LOOP-001",
                    f"unknown feedback mapping {output_name} -> {input_name}",
                    f"program.slots.{parent.id}",
                ))
            elif not output.value_type.is_assignable_to(input_.value_type):
                diagnostics.append(Diagnostic(
                    "UNG-LOOP-002",
                    f"feedback mapping {output_name} -> {input_name} is not type compatible",
                    f"program.slots.{parent.id}",
                ))
        if diagnostics:
            raise ValidationError("invalid bounded loop feedback", diagnostics)

        prefixes = tuple(
            f"{parent.id}/iteration-{index}"
            for index in range(1, policy.max_iterations + 1)
        )
        expanded_slots = tuple(
            _namespaced_slot(
                slot,
                prefix,
                parent.group + (parent.id, f"iteration-{index}"),
            )
            for index, prefix in enumerate(prefixes, start=1)
            for slot in child.slots
        )
        edges: list[Edge] = [
            _namespaced_edge(edge, prefix)
            for prefix in prefixes
            for edge in child.edges
        ]

        def iteration_target(prefix: str, port_name: str) -> tuple[str, str]:
            target = child_inputs[port_name]
            return f"{prefix}/{target.target_slot}", target.target_port

        def iteration_source(prefix: str, port_name: str) -> tuple[str, str]:
            source = child_outputs[port_name]
            return f"{prefix}/{source.source_slot}", source.source_port

        feedback_inputs = set(feedback.values())
        if feedback_inputs != set(child_inputs):
            raise ValidationError(
                "bounded loop bodies require explicit feedback for every input",
                (Diagnostic(
                    "UNG-LOOP-003",
                    "every child graph input must be fed by one child graph output; "
                    "carry loop-invariant values inside the explicit state envelope",
                    f"program.slots.{parent.id}",
                ),),
            )
        for edge in program.edges:
            if edge.target_slot == parent.id:
                target_prefixes = (
                    prefixes[:1]
                    if edge.target_port in feedback_inputs
                    else prefixes
                )
                for prefix in target_prefixes:
                    target_slot, target_port = iteration_target(prefix, edge.target_port)
                    edges.append(Edge(
                        edge.source_slot, edge.source_port, target_slot, target_port
                    ))
            elif edge.source_slot == parent.id:
                source_slot, source_port = iteration_source(
                    prefixes[-1], edge.source_port
                )
                edges.append(Edge(
                    source_slot, source_port, edge.target_slot, edge.target_port
                ))
            else:
                edges.append(edge)

        for previous, current in zip(prefixes, prefixes[1:], strict=False):
            for output_name, input_name in policy.feedback:
                source_slot, source_port = iteration_source(previous, output_name)
                target_slot, target_port = iteration_target(current, input_name)
                edges.append(Edge(source_slot, source_port, target_slot, target_port))

        inputs: list[GraphInput] = []
        for item in program.inputs:
            if item.target_slot != parent.id:
                inputs.append(item)
                continue
            target_prefixes = (
                prefixes[:1] if item.target_port in feedback_inputs else prefixes
            )
            for index, prefix in enumerate(target_prefixes, start=1):
                target_slot, target_port = iteration_target(prefix, item.target_port)
                name = item.name if len(target_prefixes) == 1 else f"{item.name}_iteration_{index}"
                inputs.append(GraphInput(name, item.value_type, target_slot, target_port))

        outputs = tuple(
            GraphOutput(
                item.name,
                item.value_type,
                *iteration_source(prefixes[-1], item.source_port),
            )
            if item.source_slot == parent.id
            else item
            for item in program.outputs
        )
        slots: list[SemanticSlot] = []
        for slot in program.slots:
            slots.extend(expanded_slots if slot.id == parent.id else (slot,))
        lowered = replace(
            program,
            slots=tuple(slots),
            edges=tuple(edges),
            inputs=tuple(inputs),
            outputs=outputs,
        )
        return lowered, ExpansionRecord(
            slot_id=parent.id,
            kind=parent.kind.value,
            subgraph_id=child.id,
            subgraph_digest=child.digest,
            expanded_slot_ids=tuple(slot.id for slot in expanded_slots),
            iterations=policy.max_iterations,
        )


__all__ = [
    "ExpansionRecord",
    "LoopPolicy",
    "LoweredProgram",
    "LoweringReceipt",
    "STRUCTURED_MODEL_VERSION",
    "StructuredCompiler",
    "SubgraphCatalog",
]
