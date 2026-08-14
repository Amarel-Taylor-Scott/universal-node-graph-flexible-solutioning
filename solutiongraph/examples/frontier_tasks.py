"""Dependency-free fixtures for frontier modalities and simulated systems.

The fixtures exercise strict typed graphs, interchangeable candidates, frozen
routes, and independent verification.  They are mechanism evidence only: no
fixture is a production security investigation, media codec, game engine,
robot controller, device fleet, or validated physical digital twin.
"""

from __future__ import annotations

import math
from collections import Counter
from copy import deepcopy
from typing import Any

from solutiongraph.evidence import Objective
from solutiongraph.examples.tasks import ExampleRoute, ExecutableExample
from solutiongraph.executor import (
    CallableVerifier,
    ExecutionPolicy,
    VerificationContext,
    VerificationResult,
    callable_implementation_digest,
)
from solutiongraph.experiments import ExperimentCase
from solutiongraph.model import (
    Candidate,
    Edge,
    GraphInput,
    GraphOutput,
    Idempotency,
    NodeSpec,
    ParameterSpec,
    Port,
    ProgramGraph,
    Registry,
    SemanticSlot,
    ValueType,
    sha256_digest,
)

FRONTIER_PAYLOAD = ValueType("example.frontier-workflow-payload")


