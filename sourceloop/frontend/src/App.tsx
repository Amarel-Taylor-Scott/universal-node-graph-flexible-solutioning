import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const stages = [
  "orient",
  "reconcile_horizon",
  "assess_prepare",
  "decide_next",
  "how",
  "act",
  "verify",
  "integrate_commit",
  "route",
] as const;

type Stage = (typeof stages)[number];
type Tab = "overview" | "outreach" | "intelligence" | "evidence" | "agents";

type GeoPoint = {
  latitude: number;
  longitude: number;
  label: string;
  precision?: string;
};

type Contact = {
  id: string;
  organization_name: string;
  legal_entity_name?: string;
  role_title: string;
  endpoint: string;
  channel: string;
  source: string;
  source_public: boolean;
  business_only: boolean;
  confidence: number;
  geography?: string;
  jurisdiction?: string;
  location?: GeoPoint;
};

type Action = {
  id: string;
  status: string;
  recipient: string;
  organization_name: string;
  subject: string;
  body: string;
  followup: boolean;
  thread_id?: string;
  policy_receipt: Record<string, unknown>;
};

type AgentRun = {
  id: string;
  role: string;
  stage: Stage;
  runtime: string;
  status: string;
  started_at: string;
  finished_at?: string;
  error?: string;
};

type Claim = {
  id: string;
  predicate: string;
  value: unknown;
  kind: string;
  confidence: number;
  corroboration_status: string;
  evidence_ids: string[];
};

type QuoteLine = {
  description: string;
  unit: string;
  quantity?: number;
  unit_price: number;
  currency: string;
  one_time: boolean;
};

type Quote = {
  id: string;
  supplier_name: string;
  line_items: QuoteLine[];
  commercial_terms: Record<string, unknown>;
  operational_terms: Record<string, unknown>;
  exclusions: string[];
  assumptions: string[];
  extraction_confidence: number;
  unresolved_fields: string[];
  valid_until?: string;
  evidence_ids: string[];
};

type Finding = {
  id: string;
  rule_id: string;
  kind: string;
  severity: string;
  title: string;
  summary: string;
  subject_id: string;
  value: unknown;
  evidence_ids: string[];
  confidence: number;
  status: string;
  source_scope: string;
  requires_human_review: boolean;
  reviewed_by?: string;
  reviewed_at?: string;
  review_notes?: string;
};

type RegistryCheck = {
  id: string;
  registry: string;
  query: string;
  subject_id?: string;
  status: string;
  identifier?: string;
  entity_name?: string;
  jurisdiction?: string;
  source?: string;
  checked_at: string;
  notes: string;
};

type Interaction = {
  id: string;
  direction: string;
  endpoint: string;
  subject: string;
  body: string;
  thread_id: string;
  evidence_id: string;
  raw_evidence_path?: string;
  provider_message_id?: string;
  attachments: Array<{ filename: string; status: string; size_bytes: number }>;
  created_at: string;
};

type CaseRecord = {
  id: string;
  title: string;
  kind: string;
  objective: string;
  requester_name: string;
  requester_email?: string;
  pack?: string;
  stage: Stage;
  status: string;
  demo: boolean;
  location?: GeoPoint;
  completion_target: number;
  max_contacts: number;
  max_followups: number;
  contacts: Contact[];
  actions: Action[];
  agent_runs: AgentRun[];
  claims: Claim[];
  quotes: Quote[];
  findings: Finding[];
  registry_checks: RegistryCheck[];
  response_coverage: Record<string, string[]>;
  risk_tier: string;
  investigation_mode?: string;
  governance: Record<string, unknown>;
  interactions: Interaction[];
  updated_at: string;
};

type ResponseField = {
  id: string;
  label: string;
  question: string;
  markers: string[];
  critical: boolean;
};

type Pack = {
  id: string;
  name: string;
  case_kind: string;
  description: string;
  investigation_mode?: string;
  risk_tier: string;
  institutional_only: boolean;
  requires_requester_email: boolean;
  required_acknowledgements: string[];
  required_fields: string[];
  optional_fields: string[];
  prohibited_actions: string[];
  question_prompts: string[];
  response_fields: ResponseField[];
  max_contacts: number;
  max_followups: number;
  completion_target: number;
  message_purpose: string;
  respondent_value: string;
  reuse_policy: string;
};

type Feature = {
  id: string;
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: Record<string, string | number>;
};

type FeatureCollection = { type: "FeatureCollection"; features: Feature[] };

type WorkerInfo = {
  worker_id: string;
  status: string;
  updated_at: string;
  details: Record<string, unknown>;
};

type RuntimeInfo = {
  name: string;
  version: string;
  environment: string;
  email_mode: string;
  external_send_enabled: boolean;
  mailbox_mode: string;
  mailbox_enabled: boolean;
  agent_runtime: string;
  pack_count: number;
  worker?: WorkerInfo;
};

type CaseReport = {
  case: Record<string, unknown>;
  activity: Record<string, number>;
  results: Record<string, unknown>;
  market_prices: Record<string, { count: number; minimum: number; median: number; maximum: number; mean: number }>;
  response_coverage: Array<{
    endpoint: string;
    covered: string[];
    missing_critical: string[];
    coverage_ratio: number;
  }>;
  evidence_ids: string[];
  interpretation_notice: string;
};

type NewCaseDraft = {
  pack: string;
  title: string;
  objective: string;
  requesterName: string;
  requesterEmail: string;
  requirements: string;
  contacts: string;
  acknowledgements: Record<string, boolean>;
};

