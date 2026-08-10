"""Hierarchical demonstration data for the universal graph workbench.

The values are explicitly UI demonstration priors, not benchmark claims.  The
same viewer accepts measured metrics and receipts from a real optimizer.

The important structural point is that the six conceptual macro stages are not
selection columns.  They expand into twenty-one ordered, typed substeps.  A
route selects one concrete candidate at every substep, so large ideas such as
"canonicalize" or "verify" no longer hide several different operations inside
one choice.
"""
from __future__ import annotations

from math import prod
from typing import Any

from browsergraph.manifest import NodeManifest, ParameterSpec, PortSpec
from browsergraph.workbench import (
    FeedbackDefinition,
    MacroStageDefinition,
    OptimizationObjective,
    OptimizationProfile,
    SolutionDefinition,
    StageDefinition,
    WorkbenchDefinition,
    candidate_id,
    expand_node_candidates,
)


def _parameter(name: str, choices: tuple[str, ...]) -> ParameterSpec:
    return ParameterSpec(
        name=name,
        data_type="string",
        choices=choices,
        default=choices[0] if choices else None,
    )


def _manifest(
    stage: StageDefinition,
    slug: str,
    name: str,
    roles: tuple[str, ...],
    *,
    description: str = "",
    axes: dict[str, tuple[str, ...]] | None = None,
    capabilities: tuple[str, ...] = (),
    effects: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
    dependencies: tuple[str, ...] = (),
    resources: dict[str, Any] | None = None,
    runtime: dict[str, Any] | None = None,
    index: int = 0,
    pass_through: bool = False,
) -> NodeManifest:
    parameters = tuple(_parameter(axis, choices)
                       for axis, choices in (axes or {}).items())
    deterministic = "model" not in roles and "human" not in roles
    return NodeManifest(
        id=f"demo.{stage.id}.{slug}",
        kind=f"{stage.id}_{slug}".replace(".", "_").replace("-", "_"),
        name=name,
        version="0.2.0",
        description=(description or
                     f"Implements {stage.name.lower()} using {name.lower()} behind the declared typed contract."),
        roles=roles + (("pass_through",) if pass_through else ()),
        capabilities=(stage.id, stage.macro_stage_id) + capabilities + (
            ("pass_through",) if pass_through else ()),
        inputs=(PortSpec(
            name="input",
            data_type=stage.input_type,
            description=f"Input contract for {stage.name}",
        ),),
        outputs=(PortSpec(
            name="output",
            data_type=stage.output_type,
            description=("Unchanged semantic payload certified for the next contract"
                         if pass_through else f"Output contract for {stage.name}"),
        ),),
        parameters=parameters,
        effects=effects,
        permissions=permissions,
        dependencies=dependencies,
        resources=resources or {"cpu": "small", "memory_mb": 96 + index * 32},
        runtime=runtime or {"deterministic": deterministic, "sandbox": "process"},
        context={
            "reads": [stage.input_type],
            "writes": [stage.output_type],
            "default_scopes": ["attempt", "substep", "macro_stage"],
            "global_access": "brokered",
        },
        intelligence={
            "mode": "model_assisted" if "model" in roles else "deterministic",
            "micro_model": None,
            "may_propose_route_change": False,
        },
        metrics={
            "metric_source": "illustrative_ui_demo",
            "quality_prior": round(min(0.97, 0.73 + index * 0.024), 3),
            "latency_ms_prior": 24 + index * 47,
            "cost_usd_prior": round(index * 0.0013, 4),
        },
        source=f"browsergraph.demo:{stage.id}/{slug}",
        docs="UNIVERSAL_GRAPH_SYSTEM.md#standardized-node-definition",
        tags=("demo", stage.macro_stage_id, stage.id),
    ).assert_valid()