def _state(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    result = deepcopy(payload)
    state = result.setdefault("state", {})
    result.setdefault("completed", [])
    result.setdefault("warnings", [])
    return result, state


def _apply_cyber(result: dict[str, Any], state: dict[str, Any], operation: str) -> None:
    raw = result["raw"]
    if operation == "scope":
        authority = raw["authorization"]
        systems = set(authority["systems"])
        state["authorized"] = (
            authority["purpose"] == "defensive"
            and bool(authority.get("approved_by"))
            and all(event["system"] in systems for event in raw["events"])
        )
        state["scope"] = sorted(systems)
    elif operation == "normalize":
        seen: set[str] = set()
        events = []
        for event in sorted(raw["events"], key=lambda item: (item["ts"], item["id"])):
            if event["id"] in seen:
                continue
            seen.add(event["id"])
            events.append({**event, "kind": event["kind"].lower()})
        state["events"] = events
        state["event_ids"] = [event["id"] for event in events]
    elif operation == "correlate":
        kinds = Counter(event["kind"] for event in state["events"])
        suspicious = (
            kinds["auth.failure"] >= 2 and kinds["auth.success"] >= 1 and kinds["data.read"] >= 1
        )
        state["correlation"] = {
            "suspicious": suspicious,
            "evidence_ids": list(state["event_ids"]),
            "actor": state["events"][0]["actor"],
        }
    elif operation == "test-hypotheses":
        evidence = state["correlation"]
        state["hypotheses"] = {
            "credential-compromise": "supported" if evidence["suspicious"] else "unsupported",
            "routine-batch-job": "contradicted" if evidence["suspicious"] else "unresolved",
            "remaining_uncertainty": "fixture lacks endpoint process telemetry",
        }
    elif operation == "report":
        supported = state["hypotheses"]["credential-compromise"] == "supported"
        state["report"] = {
            "severity": "high" if supported else "informational",
            "finding": "possible credential compromise" if supported else "no supported finding",
            "evidence_ids": list(state["correlation"]["evidence_ids"]),
            "proposed_actions": ["revoke session", "rotate scoped credential"] if supported else [],
            "effects_executed": [],
            "claim_boundary": "defensive synthetic telemetry fixture",
        }


def _apply_video(result: dict[str, Any], state: dict[str, Any], operation: str) -> None:
    raw = result["raw"]
    if operation == "probe":
        video = raw["video"]
        state["probe"] = {
            "frame_count": len(video["pts"]),
            "fps": float(video["fps"]),
            "video_duration": len(video["pts"]) / float(video["fps"]),
            "audio_duration": float(raw["audio"]["duration"]),
            "codec": video["codec"],
        }
    elif operation == "timeline":
        points = [float(value) for value in raw["video"]["pts"]]
        expected_step = 1.0 / state["probe"]["fps"]
        gaps = [right - left for left, right in zip(points, points[1:], strict=False)]
        state["timeline"] = {
            "monotonic": all(right > left for left, right in zip(points, points[1:], strict=False)),
            "dropped_intervals": sum(abs(gap - expected_step) > 1e-9 for gap in gaps),
            "time_base": "seconds",
        }
    elif operation == "align":
        state["alignment"] = {
            "av_sync_error_ms": abs(
                state["probe"]["video_duration"] - state["probe"]["audio_duration"]
            )
            * 1000.0,
            "caption_track_count": len(raw["captions"]),
        }
    elif operation == "captions":
        captions = raw["captions"]
        duration = state["probe"]["video_duration"]
        state["caption_assurance"] = {
            "valid_timing": all(
                0 <= float(item["start"]) < float(item["end"]) <= duration for item in captions
            ),
            "nonempty": all(str(item["text"]).strip() for item in captions),
            "coverage": sum(float(item["end"]) - float(item["start"]) for item in captions)
            / duration,
        }
    elif operation == "assure":
        state["report"] = {
            "integrity": state["timeline"]["monotonic"]
            and state["timeline"]["dropped_intervals"] == 0,
            "sync_ok": state["alignment"]["av_sync_error_ms"] <= 1.0,
            "captions_ok": state["caption_assurance"]["valid_timing"]
            and state["caption_assurance"]["nonempty"]
            and state["caption_assurance"]["coverage"] >= 0.99,
            "claim_boundary": "metadata and timeline fixture; no codec quality claim",
        }


def _mesh_edges(face: list[int]) -> tuple[tuple[int, int], ...]:
    return tuple(
        tuple(sorted((face[index], face[(index + 1) % len(face)]))) for index in range(len(face))
    )


def _apply_three_d(result: dict[str, Any], state: dict[str, Any], operation: str) -> None:
    raw = result["raw"]
    mesh = raw["mesh"]
    if operation == "parse":
        state["geometry"] = {
            "vertex_count": len(mesh["vertices"]),
            "face_count": len(mesh["faces"]),
            "units": mesh["units"],
            "handedness": mesh["handedness"],
        }
    elif operation == "topology":
        edge_counts: Counter[tuple[int, int]] = Counter()
        degenerate = 0
        for face in mesh["faces"]:
            if len(set(face)) != len(face):
                degenerate += 1
            edge_counts.update(_mesh_edges(face))
        state["topology"] = {
            "degenerate_faces": degenerate,
            "non_manifold_edges": sum(count != 2 for count in edge_counts.values()),
            "closed_manifold": bool(edge_counts)
            and all(count == 2 for count in edge_counts.values()),
        }
    elif operation == "materials":
        known = set(raw["materials"])
        assigned = mesh["face_materials"]
        state["materials"] = {
            "all_faces_assigned": len(assigned) == len(mesh["faces"]),
            "references_valid": all(item in known for item in assigned),
        }
    elif operation == "collision":
        coordinates = list(zip(*mesh["vertices"], strict=True))
        bounds = [[min(axis), max(axis)] for axis in coordinates]
        state["collision"] = {
            "computed_bounds": bounds,
            "matches_declared": bounds == raw["collision"]["bounds"],
            "layer": raw["collision"]["layer"],
        }
    elif operation == "budget":
        geometry = state["geometry"]
        state["report"] = {
            "geometry_ok": state["topology"]["closed_manifold"]
            and state["topology"]["degenerate_faces"] == 0,
            "materials_ok": all(state["materials"].values()),
            "collision_ok": state["collision"]["matches_declared"],
            "triangle_budget_ok": geometry["face_count"] <= raw["budgets"]["max_triangles"],
            "asset_digest": sha256_digest(mesh),
            "claim_boundary": "synthetic mesh contract; no engine render or physics claim",
        }


def _apply_game(result: dict[str, Any], state: dict[str, Any], operation: str) -> None:
    raw = result["raw"]
    if operation == "rules":
        rules = raw["rules"]
        state["rules"] = {
            "start": int(rules["start"]),
            "goal": int(rules["goal"]),
            "allowed_actions": sorted(rules["allowed_actions"]),
            "valid": rules["goal"] > rules["start"] and "move" in rules["allowed_actions"],
        }
    elif operation == "replay":
        position = state["rules"]["start"]
        score = 0
        hashes = []
        for action in raw["replay"]:
            if action not in state["rules"]["allowed_actions"]:
                raise ValueError(f"unknown fixture action {action!r}")
            if action == "move":
                position += 1
            elif action == "collect":
                score += 10
            hashes.append(sha256_digest({"position": position, "score": score}))
        state["replay"] = {
            "position": position,
            "score": score,
            "state_hashes": hashes,
            "won": position >= state["rules"]["goal"],
        }
    elif operation == "regression":
        observed = {key: state["replay"][key] for key in ("position", "score", "won")}
        state["regression"] = {
            "matches_expected": observed == raw["expected_final"],
            "observed": observed,
        }
    elif operation == "balance":
        outcomes = raw["match_outcomes"]
        wins = Counter(outcomes)
        total = len(outcomes)
        state["balance"] = {
            "win_rates": {player: count / total for player, count in sorted(wins.items())},
            "max_rate_gap": (max(wins.values()) - min(wins.values())) / total,
            "sample_size": total,
        }
    elif operation == "gate":
        state["report"] = {
            "rules_ok": state["rules"]["valid"],
            "deterministic_replay_ok": state["regression"]["matches_expected"],
            "balance_fixture_ok": state["balance"]["max_rate_gap"] <= 0.25,
            "human_fun_evidence": "not measured",
            "claim_boundary": "deterministic rules fixture; no engine, player-retention, or fun claim",
        }


def _apply_robotics(result: dict[str, Any], state: dict[str, Any], operation: str) -> None:
    raw = result["raw"]
    if operation == "model":
        robot = raw["robot"]
        state["model"] = {
            "limits_valid": robot["joint_min"] < robot["joint_max"],
            "max_step": float(robot["max_step"]),
            "frame": robot["frame"],
        }
    elif operation == "plan":
        path = [float(value) for value in raw["waypoints"]]
        state["plan"] = {
            "path": path,
            "start_matches": math.isclose(path[0], float(raw["start"])),
            "goal_matches": math.isclose(path[-1], float(raw["goal"])),
        }
    elif operation == "simulate":
        path = state["plan"]["path"]
        steps = [abs(right - left) for left, right in zip(path, path[1:], strict=False)]
        state["simulation"] = {
            "max_observed_step": max(steps, default=0.0),
            "within_actuator_limit": max(steps, default=0.0) <= state["model"]["max_step"],
            "final_state": path[-1],
        }
    elif operation == "safety":
        distances = [
            abs(position - float(obstacle))
            for position in state["plan"]["path"]
            for obstacle in raw["obstacles"]
        ]
        minimum = min(distances, default=math.inf)
        state["safety"] = {
            "minimum_distance": minimum,
            "threshold": float(raw["minimum_safe_distance"]),
            "safe": minimum >= float(raw["minimum_safe_distance"]),
        }
    elif operation == "gate":
        state["report"] = {
            "model_ok": state["model"]["limits_valid"],
            "plan_ok": state["plan"]["start_matches"] and state["plan"]["goal_matches"],
            "simulation_ok": state["simulation"]["within_actuator_limit"],
            "safety_ok": state["safety"]["safe"],
            "effects_executed": [],
            "claim_boundary": "one-dimensional simulation fixture; no physical control authority",
        }


def _apply_iot(result: dict[str, Any], state: dict[str, Any], operation: str) -> None:
    raw = result["raw"]
    if operation == "schema":
        required = {"id", "device_id", "ts", "temperature", "firmware"}
        state["schema"] = {
            "valid": all(required.issubset(event) for event in raw["events"]),
            "device_ids": sorted({event["device_id"] for event in raw["events"]}),
        }
    elif operation == "event-time":
        seen: set[str] = set()
        events = []
        for event in sorted(raw["events"], key=lambda item: (item["ts"], item["id"])):
            if event["id"] in seen:
                continue
            seen.add(event["id"])
            events.append(dict(event))
        state["events"] = events
        state["duplicate_count"] = len(raw["events"]) - len(events)
    elif operation == "anomalies":
        threshold = float(raw["temperature_limit"])
        state["anomalies"] = [
            event["id"] for event in state["events"] if float(event["temperature"]) > threshold
        ]
    elif operation == "state":
        latest: dict[str, dict[str, Any]] = {}
        for event in state["events"]:
            latest[event["device_id"]] = event
        state["device_state"] = {
            device: {
                "temperature": float(event["temperature"]),
                "firmware": event["firmware"],
                "event_id": event["id"],
            }
            for device, event in sorted(latest.items())
        }
    elif operation == "assure":
        state["report"] = {
            "schema_ok": state["schema"]["valid"],
            "deduped": state["duplicate_count"] == 1,
            "anomaly_count": len(state["anomalies"]),
            "fleet_size": len(state["device_state"]),
            "claim_boundary": "finite telemetry fixture; no authenticated device or fleet connector",
        }


def _fit_line(observations: list[dict[str, float]]) -> tuple[float, float]:
    xs = [float(item["input"]) for item in observations]
    ys = [float(item["observed"]) for item in observations]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((value - x_mean) ** 2 for value in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True)) / denominator
    return slope, y_mean - slope * x_mean