type RegistryDraft = {
  registry: string;
  query: string;
  subjectId: string;
  status: string;
  identifier: string;
  entityName: string;
  jurisdiction: string;
  source: string;
  notes: string;
};

const emptyRegistry: RegistryDraft = {
  registry: "",
  query: "",
  subjectId: "",
  status: "matched",
  identifier: "",
  entityName: "",
  jurisdiction: "",
  source: "",
  notes: "",
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({ detail: response.statusText }))) as {
      detail?: string;
    };
    throw new Error(payload.detail ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

function titleize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatDate(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}

function quoteTotal(quote: Quote): number {
  return quote.line_items.reduce((total, line) => total + (line.quantity ?? 1) * line.unit_price, 0);
}

function parseContacts(raw: string): Array<Record<string, unknown>> {
  if (!raw.trim()) return [];
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [organization_name, role_title, endpoint, geography, latitude, longitude, source] = line
        .split("|")
        .map((part) => part.trim());
      if (!organization_name || !endpoint) {
        throw new Error("Each contact line needs at least Organization | Role | email.");
      }
      const lat = latitude ? Number(latitude) : undefined;
      const lon = longitude ? Number(longitude) : undefined;
      return {
        organization_name,
        role_title: role_title || "Public or business inquiry contact",
        endpoint,
        geography: geography || undefined,
        source: source || "operator_supplied",
        source_public: true,
        business_only: true,
        confidence: 0.8,
        location:
          lat !== undefined && lon !== undefined && Number.isFinite(lat) && Number.isFinite(lon)
            ? { latitude: lat, longitude: lon, label: organization_name, precision: "public_office" }
            : undefined,
      };
    });
}

function sampleRequirements(packId: string): Record<string, unknown> {
  const samples: Record<string, Record<string, unknown>> = {
    facilities_quote: { service: "commercial HVAC maintenance", property_count: 5, minimum_quotes: 2 },
    local_services_quote: {
      service: "weekly lawn mowing",
      geography: "Pittsburgh, Pennsylvania",
      lawn_area_sqft: 9500,
      scope: ["mowing", "edging", "blowing"],
      requested_start: "within 14 days",
      minimum_quotes: 2,
    },
    bpo_quote: {
      service: "bilingual customer support",
      seats: 30,
      languages: ["English", "Spanish"],
      coverage: "24x7",
      start_window: "45 days",
      minimum_quotes: 2,
    },
    staffing_procurement: {
      roles: "warehouse associates",
      workers: 20,
      geography: "Allentown, Pennsylvania",
      shift: "second shift",
      start_window: "three weeks",
      temp_to_hire: true,
      minimum_quotes: 2,
    },
    employment_agency_audit: {
      geography: "Example metropolitan area",
      research_purpose: "public employment-practice comparison",
      scenario: "Public inquiry about a currently advertised warehouse role",
    },
    lender_disclosure_audit: {
      geography: "Example State",
      research_purpose: "institutional public disclosure audit",
      scenario: "$300 principal for 14 days",
    },
    contractor_license_audit: {
      geography: "Example State",
      trade: "commercial roofing",
      research_purpose: "public authorization and practice verification",
    },
    informal_business_verification: {
      geography: "Example market",
      service: "lawn and grounds maintenance",
      research_purpose: "business identity and service verification",
    },
    franchise_service_audit: {
      brand_or_category: "hotel",
      geography: "Example market",
      standardized_scenario: "One-night public rate and fee inquiry",
      research_purpose: "location-level price and policy comparison",
    },
    civic_intelligence: { geography: "Pike County, Pennsylvania", purpose: "public organization routing" },
    business_record_verification: { record_type: "public business location", jurisdiction: "Pennsylvania" },
  };
  return samples[packId] ?? {};
}

function newDraft(pack: Pack | undefined): NewCaseDraft {
  const selected = pack;
  return {
    pack: selected?.id ?? "facilities_quote",
    title: selected ? `${selected.name} case` : "New SourceLoop case",
    objective: selected?.message_purpose ? titleize(selected.message_purpose) : "Obtain current direct-source information.",
    requesterName: "",
    requesterEmail: "",
    requirements: JSON.stringify(sampleRequirements(selected?.id ?? "facilities_quote"), null, 2),
    contacts: "",
    acknowledgements: Object.fromEntries((selected?.required_acknowledgements ?? []).map((key) => [key, false])),
  };
}

function StateDot({ state }: { state: string }) {
  return <span className={`state-dot state-${state}`} aria-hidden="true" />;
}

function RiskBadge({ risk }: { risk: string }) {
  return <span className={`risk-badge risk-${risk}`}>{titleize(risk)}</span>;
}