def build_demo_workbench() -> WorkbenchDefinition:
    """Build a six-macro-stage, twenty-one-substep universal example."""

    stages = (
        StageDefinition(
            id="acquire.resolve", macro_stage_id="acquire", name="Resolve source",
            description="Resolve the task reference into a concrete source identity.",
            input_type="TaskReference", output_type="ResolvedReference",
            success="the source identity and addressing mode are explicit",
            optional=False, variant_axes=("source", "controller", "binary", "transport"),
            required_capabilities=("acquire.resolve",)),
        StageDefinition(
            id="acquire.authorize", macro_stage_id="acquire", name="Authorize access",
            description="Attach the least authority required to read the resolved source.",
            input_type="ResolvedReference", output_type="AuthorizedReference",
            success="access is authorized, scoped and auditable",
            optional=True, variant_axes=("credential", "identity", "session", "scope"),
            required_capabilities=("acquire.authorize",)),
        StageDefinition(
            id="acquire.retrieve", macro_stage_id="acquire", name="Retrieve payload",
            description="Read or capture the source through a typed transport.",
            input_type="AuthorizedReference", output_type="RetrievedPayload",
            success="the requested bytes, records, events or state are available",
            optional=True, variant_axes=("transport", "delivery", "capture", "cache"),
            required_capabilities=("acquire.retrieve",)),
        StageDefinition(
            id="acquire.identify", macro_stage_id="acquire", name="Identify and fingerprint",
            description="Establish content identity, format hints, version and integrity.",
            input_type="RetrievedPayload", output_type="InputHandle",
            success="the payload is versioned, fingerprinted and safe to process",
            optional=True, variant_axes=("hash", "mime", "version", "integrity"),
            required_capabilities=("acquire.identify",)),

        StageDefinition(
            id="canonicalize.detect", macro_stage_id="canonicalize", name="Detect representation",
            description="Determine the payload format without yet interpreting its content.",
            input_type="InputHandle", output_type="FormatEnvelope",
            success="format and encoding hypotheses are explicit with confidence",
            optional=True, variant_axes=("detector", "confidence", "ensemble"),
            required_capabilities=("canonicalize.detect",)),
        StageDefinition(
            id="canonicalize.decode", macro_stage_id="canonicalize", name="Decode content",
            description="Turn bytes or application state into typed decoded content.",
            input_type="FormatEnvelope", output_type="DecodedContent",
            success="content is readable with source locations preserved",
            optional=True, variant_axes=("format", "engine", "ocr", "model"),
            required_capabilities=("canonicalize.decode",)),
        StageDefinition(
            id="canonicalize.normalize", macro_stage_id="canonicalize", name="Normalize values",
            description="Standardize encoding, units, locale, layout and missing values.",
            input_type="DecodedContent", output_type="NormalizedContent",
            success="equivalent values share a stable normalized representation",
            optional=True, variant_axes=("encoding", "units", "locale", "cleanup"),
            required_capabilities=("canonicalize.normalize",)),
        StageDefinition(
            id="canonicalize.schema", macro_stage_id="canonicalize", name="Map canonical schema",
            description="Map normalized content into the task's typed canonical schema.",
            input_type="NormalizedContent", output_type="CanonicalState",
            success="required fields, identities and confidence are schema-valid",
            optional=True, variant_axes=("mapper", "schema", "model", "strategy"),
            required_capabilities=("canonicalize.schema",)),

        StageDefinition(
            id="enrich.clean", macro_stage_id="enrich", name="Clean and protect",
            description="Remove noise, duplicates and unsafe or policy-sensitive content.",
            input_type="CanonicalState", output_type="CleanState",
            success="quality and protection policies pass with changes attributed",
            optional=True, variant_axes=("rules", "dedupe", "privacy", "outliers"),
            required_capabilities=("enrich.clean",)),
        StageDefinition(
            id="enrich.language", macro_stage_id="enrich", name="Resolve language",
            description="Detect, translate, transliterate or preserve language as required.",
            input_type="CleanState", output_type="LinguisticState",
            success="language and terminology are usable by downstream nodes",
            optional=True, variant_axes=("detector", "translator", "strategy", "glossary"),
            required_capabilities=("enrich.language",)),
        StageDefinition(
            id="enrich.context", macro_stage_id="enrich", name="Retrieve context",
            description="Attach relevant internal or external evidence with provenance.",
            input_type="LinguisticState", output_type="ContextState",
            success="required context meets freshness, relevance and authority bounds",
            optional=True, variant_axes=("retrieval", "source", "index", "freshness"),
            required_capabilities=("enrich.context",)),
        StageDefinition(
            id="enrich.analyze", macro_stage_id="enrich", name="Derive features and evidence",
            description="Derive fields, features, predictions and reconciled evidence.",
            input_type="ContextState", output_type="EnrichedState",
            success="derived context is calibrated, attributed and task-ready",
            optional=True, variant_axes=("rules", "features", "model", "ensemble"),
            required_capabilities=("enrich.analyze",)),

        StageDefinition(
            id="transform.plan", macro_stage_id="transform", name="Plan operation",
            description="Decompose the requested transformation or effect into a bounded plan.",
            input_type="EnrichedState", output_type="ActionPlan",
            success="the plan is executable, authorized and budgeted",
            optional=True, variant_axes=("planner", "search", "constraints", "budget"),
            required_capabilities=("transform.plan",)),
        StageDefinition(
            id="transform.execute", macro_stage_id="transform", name="Execute operation",
            description="Run the selected function, package, model, browser action or subgraph.",
            input_type="ActionPlan", output_type="RawResult",
            success="the declared transformation or permitted effect is observed",
            optional=True, variant_axes=("runtime", "controller", "model", "composition"),
            required_capabilities=("transform.execute",)),
        StageDefinition(
            id="transform.reconcile", macro_stage_id="transform", name="Reconcile result",
            description="Assemble, post-process, calibrate and resolve conflicting outputs.",
            input_type="RawResult", output_type="CandidateResult",
            success="one candidate result satisfies the declared output contract",
            optional=True, variant_axes=("assembly", "ensemble", "conflict", "calibration"),
            required_capabilities=("transform.reconcile",)),

        StageDefinition(
            id="verify.contract", macro_stage_id="verify", name="Validate contract",
            description="Check shape, types, invariants, security and effect policy.",
            input_type="CandidateResult", output_type="ContractCheckedResult",
            success="the result passes all mandatory deterministic gates",
            optional=True, variant_axes=("schema", "invariant", "security", "policy"),
            required_capabilities=("verify.contract",)),
        StageDefinition(
            id="verify.outcome", macro_stage_id="verify", name="Verify outcome independently",
            description="Judge actual success using evidence independent of the producer.",
            input_type="ContractCheckedResult", output_type="EvidenceVerdict",
            success="independent evidence supports an acceptance or rejection verdict",
            optional=True, variant_axes=("oracle", "source", "model", "human"),
            required_capabilities=("verify.outcome",)),
        StageDefinition(
            id="verify.adjudicate", macro_stage_id="verify", name="Adjudicate confidence and risk",
            description="Combine verdicts, uncertainty, risk and escalation policy.",
            input_type="EvidenceVerdict", output_type="VerifiedOutcome",
            success="a policy-valid final verdict and confidence are explicit",
            optional=True, variant_axes=("threshold", "consensus", "risk", "escalation"),
            required_capabilities=("verify.adjudicate",)),

        StageDefinition(
            id="emit.package", macro_stage_id="emit", name="Package result and evidence",
            description="Bundle the result, evidence, provenance and reproducibility data.",
            input_type="VerifiedOutcome", output_type="ReceiptBundle",
            success="the bundle is complete, typed and tamper-evident",
            optional=True, variant_axes=("result_format", "evidence", "compression", "encryption"),
            required_capabilities=("emit.package",)),
        StageDefinition(
            id="emit.deliver", macro_stage_id="emit", name="Deliver or persist",
            description="Write the bundle to a declared sink using idempotent semantics.",
            input_type="ReceiptBundle", output_type="DurableResult",
            success="the result is durably addressable by its intended consumer",
            optional=True, variant_axes=("sink", "transport", "retention", "access"),
            required_capabilities=("emit.deliver",)),
        StageDefinition(
            id="emit.register", macro_stage_id="emit", name="Register receipt and checkpoint",
            description="Publish the execution receipt, lineage, checkpoint and monitoring signals.",
            input_type="DurableResult", output_type="TaskReceipt",
            success="the exact route and evidence are replayable and discoverable",
            optional=True, variant_axes=("checkpoint", "ledger", "catalog", "monitor"),
            required_capabilities=("emit.register",)),
    )

    macro_stages = (
        MacroStageDefinition(
            id="acquire", name="Acquire inputs", input_type="TaskReference",
            output_type="InputHandle",
            success="authorized, versioned inputs are ready for interpretation",
            description="Resolve, authorize, retrieve, and identify the inputs.",
            substeps=("acquire.resolve", "acquire.authorize", "acquire.retrieve", "acquire.identify")),
        MacroStageDefinition(
            id="canonicalize", name="Canonicalize representation", input_type="InputHandle",
            output_type="CanonicalState",
            success="the input has a typed canonical representation",
            description="Detect, decode, normalize, and map the input schema.", optional=True,
            substeps=("canonicalize.detect", "canonicalize.decode", "canonicalize.normalize", "canonicalize.schema")),
        MacroStageDefinition(
            id="enrich", name="Enrich context", input_type="CanonicalState",
            output_type="EnrichedState",
            success="the task state contains sufficient cleaned and attributed context",
            description="Clean, resolve language, retrieve context, and derive evidence.", optional=True,
            substeps=("enrich.clean", "enrich.language", "enrich.context", "enrich.analyze")),
        MacroStageDefinition(
            id="transform", name="Transform or act", input_type="EnrichedState",
            output_type="CandidateResult",
            success="a bounded plan has produced one candidate result",
            description="Plan, execute, and reconcile the task operation.", optional=True,
            substeps=("transform.plan", "transform.execute", "transform.reconcile")),
        MacroStageDefinition(
            id="verify", name="Verify success", input_type="CandidateResult",
            output_type="VerifiedOutcome",
            success="contract, outcome, confidence, and risk gates pass",
            description="Validate, independently verify, and adjudicate the result.", optional=True,
            substeps=("verify.contract", "verify.outcome", "verify.adjudicate")),
        MacroStageDefinition(
            id="emit", name="Emit result and receipt", input_type="VerifiedOutcome",
            output_type="TaskReceipt",
            success="the result and route evidence are durable and replayable",
            description="Package, deliver, and register the result and receipt.", optional=True,
            substeps=("emit.package", "emit.deliver", "emit.register")),
    )

    stage_map = {stage.id: stage for stage in stages}
    nodes_by_stage: dict[str, list[NodeManifest]] = {stage.id: [] for stage in stages}

    def add(stage_id: str, slug: str, name: str, roles: tuple[str, ...], **kwargs: Any) -> None:
        index = len(nodes_by_stage[stage_id])
        nodes_by_stage[stage_id].append(
            _manifest(stage_map[stage_id], slug, name, roles, index=index, **kwargs))

    # Acquire inputs: 30 definitions and 141 concrete candidates.
    add("acquire.resolve", "file", "File/source reference", ("source", "adapter"),
        axes={"path_mode": ("file", "directory", "glob")})
    add("acquire.resolve", "api", "API reference", ("source", "adapter"),
        axes={"method": ("GET", "POST", "PUT", "GraphQL")}, permissions=("network",))
    add("acquire.resolve", "browser", "Browser target", ("source", "adapter", "browser"),
        axes={"controller": ("BrowserPort", "Playwright", "Selenium", "Puppeteer", "CDP"),
              "binary": ("Chrome", "Chromium", "Edge", "Firefox", "WebKit", "Brave"),
              "display": ("headless", "headed")},
        permissions=("browser", "network"), dependencies=("browser-runtime",))
    add("acquire.resolve", "database", "Database reference", ("source", "adapter"),
        axes={"driver": ("PostgreSQL", "MySQL", "SQLite", "BigQuery", "Snowflake")},
        permissions=("database",))
    add("acquire.resolve", "event", "Event or sensor reference", ("source", "adapter"),
        axes={"delivery": ("stream", "poll", "batch")})
    add("acquire.resolve", "model", "Model endpoint reference", ("source", "adapter", "model"),
        axes={"endpoint": ("Ollama", "vLLM", "OpenAI-compatible", "custom")},
        permissions=("llm", "network"))
    add("acquire.resolve", "generated", "Generated adapter", ("source", "adapter", "generated"),
        permissions=("sandbox",))
    add("acquire.resolve", "context", "Existing context reference", ("source", "adapter"))

    add("acquire.authorize", "credential", "Credential resolver", ("control", "adapter"),
        axes={"source": ("environment", "vault", "profile", "broker")})
    add("acquire.authorize", "oauth", "OAuth flow", ("control", "adapter"),
        axes={"flow": ("auth-code", "device", "service-account")}, permissions=("network",))
    add("acquire.authorize", "api-key", "API-key broker", ("control", "adapter"),
        axes={"provider": ("environment", "vault", "broker", "KMS")})
    add("acquire.authorize", "session", "Browser session policy", ("control", "browser"),
        axes={"mode": ("fresh", "persisted", "isolated", "shared")}, permissions=("browser",))
    add("acquire.authorize", "identity", "Workload identity", ("control", "adapter"),
        axes={"provider": ("AWS", "GCP", "Azure", "Kubernetes")})
    add("acquire.authorize", "signed-url", "Signed URL verifier", ("control", "verifier"))
    add("acquire.authorize", "local-check", "Local permission check", ("control", "verifier"))
    add("acquire.authorize", "pass", "Authorized pass-through", ("control",), pass_through=True)

    add("acquire.retrieve", "file-read", "File reader", ("source", "adapter"),
        axes={"mode": ("binary", "text", "mmap")})
    add("acquire.retrieve", "http-fetch", "HTTP fetcher", ("source", "adapter"),
        axes={"client": ("stdlib", "httpx", "curl-cffi")}, permissions=("network",))
    add("acquire.retrieve", "browser-capture", "Browser capture", ("source", "browser"),
        axes={"capture": ("DOM", "screenshot", "accessibility", "network")},
        permissions=("browser", "network"))
    add("acquire.retrieve", "db-query", "Database query", ("source", "adapter"),
        axes={"mode": ("parameterized", "streaming", "snapshot")}, permissions=("database",))
    add("acquire.retrieve", "stream", "Stream consumer", ("source", "adapter"),
        axes={"mode": ("at-least-once", "exactly-once", "latest")})
    add("acquire.retrieve", "model-response", "Model response reader", ("source", "model"),
        axes={"protocol": ("chat", "completion", "batch")}, permissions=("llm",))
    add("acquire.retrieve", "cache", "Cache lookup", ("source", "adapter"),
        axes={"backend": ("memory", "disk", "distributed")})
    add("acquire.retrieve", "pass", "Retrieved pass-through", ("control",), pass_through=True)

    add("acquire.identify", "hash", "Content fingerprint", ("analyzer", "verifier"),
        axes={"algorithm": ("sha256", "blake3", "sha512", "content-id")})
    add("acquire.identify", "mime", "MIME detector", ("analyzer",),
        axes={"strategy": ("magic", "header", "extension")})
    add("acquire.identify", "malware", "Payload safety checker", ("verifier",),
        axes={"engine": ("ClamAV", "YARA", "sandbox")})
    add("acquire.identify", "version", "Source version pin", ("analyzer",),
        axes={"method": ("ETag", "last-modified", "snapshot-id")})
    add("acquire.identify", "integrity", "Integrity composite", ("verifier", "composite"))
    add("acquire.identify", "pass", "Identified pass-through", ("control",), pass_through=True)

    # Canonicalize: format detection, decoding, normalization, then schema mapping.
    add("canonicalize.detect", "extension", "Extension detector", ("analyzer",))
    add("canonicalize.detect", "magic", "Magic-byte detector", ("analyzer",))
    add("canonicalize.detect", "header", "Header detector", ("analyzer",))
    add("canonicalize.detect", "mime", "MIME detector", ("analyzer",))
    add("canonicalize.detect", "learned", "Learned format detector", ("analyzer", "model"),
        axes={"confidence": ("0.70", "0.85", "0.95")})
    add("canonicalize.detect", "llm", "LLM format detector", ("analyzer", "model"),
        axes={"model": ("Gemini", "DeepSeek", "GLM", "Qwen", "Claude", "GPT")},
        permissions=("llm",))
    add("canonicalize.detect", "ensemble", "Detector ensemble", ("analyzer", "composite"))
    add("canonicalize.detect", "pass", "Known-format pass-through", ("control",), pass_through=True)

    add("canonicalize.decode", "pdf", "PDF decoder", ("transform", "adapter"),
        axes={"engine": ("PyMuPDF", "pdfplumber", "pypdf", "OCRmyPDF", "Tesseract")})
    add("canonicalize.decode", "office", "Office document decoder", ("transform", "adapter"),
        axes={"engine": ("LibreOffice", "python-docx", "openpyxl", "Apache-Tika")})
    add("canonicalize.decode", "image-ocr", "Image OCR", ("transform", "model"),
        axes={"engine": ("Tesseract", "EasyOCR", "PaddleOCR", "docTR", "cloud-vision")})
    add("canonicalize.decode", "html", "HTML decoder", ("transform", "adapter"),
        axes={"engine": ("BeautifulSoup", "readability", "selectolax", "DOM-snapshot")})
    add("canonicalize.decode", "audio", "Audio transcription", ("transform", "model"),
        axes={"engine": ("Whisper", "faster-whisper", "Vosk", "Deepgram", "Gemini")})
    add("canonicalize.decode", "table", "Table decoder", ("transform", "adapter"),
        axes={"engine": ("pandas", "polars", "duckdb", "petl")})
    add("canonicalize.decode", "structured", "Structured-data decoder", ("transform", "adapter"),
        axes={"format": ("json", "csv", "xml", "yaml")})
    add("canonicalize.decode", "llm", "LLM decoder", ("transform", "model"),
        axes={"model": ("Gemini", "DeepSeek", "GLM", "Qwen", "Claude", "GPT")},
        permissions=("llm",))
    add("canonicalize.decode", "pass", "Decoded pass-through", ("control",), pass_through=True)

    add("canonicalize.normalize", "encoding", "Encoding normalizer", ("transform",),
        axes={"method": ("utf-8", "chardet", "charset-normalizer")})
    add("canonicalize.normalize", "unicode", "Unicode normalizer", ("transform",),
        axes={"form": ("NFC", "NFKC", "ICU")})
    add("canonicalize.normalize", "units", "Unit normalizer", ("transform",),
        axes={"system": ("SI", "domain-native", "pint", "quantities")})
    add("canonicalize.normalize", "locale", "Locale normalizer", ("transform",),
        axes={"mode": ("en-US", "multilingual", "timezone-aware", "Babel")})
    add("canonicalize.normalize", "whitespace", "Whitespace and layout cleaner", ("transform",),
        axes={"mode": ("trim", "collapse", "layout-aware", "markdown")})
    add("canonicalize.normalize", "junk", "Junk-data remover", ("transform",),
        axes={"mode": ("symbols", "headers-footers", "watermarks", "boilerplate")})
    add("canonicalize.normalize", "missing", "Missing-value normalizer", ("transform",),
        axes={"mode": ("null", "sentinel", "typed-missing")})
    add("canonicalize.normalize", "learned", "Learned normalizer", ("transform", "model"),
        axes={"model": ("rules+ML", "small-transformer", "LLM-cleaner")})
    add("canonicalize.normalize", "pass", "Normalized pass-through", ("control",), pass_through=True)

    add("canonicalize.schema", "field-map", "Deterministic field mapper", ("transform",),
        axes={"engine": ("manual", "DSL", "jq", "JMESPath")})
    add("canonicalize.schema", "schema", "Schema adapter", ("transform", "adapter"),
        axes={"schema": ("JSON-Schema", "Pydantic", "Arrow")})
    add("canonicalize.schema", "entity", "Entity resolver", ("transform", "analyzer"),
        axes={"strategy": ("exact", "fuzzy", "knowledge-base")})
    add("canonicalize.schema", "learned", "Learned parser", ("transform", "model"),
        axes={"confidence": ("0.70", "0.85", "0.95")})
    add("canonicalize.schema", "llm", "LLM schema parser", ("transform", "model"),
        axes={"model": ("Gemini", "DeepSeek", "GLM", "Qwen", "Claude", "GPT"),
              "strategy": ("single-schema", "field-by-field", "map-reduce")},
        permissions=("llm",))
    add("canonicalize.schema", "composite", "Schema-mapping subgraph", ("transform", "composite"),
        axes={"mode": ("deterministic", "model-assisted", "hybrid")})
    add("canonicalize.schema", "pass", "Schema-valid pass-through", ("control",), pass_through=True)

    # Enrich: cleaning, language, context retrieval, and evidence derivation.
    add("enrich.clean", "rules", "Cleaning rules", ("transform",),
        axes={"ruleset": ("basic", "domain", "compliance", "custom")})
    add("enrich.clean", "junk", "Noise filter", ("transform",),
        axes={"mode": ("symbols", "boilerplate", "noise", "low-confidence")})
    add("enrich.clean", "dedupe", "Deduplicator", ("transform", "analyzer"),
        axes={"mode": ("exact", "fuzzy", "semantic", "entity-aware")})
    add("enrich.clean", "pii", "Sensitive-data protector", ("transform", "control"),
        axes={"mode": ("redact", "tokenize", "hash", "retain-with-policy")})
    add("enrich.clean", "outlier", "Outlier cleaner", ("transform", "model"),
        axes={"method": ("IQR", "robust-z", "isolation-forest", "cleanlab")})
    add("enrich.clean", "quality", "Quality gate", ("verifier",),
        axes={"dimension": ("completeness", "consistency", "validity", "combined")})
    add("enrich.clean", "pass", "Clean pass-through", ("control",), pass_through=True)

    add("enrich.language", "detect", "Language detector", ("analyzer", "model"),
        axes={"engine": ("langdetect", "fastText", "CLD3", "LLM")})
    add("enrich.language", "translate", "Translator", ("transform", "model"),
        axes={"engine": ("Marian", "NLLB", "DeepL", "Google", "Gemini", "GLM", "Qwen", "DeepSeek"),
              "strategy": ("direct", "chunked", "terminology-aware")},
        permissions=("llm",))
    add("enrich.language", "transliterate", "Transliterator", ("transform",),
        axes={"engine": ("ICU", "Unidecode", "language-specific", "LLM")})
    add("enrich.language", "terminology", "Terminology resolver", ("transform", "analyzer"),
        axes={"source": ("glossary", "translation-memory", "ontology")})
    add("enrich.language", "pass", "Language pass-through", ("control",), pass_through=True)

    add("enrich.context", "retriever", "Document retriever", ("analyzer",),
        axes={"ranking": ("BM25", "embedding", "hybrid", "reranked")})
    add("enrich.context", "reference", "Reference lookup", ("analyzer",),
        axes={"source": ("local-table", "USPS", "Census")})
    add("enrich.context", "external", "External evidence service", ("analyzer", "adapter"),
        axes={"source": ("authoritative-api", "commercial-api", "public-data", "partner-feed", "browser-source")},
        permissions=("network",))
    add("enrich.context", "graph", "Knowledge-graph lookup", ("analyzer",),
        axes={"engine": ("Neo4j", "RDF", "property-graph", "GraphRAG")})
    add("enrich.context", "web", "Web research", ("analyzer", "browser"),
        axes={"mode": ("search", "site-crawl", "browser-research", "API-search")},
        permissions=("browser", "network"))
    add("enrich.context", "vector", "Vector-store retrieval", ("analyzer",),
        axes={"engine": ("FAISS", "Qdrant", "Weaviate", "Milvus", "pgvector")})
    add("enrich.context", "cache", "Context cache", ("analyzer",),
        axes={"backend": ("memory", "disk", "distributed")})
    add("enrich.context", "pass", "Context pass-through", ("control",), pass_through=True)

    add("enrich.analyze", "rules", "Derived-field rules", ("analyzer",),
        axes={"ruleset": ("basic", "domain", "compliance", "custom")})
    add("enrich.analyze", "stats", "Statistical analyzer", ("analyzer", "model"),
        axes={"method": ("descriptive", "robust", "Bayesian", "causal")})
    add("enrich.analyze", "features", "Feature generator", ("analyzer",),
        axes={"engine": ("scikit-learn", "Featuretools", "tsfresh", "domain", "custom")})
    add("enrich.analyze", "classifier", "Classifier", ("analyzer", "model"),
        axes={"model": ("logistic", "XGBoost", "LightGBM", "CatBoost", "neural", "zero-shot")})
    add("enrich.analyze", "llm", "LLM evidence analyst", ("analyzer", "model"),
        axes={"model": ("Gemini", "DeepSeek", "GLM", "Qwen", "Claude", "GPT")},
        permissions=("llm",))
    add("enrich.analyze", "ensemble", "Evidence ensemble", ("analyzer", "composite"),
        axes={"method": ("voting", "stacking", "evidence", "debate")})
    add("enrich.analyze", "calibration", "Confidence calibrator", ("analyzer",),
        axes={"method": ("isotonic", "Platt", "conformal")})
    add("enrich.analyze", "pass", "Analysis pass-through", ("control",), pass_through=True)

    # Transform or act: planning, execution, and reconciliation remain distinct.
    add("transform.plan", "template", "Plan template", ("planner",),
        axes={"mode": ("fixed", "rule-driven", "state-machine", "workflow")})
    add("transform.plan", "solver", "Constraint solver", ("planner",),
        axes={"engine": ("OR-Tools", "Z3", "CP-SAT", "linear")})
    add("transform.plan", "search", "Search planner", ("planner", "optimizer"),
        axes={"strategy": ("BFS", "beam", "MCTS", "genetic", "Bayesian")})
    add("transform.plan", "llm", "LLM planner", ("planner", "model"),
        axes={"model": ("Gemini", "DeepSeek", "GLM", "Qwen", "Claude", "GPT")},
        permissions=("llm",))
    add("transform.plan", "workflow", "Workflow compiler", ("planner", "composite"),
        axes={"mode": ("DAG", "event-driven", "stateful", "multi-agent")})
    add("transform.plan", "pass", "Existing-plan pass-through", ("control",), pass_through=True)

    add("transform.execute", "function", "Function runtime", ("action", "transform"),
        axes={"runtime": ("Python", "Rust", "JavaScript", "Java", "WASM")})
    add("transform.execute", "package", "Package runtime", ("action", "adapter"),
        axes={"package": ("pandas", "polars", "OpenCV", "scikit-learn")},
        dependencies=("package-lock",))
    add("transform.execute", "api", "External API action", ("action", "adapter"),
        axes={"protocol": ("REST", "GraphQL", "gRPC", "function")},
        effects=("external_state",), permissions=("network",))
    add("transform.execute", "browser", "Browser action", ("action", "browser"),
        axes={"controller": ("BrowserPort", "Playwright", "Selenium", "Puppeteer", "CDP"),
              "action": ("click", "type", "navigate", "extract", "upload")},
        effects=("remote_state",), permissions=("browser", "network"))
    add("transform.execute", "ml", "ML inference runtime", ("action", "model"),
        axes={"runtime": ("CPU", "GPU", "ONNX", "remote")})
    add("transform.execute", "llm", "LLM agent", ("action", "model"),
        axes={"model": ("Gemini", "DeepSeek", "GLM", "Qwen", "Claude", "Kimi"),
              "mode": ("tool-use", "code-execution", "multi-agent")},
        effects=("bounded_tool_effects",), permissions=("llm",))
    add("transform.execute", "workflow", "Workflow engine", ("action", "composite"),
        axes={"engine": ("Temporal", "Airflow", "Prefect", "Ray")})
    add("transform.execute", "composite", "Composite child graph", ("action", "composite"),
        axes={"mode": ("sequential", "parallel", "adaptive")})
    add("transform.execute", "pass", "Execution pass-through", ("control",), pass_through=True)

    add("transform.reconcile", "assembly", "Schema assembler", ("transform",),
        axes={"engine": ("Pydantic", "dataclass", "Arrow", "JSON-schema")})
    add("transform.reconcile", "post", "Postprocessor", ("transform",),
        axes={"mode": ("rules", "package", "model", "LLM")})
    add("transform.reconcile", "ensemble", "Result ensemble", ("transform", "composite"),
        axes={"method": ("voting", "weighted", "stacking", "mixture-of-experts", "judge")})
    add("transform.reconcile", "conflict", "Conflict resolver", ("transform", "control"),
        axes={"policy": ("priority", "confidence", "recency", "source-trust")})
    add("transform.reconcile", "calibration", "Result calibrator", ("transform",),
        axes={"method": ("isotonic", "Platt", "conformal", "Bayesian")})
    add("transform.reconcile", "rollback", "Rollback coordinator", ("control",),
        axes={"mode": ("transaction", "checkpoint", "compensating-action")})
    add("transform.reconcile", "pass", "Reconciled pass-through", ("control",), pass_through=True)

    # Verify: deterministic contract gates, independent outcome evidence, adjudication.
    add("verify.contract", "schema", "Schema validator", ("verifier",),
        axes={"schema": ("JSON-Schema", "Pydantic", "Arrow", "Protobuf")})
    add("verify.contract", "types", "Type checker", ("verifier",),
        axes={"mode": ("static", "runtime", "boundary")})
    add("verify.contract", "invariant", "Invariant checker", ("verifier",),
        axes={"mode": ("exact", "tolerance", "property-based", "metamorphic")})
    add("verify.contract", "security", "Security scanner", ("verifier",),
        axes={"mode": ("taint", "secret", "malware", "prompt-injection")})
    add("verify.contract", "policy", "Authority and effect gate", ("verifier", "control"),
        axes={"dimension": ("permissions", "effects", "budget")})
    add("verify.contract", "pass", "Contract-certified pass-through", ("control",), pass_through=True)

    add("verify.outcome", "oracle", "Deterministic oracle", ("verifier",),
        axes={"mode": ("exact", "golden", "simulation", "task-specific")})
    add("verify.outcome", "external", "Independent external verifier", ("verifier", "adapter"),
        axes={"source": ("authoritative-api", "independent-source", "side-effect-query")},
        permissions=("network",))
    add("verify.outcome", "replay", "Replay verifier", ("verifier",),
        axes={"mode": ("deterministic", "recorded", "shadow")})
    add("verify.outcome", "model", "Independent model verifier", ("verifier", "model"),
        axes={"model": ("Gemini", "DeepSeek", "GLM", "Qwen", "Claude", "local")},
        permissions=("llm",))
    add("verify.outcome", "vision", "Visual verifier", ("verifier", "model"),
        axes={"engine": ("OpenCV", "OCR", "vision-model", "multimodal-LLM")})
    add("verify.outcome", "human", "Human review", ("verifier", "human"),
        axes={"mode": ("operator", "expert", "dual-review")}, permissions=("human_review",))
    add("verify.outcome", "simulation", "Simulation verifier", ("verifier",),
        axes={"mode": ("sandbox", "digital-twin", "counterfactual")})
    add("verify.outcome", "pass", "Verified-evidence pass-through", ("control",), pass_through=True)

    add("verify.adjudicate", "threshold", "Threshold policy", ("verifier", "control"),
        axes={"mode": ("strict", "balanced", "recall-first", "risk-adjusted")})
    add("verify.adjudicate", "consensus", "Verifier consensus", ("verifier", "composite"),
        axes={"method": ("majority", "weighted", "unanimous", "Bayesian", "judge")})
    add("verify.adjudicate", "risk", "Risk gate", ("verifier", "control"),
        axes={"tier": ("low", "medium", "high", "regulated")})
    add("verify.adjudicate", "escalation", "Escalation controller", ("verifier", "control"),
        axes={"action": ("fallback", "retry", "human", "stop")})
    add("verify.adjudicate", "counterfactual", "Counterfactual check", ("verifier",),
        axes={"mode": ("perturbation", "holdout", "adversarial")})
    add("verify.adjudicate", "pass", "Adjudicated pass-through", ("control",), pass_through=True)

    # Emit: package, persist, then register a replayable receipt.
    add("emit.package", "result", "Result serializer", ("sink", "transform"),
        axes={"format": ("JSON", "CSV", "Parquet", "object")})
    add("emit.package", "evidence", "Evidence packager", ("sink",),
        axes={"format": ("JSONL", "PROV-O", "OpenTelemetry", "bundle")})
    add("emit.package", "provenance", "Provenance packager", ("sink",),
        axes={"format": ("W3C-PROV", "lineage-graph", "hash-chain", "manifest")})
    add("emit.package", "artifact", "Artifact packager", ("sink",),
        axes={"kind": ("file", "model", "document", "dataset")})
    add("emit.package", "compress", "Compression layer", ("sink", "transform"),
        axes={"mode": ("none", "gzip", "zstd")})
    add("emit.package", "encrypt", "Encryption layer", ("sink", "control"),
        axes={"mode": ("none", "envelope", "tenant-key")})
    add("emit.package", "pass", "Packaged pass-through", ("control",), pass_through=True)

    add("emit.deliver", "memory", "In-memory result", ("sink",))
    add("emit.deliver", "file", "File sink", ("sink", "adapter"),
        axes={"mode": ("local", "mounted", "content-addressed", "archive")},
        effects=("filesystem_state",), permissions=("filesystem",))
    add("emit.deliver", "database", "Database sink", ("sink", "adapter"),
        axes={"engine": ("PostgreSQL", "SQLite", "BigQuery", "Snowflake", "Neo4j")},
        effects=("external_state",), permissions=("database",))
    add("emit.deliver", "object", "Object-store sink", ("sink", "adapter"),
        axes={"engine": ("S3", "GCS", "Azure-Blob", "MinIO")},
        effects=("external_state",), permissions=("network",))
    add("emit.deliver", "event", "Event sink", ("sink", "adapter"),
        axes={"engine": ("Kafka", "PubSub", "SQS", "webhook")},
        effects=("external_state",), permissions=("network",))
    add("emit.deliver", "callback", "Callback sink", ("sink", "adapter"),
        axes={"protocol": ("REST", "gRPC", "email", "queue")},
        effects=("external_state",), permissions=("network",))
    add("emit.deliver", "human", "Human delivery", ("sink", "human"),
        axes={"mode": ("dashboard", "approval-inbox", "download")}, permissions=("human_review",))
    add("emit.deliver", "pass", "Durable-result pass-through", ("control",), pass_through=True)

    add("emit.register", "checkpoint", "Graph checkpoint", ("sink", "verifier"),
        axes={"mode": ("full", "incremental", "content-addressed", "resumable")})
    add("emit.register", "ledger", "Receipt ledger", ("sink", "verifier"),
        axes={"mode": ("append-only", "signed", "replicated", "tenant")})
    add("emit.register", "catalog", "Result catalog", ("sink", "adapter"),
        axes={"catalog": ("metadata", "lineage", "feature-store", "model-registry")})
    add("emit.register", "audit", "Audit receipt", ("sink", "verifier"),
        axes={"detail": ("compact", "detailed", "regulatory", "replay")})
    add("emit.register", "monitor", "Monitoring signal", ("sink", "adapter"),
        axes={"mode": ("metric", "event", "alert")})
    add("emit.register", "pass", "Registered-receipt pass-through", ("control",), pass_through=True)

    all_nodes = tuple(node for stage in stages for node in nodes_by_stage[stage.id])
    all_candidates = expand_node_candidates(list(all_nodes))
    complete_stages = tuple(
        stage.with_discovered_candidates(list(all_nodes), list(all_candidates))
        for stage in stages)

    def pick(stage_id: str, slug: str, **parameters: str) -> str:
        return candidate_id(f"demo.{stage_id}.{slug}", parameters)

    def materialize(specification: dict[str, tuple[str, dict[str, str]]]) -> dict[str, str]:
        expected = {stage.id for stage in complete_stages}
        if set(specification) != expected:
            raise ValueError("demo route must define every atomic substep")
        return {
            stage.id: pick(stage.id, specification[stage.id][0],
                           **specification[stage.id][1])
            for stage in complete_stages
        }

    def choice(slug: str, **parameters: str) -> tuple[str, dict[str, str]]:
        return slug, parameters

    deterministic = {
        "acquire.resolve": choice("file", path_mode="file"),
        "acquire.authorize": choice("local-check"),
        "acquire.retrieve": choice("file-read", mode="text"),
        "acquire.identify": choice("hash", algorithm="sha256"),
        "canonicalize.detect": choice("magic"),
        "canonicalize.decode": choice("structured", format="json"),
        "canonicalize.normalize": choice("encoding", method="utf-8"),
        "canonicalize.schema": choice("field-map", engine="DSL"),
        "enrich.clean": choice("rules", ruleset="domain"),
        "enrich.language": choice("pass"),
        "enrich.context": choice("reference", source="local-table"),
        "enrich.analyze": choice("rules", ruleset="domain"),
        "transform.plan": choice("template", mode="rule-driven"),
        "transform.execute": choice("function", runtime="Python"),
        "transform.reconcile": choice("assembly", engine="Pydantic"),
        "verify.contract": choice("schema", schema="JSON-Schema"),
        "verify.outcome": choice("oracle", mode="exact"),
        "verify.adjudicate": choice("threshold", mode="strict"),
        "emit.package": choice("evidence", format="JSONL"),
        "emit.deliver": choice("file", mode="content-addressed"),
        "emit.register": choice("audit", detail="detailed"),
    }
    browser = {
        "acquire.resolve": choice("browser", controller="Playwright", binary="Firefox", display="headless"),
        "acquire.authorize": choice("session", mode="isolated"),
        "acquire.retrieve": choice("browser-capture", capture="DOM"),
        "acquire.identify": choice("hash", algorithm="blake3"),
        "canonicalize.detect": choice("mime"),
        "canonicalize.decode": choice("html", engine="DOM-snapshot"),
        "canonicalize.normalize": choice("whitespace", mode="layout-aware"),
        "canonicalize.schema": choice("field-map", engine="JMESPath"),
        "enrich.clean": choice("junk", mode="boilerplate"),
        "enrich.language": choice("detect", engine="CLD3"),
        "enrich.context": choice("web", mode="browser-research"),
        "enrich.analyze": choice("llm", model="Qwen"),
        "transform.plan": choice("search", strategy="beam"),
        "transform.execute": choice("browser", controller="BrowserPort", action="extract"),
        "transform.reconcile": choice("assembly", engine="JSON-schema"),
        "verify.contract": choice("invariant", mode="property-based"),
        "verify.outcome": choice("external", source="side-effect-query"),
        "verify.adjudicate": choice("consensus", method="weighted"),
        "emit.package": choice("evidence", format="bundle"),
        "emit.deliver": choice("object", engine="MinIO"),
        "emit.register": choice("ledger", mode="signed"),
    }
    llm = {
        "acquire.resolve": choice("api", method="POST"),
        "acquire.authorize": choice("oauth", flow="service-account"),
        "acquire.retrieve": choice("http-fetch", client="curl-cffi"),
        "acquire.identify": choice("hash", algorithm="sha256"),
        "canonicalize.detect": choice("llm", model="GLM"),
        "canonicalize.decode": choice("llm", model="GLM"),
        "canonicalize.normalize": choice("learned", model="LLM-cleaner"),
        "canonicalize.schema": choice("llm", model="GLM", strategy="field-by-field"),
        "enrich.clean": choice("quality", dimension="combined"),
        "enrich.language": choice("translate", engine="GLM", strategy="terminology-aware"),
        "enrich.context": choice("retriever", ranking="hybrid"),
        "enrich.analyze": choice("llm", model="Gemini"),
        "transform.plan": choice("llm", model="DeepSeek"),
        "transform.execute": choice("llm", model="DeepSeek", mode="tool-use"),
        "transform.reconcile": choice("conflict", policy="confidence"),
        "verify.contract": choice("policy", dimension="effects"),
        "verify.outcome": choice("model", model="GLM"),
        "verify.adjudicate": choice("consensus", method="judge"),
        "emit.package": choice("provenance", format="manifest"),
        "emit.deliver": choice("callback", protocol="REST"),
        "emit.register": choice("audit", detail="replay"),
    }
    accuracy = {
        "acquire.resolve": choice("database", driver="Snowflake"),
        "acquire.authorize": choice("identity", provider="GCP"),
        "acquire.retrieve": choice("db-query", mode="snapshot"),
        "acquire.identify": choice("integrity"),
        "canonicalize.detect": choice("ensemble"),
        "canonicalize.decode": choice("pdf", engine="OCRmyPDF"),
        "canonicalize.normalize": choice("unicode", form="NFKC"),
        "canonicalize.schema": choice("composite", mode="hybrid"),
        "enrich.clean": choice("quality", dimension="combined"),
        "enrich.language": choice("translate", engine="Gemini", strategy="terminology-aware"),
        "enrich.context": choice("graph", engine="GraphRAG"),
        "enrich.analyze": choice("ensemble", method="evidence"),
        "transform.plan": choice("search", strategy="MCTS"),
        "transform.execute": choice("composite", mode="adaptive"),
        "transform.reconcile": choice("ensemble", method="mixture-of-experts"),
        "verify.contract": choice("invariant", mode="metamorphic"),
        "verify.outcome": choice("simulation", mode="digital-twin"),
        "verify.adjudicate": choice("consensus", method="Bayesian"),
        "emit.package": choice("evidence", format="PROV-O"),
        "emit.deliver": choice("object", engine="S3"),
        "emit.register": choice("ledger", mode="replicated"),
    }
    resource = {
        "acquire.resolve": choice("context"),
        "acquire.authorize": choice("pass"),
        "acquire.retrieve": choice("cache", backend="memory"),
        "acquire.identify": choice("hash", algorithm="blake3"),
        "canonicalize.detect": choice("extension"),
        "canonicalize.decode": choice("structured", format="csv"),
        "canonicalize.normalize": choice("whitespace", mode="trim"),
        "canonicalize.schema": choice("field-map", engine="jq"),
        "enrich.clean": choice("pass"),
        "enrich.language": choice("pass"),
        "enrich.context": choice("pass"),
        "enrich.analyze": choice("stats", method="robust"),
        "transform.plan": choice("template", mode="fixed"),
        "transform.execute": choice("function", runtime="Rust"),
        "transform.reconcile": choice("assembly", engine="dataclass"),
        "verify.contract": choice("types", mode="static"),
        "verify.outcome": choice("replay", mode="deterministic"),
        "verify.adjudicate": choice("threshold", mode="balanced"),
        "emit.package": choice("result", format="object"),
        "emit.deliver": choice("memory"),
        "emit.register": choice("checkpoint", mode="incremental"),
    }

    solutions = (
        SolutionDefinition(
            id="deterministic_floor", name="Deterministic floor", status="champion",
            description="A local, replayable route across all twenty-one atomic substeps.",
            route=materialize(deterministic),
            fallbacks={
                "canonicalize.detect": (pick("canonicalize.detect", "header"),),
                "canonicalize.decode": (pick("canonicalize.decode", "table", engine="pandas"),),
                "verify.contract": (pick("verify.contract", "invariant", mode="exact"),),
                "verify.outcome": (pick("verify.outcome", "replay", mode="deterministic"),),
            },
            metrics={"quality": 0.86, "latency_ms": 910, "cost_usd": 0.0,
                     "reliability": 0.97, "memory_mb": 260},
            tags=("deterministic", "local", "replayable")),
        SolutionDefinition(
            id="browser_resilient", name="Browser-resilient route", status="challenger",
            description="Separates browser source resolution, session, capture, action, and verification.",
            route=materialize(browser),
            fallbacks={
                "acquire.resolve": (pick("acquire.resolve", "api", method="GET"),),
                "acquire.retrieve": (pick("acquire.retrieve", "browser-capture", capture="accessibility"),),
                "transform.execute": (pick("transform.execute", "browser", controller="CDP", action="extract"),),
                "verify.outcome": (pick("verify.outcome", "oracle", mode="task-specific"),),
            },
            metrics={"quality": 0.91, "latency_ms": 3350, "cost_usd": 0.018,
                     "reliability": 0.92, "memory_mb": 690},
            tags=("browser", "isolated-session", "external-verification")),
        SolutionDefinition(
            id="llm_adaptive", name="LLM-adaptive route", status="challenger",
            description="Uses models at distinct detection, decoding, mapping, planning, action, and verification substeps.",
            route=materialize(llm),
            fallbacks={
                "canonicalize.detect": (pick("canonicalize.detect", "ensemble"),),
                "canonicalize.schema": (pick("canonicalize.schema", "composite", mode="hybrid"),),
                "transform.plan": (pick("transform.plan", "search", strategy="beam"),),
                "transform.execute": (pick("transform.execute", "composite", mode="adaptive"),),
                "verify.outcome": (pick("verify.outcome", "human", mode="expert"),),
            },
            metrics={"quality": 0.94, "latency_ms": 5600, "cost_usd": 0.112,
                     "reliability": 0.90, "memory_mb": 460},
            tags=("adaptive", "model-backed", "schema-constrained")),
        SolutionDefinition(
            id="accuracy_ensemble", name="Accuracy-first ensemble", status="pareto",
            description="Combines hybrid schema mapping, evidence ensembles, search, simulation, and consensus.",
            route=materialize(accuracy),
            fallbacks={
                "canonicalize.decode": (pick("canonicalize.decode", "llm", model="Gemini"),),
                "enrich.context": (pick("enrich.context", "retriever", ranking="reranked"),),
                "enrich.analyze": (pick("enrich.analyze", "llm", model="Claude"),),
                "transform.execute": (pick("transform.execute", "ml", runtime="GPU"),),
                "verify.outcome": (pick("verify.outcome", "human", mode="dual-review"),),
            },
            metrics={"quality": 0.981, "latency_ms": 8700, "cost_usd": 0.21,
                     "reliability": 0.962, "memory_mb": 1380},
            tags=("accuracy", "ensemble", "high-evidence")),
        SolutionDefinition(
            id="resource_minimum", name="Resource-minimum route", status="pareto",
            description="Selects low-cost local candidates at every atomic substep.",
            route=materialize(resource),
            fallbacks={
                "canonicalize.decode": (pick("canonicalize.decode", "structured", format="json"),),
                "transform.execute": (pick("transform.execute", "function", runtime="Python"),),
                "verify.outcome": (pick("verify.outcome", "oracle", mode="exact"),),
            },
            metrics={"quality": 0.80, "latency_ms": 470, "cost_usd": 0.0,
                     "reliability": 0.94, "memory_mb": 112},
            tags=("local", "cpu", "low-memory")),
    )

    feedback_channels = (
        FeedbackDefinition(
            id="feedback.contract_compatibility", name="Contract compatibility",
            signal="contract_status", scope="edge", producer="compiler",
            consumer="admission_gate", action="reject_incompatible_transition",
            description="Rejects a route when any adjacent substep port cannot connect.", required=True),
        FeedbackDefinition(
            id="feedback.execution_diagnosis", name="Execution status and diagnosis",
            signal="attempt_outcome", scope="candidate", producer="supervisor",
            consumer="route_controller", action="retry_fallback_circuit_break_or_stop",
            description="Attributes a typed failure at the exact substep before recovery.", required=True),
        FeedbackDefinition(
            id="feedback.verification_verdict", name="Independent verification",
            signal="acceptance_verdict", scope="route", producer="verifier",
            consumer="acceptance_gate", action="accept_or_reject",
            description="Keeps production and acceptance evidence independent.", required=True),
        FeedbackDefinition(
            id="feedback.quality_yield", name="Quality and yield",
            signal="quality_yield_receipt", scope="route", producer="run_receipt",
            consumer="learner", action="update_quality_prior",
            description="Updates uncertainty-aware evidence instead of replacing it with one score."),
        FeedbackDefinition(
            id="feedback.latency_resources", name="Latency and resources",
            signal="resource_receipt", scope="candidate", producer="runtime",
            consumer="optimizer", action="update_latency_and_resource_models",
            description="Learns cost at candidate, substep, macro-stage, and route scopes."),
        FeedbackDefinition(
            id="feedback.cost_tokens", name="Cost and token spend",
            signal="cost_receipt", scope="route", producer="budget_tracker",
            consumer="optimizer", action="constrain_and_rank",
            description="Evaluates complete routes against the active objective profile."),
        FeedbackDefinition(
            id="feedback.policy_authority", name="Policy, authority and effects",
            signal="policy_decision", scope="route", producer="policy_gate",
            consumer="executor", action="allow_or_stop",
            description="Prevents optimization from bypassing permissions or effects.", required=True),
        FeedbackDefinition(
            id="feedback.provenance_drift", name="Provenance, drift and freshness",
            signal="freshness_receipt", scope="candidate", producer="registry_monitor",
            consumer="learner", action="invalidate_stale_evidence",
            description="Keeps priors version-aware, scoped, and replayable."),
    )

    optimization_profiles = (
        OptimizationProfile(
            id="profile.balanced", name="Balanced",
            description="Prefer quality with meaningful latency and cost pressure.",
            objectives=(OptimizationObjective("quality_prior", "maximize", 0.50),
                        OptimizationObjective("latency_ms_prior", "minimize", 0.25),
                        OptimizationObjective("cost_usd_prior", "minimize", 0.25))),
        OptimizationProfile(
            id="profile.quality", name="Quality prior",
            description="Emphasize quality with efficiency tie-breakers.",
            objectives=(OptimizationObjective("quality_prior", "maximize", 0.80),
                        OptimizationObjective("latency_ms_prior", "minimize", 0.10),
                        OptimizationObjective("cost_usd_prior", "minimize", 0.10))),
        OptimizationProfile(
            id="profile.speed", name="Lowest latency",
            description="Emphasize fast completion while preserving quality pressure.",
            objectives=(OptimizationObjective("quality_prior", "maximize", 0.20),
                        OptimizationObjective("latency_ms_prior", "minimize", 0.70),
                        OptimizationObjective("cost_usd_prior", "minimize", 0.10))),
        OptimizationProfile(
            id="profile.cost", name="Lowest cost",
            description="Emphasize marginal cost while retaining quality pressure.",
            objectives=(OptimizationObjective("quality_prior", "maximize", 0.20),
                        OptimizationObjective("latency_ms_prior", "minimize", 0.10),
                        OptimizationObjective("cost_usd_prior", "minimize", 0.70))),
    )

    route_count = prod(len(stage.candidates) for stage in complete_stages)
    return WorkbenchDefinition(
        title="Universal Hierarchical Node Graph Workbench",
        task=("Transform an authorized input into a verified task result through macro "
              "stages that expand into independently selectable atomic substeps."),
        success=("Every substep contract connects, the final outcome is independently "
                 "verified, and the exact hierarchical route is recorded."),
        nodes=all_nodes,
        candidates=all_candidates,
        macro_stages=macro_stages,
        stages=complete_stages,
        solutions=solutions,
        feedback_channels=feedback_channels,
        optimization_profiles=optimization_profiles,
        metadata={
            "metric_source": "Illustrative UI values — replace with measured run-receipt metrics",
            "candidate_policy": "all atomic bindings; no top-k truncation",
            "hierarchy": "task → macro stage → ordered atomic substep → candidate binding",
            "macro_stage_count": len(macro_stages),
            "substep_count": len(complete_stages),
            "concrete_route_count": str(route_count),
            "default_candidate": pick(
                "acquire.resolve", "browser", controller="Playwright",
                binary="Firefox", display="headless"),
        },
    ).assert_valid()