def _apply_digital_twin(result: dict[str, Any], state: dict[str, Any], operation: str) -> None:
    raw = result["raw"]
    if operation == "calibrate":
        slope, intercept = _fit_line(raw["calibration"])
        state["parameters"] = {"slope": slope, "intercept": intercept}
    elif operation == "simulate":
        parameters = state["parameters"]
        state["simulations"] = [
            {
                "input": float(item["input"]),
                "predicted": parameters["intercept"] + parameters["slope"] * float(item["input"]),
            }
            for item in raw["validation"]
        ]
    elif operation == "validate":
        residuals = [
            simulation["predicted"] - float(observation["observed"])
            for simulation, observation in zip(state["simulations"], raw["validation"], strict=True)
        ]
        state["validation"] = {
            "rmse": math.sqrt(sum(value * value for value in residuals) / len(residuals)),
            "residuals": residuals,
            "untouched_count": len(residuals),
        }
    elif operation == "sensitivity":
        base = state["parameters"]["slope"]
        target = float(raw["sensitivity_input"])
        outputs = [(base * factor) * target for factor in (0.9, 1.0, 1.1)]
        state["sensitivity"] = {
            "outputs": outputs,
            "range": max(outputs) - min(outputs),
        }
    elif operation == "report":
        state["report"] = {
            "calibration_ok": math.isclose(state["parameters"]["slope"], 2.0)
            and math.isclose(state["parameters"]["intercept"], 1.0),
            "validation_ok": state["validation"]["rmse"] < 1e-12,
            "sensitivity_recorded": state["sensitivity"]["range"] > 0,
            "claim_boundary": "linear synthetic fixture; no validated physical-system fidelity",
        }


