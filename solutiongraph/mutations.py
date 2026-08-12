"""Typed, compiler-gated construction of explicit topology variants.

Mutation is an authoring operation.  It never edits a running graph or grants a
new node admission.  Every operation returns a complete :class:`ProgramGraph`,
preserves the parent's external interface, and is validated by the ordinary
compiler before it can enter a :class:`TopologyFamily`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from math import isfinite
from typing import Any, ClassVar, Protocol

from solutiongraph.compiler import Compiler
from solutiongraph.model import (
    DIGEST_RE,
    ID_RE,
    Edge,
    GraphInput,
    GraphOutput,
    ProgramGraph,
    SemanticSlot,
    canonical_json,
    sha256_digest,
)
from solutiongraph.topology import TopologyFamily, TopologyVariant

MUTATION_MODEL_VERSION = "0.1"


def _external_interface(program: ProgramGraph) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    return (
        tuple(sorted((item.name, item.value_type.to_dict()) for item in program.inputs)),
        tuple(sorted((item.name, item.value_type.to_dict()) for item in program.outputs)),
    )


def _slot_index(program: ProgramGraph, slot_id: str) -> int:
    try:
        return next(index for index, slot in enumerate(program.slots) if slot.id == slot_id)
    except StopIteration as exc:
        raise ValueError(f"unknown semantic slot {slot_id!r}") from exc


def _require_new_slot(program: ProgramGraph, slot: SemanticSlot) -> None:
    if slot.id in {item.id for item in program.slots}:
        raise ValueError(f"mutation slot {slot.id!r} already exists")
    problems = slot.validate("mutation.slot")
    if problems:
        raise ValueError("invalid mutation slot: " + "; ".join(problems))


class MutationOperation(Protocol):
    """Extension seam for deterministic, serialisable graph rewrites."""

    operator_id: ClassVar[str]

    def apply(self, program: ProgramGraph) -> ProgramGraph: ...

    def parameters(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class InsertSlotOnEdge:
    """Split one exact internal edge with a new semantic obligation."""

    operator_id: ClassVar[str] = "operator.insert-slot-on-edge"

    slot: SemanticSlot
    source_slot: str
    source_port: str
    target_slot: str
    target_port: str
    inserted_input_port: str
    inserted_output_port: str

    def apply(self, program: ProgramGraph) -> ProgramGraph:
        _require_new_slot(program, self.slot)
        selected = Edge(
            self.source_slot,
            self.source_port,
            self.target_slot,
            self.target_port,
        )
        if selected not in program.edges:
            raise ValueError("insert-on-edge mutation references an edge that does not exist")
        if self.slot.port("input", self.inserted_input_port) is None:
            raise ValueError("inserted_input_port is not an input on the new slot")
        if self.slot.port("output", self.inserted_output_port) is None:
            raise ValueError("inserted_output_port is not an output on the new slot")
        target_index = _slot_index(program, self.target_slot)
        slots = (
            *program.slots[:target_index],
            self.slot,
            *program.slots[target_index:],
        )
        edges = tuple(edge for edge in program.edges if edge != selected) + (
            Edge(
                self.source_slot,
                self.source_port,
                self.slot.id,
                self.inserted_input_port,
            ),
            Edge(
                self.slot.id,
                self.inserted_output_port,
                self.target_slot,
                self.target_port,
            ),
        )
        return replace(program, slots=slots, edges=edges)

    def parameters(self) -> Mapping[str, Any]:
        return {
            "slot": self.slot.to_dict(),
            "source_slot": self.source_slot,
            "source_port": self.source_port,
            "target_slot": self.target_slot,
            "target_port": self.target_port,
            "inserted_input_port": self.inserted_input_port,
            "inserted_output_port": self.inserted_output_port,
        }


@dataclass(frozen=True)
class InsertSlotAfterInput:
    """Insert a slot after one graph input without changing that public input."""

    operator_id: ClassVar[str] = "operator.insert-slot-after-input"

    slot: SemanticSlot
    graph_input_name: str
    inserted_input_port: str
    inserted_output_port: str

    def apply(self, program: ProgramGraph) -> ProgramGraph:
        _require_new_slot(program, self.slot)
        matches = tuple(item for item in program.inputs if item.name == self.graph_input_name)
        if len(matches) != 1:
            raise ValueError("insert-after-input requires one exact graph input")
        original = matches[0]
        if self.slot.port("input", self.inserted_input_port) is None:
            raise ValueError("inserted_input_port is not an input on the new slot")
        if self.slot.port("output", self.inserted_output_port) is None:
            raise ValueError("inserted_output_port is not an output on the new slot")
        target_index = _slot_index(program, original.target_slot)
        inputs = tuple(
            GraphInput(
                item.name,
                item.value_type,
                self.slot.id,
                self.inserted_input_port,
            )
            if item == original
            else item
            for item in program.inputs
        )
        return replace(
            program,
            slots=(
                *program.slots[:target_index],
                self.slot,
                *program.slots[target_index:],
            ),
            inputs=inputs,
            edges=(
                *program.edges,
                Edge(
                    self.slot.id,
                    self.inserted_output_port,
                    original.target_slot,
                    original.target_port,
                ),
            ),
        )

    def parameters(self) -> Mapping[str, Any]:
        return {
            "slot": self.slot.to_dict(),
            "graph_input_name": self.graph_input_name,
            "inserted_input_port": self.inserted_input_port,
            "inserted_output_port": self.inserted_output_port,
        }


@dataclass(frozen=True)
class InsertSlotBeforeOutput:
    """Insert a slot before one graph output while preserving its public contract."""

    operator_id: ClassVar[str] = "operator.insert-slot-before-output"

    slot: SemanticSlot
    graph_output_name: str
    inserted_input_port: str
    inserted_output_port: str

    def apply(self, program: ProgramGraph) -> ProgramGraph:
        _require_new_slot(program, self.slot)
        matches = tuple(item for item in program.outputs if item.name == self.graph_output_name)
        if len(matches) != 1:
            raise ValueError("insert-before-output requires one exact graph output")
        original = matches[0]
        if self.slot.port("input", self.inserted_input_port) is None:
            raise ValueError("inserted_input_port is not an input on the new slot")
        if self.slot.port("output", self.inserted_output_port) is None:
            raise ValueError("inserted_output_port is not an output on the new slot")
        source_index = _slot_index(program, original.source_slot)
        outputs = tuple(
            GraphOutput(
                item.name,
                item.value_type,
                self.slot.id,
                self.inserted_output_port,
            )
            if item == original
            else item
            for item in program.outputs
        )
        return replace(
            program,
            slots=(
                *program.slots[: source_index + 1],
                self.slot,
                *program.slots[source_index + 1 :],
            ),
            outputs=outputs,
            edges=(
                *program.edges,
                Edge(
                    original.source_slot,
                    original.source_port,
                    self.slot.id,
                    self.inserted_input_port,
                ),
            ),
        )

    def parameters(self) -> Mapping[str, Any]:
        return {
            "slot": self.slot.to_dict(),
            "graph_output_name": self.graph_output_name,
            "inserted_input_port": self.inserted_input_port,
            "inserted_output_port": self.inserted_output_port,
        }


@dataclass(frozen=True)
class RemoveLinearSlot:
    """Remove one strictly internal one-input/one-output pass-through position.

    This operator does not assert that removal is a good idea.  It only limits
    the rewrite to an unambiguous internal shape; the complete child is still
    compiler-validated and must later pass the unchanged task oracle.
    """

    operator_id: ClassVar[str] = "operator.remove-linear-slot"

    slot_id: str

    def apply(self, program: ProgramGraph) -> ProgramGraph:
        index = _slot_index(program, self.slot_id)
        slot = program.slots[index]
        incoming = tuple(edge for edge in program.edges if edge.target_slot == self.slot_id)
        outgoing = tuple(edge for edge in program.edges if edge.source_slot == self.slot_id)
        if len(slot.inputs) != 1 or len(slot.outputs) != 1:
            raise ValueError("remove-linear-slot requires exactly one declared input and output")
        if len(incoming) != 1 or len(outgoing) != 1:
            raise ValueError("remove-linear-slot requires exactly one incoming and outgoing edge")
        if any(item.target_slot == self.slot_id for item in program.inputs):
            raise ValueError("remove-linear-slot cannot remove a graph-input boundary")
        if any(item.source_slot == self.slot_id for item in program.outputs):
            raise ValueError("remove-linear-slot cannot remove a graph-output boundary")
        if any(item.activation_slot == self.slot_id for item in program.slots):
            raise ValueError("remove-linear-slot cannot remove an activation source")
        before, after = incoming[0], outgoing[0]
        bridge = Edge(
            before.source_slot,
            before.source_port,
            after.target_slot,
            after.target_port,
        )
        edges = tuple(
            edge for edge in program.edges if edge not in (before, after)
        ) + (bridge,)
        return replace(
            program,
            slots=(*program.slots[:index], *program.slots[index + 1 :]),
            edges=edges,
        )

    def parameters(self) -> Mapping[str, Any]:
        return {"slot_id": self.slot_id}


@dataclass(frozen=True)
class ReplaceSlotContract:
    """Replace one obligation while retaining its exact wiring interface."""

    operator_id: ClassVar[str] = "operator.replace-slot-contract"

    replacement: SemanticSlot

    def apply(self, program: ProgramGraph) -> ProgramGraph:
        index = _slot_index(program, self.replacement.id)
        original = program.slots[index]
        if tuple(port.to_dict() for port in original.inputs) != tuple(
            port.to_dict() for port in self.replacement.inputs
        ):
            raise ValueError("replacement slot must preserve every exact input port contract")
        if tuple(port.to_dict() for port in original.outputs) != tuple(
            port.to_dict() for port in self.replacement.outputs
        ):
            raise ValueError("replacement slot must preserve every exact output port contract")
        problems = self.replacement.validate("mutation.replacement")
        if problems:
            raise ValueError("invalid replacement slot: " + "; ".join(problems))
        if self.replacement.to_dict() == original.to_dict():
            raise ValueError("replacement slot must be content-distinct")
        return replace(
            program,
            slots=(
                *program.slots[:index],
                self.replacement,
                *program.slots[index + 1 :],
            ),
        )

    def parameters(self) -> Mapping[str, Any]:
        return {"replacement": self.replacement.to_dict()}


MUTATION_OPERATOR_IDS = (
    InsertSlotOnEdge.operator_id,
    InsertSlotAfterInput.operator_id,
    InsertSlotBeforeOutput.operator_id,
    RemoveLinearSlot.operator_id,
    ReplaceSlotContract.operator_id,
)


@dataclass(frozen=True)
class MutationContext:
    """Identity, hypothesis, and ancestry for a proposed child variant."""

    child_variant_id: str
    child_title: str
    child_program_id: str
    child_program_version: str
    rationale: str
    hypothesis: str
    proposer_id: str
    prior_log_weight: float = 0.0
    tags: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("child_variant_id", self.child_variant_id),
            ("child_program_id", self.child_program_id),
            ("proposer_id", self.proposer_id),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{label} must be a namespaced identifier")
        for label, value in (
            ("child_title", self.child_title),
            ("child_program_version", self.child_program_version),
            ("rationale", self.rationale),
            ("hypothesis", self.hypothesis),
        ):
            if not value.strip():
                problems.append(f"{label} must not be empty")
        if not isfinite(self.prior_log_weight):
            problems.append("prior_log_weight must be finite")
        if len(self.tags) != len(set(self.tags)) or any(
            not ID_RE.fullmatch(tag) for tag in self.tags
        ):
            problems.append("tags must contain unique namespaced identifiers")
        return problems


@dataclass(frozen=True)
class MutationReceipt:
    """Immutable authoring evidence for one deterministic topology rewrite."""

    operator_id: str
    parent_variant_id: str
    child_variant_id: str
    parent_program_digest: str
    child_program_digest: str
    hypothesis: str
    proposer_id: str
    parameters: Mapping[str, Any]
    external_interface_preserved: bool

    @property
    def id(self) -> str:
        suffix = sha256_digest(self._identity_payload()).removeprefix("sha256:")[:24]
        return f"mutation.{suffix}"

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "parent_variant_id": self.parent_variant_id,
            "child_variant_id": self.child_variant_id,
            "parent_program_digest": self.parent_program_digest,
            "child_program_digest": self.child_program_digest,
            "hypothesis": self.hypothesis,
            "proposer_id": self.proposer_id,
            "parameters": self.parameters,
            "external_interface_preserved": self.external_interface_preserved,
        }

    def validate(self) -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("operator_id", self.operator_id),
            ("parent_variant_id", self.parent_variant_id),
            ("child_variant_id", self.child_variant_id),
            ("proposer_id", self.proposer_id),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{label} must be a namespaced identifier")
        if self.parent_variant_id == self.child_variant_id:
            problems.append("mutation parent and child variant ids must differ")
        for label, digest in (
            ("parent_program_digest", self.parent_program_digest),
            ("child_program_digest", self.child_program_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{label} must be a sha256 digest")
        if self.parent_program_digest == self.child_program_digest:
            problems.append("mutation parent and child programs must be content-distinct")
        if not self.hypothesis.strip():
            problems.append("mutation hypothesis must not be empty")
        try:
            canonical_json(self.parameters)
        except (TypeError, ValueError):
            problems.append("mutation parameters must be JSON serialisable")
        if not self.external_interface_preserved:
            problems.append("mutation must preserve the external graph interface")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_model_version": MUTATION_MODEL_VERSION,
            "id": self.id,
            **self._identity_payload(),
        }


@dataclass(frozen=True)
class MutationResult:
    variant: TopologyVariant
    receipt: MutationReceipt

    def validate(self) -> list[str]:
        problems = list(self.variant.validate())
        problems.extend(self.receipt.validate())
        if self.variant.id != self.receipt.child_variant_id:
            problems.append("mutation receipt child does not match the produced variant")
        if self.variant.program.digest != self.receipt.child_program_digest:
            problems.append("mutation receipt program digest does not match the produced variant")
        return problems


class GraphMutationEngine:
    """Apply typed operations and quarantine each child behind compiler validation."""

    def __init__(self, compiler: Compiler | None = None) -> None:
        self.compiler = compiler or Compiler()

    def apply(
        self,
        parent: TopologyVariant,
        operation: MutationOperation,
        context: MutationContext,
    ) -> MutationResult:
        problems = (*parent.validate(), *context.validate())
        if problems:
            raise ValueError("invalid graph mutation input: " + "; ".join(problems))
        if not ID_RE.fullmatch(operation.operator_id):
            raise ValueError("mutation operator_id must be namespaced")
        try:
            canonical_json(operation.parameters())
        except (TypeError, ValueError) as exc:
            raise ValueError("mutation operation parameters must be JSON serialisable") from exc

        child_program = operation.apply(parent.program)
        child_program = replace(
            child_program,
            id=context.child_program_id,
            version=context.child_program_version,
        )
        diagnostics = self.compiler.validate_program(child_program)
        if diagnostics:
            details = "; ".join(
                f"{item.code}: {item.message} ({item.path})" for item in diagnostics
            )
            raise ValueError("mutated graph is compiler-invalid: " + details)
        interface_preserved = _external_interface(parent.program) == _external_interface(
            child_program
        )
        if not interface_preserved:
            raise ValueError("mutated graph changed the parent's external interface")
        if child_program.digest == parent.program.digest:
            raise ValueError("mutation must produce a content-distinct program")

        variant = TopologyVariant(
            id=context.child_variant_id,
            title=context.child_title,
            program=child_program,
            rationale=context.rationale,
            prior_log_weight=context.prior_log_weight,
            parent_variant_id=parent.id,
            operators=(operation.operator_id,),
            tags=context.tags,
        )
        receipt = MutationReceipt(
            operation.operator_id,
            parent.id,
            variant.id,
            parent.program.digest,
            child_program.digest,
            context.hypothesis,
            context.proposer_id,
            dict(operation.parameters()),
            interface_preserved,
        )
        result = MutationResult(variant, receipt)
        result_problems = result.validate()
        if result_problems:
            raise ValueError("invalid graph mutation result: " + "; ".join(result_problems))
        return result

    @staticmethod
    def family(
        *,
        family_id: str,
        version: str,
        parent: TopologyVariant,
        mutations: tuple[MutationResult, ...],
    ) -> TopologyFamily:
        family = TopologyFamily(
            family_id,
            version,
            parent.program.task,
            parent.program.success_contract,
            (parent, *(result.variant for result in mutations)),
        )
        problems = family.validate()
        if problems:
            raise ValueError("invalid mutation topology family: " + "; ".join(problems))
        return family


__all__ = [
    "MUTATION_MODEL_VERSION",
    "MUTATION_OPERATOR_IDS",
    "GraphMutationEngine",
    "InsertSlotAfterInput",
    "InsertSlotBeforeOutput",
    "InsertSlotOnEdge",
    "MutationContext",
    "MutationOperation",
    "MutationReceipt",
    "MutationResult",
    "RemoveLinearSlot",
    "ReplaceSlotContract",
]