function SpatialView({ selected, features }: { selected: CaseRecord; features: FeatureCollection }) {
  const points = features.features.filter(
    (feature) => feature.id === selected.id || feature.properties.case_id === selected.id,
  );
  if (!points.length) {
    return <div className="empty-card">Add case and contact coordinates to materialize the GIS projection.</div>;
  }
  const xs = points.map((point) => point.geometry.coordinates[0]);
  const ys = points.map((point) => point.geometry.coordinates[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const projectX = (value: number) => 42 + ((value - minX) / Math.max(maxX - minX, 0.01)) * 516;
  const projectY = (value: number) => 258 - ((value - minY) / Math.max(maxY - minY, 0.01)) * 216;
  const casePoint = points.find((point) => point.id === selected.id);

  return (
    <div className="map-shell">
      <svg viewBox="0 0 600 300" role="img" aria-label="Case and contact spatial projection">
        <defs>
          <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M 24 0 L 0 0 0 24" className="map-grid" fill="none" />
          </pattern>
        </defs>
        <rect x="0" y="0" width="600" height="300" fill="url(#grid)" rx="18" />
        {casePoint &&
          points
            .filter((point) => point.id !== selected.id)
            .map((point) => (
              <line
                key={`line-${point.id}`}
                x1={projectX(casePoint.geometry.coordinates[0])}
                y1={projectY(casePoint.geometry.coordinates[1])}
                x2={projectX(point.geometry.coordinates[0])}
                y2={projectY(point.geometry.coordinates[1])}
                className="map-link"
              />
            ))}
        {points.map((point) => {
          const isCase = point.id === selected.id;
          return (
            <g key={point.id}>
              <circle
                cx={projectX(point.geometry.coordinates[0])}
                cy={projectY(point.geometry.coordinates[1])}
                r={isCase ? 10 : 7}
                className={isCase ? "map-case" : "map-contact"}
              />
              <text
                x={projectX(point.geometry.coordinates[0]) + 12}
                y={projectY(point.geometry.coordinates[1]) - 10}
                className="map-label"
              >
                {String(point.properties.label ?? point.id).slice(0, 34)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function ProgressBar({ ratio }: { ratio: number }) {
  return (
    <div className="progress-track" aria-label={`${Math.round(ratio * 100)}% field coverage`}>
      <span style={{ width: `${Math.max(0, Math.min(100, ratio * 100))}%` }} />
    </div>
  );
}

export default function App() {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [packs, setPacks] = useState<Pack[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [features, setFeatures] = useState<FeatureCollection>({ type: "FeatureCollection", features: [] });
  const [runtime, setRuntime] = useState<RuntimeInfo>();
  const [report, setReport] = useState<CaseReport>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [showCreate, setShowCreate] = useState(false);
  const [showRegistry, setShowRegistry] = useState(false);
  const [draft, setDraft] = useState<NewCaseDraft>(newDraft(undefined));
  const [registryDraft, setRegistryDraft] = useState<RegistryDraft>(emptyRegistry);
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  const refresh = useCallback(async () => {
    const [caseRows, mapRows, info, packRows] = await Promise.all([
      request<CaseRecord[]>("/api/v1/cases"),
      request<FeatureCollection>("/api/v1/map/features"),
      request<RuntimeInfo>("/api/v1/runtime"),
      request<Pack[]>("/api/v1/packs"),
    ]);
    setCases(caseRows);
    setFeatures(mapRows);
    setRuntime(info);
    setPacks(packRows);
    setSelectedId((current) => current ?? caseRows[0]?.id);
  }, []);

  useEffect(() => {
    refresh().catch((reason: Error) => setError(reason.message));
    const interval = window.setInterval(() => refresh().catch(() => undefined), 12_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const selected = useMemo(
    () => cases.find((candidate) => candidate.id === selectedId) ?? cases[0],
    [cases, selectedId],
  );
  const selectedPack = useMemo(
    () => packs.find((pack) => pack.id === selected?.pack),
    [packs, selected?.pack],
  );
  const draftPack = useMemo(() => packs.find((pack) => pack.id === draft.pack), [packs, draft.pack]);

  useEffect(() => {
    if (!selected) {
      setReport(undefined);
      return;
    }
    request<CaseReport>(`/api/v1/cases/${selected.id}/report`)
      .then(setReport)
      .catch(() => setReport(undefined));
  }, [selected?.id, selected?.updated_at]);

  const execute = async (operation: () => Promise<unknown>) => {
    setBusy(true);
    setError(undefined);
    try {
      await operation();
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  const choosePack = (packId: string) => {
    const pack = packs.find((candidate) => candidate.id === packId);
    setDraft((current) => ({
      ...newDraft(pack),
      requesterName: current.requesterName,
      requesterEmail: current.requesterEmail,
    }));
  };

  const createDemo = () =>
    execute(async () => {
      const created = await request<CaseRecord>("/api/v1/cases", {
        method: "POST",
        body: JSON.stringify({
          title: "Pittsburgh local lawn-service market",
          kind: "quote_intelligence",
          pack: "local_services_quote",
          objective:
            "Obtain comparable non-binding pricing, availability, scope, surcharges, payment terms, and validity.",
          requester_name: "Demo Property Team",
          requester_email: "demo@example.test",
          demo: true,
          location: {
            latitude: 40.4406,
            longitude: -79.9959,
            label: "Pittsburgh demonstration property",
            precision: "public_venue",
          },
          requirements: sampleRequirements("local_services_quote"),
          governance_acknowledgements: { authorized_requester: true, research_only: true },
        }),
      });
      setSelectedId(created.id);
      await request(`/api/v1/cases/${created.id}/run`, { method: "POST" });
    });

  const createCustom = (event: FormEvent) => {
    event.preventDefault();
    return execute(async () => {
      if (!draftPack) throw new Error("Select a valid investigation pack.");
      const requirements = JSON.parse(draft.requirements || "{}") as Record<string, unknown>;
      const contacts = parseContacts(draft.contacts);
      const created = await request<CaseRecord>("/api/v1/cases", {
        method: "POST",
        body: JSON.stringify({
          title: draft.title,
          kind: draftPack.case_kind,
          pack: draftPack.id,
          investigation_mode: draftPack.investigation_mode || undefined,
          objective: draft.objective,
          requester_name: draft.requesterName,
          requester_email: draft.requesterEmail || undefined,
          demo: false,
          requirements,
          contacts,
          governance_acknowledgements: draft.acknowledgements,
        }),
      });
      setSelectedId(created.id);
      setShowCreate(false);
      setDraft(newDraft(packs[0]));
      await request(`/api/v1/cases/${created.id}/run`, { method: "POST" });
    });
  };

  const runSelected = () =>
    selected && execute(() => request(`/api/v1/cases/${selected.id}/run`, { method: "POST" }));

  const approveAction = (actionId: string) =>
    selected &&
    execute(() =>
      request(`/api/v1/cases/${selected.id}/actions/${actionId}/approve`, {
        method: "POST",
        body: JSON.stringify({ approver: "console-operator", note: "Reviewed in SourceLoop console" }),
      }),
    );

  const rejectAction = (actionId: string) =>
    selected &&
    execute(() =>
      request(`/api/v1/cases/${selected.id}/actions/${actionId}/reject`, {
        method: "POST",
        body: JSON.stringify({ approver: "console-operator", note: "Rejected in SourceLoop console" }),
      }),
    );

  const approveAllAndDispatch = () =>
    selected &&
    execute(async () => {
      const pending = selected.actions.filter((action) => action.status === "pending");
      for (const action of pending) {
        await request(`/api/v1/cases/${selected.id}/actions/${action.id}/approve`, {
          method: "POST",
          body: JSON.stringify({ approver: "console-operator", note: "Bulk-reviewed in SourceLoop console" }),
        });
      }
      await request(`/api/v1/cases/${selected.id}/dispatch`, { method: "POST" });
    });

  const dispatchApproved = () =>
    selected && execute(() => request(`/api/v1/cases/${selected.id}/dispatch`, { method: "POST" }));

  const syncMailbox = () => execute(() => request("/api/v1/mailbox/sync", { method: "POST" }));

  const simulateReplies = () =>
    selected && execute(() => request(`/api/v1/demo/${selected.id}/replies`, { method: "POST" }));

  const reviewFinding = (findingId: string, status: string) =>
    selected &&
    execute(() =>
      request(`/api/v1/cases/${selected.id}/findings/${findingId}/review`, {
        method: "POST",
        body: JSON.stringify({
          status,
          reviewer: "console-operator",
          notes: `Marked ${status} in SourceLoop console.`,
        }),
      }),
    );

  const addRegistryCheck = (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return Promise.resolve();
    return execute(async () => {
      await request(`/api/v1/cases/${selected.id}/registry-checks`, {
        method: "POST",
        body: JSON.stringify({
          registry: registryDraft.registry,
          query: registryDraft.query,
          subject_id: registryDraft.subjectId || undefined,
          status: registryDraft.status,
          identifier: registryDraft.identifier || undefined,
          entity_name: registryDraft.entityName || undefined,
          jurisdiction: registryDraft.jurisdiction || undefined,
          source: registryDraft.source || undefined,
          notes: registryDraft.notes,
        }),
      });
      setShowRegistry(false);
      setRegistryDraft(emptyRegistry);
    });
  };

  const pendingActions = selected?.actions.filter((action) => action.status === "pending").length ?? 0;
  const approvedActions = selected?.actions.filter((action) => action.status === "approved").length ?? 0;
  const dispatchedActions = selected?.actions.filter((action) => action.status === "dispatched").length ?? 0;
  const openFindings = selected?.findings.filter((finding) => finding.status === "open").length ?? 0;
  const realMail = runtime?.email_mode === "smtp" && runtime.external_send_enabled;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-mark">SL</span>
          <div>
            <p className="eyebrow">ACTIVE MARKET INTELLIGENCE OS</p>
            <h1>SourceLoop Investigate</h1>
          </div>
        </div>
        <div className="runtime-badges">
          <span><StateDot state="active" />{runtime?.agent_runtime ?? "loading"} brain</span>
          <span><StateDot state={runtime?.mailbox_enabled ? "active" : "muted"} />{runtime?.mailbox_mode ?? "—"} inbox</span>
          <span><StateDot state={realMail ? "warning" : "safe"} />{runtime?.email_mode ?? "—"} outbound</span>
          <span>{runtime?.pack_count ?? packs.length} packs</span>
          <button className="secondary compact" disabled={busy} onClick={createDemo}>Run market demo</button>
          <button className="primary compact" disabled={busy} onClick={() => setShowCreate(true)}>New case</button>
        </div>
      </header>

      <div className={realMail ? "safety-banner live" : "safety-banner"}>
        <strong>{realMail ? "Live SMTP is enabled." : "External delivery is locked."}</strong>
        <span>
          {realMail
            ? "Only human-approved, policy-cleared business outreach can leave the container."
            : "Approved messages are preserved in the dry-run outbox without public delivery."}
        </span>
      </div>
      {error && <div className="error-banner"><strong>Operation failed</strong><span>{error}</span></div>}

      <main className="workspace">
        <aside className="case-list panel">
          <div className="panel-heading">
            <div><p className="eyebrow">CASE QUEUE</p><h2>{cases.length} records</h2></div>
            <button className="ghost" disabled={busy} onClick={() => refresh()}>Refresh</button>
          </div>
          <div className="case-scroll">
            {cases.length === 0 && (
              <div className="empty-state">
                <strong>No cases yet</strong>
                <span>Launch a safe demo or create an approval-gated investigation.</span>
              </div>
            )}
            {cases.map((item) => (
              <button
                key={item.id}
                className={`case-card ${item.id === selected?.id ? "selected" : ""}`}
                onClick={() => setSelectedId(item.id)}
              >
                <div className="case-card-top">
                  <span className="case-kind">{titleize(item.pack ?? item.kind)}</span>
                  <RiskBadge risk={item.risk_tier} />
                </div>
                <strong>{item.title}</strong>
                <span className="case-meta">{titleize(item.stage)} · {titleize(item.status)}</span>
                <div className="micro-metrics">
                  <span>{item.interactions.length} messages</span>
                  <span>{item.quotes.length} quotes</span>
                  <span>{item.findings.length} findings</span>
                </div>
              </button>
            ))}
          </div>
          <div className="worker-card">
            <div><span className="eyebrow">MAIL WORKER</span><strong>{runtime?.worker?.status ? titleize(runtime.worker.status) : "No heartbeat"}</strong></div>
            <span>{runtime?.worker ? formatDate(runtime.worker.updated_at) : "Start the worker container to monitor replies."}</span>
            {runtime?.mailbox_enabled && <button className="secondary" disabled={busy} onClick={syncMailbox}>Sync mailbox now</button>}
          </div>
        </aside>

        <section className="main-column">
          {!selected ? (
            <section className="panel empty-main">
              <span className="hero-chip">Unknown → Question → Conversation → Evidence → Market Graph</span>
              <h2>Ask the market what passive data cannot tell you.</h2>
              <p>
                SourceLoop compiles standardized scenarios, runs scoped specialist swarms, contacts a small
                approved business panel, monitors replies, asks bounded clarifications, calculates transparent
                metrics, and preserves every conclusion beside its evidence.
              </p>
              <div className="hero-actions">
                <button className="primary" onClick={() => setShowCreate(true)} disabled={busy}>Create investigation</button>
                <button className="secondary" onClick={createDemo} disabled={busy}>Exercise safe demo</button>
              </div>
            </section>
          ) : (
            <>
              <section className="panel case-header">
                <div>
                  <div className="status-row">
                    <span className={`status-pill status-${selected.status}`}>{titleize(selected.status)}</span>
                    <RiskBadge risk={selected.risk_tier} />
                    <span>{titleize(selected.investigation_mode ?? selected.kind)}</span>
                    <span>{selected.demo ? "demonstration" : "live case"}</span>
                  </div>
                  <h2>{selected.title}</h2>
                  <p>{selected.objective}</p>
                  {selectedPack && <p className="pack-description">{selectedPack.description}</p>}
                </div>
                <div className="case-actions">
                  <button className="secondary" disabled={busy || selected.status !== "active"} onClick={runSelected}>Run practitioner</button>
                  <button className="primary" disabled={busy || pendingActions === 0} onClick={approveAllAndDispatch}>
                    Approve + {realMail ? "send" : "capture"} {pendingActions || ""}
                  </button>
                  <button className="secondary" disabled={busy || approvedActions === 0} onClick={dispatchApproved}>Dispatch approved</button>
                  <button className="secondary" disabled={busy || dispatchedActions === 0 || !selected.demo} onClick={simulateReplies}>Simulate replies</button>
                </div>
              </section>

              <section className="panel practitioner">
                <div className="panel-heading">
                  <div><p className="eyebrow">PRACTITIONER RECEIPT</p><h2>Nine-stage execution rail</h2></div>
                  <span className="target">Target: {selected.completion_target} complete result(s)</span>
                </div>
                <div className="stage-rail">
                  {stages.map((stage, index) => {
                    const current = stages.indexOf(selected.stage);
                    const state = index < current || selected.status === "completed" ? "done" : index === current ? "current" : "future";
                    return (
                      <div className={`stage ${state}`} key={stage}>
                        <span className="stage-index">{index + 1}</span>
                        <span>{titleize(stage)}</span>
                      </div>
                    );
                  })}
                </div>
              </section>

              <nav className="tabbar panel" aria-label="Case detail sections">
                {(["overview", "outreach", "intelligence", "evidence", "agents"] as Tab[]).map((tab) => (
                  <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
                    {titleize(tab)}
                    {tab === "intelligence" && openFindings > 0 && <span className="tab-count">{openFindings}</span>}
                  </button>
                ))}
              </nav>

              {activeTab === "overview" && (
                <div className="content-grid">
                  <section className="panel metric-panel full-span">
                    <p className="eyebrow">CASE TELEMETRY</p>
                    <div className="metric-grid">
                      <div><strong>{selected.contacts.length}</strong><span>counterparties</span></div>
                      <div><strong>{selected.interactions.length}</strong><span>messages</span></div>
                      <div><strong>{selected.quotes.length}</strong><span>quotes</span></div>
                      <div><strong>{selected.findings.length}</strong><span>findings</span></div>
                      <div><strong>{openFindings}</strong><span>open review</span></div>
                      <div><strong>{selected.agent_runs.length}</strong><span>agent receipts</span></div>
                    </div>
                  </section>
                  <section className="panel map-panel">
                    <div className="panel-heading">
                      <div><p className="eyebrow">GIS PROJECTION</p><h2>Market terrain</h2></div>
                      <span className="target">{selected.contacts.filter((contact) => contact.location).length} geocoded routes</span>
                    </div>
                    <SpatialView selected={selected} features={features} />
                  </section>
                  <section className="panel contacts-panel">
                    <div className="panel-heading"><div><p className="eyebrow">CONTACT ROUTES</p><h2>Selected panel</h2></div></div>
                    <div className="stack-list">
                      {selected.contacts.length === 0 && <div className="empty-card">Waiting for public or customer-authorized business contacts.</div>}
                      {selected.contacts.map((contact) => (
                        <article className="route-card" key={contact.id}>
                          <div><strong>{contact.organization_name}</strong><span>{contact.role_title}</span></div>
                          <code>{contact.endpoint}</code>
                          <div className="route-meta">
                            <span>{contact.geography ?? "geography not supplied"}</span>
                            <span>{Math.round(contact.confidence * 100)}% confidence</span>
                            <span>{contact.source_public ? "public route" : "private route"}</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                  <section className="panel coverage-panel full-span">
                    <div className="panel-heading"><div><p className="eyebrow">FIELD COVERAGE</p><h2>What each respondent actually answered</h2></div></div>
                    <div className="coverage-grid">
                      {(report?.response_coverage ?? []).map((row) => (
                        <article className="coverage-card" key={row.endpoint}>
                          <div className="coverage-head"><strong>{row.endpoint}</strong><span>{Math.round(row.coverage_ratio * 100)}%</span></div>
                          <ProgressBar ratio={row.coverage_ratio} />
                          <small>{row.covered.length} fields covered · {row.missing_critical.length} critical gaps</small>
                          {row.missing_critical.length > 0 && <div className="tag-row">{row.missing_critical.map((field) => <span className="tag warning" key={field}>{titleize(field)}</span>)}</div>}
                        </article>
                      ))}
                      {(report?.response_coverage.length ?? 0) === 0 && <div className="empty-card">Coverage appears after the first direct response.</div>}
                    </div>
                  </section>
                </div>
              )}

              {activeTab === "outreach" && (
                <div className="content-grid">
                  <section className="panel actions-panel full-span">
                    <div className="panel-heading"><div><p className="eyebrow">ACTION LEDGER</p><h2>Exact messages and approvals</h2></div><span className="target">{pendingActions} pending · {approvedActions} approved</span></div>
                    <div className="stack-list">
                      {selected.actions.length === 0 && <div className="empty-card">Run the practitioner after supplying contacts to create outreach proposals.</div>}
                      {selected.actions.map((action) => (
                        <article className="action-card" key={action.id}>
                          <div className="action-top">
                            <div><span className={`status-pill status-${action.status}`}>{titleize(action.status)}</span>{action.followup && <span className="tag">Clarification</span>}</div>
                            <code>{action.recipient}</code>
                          </div>
                          <h3>{action.subject}</h3>
                          <pre>{action.body}</pre>
                          <div className="row-actions">
                            <button className="primary" disabled={busy || action.status !== "pending"} onClick={() => approveAction(action.id)}>Approve</button>
                            <button className="danger-button" disabled={busy || !["pending", "approved"].includes(action.status)} onClick={() => rejectAction(action.id)}>Reject</button>
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                  <section className="panel interactions-panel full-span">
                    <div className="panel-heading"><div><p className="eyebrow">CONVERSATIONS</p><h2>Thread and evidence timeline</h2></div></div>
                    <div className="timeline">
                      {selected.interactions.length === 0 && <div className="empty-card">No messages have been recorded.</div>}
                      {selected.interactions.map((interaction) => (
                        <article className={`interaction ${interaction.direction}`} key={interaction.id}>
                          <div className="interaction-marker"><StateDot state={interaction.direction === "inbound" ? "safe" : "active"} /></div>
                          <div className="interaction-body">
                            <div className="interaction-head"><strong>{titleize(interaction.direction)}</strong><span>{formatDate(interaction.created_at)}</span></div>
                            <h3>{interaction.subject}</h3>
                            <p>{interaction.body}</p>
                            <div className="tag-row">
                              <span className="tag">{interaction.endpoint}</span>
                              <span className="tag">evidence {interaction.evidence_id.slice(-8)}</span>
                              {interaction.attachments.map((attachment) => <span className="tag" key={attachment.filename}>{attachment.filename} · {attachment.status}</span>)}
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                </div>
              )}

              {activeTab === "intelligence" && (
                <div className="content-grid">
                  <section className="panel quote-panel full-span">
                    <div className="panel-heading"><div><p className="eyebrow">LIVE MARKET PRICING</p><h2>Normalized quotes and price bands</h2></div></div>
                    {Object.keys(report?.market_prices ?? {}).length > 0 && (
                      <div className="price-band-grid">
                        {Object.entries(report?.market_prices ?? {}).map(([unit, stats]) => (
                          <article className="price-band" key={unit}>
                            <span>{unit}</span><strong>{stats.median.toLocaleString()}</strong>
                            <small>{stats.minimum.toLocaleString()} min · {stats.maximum.toLocaleString()} max · n={stats.count}</small>
                          </article>
                        ))}
                      </div>
                    )}
                    <div className="quote-grid">
                      {selected.quotes.length === 0 && <div className="empty-card">No comparable quote has been extracted yet.</div>}
                      {selected.quotes.map((quote) => (
                        <article className="quote-card" key={quote.id}>
                          <div className="quote-head"><div><strong>{quote.supplier_name}</strong><span>{Math.round(quote.extraction_confidence * 100)}% extraction confidence</span></div><b>${quoteTotal(quote).toLocaleString()}</b></div>
                          <div className="quote-lines">
                            {quote.line_items.map((line, index) => (
                              <div key={`${quote.id}-${index}`}><span>{line.description}</span><strong>{line.currency} {line.unit_price.toLocaleString()} / {titleize(line.unit)}</strong></div>
                            ))}
                          </div>
                          <div className="tag-row">
                            {quote.unresolved_fields.map((field) => <span className="tag warning" key={field}>{titleize(field)}</span>)}
                            {quote.exclusions.map((value) => <span className="tag" key={value}>{value}</span>)}
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                  <section className="panel findings-panel full-span">
                    <div className="panel-heading">
                      <div><p className="eyebrow">INVESTIGATION FINDINGS</p><h2>Reviewable signals, not automatic verdicts</h2></div>
                      <button className="secondary" onClick={() => setShowRegistry(true)}>Add registry check</button>
                    </div>
                    <p className="notice">{report?.interpretation_notice}</p>
                    <div className="finding-grid">
                      {selected.findings.length === 0 && <div className="empty-card">Findings appear after replies or registry checks.</div>}
                      {selected.findings.map((finding) => (
                        <article className={`finding-card severity-${finding.severity}`} key={finding.id}>
                          <div className="finding-head">
                            <div><span className={`severity-pill severity-${finding.severity}`}>{titleize(finding.severity)}</span><span className="tag">{titleize(finding.kind)}</span></div>
                            <span className={`status-pill status-${finding.status}`}>{titleize(finding.status)}</span>
                          </div>
                          <h3>{finding.title}</h3>
                          <p>{finding.summary}</p>
                          {finding.value !== null && finding.value !== undefined && <pre className="value-block">{JSON.stringify(finding.value, null, 2)}</pre>}
                          <div className="finding-meta"><span>{Math.round(finding.confidence * 100)}% confidence</span><span>{finding.source_scope}</span><span>{finding.evidence_ids.length} evidence link(s)</span></div>
                          {finding.review_notes && <small className="review-note">{finding.review_notes}</small>}
                          {finding.status === "open" && (
                            <div className="row-actions">
                              <button className="secondary" disabled={busy} onClick={() => reviewFinding(finding.id, "corroborated")}>Corroborate</button>
                              <button className="secondary" disabled={busy} onClick={() => reviewFinding(finding.id, "resolved")}>Resolve</button>
                              <button className="ghost" disabled={busy} onClick={() => reviewFinding(finding.id, "dismissed")}>Dismiss</button>
                            </div>
                          )}
                        </article>
                      ))}
                    </div>
                    <div className="registry-list">
                      {selected.registry_checks.map((check) => (
                        <article className="registry-card" key={check.id}>
                          <div><strong>{check.registry}</strong><span>{check.query}</span></div>
                          <span className={`status-pill status-${check.status}`}>{titleize(check.status)}</span>
                          <small>{check.identifier ?? "No identifier"} · {formatDate(check.checked_at)}</small>
                        </article>
                      ))}
                    </div>
                  </section>
                </div>
              )}

              {activeTab === "evidence" && (
                <div className="content-grid">
                  <section className="panel evidence-panel full-span">
                    <div className="panel-heading">
                      <div><p className="eyebrow">REPORTING</p><h2>Evidence-linked deliverables</h2></div>
                      <div className="row-actions">
                        <a className="button-link secondary" href={`${API}/api/v1/cases/${selected.id}/report`} target="_blank" rel="noreferrer">Open JSON</a>
                        <a className="button-link primary" href={`${API}/api/v1/cases/${selected.id}/report.csv`}>Download CSV</a>
                      </div>
                    </div>
                    <div className="report-grid">
                      <div><span>Response rate</span><strong>{Math.round(Number(report?.activity.response_rate ?? 0) * 100)}%</strong></div>
                      <div><span>Completion quality</span><strong>{titleize(String(report?.results.completion_quality ?? "in progress"))}</strong></div>
                      <div><span>Evidence objects</span><strong>{report?.evidence_ids.length ?? 0}</strong></div>
                      <div><span>Registry checks</span><strong>{selected.registry_checks.length}</strong></div>
                    </div>
                    <h3>Evidence IDs</h3>
                    <div className="evidence-list">
                      {(report?.evidence_ids ?? []).map((evidence) => <code key={evidence}>{evidence}</code>)}
                      {(report?.evidence_ids.length ?? 0) === 0 && <div className="empty-card">Evidence identifiers appear after interactions, findings, or quotes.</div>}
                    </div>
                    <h3>Governance receipt</h3>
                    <pre className="governance-block">{JSON.stringify(selected.governance, null, 2)}</pre>
                  </section>
                </div>
              )}

              {activeTab === "agents" && (
                <section className="panel runs-panel">
                  <div className="panel-heading"><div><p className="eyebrow">SWARM RECEIPTS</p><h2>Internal specialist execution</h2></div><span className="target">{selected.agent_runs.length} runs</span></div>
                  <div className="run-grid">
                    {selected.agent_runs.map((run) => (
                      <article className="run-card" key={run.id}>
                        <div><StateDot state={run.status === "succeeded" ? "safe" : run.status === "failed" ? "warning" : "active"} /><strong>{titleize(run.role)}</strong></div>
                        <span>{titleize(run.stage)}</span><span>{run.runtime}</span><span>{formatDate(run.finished_at ?? run.started_at)}</span>
                        {run.error && <small>{run.error}</small>}
                      </article>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </section>
      </main>

      {showCreate && (
        <div className="modal-backdrop" onMouseDown={() => setShowCreate(false)}>
          <form className="modal large-modal" onSubmit={createCustom} onMouseDown={(event: { stopPropagation(): void }) => event.stopPropagation()}>
            <div className="modal-header"><div><p className="eyebrow">NEW GOVERNED CASE</p><h2>Configure direct-source acquisition</h2></div><button type="button" className="ghost" onClick={() => setShowCreate(false)}>Close</button></div>
            <div className="modal-grid">
              <label className="full-field"><span>Investigation pack</span><select value={draft.pack} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => choosePack(event.target.value)} required><option value="">Select a pack</option>{packs.map((pack) => <option key={pack.id} value={pack.id}>{pack.name} · {titleize(pack.risk_tier)}</option>)}</select></label>
              {draftPack && (
                <div className={`pack-preview full-field risk-panel risk-panel-${draftPack.risk_tier}`}>
                  <div><RiskBadge risk={draftPack.risk_tier} /><strong>{titleize(draftPack.investigation_mode ?? draftPack.case_kind)}</strong>{draftPack.institutional_only && <span className="tag warning">Institutional only</span>}</div>
                  <p>{draftPack.description}</p>
                  <small>{draftPack.max_contacts} contacts · {draftPack.max_followups} follow-up(s) · {draftPack.response_fields.length} response fields</small>
                </div>
              )}
              <label className="full-field"><span>Case title</span><input value={draft.title} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setDraft({ ...draft, title: event.target.value })} required /></label>
              <label className="full-field"><span>Objective</span><textarea rows={3} value={draft.objective} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setDraft({ ...draft, objective: event.target.value })} required /></label>
              <label><span>Truthful requester name</span><input value={draft.requesterName} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setDraft({ ...draft, requesterName: event.target.value })} required /></label>
              <label><span>Requester email</span><input type="email" value={draft.requesterEmail} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setDraft({ ...draft, requesterEmail: event.target.value })} required={draftPack?.requires_requester_email} /></label>
              <label className="full-field"><span>Requirements JSON</span><textarea className="code-input" rows={11} value={draft.requirements} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setDraft({ ...draft, requirements: event.target.value })} required /><small>Required fields: {(draftPack?.required_fields ?? []).join(", ") || "none"}</small></label>
              <label className="full-field"><span>Public/business contacts</span><textarea className="code-input" rows={5} value={draft.contacts} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setDraft({ ...draft, contacts: event.target.value })} placeholder="Organization | Role | email | Geography | latitude | longitude | source" /><small>One contact per line. Elevated and restricted packs accept only public or customer-authorized routes.</small></label>
              {(draftPack?.required_acknowledgements.length ?? 0) > 0 && (
                <fieldset className="acknowledgements full-field">
                  <legend>Required governance acknowledgements</legend>
                  {draftPack?.required_acknowledgements.map((key) => (
                    <label className="check-row" key={key}>
                      <input type="checkbox" checked={Boolean(draft.acknowledgements[key])} onChange={(event: ChangeEvent<HTMLInputElement>) => setDraft({ ...draft, acknowledgements: { ...draft.acknowledgements, [key]: event.target.checked } })} />
                      <span>{titleize(key)}</span>
                    </label>
                  ))}
                </fieldset>
              )}
            </div>
            <div className="modal-actions"><button type="button" className="ghost" onClick={() => setShowCreate(false)}>Cancel</button><button type="submit" className="primary" disabled={busy}>Create and run practitioner</button></div>
          </form>
        </div>
      )}

      {showRegistry && selected && (
        <div className="modal-backdrop" onMouseDown={() => setShowRegistry(false)}>
          <form className="modal" onSubmit={addRegistryCheck} onMouseDown={(event: { stopPropagation(): void }) => event.stopPropagation()}>
            <div className="modal-header"><div><p className="eyebrow">CORROBORATION</p><h2>Add registry check</h2></div><button type="button" className="ghost" onClick={() => setShowRegistry(false)}>Close</button></div>
            <div className="modal-grid">
              <label><span>Registry</span><input value={registryDraft.registry} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRegistryDraft({ ...registryDraft, registry: event.target.value })} required /></label>
              <label><span>Status</span><select value={registryDraft.status} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRegistryDraft({ ...registryDraft, status: event.target.value })}><option value="matched">Matched</option><option value="verified">Verified</option><option value="not_found">Not found</option><option value="inactive">Inactive</option><option value="expired">Expired</option><option value="unverified">Unverified</option></select></label>
              <label className="full-field"><span>Query</span><input value={registryDraft.query} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRegistryDraft({ ...registryDraft, query: event.target.value })} required /></label>
              <label><span>Subject/contact ID</span><input value={registryDraft.subjectId} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRegistryDraft({ ...registryDraft, subjectId: event.target.value })} /></label>
              <label><span>Identifier</span><input value={registryDraft.identifier} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRegistryDraft({ ...registryDraft, identifier: event.target.value })} /></label>
              <label><span>Entity name</span><input value={registryDraft.entityName} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRegistryDraft({ ...registryDraft, entityName: event.target.value })} /></label>
              <label><span>Jurisdiction</span><input value={registryDraft.jurisdiction} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRegistryDraft({ ...registryDraft, jurisdiction: event.target.value })} /></label>
              <label className="full-field"><span>Official source</span><input value={registryDraft.source} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRegistryDraft({ ...registryDraft, source: event.target.value })} /></label>
              <label className="full-field"><span>Notes</span><textarea rows={3} value={registryDraft.notes} onChange={(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRegistryDraft({ ...registryDraft, notes: event.target.value })} /></label>
            </div>
            <div className="modal-actions"><button type="button" className="ghost" onClick={() => setShowRegistry(false)}>Cancel</button><button type="submit" className="primary" disabled={busy}>Record registry result</button></div>
          </form>
        </div>
      )}
    </div>
  );
}