def _apply_step(payload: dict[str, Any], domain: str, operation: str) -> dict[str, Any]:
    result, state = _state(payload)
    handlers = {
        "cyber": _apply_cyber,
        "video": _apply_video,
        "three-d": _apply_three_d,
        "game": _apply_game,
        "robotics": _apply_robotics,
        "iot": _apply_iot,
        "digital-twin": _apply_digital_twin,
    }
    try:
        handler = handlers[domain]
    except KeyError as exc:
        raise ValueError(f"unknown frontier domain {domain!r}") from exc
    handler(result, state, operation)
    result["completed"].append(operation)
    return result


def execute_reference_step(payload: dict[str, Any], domain: str, operation: str) -> dict[str, Any]:
    """Execute one deterministic reference operation."""
    return _apply_step(payload, domain, operation)


def execute_shortcut_step(payload: dict[str, Any], domain: str, operation: str) -> dict[str, Any]:
    """Execute the operation while disclosing missing assurance evidence."""
    result = _apply_step(payload, domain, operation)
    result["warnings"].append(f"{domain}.{operation}:shortcut-evidence")
    return result


DOMAIN_OPERATIONS = {
    "cyber": ("scope", "normalize", "correlate", "test-hypotheses", "report"),
    "video": ("probe", "timeline", "align", "captions", "assure"),
    "three-d": ("parse", "topology", "materials", "collision", "budget"),
    "game": ("rules", "replay", "regression", "balance", "gate"),
    "robotics": ("model", "plan", "simulate", "safety", "gate"),
    "iot": ("schema", "event-time", "anomalies", "state", "assure"),
    "digital-twin": ("calibrate", "simulate", "validate", "sensitivity", "report"),
}


