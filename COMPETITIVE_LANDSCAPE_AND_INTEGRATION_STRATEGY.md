# Competitive landscape and integration strategy

Research snapshot: 2026-08-13. This review uses primary project documentation
and treats vendor claims as descriptions of their own products, not independent
benchmarks.

## Executive position

SolutionGraph should not try to become another scheduler, data catalog, model
registry, agent runtime, game engine, robot middleware, or 3D renderer. Its
defensible role is the layer immediately before and around those systems:

- decompose a task into typed semantic obligations;
- expose all compatible candidates instead of hiding one implementation;
- compile only contract-, authority-, and topology-compatible routes;
- compare controls, mutations, models, tools, and topologies under fixed cases;
- retain positive and negative receipts, provenance, uncertainty, and claim
  boundaries; and
- export a frozen route to the runtime that already owns durable execution.

That is a complementary control and evidence plane. The repository should
integrate mature ecosystem tools at typed boundaries and compete on universal
solution-space construction, compatibility, experimentation, and due-care
evaluation.

## Workflow and orchestration systems

| Ecosystem | What its own documentation emphasizes | SolutionGraph boundary |
|---|---|---|
| [Apache Airflow](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html) | Scheduled DAGs composed of tasks, dependencies, callbacks, retries, and operational controls | Keep the existing frozen-plan projection; let a production adapter create and operate native Airflow DAGs |
| [Dagster](https://docs.dagster.io/) | Asset-oriented data orchestration with lineage, observability, declarative definitions, and testability | Project accepted artifact lineage and quality gates into assets/checks; do not reproduce the Dagster control plane |
| [Prefect](https://docs.prefect.io/v3/concepts/tasks) | Python-native flows and small cacheable/retryable tasks with tracked state and transactional semantics | Add an optional native adapter after the frozen-plan contract stabilizes; retain SolutionGraph admission and evidence outside the flow runtime |
| [Temporal](https://github.com/temporalio/temporal/blob/main/docs/architecture/README.md) | Event-sourced durable workflows, deterministic workflow logic, and retryable activities | Use Temporal for long-running effects, timers, signals, and crash recovery; preserve exact node/plan identity in activity inputs and receipts |
| [Flyte](https://flyte.org/platform) | Strongly typed, versioned, container-oriented AI/data workflows with caching, lineage, resources, and recovery | Map frozen node ports and resources to Flyte tasks; keep search and evaluation as pre-deployment or campaign graphs |
| [Kubeflow Pipelines](https://www.kubeflow.org/docs/components/pipelines/concepts/component/) | Reusable container/Python components with typed parameters, artifacts, dependencies, resources, and Kubernetes execution | Export admitted ML routes and immutable artifacts to KFP; do not duplicate cluster scheduling or metadata storage |

Near-term action: keep Airflow, Dagster, Temporal, and Kubernetes exports
manifest-only and add contract tests before generating native code. Prefect,
Flyte, and Kubeflow are logical next adapter packages, not core dependencies.

## LLM, agent, and evaluation systems

| Ecosystem | What its own documentation emphasizes | SolutionGraph boundary |
|---|---|---|
| [LangGraph](https://docs.langchain.com/oss/javascript/langgraph/overview) | Stateful agent graphs with durable execution, memory, human interruption, and deployment tooling | Treat a LangGraph agent as a candidate system or external runtime; evaluate exact trajectories through the LLM evaluation/safety pack |
| [Inspect AI](https://inspect.aisi.org.uk/tasks.html) | Evaluation tasks with replaceable models, solvers, scorers, metrics, sample selection, and re-scoring | Project SolutionGraph cases/arms into Inspect tasks and import signed logs as external evidence; keep sealed-case and promotion authority separate |
| [Arize Phoenix](https://arize.com/docs/phoenix) | OpenTelemetry-based traces, code/model/human evaluation, datasets, experiments, prompt iteration, and replay | Export traces and experiment metadata; import evaluator results without granting them independent-oracle status automatically |
| [MLflow GenAI](https://mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/prompts/) | Prompt/model evaluation over datasets, tracing, experiment comparison, and prompt lineage | Use MLflow as an experiment/trace backend while SolutionGraph owns graph identity, compiler admission, control/mutation pairing, and claim scope |

The LLM evaluation/safety pack adds a useful distinction these products do not
guarantee by themselves: producer, judge, adjudicator, promotion authority, and
sealed outer evaluator are separately identified graphs with explicit feedback
visibility. Integration must never collapse those roles merely because one UI
can run all of them.

## Data quality, provenance, and observability

| Ecosystem | Reuse | SolutionGraph contribution |
|---|---|---|
| [Great Expectations](https://docs.greatexpectations.io/docs/core/introduction/gx_overview/) | Expectation suites, validation definitions/results, checkpoints, and actions | Compile semantic question-bank findings into explicit validations where possible; retain repair proposals, unresolved conflicts, and LLM review as separate nodes |
| [OpenLineage](https://openlineage.io/docs/next/spec/object-model/) | Standard run, job, dataset, and extensible facet events | Continue projecting immutable run receipts; never treat lineage metadata as execution or correctness evidence |
| [OpenTelemetry](https://opentelemetry.io/docs/concepts/signals/) | Vendor-neutral traces, metrics, logs, and baggage | Export runtime observations with plan/node/receipt identities; keep acceptance verdicts and claim boundaries in SolutionGraph evidence |

## Cyber-physical and media ecosystems

| Ecosystem | Reuse | SolutionGraph contribution |
|---|---|---|
| [MITRE CALDERA](https://github.com/mitre/caldera) | Authorized adversary-emulation operations and plugin ecosystem | Keep the core defensive and read-only; a separate, tightly scoped adapter can execute approved emulations and return evidence to the cyber pack |
| [ROS 2 lifecycle nodes](https://docs.ros.org/en/rolling/p/lifecycle/) and [Gazebo](https://docs.ros.org/en/rolling/Tutorials/Advanced/Simulators/Gazebo/Gazebo.html) | Robot middleware, managed lifecycle states, device interfaces, launch/testing, and simulation | Compile plans and safety scenarios, but require ROS/Gazebo adapters, lifecycle enforcement, emergency-stop testing, and qualified approval for physical effects |
| [OpenUSD asset validation](https://docs.nvidia.com/learn-openusd/latest/data-exchange/asset-validation/what-is-asset-validation.html) | `usdchecker` rules for interoperable/renderable stages and USDZ packages | Translate 3D assurance recipes into validator, render-regression, and engine-budget nodes while retaining exact asset and tool identities |
| [NVIDIA Omniverse](https://docs.nvidia.com/omniverse/index.html) | OpenUSD-based rendering, physics, sensor simulation, storage, packaging, and digital-twin libraries | Use optional adapters for simulation and synthetic media; keep calibration, untouched validation, sensitivity, and applicability gates in the digital-twin pack |

## Where SolutionGraph can differentiate

1. **A universal typed candidate matrix.** Existing orchestrators generally run
   a selected graph. SolutionGraph explicitly represents the full admitted
   matrix of interchangeable nodes, parameters, and topology families.
2. **Control-versus-mutation experiments.** A frozen control and compatible
   graph mutation share cases, seeds, objectives, and independent oracles.
3. **All-visible recommendation.** Every specialized pack remains in the report
   with matched evidence, missing interfaces, and unavoidable permissions.
4. **History as a prior, never authority.** Historical routes, embeddings, and
   task fingerprints can seed sprouts without bypassing compatibility or
   acceptance.
5. **Negative evidence and claim boundaries.** Failed controls, invalid routes,
   unvisited search space, evaluator disagreement, and production limitations
   remain first-class outputs.
6. **Cross-domain composition.** The same artifact-kind and node contracts can
   connect data, documents, LLMs, cyber, media, simulation, and human review
   without forcing all work into an AI/ML ontology.

## Prioritized integration backlog

### P0 — evidence interoperability

- OpenTelemetry exporter carrying program, plan, node, candidate, case, and
  receipt identities.
- Inspect AI and MLflow/Phoenix experiment import/export with explicit evaluator
  identity and no automatic trust upgrade.
- Great Expectations projection for deterministic data-question checks.
- OpenUSD `usdchecker` adapter and fixed-camera render-regression receipt.

### P1 — production runtime adapters

- Native Temporal activity/workflow adapter for durable effectful graphs.
- Native Airflow/Dagster adapter generated only from frozen admitted plans.
- Flyte/Kubeflow component projection for containerized ML and simulation work.
- ROS 2/Gazebo simulation adapter with an unforgeable no-physical-effects mode.

### P2 — governed domain adapters

- Current, licensed geospatial/address/time-zone authority sources.
- Read-only SIEM/STIX ingestion and separately authorized CALDERA emulation.
- Game-engine replay/performance adapters for Godot, Unity, or Unreal.
- Blender/OpenUSD/Omniverse asset, render, physics, and digital-twin adapters.

Every adapter must declare versions, credentials, effects, permissions,
isolation, idempotency, compensation, source identity, and failure semantics.
An adapter is not “supported” until its native integration has reproducible
fixtures and an independently verified failure path.
