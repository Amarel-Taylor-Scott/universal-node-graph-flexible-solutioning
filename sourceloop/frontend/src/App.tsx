import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

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

type GeoPoint = {
  latitude: number;
  longitude: number;
  label: string;
  precision?: string;
};

type Contact = {
  id: string;
  organization_name: string;
  role_title: string;
  endpoint: string;
  confidence: number;
  geography?: string;
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
  error?: string;
};

type Claim = {
  id: string;
  predicate: string;
  value: unknown;
  kind: string;
  confidence: number;
  corroboration_status: string;
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
};

type Interaction = {
  id: string;
  direction: string;
  endpoint: string;
  subject: string;
  thread_id: string;
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
  pack?: string;
  stage: Stage;
  status: string;
  demo: boolean;
  location?: GeoPoint;
  completion_target: number;
  contacts: Contact[];
  actions: Action[];
  agent_runs: AgentRun[];
  claims: Claim[];
  quotes: Quote[];
  interactions: Interaction[];
  updated_at: string;
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
  worker?: WorkerInfo;
};

type NewCaseDraft = {
  title: string;
  kind: "quote_intelligence" | "civic_intelligence" | "data_verification";
  pack: string;
  objective: string;
  requesterName: string;
  requesterEmail: string;
  requirements: string;
  contacts: string;
};

const initialDraft: NewCaseDraft = {
  title: "",
  kind: "quote_intelligence",
  pack: "facilities_quote",
  objective: "",
  requesterName: "",
  requesterEmail: "",
  requirements: '{\n  "service": "commercial HVAC maintenance",\n  "minimum_quotes": 2\n}',
  contacts: "",
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

function titleize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function quoteTotal(quote: Quote): number {
  return quote.line_items.reduce((total, line) => total + (line.quantity ?? 1) * line.unit_price, 0);
}

function formatDate(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}

function parseContacts(raw: string): Array<Record<string, unknown>> {
  if (!raw.trim()) return [];
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [organization_name, role_title, endpoint, geography, latitude, longitude] = line
        .split("|")
        .map((part) => part.trim());
      if (!organization_name || !endpoint) {
        throw new Error("Each contact line needs at least: Organization | Role | email");
      }
      const lat = latitude ? Number(latitude) : undefined;
      const lon = longitude ? Number(longitude) : undefined;
      return {
        organization_name,
        role_title: role_title || "Public or business inquiry contact",
        endpoint,
        geography: geography || undefined,
        source: "operator_supplied",
        source_public: true,
        confidence: 0.8,
        location:
          lat !== undefined && lon !== undefined && Number.isFinite(lat) && Number.isFinite(lon)
            ? { latitude: lat, longitude: lon, label: organization_name, precision: "public_office" }
            : undefined,
      };
    });
}