def _node(domain: str, operation: str, strategy: str) -> NodeSpec:
    function = execute_reference_step if strategy == "reference" else execute_shortcut_step
    return NodeSpec(
        id=f"example.frontier.{domain}.{operation}.{strategy}",
        version="1.0.0",
        implementation_digest=callable_implementation_digest(function),
        inputs=(Port("payload", FRONTIER_PAYLOAD),),
        outputs=(Port("payload", FRONTIER_PAYLOAD),),
        runtime="python",
        entrypoint=f"{function.__module__}:{function.__name__}",
        description=f"{strategy.title()} mechanism fixture for {domain}/{operation}.",
        parameters=(
            ParameterSpec("domain", "string", required=True, choices=(domain,)),
            ParameterSpec("operation", "string", required=True, choices=(operation,)),
        ),
        capabilities=(f"frontier.{domain}.{operation}",),
        idempotency=Idempotency.IDEMPOTENT,
        source="solutiongraph/examples/frontier_tasks.py",
    )


FRONTIER_NODES = tuple(
    _node(domain, operation, strategy)
    for domain, operations in DOMAIN_OPERATIONS.items()
    for operation in operations
    for strategy in ("reference", "shortcut")
)
FRONTIER_CANDIDATES = tuple(
    Candidate(
        id=f"candidate.{node.id}",
        node_id=node.id,
        node_version=node.version,
        implementation_digest=node.implementation_digest,
        parameters={
            "domain": node.id.split(".")[2],
            "operation": node.id.split(".")[3],
        },
    )
    for node in FRONTIER_NODES
)
FRONTIER_REGISTRY = Registry(
    "example.frontier-domain-registry",
    "1.0.0",
    FRONTIER_NODES,
    FRONTIER_CANDIDATES,
)


def _program(domain: str, title: str) -> ProgramGraph:
    operations = DOMAIN_OPERATIONS[domain]
    slots = tuple(
        SemanticSlot(
            operation,
            f"Execute the {operation} obligation for the {domain} mechanism fixture.",
            (Port("payload", FRONTIER_PAYLOAD),),
            (Port("payload", FRONTIER_PAYLOAD),),
            f"The {operation} result is explicit, typed, and independently checkable.",
            group=(f"stage.{domain}",),
            required_capabilities=(f"frontier.{domain}.{operation}",),
        )
        for operation in operations
    )
    return ProgramGraph(
        f"example.frontier-{domain}",
        "1.0.0",
        title,
        "The independent fixture oracle accepts exact results and rejects shortcut-only evidence.",
        slots,
        tuple(
            Edge(left, "payload", right, "payload")
            for left, right in zip(operations, operations[1:], strict=False)
        ),
        (GraphInput("payload", FRONTIER_PAYLOAD, operations[0], "payload"),),
        (GraphOutput("result", FRONTIER_PAYLOAD, operations[-1], "payload"),),
    )


def _accepted_state(domain: str, state: dict[str, Any]) -> bool:
    report = state.get("report", {})
    if domain == "cyber":
        return (
            state.get("authorized") is True
            and report.get("severity") == "high"
            and len(report.get("evidence_ids", ())) == 4
            and report.get("effects_executed") == []
        )
    if domain == "video":
        return all(report.get(key) is True for key in ("integrity", "sync_ok", "captions_ok"))
    if domain == "three-d":
        return all(
            report.get(key) is True
            for key in ("geometry_ok", "materials_ok", "collision_ok", "triangle_budget_ok")
        )
    if domain == "game":
        return (
            all(
                report.get(key) is True
                for key in ("rules_ok", "deterministic_replay_ok", "balance_fixture_ok")
            )
            and report.get("human_fun_evidence") == "not measured"
        )
    if domain == "robotics":
        return (
            all(
                report.get(key) is True
                for key in ("model_ok", "plan_ok", "simulation_ok", "safety_ok")
            )
            and report.get("effects_executed") == []
        )
    if domain == "iot":
        return (
            report.get("schema_ok") is True
            and report.get("deduped") is True
            and report.get("anomaly_count") == 1
            and report.get("fleet_size") == 2
        )
    if domain == "digital-twin":
        return all(
            report.get(key) is True
            for key in ("calibration_ok", "validation_ok", "sensitivity_recorded")
        )
    return False


def verify_frontier(context: VerificationContext) -> VerificationResult:
    result = context.outputs["result"]
    domain = context.program.id.removeprefix("example.frontier-")
    accepted = (
        result.get("completed") == list(DOMAIN_OPERATIONS[domain])
        and not result.get("warnings")
        and _accepted_state(domain, result.get("state", {}))
    )
    return VerificationResult(
        accepted,
        "frontier-fixture-accepted" if accepted else "frontier-fixture-rejected",
        {"quality": 1.0 if accepted else 0.0},
        {
            "domain": domain,
            "completed": result.get("completed", []),
            "claim_boundary": result.get("state", {}).get("report", {}).get("claim_boundary", ""),
        },
    )


FIXTURES: dict[str, dict[str, Any]] = {
    "cyber": {
        "id": "defensive-cyber-investigation",
        "title": "Defensive cyber investigation fixture",
        "task": "Scope, correlate, test, and report a defensive telemetry hypothesis without executing containment.",
        "raw": {
            "authorization": {
                "purpose": "defensive",
                "systems": ["checkout-api"],
                "approved_by": "fixture.system-owner",
            },
            "events": [
                {
                    "id": "event.1",
                    "ts": 1,
                    "system": "checkout-api",
                    "actor": "svc-export",
                    "kind": "AUTH.FAILURE",
                },
                {
                    "id": "event.2",
                    "ts": 2,
                    "system": "checkout-api",
                    "actor": "svc-export",
                    "kind": "AUTH.FAILURE",
                },
                {
                    "id": "event.3",
                    "ts": 3,
                    "system": "checkout-api",
                    "actor": "svc-export",
                    "kind": "AUTH.SUCCESS",
                },
                {
                    "id": "event.4",
                    "ts": 4,
                    "system": "checkout-api",
                    "actor": "svc-export",
                    "kind": "DATA.READ",
                },
            ],
        },
    },
    "video": {
        "id": "video-media-assurance",
        "title": "Video timeline and caption assurance",
        "task": "Probe a bounded media fixture and independently verify timeline, A/V synchronization, and captions.",
        "raw": {
            "video": {"codec": "fixture.raw", "fps": 24, "pts": [0.0, 1 / 24, 2 / 24]},
            "audio": {"duration": 0.125},
            "captions": [{"start": 0.0, "end": 0.125, "text": "A short fixture."}],
        },
    },
    "three-d": {
        "id": "three-d-asset-assurance",
        "title": "3D mesh and asset assurance",
        "task": "Validate topology, materials, collision bounds, and budgets for a synthetic tetrahedron asset.",
        "raw": {
            "mesh": {
                "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "faces": [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]],
                "face_materials": ["mat.default"] * 4,
                "units": "meters",
                "handedness": "right",
            },
            "materials": {"mat.default": {"base_color": [1, 1, 1]}},
            "collision": {"bounds": [[0, 1], [0, 1], [0, 1]], "layer": "world"},
            "budgets": {"max_triangles": 8},
        },
    },
    "game": {
        "id": "gameplay-replay-and-balance",
        "title": "Gameplay replay and balance fixture",
        "task": "Replay deterministic game actions, compare state, inspect balance evidence, and apply a release gate.",
        "raw": {
            "rules": {"start": 0, "goal": 3, "allowed_actions": ["move", "collect"]},
            "replay": ["move", "collect", "move", "move"],
            "expected_final": {"position": 3, "score": 10, "won": True},
            "match_outcomes": ["player-a", "player-b", "player-a", "player-b"],
        },
    },
    "robotics": {
        "id": "robotics-safety-simulation",
        "title": "Robotics safety simulation fixture",
        "task": "Validate a bounded one-dimensional motion plan without granting physical execution authority.",
        "raw": {
            "robot": {"joint_min": -5, "joint_max": 5, "max_step": 1.0, "frame": "fixture.world"},
            "start": 0,
            "goal": 3,
            "waypoints": [0, 1, 2, 3],
            "obstacles": [10],
            "minimum_safe_distance": 2,
        },
    },
    "iot": {
        "id": "iot-telemetry-assurance",
        "title": "IoT event-time telemetry assurance",
        "task": "Validate, deduplicate, order, profile, and assure a finite device telemetry fixture.",
        "raw": {
            "temperature_limit": 80,
            "events": [
                {
                    "id": "event.a",
                    "device_id": "device.1",
                    "ts": 2,
                    "temperature": 90,
                    "firmware": "1.0",
                },
                {
                    "id": "event.b",
                    "device_id": "device.2",
                    "ts": 1,
                    "temperature": 40,
                    "firmware": "1.1",
                },
                {
                    "id": "event.a",
                    "device_id": "device.1",
                    "ts": 2,
                    "temperature": 90,
                    "firmware": "1.0",
                },
                {
                    "id": "event.c",
                    "device_id": "device.1",
                    "ts": 3,
                    "temperature": 70,
                    "firmware": "1.0",
                },
            ],
        },
    },
    "digital-twin": {
        "id": "digital-twin-validation",
        "title": "Digital twin calibration and validation fixture",
        "task": "Calibrate a transparent model, validate on untouched observations, and record sensitivity and limits.",
        "raw": {
            "calibration": [
                {"input": 0, "observed": 1},
                {"input": 1, "observed": 3},
                {"input": 2, "observed": 5},
            ],
            "validation": [
                {"input": 3, "observed": 7},
                {"input": 4, "observed": 9},
            ],
            "sensitivity_input": 5,
        },
    },
}