function StateDot({ state }: { state: string }) {
  return <span className={`state-dot state-${state}`} aria-hidden="true" />;
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
  const projectX = (value: number) => 38 + ((value - minX) / Math.max(maxX - minX, 0.01)) * 524;
  const projectY = (value: number) => 262 - ((value - minY) / Math.max(maxY - minY, 0.01)) * 224;
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

export default function App() {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [features, setFeatures] = useState<FeatureCollection>({ type: "FeatureCollection", features: [] });
  const [runtime, setRuntime] = useState<RuntimeInfo>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [showCreate, setShowCreate] = useState(false);
  const [draft, setDraft] = useState<NewCaseDraft>(initialDraft);
  const [activeTab, setActiveTab] = useState<"overview" | "outreach" | "intelligence" | "runs">("overview");

  const refresh = useCallback(async () => {
    const [caseRows, mapRows, info] = await Promise.all([
      request<CaseRecord[]>("/api/v1/cases"),
      request<FeatureCollection>("/api/v1/map/features"),
      request<RuntimeInfo>("/api/v1/runtime"),
    ]);
    setCases(caseRows);
    setFeatures(mapRows);
    setRuntime(info);
    setSelectedId((current) => current ?? caseRows[0]?.id);
  }, []);

  useEffect(() => {
    refresh().catch((reason: Error) => setError(reason.message));
    const interval = window.setInterval(() => refresh().catch(() => undefined), 10_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const selected = useMemo(
    () => cases.find((candidate) => candidate.id === selectedId) ?? cases[0],
    [cases, selectedId],
  );

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

  const createDemo = () =>
    execute(async () => {
      const created = await request<CaseRecord>("/api/v1/cases", {
        method: "POST",
        body: JSON.stringify({
          title: "Pittsburgh commercial facilities quote",
          kind: "quote_intelligence",
          pack: "facilities_quote",
          objective:
            "Obtain comparable non-binding pricing, availability, exclusions, payment terms, and validity from a small qualified provider panel.",
          requester_name: "Demo Procurement Team",
          demo: true,
          location: {
            latitude: 40.4406,
            longitude: -79.9959,
            label: "Pittsburgh demonstration portfolio",
            precision: "public_venue",
          },
          requirements: {
            service: "preventive commercial building service",
            property_count: 5,
            response_window: "two weeks",
            minimum_quotes: 2,
          },
        }),
      });
      setSelectedId(created.id);
      await request(`/api/v1/cases/${created.id}/run`, { method: "POST" });
    });

  const createCustom = (event: FormEvent) => {
    event.preventDefault();
    return execute(async () => {
      const requirements = JSON.parse(draft.requirements || "{}") as Record<string, unknown>;
      const contacts = parseContacts(draft.contacts);
      const created = await request<CaseRecord>("/api/v1/cases", {
        method: "POST",
        body: JSON.stringify({
          title: draft.title,
          kind: draft.kind,
          pack: draft.pack || undefined,
          objective: draft.objective,
          requester_name: draft.requesterName,
          requester_email: draft.requesterEmail || undefined,
          demo: false,
          requirements,
          contacts,
        }),
      });
      setSelectedId(created.id);
      setShowCreate(false);
      setDraft(initialDraft);
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

  const pendingActions = selected?.actions.filter((action) => action.status === "pending").length ?? 0;
  const approvedActions = selected?.actions.filter((action) => action.status === "approved").length ?? 0;
  const dispatchedActions = selected?.actions.filter((action) => action.status === "dispatched").length ?? 0;
  const realMail = runtime?.email_mode === "smtp" && runtime.external_send_enabled;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-mark">SL</span>
          <div>
            <p className="eyebrow">DIRECT-SOURCE INTELLIGENCE OS</p>
            <h1>SourceLoop</h1>
          </div>
        </div>
        <div className="runtime-badges">
          <span><StateDot state="active" />{runtime?.agent_runtime ?? "loading"} brain</span>
          <span><StateDot state={runtime?.mailbox_enabled ? "active" : "muted"} />{runtime?.mailbox_mode ?? "—"} inbox</span>
          <span className={realMail ? "warning-badge" : "safe-badge"}>
            <StateDot state={realMail ? "warning" : "safe"} />{runtime?.email_mode ?? "—"} outbound
          </span>
          <button className="secondary compact" disabled={busy} onClick={createDemo}>Run demo</button>
          <button className="primary compact" disabled={busy} onClick={() => setShowCreate(true)}>New case</button>
        </div>
      </header>

      <div className={realMail ? "safety-banner live" : "safety-banner"}>
        <strong>{realMail ? "Live SMTP is enabled." : "External delivery is locked."}</strong>
        <span>
          {realMail
            ? "Only approved, policy-cleared actions can leave the container."
            : "Approved messages are preserved in the dry-run outbox without network delivery."}
        </span>
      </div>
      {error && <div className="error-banner"><strong>Operation failed</strong><span>{error}</span></div>}

      <main className="workspace">
        <aside className="case-list panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">CASE QUEUE</p>
              <h2>{cases.length} records</h2>
            </div>
            <button className="ghost" disabled={busy} onClick={() => refresh()}>Refresh</button>
          </div>
          <div className="case-scroll">
            {cases.length === 0 && (
              <div className="empty-state">
                <strong>No cases yet</strong>
                <span>Launch a demo or create a live, approval-gated acquisition case.</span>
              </div>
            )}
            {cases.map((item) => (
              <button
                key={item.id}
                className={`case-card ${item.id === selected?.id ? "selected" : ""}`}
                onClick={() => setSelectedId(item.id)}
              >
                <div className="case-card-top">
                  <span className="case-kind">{titleize(item.kind)}</span>
                  <StateDot state={item.status === "completed" ? "safe" : item.status === "failed" ? "warning" : "active"} />
                </div>
                <strong>{item.title}</strong>
                <span className="case-meta">{titleize(item.stage)} · {titleize(item.status)}</span>
                <div className="micro-metrics">
                  <span>{item.agent_runs.length} runs</span>
                  <span>{item.interactions.length} messages</span>
                  <span>{item.quotes.length || item.claims.length} results</span>
                </div>
              </button>
            ))}
          </div>
          <div className="worker-card">
            <div>
              <span className="eyebrow">MAIL WORKER</span>
              <strong>{runtime?.worker?.status ? titleize(runtime.worker.status) : "No heartbeat"}</strong>
            </div>
            <span>{runtime?.worker ? formatDate(runtime.worker.updated_at) : "Start the worker container to monitor replies."}</span>
            {runtime?.mailbox_enabled && (
              <button className="secondary" disabled={busy} onClick={syncMailbox}>Sync mailbox now</button>
            )}
          </div>
        </aside>

        <section className="main-column">
          {!selected ? (
            <section className="panel empty-main">
              <span className="hero-chip">Unknown → Question → Conversation → Evidence</span>
              <h2>Launch a direct-source intelligence case</h2>
              <p>
                SourceLoop compiles the requirement, runs scoped specialists, proposes one coherent thread per
                counterparty, waits for approval, monitors replies, asks bounded clarifications, and commits
                evidence-backed intelligence to the graph.
              </p>
              <div className="hero-actions">
                <button className="primary" onClick={() => setShowCreate(true)} disabled={busy}>Create live case</button>
                <button className="secondary" onClick={createDemo} disabled={busy}>Exercise safe demo</button>
              </div>
            </section>
          ) : (
            <>
              <section className="panel case-header">
                <div>
                  <div className="status-row">
                    <span className={`status-pill status-${selected.status}`}>{titleize(selected.status)}</span>
                    <span>{titleize(selected.kind)}</span>
                    <span>{selected.pack ?? "custom pack"}</span>
                    <span>{selected.demo ? "demonstration" : "live case"}</span>
                  </div>
                  <h2>{selected.title}</h2>
                  <p>{selected.objective}</p>
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
                  <div>
                    <p className="eyebrow">PRACTITIONER RECEIPT</p>
                    <h2>Nine-stage execution rail</h2>
                  </div>
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
                {(["overview", "outreach", "intelligence", "runs"] as const).map((tab) => (
                  <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>{titleize(tab)}</button>
                ))}
              </nav>

              {activeTab === "overview" && (
                <div className="content-grid">
                  <section className="panel metric-panel">
                    <p className="eyebrow">CASE TELEMETRY</p>
                    <div className="metric-grid">
                      <div><strong>{selected.contacts.length}</strong><span>counterparties</span></div>
                      <div><strong>{selected.interactions.length}</strong><span>messages</span></div>
                      <div><strong>{selected.quotes.length}</strong><span>quotes</span></div>
                      <div><strong>{selected.claims.length}</strong><span>claims</span></div>
                      <div><strong>{pendingActions}</strong><span>awaiting approval</span></div>
                      <div><strong>{selected.agent_runs.length}</strong><span>specialist receipts</span></div>
                    </div>
                  </section>
                  <section className="panel map-panel">
                    <div className="panel-heading">
                      <div><p className="eyebrow">GIS PROJECTION</p><h2>Case terrain</h2></div>
                      <span className="target">{selected.contacts.filter((contact) => contact.location).length} geocoded routes</span>
                    </div>
                    <SpatialView selected={selected} features={features} />
                  </section>
                  <section className="panel contacts-panel">
                    <div className="panel-heading"><div><p className="eyebrow">CONTACT ROUTES</p><h2>Selected panel</h2></div></div>
                    <div className="stack-list">
                      {selected.contacts.length === 0 && <div className="empty-card">This case is waiting for supplied contacts or a discovery connector.</div>}
                      {selected.contacts.map((contact) => (
                        <article className="route-card" key={contact.id}>
                          <div><strong>{contact.organization_name}</strong><span>{contact.role_title}</span></div>
                          <code>{contact.endpoint}</code>
                          <div className="route-meta"><span>{contact.geography ?? "Unscoped geography"}</span><span>{Math.round(contact.confidence * 100)}% route confidence</span></div>
                        </article>
                      ))}
                    </div>
                  </section>
                </div>
              )}

              {activeTab === "outreach" && (
                <div className="content-grid outreach-grid">
                  <section className="panel actions-panel">
                    <div className="panel-heading"><div><p className="eyebrow">APPROVAL QUEUE</p><h2>Proposed external actions</h2></div><span className="target">{selected.actions.length} total</span></div>
                    <div className="stack-list">
                      {selected.actions.length === 0 && <div className="empty-card">No external actions have been proposed.</div>}
                      {selected.actions.map((action) => (
                        <article className={`message-card message-${action.status}`} key={action.id}>
                          <div className="message-header">
                            <div><span className="case-kind">{action.followup ? "THREAD FOLLOW-UP" : "INITIAL REQUEST"}</span><strong>{action.organization_name || action.recipient}</strong><span>{action.recipient}</span></div>
                            <span className={`status-pill status-${action.status}`}>{titleize(action.status)}</span>
                          </div>
                          <h3>{action.subject}</h3>
                          <pre>{action.body}</pre>
                          {action.status === "pending" && (
                            <div className="row-actions">
                              <button className="primary" disabled={busy} onClick={() => approveAction(action.id)}>Approve</button>
                              <button className="danger-button" disabled={busy} onClick={() => rejectAction(action.id)}>Reject</button>
                            </div>
                          )}
                        </article>
                      ))}
                    </div>
                  </section>
                  <section className="panel interactions-panel">
                    <div className="panel-heading"><div><p className="eyebrow">EVIDENCE LEDGER</p><h2>Conversation timeline</h2></div></div>
                    <div className="timeline">
                      {selected.interactions.length === 0 && <div className="empty-card">No outbound or inbound evidence yet.</div>}
                      {selected.interactions.map((interaction) => (
                        <article key={interaction.id}>
                          <span className={`timeline-marker ${interaction.direction}`} />
                          <div>
                            <div className="timeline-top"><strong>{interaction.direction === "inbound" ? "Reply received" : "Request sent"}</strong><span>{formatDate(interaction.created_at)}</span></div>
                            <h3>{interaction.subject}</h3>
                            <span>{interaction.endpoint}</span>
                            {interaction.attachments.length > 0 && <small>{interaction.attachments.length} attachment(s) stored as evidence</small>}
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                </div>
              )}

              {activeTab === "intelligence" && (
                <div className="content-grid intelligence-grid">
                  <section className="panel quote-panel">
                    <div className="panel-heading"><div><p className="eyebrow">QUOTE LEDGER</p><h2>Comparable direct-source pricing</h2></div></div>
                    <div className="stack-list">
                      {selected.quotes.length === 0 && <div className="empty-card">No quote has been extracted from a reply.</div>}
                      {selected.quotes.map((quote) => (
                        <article className="quote-card" key={quote.id}>
                          <div className="quote-top">
                            <div><strong>{quote.supplier_name}</strong><span>{quote.valid_until ? `Valid until ${new Date(quote.valid_until).toLocaleDateString()}` : "Validity unresolved"}</span></div>
                            <div className="quote-total"><span>Parsed total</span><strong>${quoteTotal(quote).toLocaleString(undefined, { maximumFractionDigits: 2 })}</strong></div>
                          </div>
                          <table>
                            <thead><tr><th>Line item</th><th>Unit</th><th>Price</th></tr></thead>
                            <tbody>{quote.line_items.map((line, index) => <tr key={`${quote.id}-${index}`}><td>{line.description}</td><td>{titleize(line.unit)}</td><td>{line.currency} {line.unit_price.toLocaleString()}</td></tr>)}</tbody>
                          </table>
                          <div className="quote-meta"><span>{Math.round(quote.extraction_confidence * 100)}% extraction confidence</span><span>{quote.unresolved_fields.length ? `Needs: ${quote.unresolved_fields.join(", ")}` : "Critical fields complete"}</span></div>
                          {quote.exclusions.length > 0 && <p><strong>Exclusions:</strong> {quote.exclusions.join(" · ")}</p>}
                        </article>
                      ))}
                    </div>
                  </section>
                  <section className="panel claims-panel">
                    <div className="panel-heading"><div><p className="eyebrow">CLAIM LEDGER</p><h2>Scoped assertions</h2></div></div>
                    <div className="stack-list compact-list">
                      {selected.claims.length === 0 && <div className="empty-card">No structured claims yet.</div>}
                      {selected.claims.map((claim) => (
                        <article className="claim-card" key={claim.id}>
                          <div><strong>{titleize(claim.predicate)}</strong><span>{titleize(claim.kind)} · {Math.round(claim.confidence * 100)}%</span></div>
                          <code>{typeof claim.value === "string" ? claim.value : JSON.stringify(claim.value)}</code>
                        </article>
                      ))}
                    </div>
                  </section>
                </div>
              )}

              {activeTab === "runs" && (
                <section className="panel runs-panel">
                  <div className="panel-heading"><div><p className="eyebrow">INTERNAL SWARM</p><h2>Specialist execution receipts</h2></div><span className="target">External recipients see one coherent owner</span></div>
                  <div className="run-grid">
                    {selected.agent_runs.map((run) => (
                      <article key={run.id}>
                        <StateDot state={run.status === "succeeded" ? "safe" : "warning"} />
                        <div><strong>{titleize(run.role)}</strong><span>{titleize(run.stage)} · {run.runtime}</span>{run.error && <small>{run.error}</small>}</div>
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
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowCreate(false)}>
          <form className="modal" onSubmit={createCustom} onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div><p className="eyebrow">NEW DIRECT-SOURCE CASE</p><h2>Define the intelligence objective</h2></div>
              <button type="button" className="ghost" onClick={() => setShowCreate(false)}>Close</button>
            </div>
            <div className="form-grid">
              <label>Title<input required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} placeholder="Regional HVAC budgetary quotes" /></label>
              <label>Case type<select value={draft.kind} onChange={(event) => {
                const kind = event.target.value as NewCaseDraft["kind"];
                setDraft({ ...draft, kind, pack: kind === "quote_intelligence" ? "facilities_quote" : kind === "civic_intelligence" ? "civic_intelligence" : "" });
              }}><option value="quote_intelligence">Quote intelligence</option><option value="civic_intelligence">Civic intelligence</option><option value="data_verification">Data verification</option></select></label>
              <label>Vertical pack<input value={draft.pack} onChange={(event) => setDraft({ ...draft, pack: event.target.value })} placeholder="facilities_quote" /></label>
              <label>Requester name<input required value={draft.requesterName} onChange={(event) => setDraft({ ...draft, requesterName: event.target.value })} /></label>
              <label className="span-2">Requester email<input type="email" value={draft.requesterEmail} onChange={(event) => setDraft({ ...draft, requesterEmail: event.target.value })} /></label>
              <label className="span-2">Objective<textarea required rows={3} value={draft.objective} onChange={(event) => setDraft({ ...draft, objective: event.target.value })} placeholder="Obtain two comparable, non-binding quotes with current availability and terms." /></label>
              <label className="span-2">Requirements JSON<textarea rows={7} value={draft.requirements} onChange={(event) => setDraft({ ...draft, requirements: event.target.value })} /></label>
              <label className="span-2">Contact routes <small>One per line: Organization | Role | email | geography | latitude | longitude</small><textarea rows={5} value={draft.contacts} onChange={(event) => setDraft({ ...draft, contacts: event.target.value })} placeholder="Acme Mechanical | Estimating | quotes@acme.example | Pittsburgh | 40.44 | -79.99" /></label>
            </div>
            <div className="modal-actions"><button type="button" className="secondary" onClick={() => setShowCreate(false)}>Cancel</button><button className="primary" disabled={busy}>Create and run</button></div>
          </form>
        </div>
      )}
    </div>
  );
}