def _candidate_id(domain: str, operation: str, strategy: str) -> str:
    return f"candidate.example.frontier.{domain}.{operation}.{strategy}"


def _example(domain: str) -> ExecutableExample:
    fixture = FIXTURES[domain]
    operations = DOMAIN_OPERATIONS[domain]
    reference = {
        operation: _candidate_id(domain, operation, "reference") for operation in operations
    }
    shortcut = {operation: _candidate_id(domain, operation, "shortcut") for operation in operations}
    return ExecutableExample(
        fixture["id"],
        fixture["title"],
        fixture["task"],
        _program(domain, fixture["task"]),
        (
            ExampleRoute(
                "shortcut-control",
                "Every operation discloses that required assurance evidence is absent.",
                shortcut,
                expected_accepted=False,
            ),
            ExampleRoute(
                "reference",
                "Every operation uses the deterministic reference fixture contract.",
                reference,
            ),
        ),
        ExperimentCase(
            f"case.frontier-{domain}",
            {"payload": {"raw": fixture["raw"]}},
            CallableVerifier("verifier.example.frontier", verify_frontier),
        ),
        ExecutionPolicy(),
        (
            Objective("quality", "maximize", hard_minimum=1.0),
            Objective("latency_ms", "minimize", weight=0.1),
        ),
        registry=FRONTIER_REGISTRY,
    )


FRONTIER_EXAMPLE_TASKS = tuple(_example(domain) for domain in DOMAIN_OPERATIONS)


__all__ = [
    "DOMAIN_OPERATIONS",
    "FIXTURES",
    "FRONTIER_CANDIDATES",
    "FRONTIER_EXAMPLE_TASKS",
    "FRONTIER_NODES",
    "FRONTIER_PAYLOAD",
    "FRONTIER_REGISTRY",
    "execute_reference_step",
    "execute_shortcut_step",
    "verify_frontier",
]
