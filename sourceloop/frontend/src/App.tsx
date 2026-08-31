import { useCallback, useEffect, useMemo, useState } from "react";

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
  exclusions: string[];
  extraction_confidence: number;
  unresolved_fields: string[];
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
  interactions: Array<{ id: string; direction: string; endpoint: string; subject: string }>;
};

type Feature = {
  id: string;
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: Record<string, string | number>;
};

type FeatureCollection = { type: "FeatureCollection"; features: Feature[] };

type RootInfo = {
  email_mode: string;
  external_send_enabled: boolean;
  agent_runtime: string;
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

export default function App() {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [features, setFeatures] = useState<FeatureCollection>({ type: "FeatureCollection", features: [] });
  const [rootInfo, setRootInfo] = useState<RootInfo>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const refresh = useCallback(async () => {
    const [caseRows, mapRows, info] = await Promise.all([
      request<CaseRecord[]>("/api/v1/cases"),
      request<FeatureCollection>("/api/v1/map/features"),
      request<RootInfo>("/"),
    ]);
    setCases(caseRows);
    setFeatures(mapRows);
    setRootInfo(info);
    setSelectedId((current) => current ?? caseRows[0]?.id);
  }, []);

  useEffect(() => {
    refresh().catch((reason: Error) => setError(reason.message));
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
            "Obtain comparable non-binding pricing, availability, exclusions, and validity from a small qualified provider panel.",
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

  const runSelected = () =>
    selected && execute(() => request(`/api/v1/cases/${selected.id}/run`, { method: "POST" }));

  const approveAndDispatch = () =>
    selected &&
    execute(async () => {
      const pending = selected.actions.filter((action) => action.status === "pending");
      for (const action of pending) {
        await request(`/api/v1/cases/${selected.id}/actions/${action.id}/approve`, {
          method: "POST",
          body: JSON.stringify({ approver: "console-operator", note: "Reviewed in SourceLoop console" }),
        });
      }
      await request(`/api/v1/cases/${selected.id}/dispatch`, { method: "POST" });
    });

  const simulateReplies = () =>
    selected &&
    execute(() => request(`/api/v1/demo/${selected.id}/replies`, { method: "POST" }));

  const pendingActions = selected?.actions.filter((action) => action.status === "pending").length ?? 0;
  const dispatchedActions = selected?.actions.filter((action) => action.status === "dispatched").length ?? 0;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">DIRECT-SOURCE INTELLIGENCE OS</p>
          <h1>SourceLoop</h1>
        </div>
        <div className="runtime-badges">
          <span>{rootInfo?.agent_runtime ?? "loading"} runtime</span>
          <span className={rootInfo?.external_send_enabled ? "danger" : "safe"}>
            {rootInfo?.email_mode ?? "—"} mail
          </span>
          <button className="primary" disabled={busy} onClick={createDemo}>
            + New live demo
          </button>
        </div>
      </header>

      {!rootInfo?.external_send_enabled && (
        <div className="safety-banner">
          External delivery is locked. Approved messages are captured in the dry-run outbox.
        </div>
      )}
      {error && <div className="error-banner">{error}</div>}

      <main className="workspace">
        <aside className="case-list panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">CASE QUEUE</p>
              <h2>{cases.length} active records</h2>
            </div>
            <button className="ghost" disabled={busy} onClick={() => refresh()}>
              Refresh
            </button>
          </div>
          <div className="case-scroll">
            {cases.length === 0 && (
              <div className="empty-state">
                <strong>No cases yet.</strong>
                <span>Create a deterministic quote case to exercise the full practitioner.</span>
              </div>
            )}
            {cases.map((item) => (
              <button
                key={item.id}
                className={`case-card ${item.id === selected?.id ? "selected" : ""}`}
                onClick={() => setSelectedId(item.id)}
              >
                <span className="case-kind">{titleize(item.kind)}</span>
                <strong>{item.title}</strong>
                <span className="case-meta">
                  {titleize(item.stage)} · {titleize(item.status)}
                </span>
                <div className="micro-metrics">
                  <span>{item.agent_runs.length} runs</span>
                  <span>{item.actions.length} actions</span>
                  <span>{item.quotes.length || item.claims.length} results</span>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <section className="main-column">
          {!selected ? (
            <section className="panel empty-main">
              <p className="eyebrow">READY</p>
              <h2>Launch a direct-source intelligence case</h2>
              <p>
                The demonstration compiles a requirement, spawns bounded internal specialists, proposes one
                coherent outreach thread per provider, waits at approval, captures dry-run mail, processes sample
                replies, and commits quote intelligence to the graph.
              </p>
              <button className="primary" onClick={createDemo} disabled={busy}>
                Build demonstration case
              </button>
            </section>
          ) : (
            <>
              <section className="panel case-header">
                <div>
                  <div className="status-row">
                    <span className={`status-pill status-${selected.status}`}>{titleize(selected.status)}</span>
                    <span>{titleize(selected.kind)}</span>
                    <span>{selected.pack ?? "custom pack"}</span>
                  </div>
                  <h2>{selected.title}</h2>
                  <p>{selected.objective}</p>
                </div>
                <div className="case-actions">
                  <button className="secondary" disabled={busy || selected.status !== "active"} onClick={runSelected}>
                    Run practitioner
                  </button>
                  <button
                    className="primary"
                    disabled={busy || pendingActions === 0}
                    onClick={approveAndDispatch}
                  >
                    Approve + dry-run {pendingActions || ""}
                  </button>
                  <button
                    className="secondary"
                    disabled={busy || dispatchedActions === 0 || !selected.demo}
                    onClick={simulateReplies}
                  >
                    Simulate replies
                  </button>
                </div>
              </section>

              <section className="panel practitioner">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">PRACTITIONER RECEIPT</p>
                    <h2>Nine-stage execution rail</h2>
                  </div>
                  <span className="target">Target: {selected.completion_target} verified result(s)</span>
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

              <div className="two-column">
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">GIS + RELATIONSHIP VIEW</p>
                      <h2>Active market graph</h2>
                    </div>
                    <span>{selected.contacts.length} routes</span>
                  </div>
                  <GeoMap features={features.features.filter((feature) => feature.id === selected.id || feature.properties.case_id === selected.id)} />
                  <div className="contact-grid">
                    {selected.contacts.map((contact) => (
                      <div className="contact-card" key={contact.id}>
                        <strong>{contact.organization_name}</strong>
                        <span>{contact.role_title}</span>
                        <small>{contact.endpoint}</small>
                        <div className="confidence"><i style={{ width: `${contact.confidence * 100}%` }} /></div>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">INTERNAL SWARM</p>
                      <h2>Specialist execution</h2>
                    </div>
                    <span>{selected.agent_runs.length} receipts</span>
                  </div>
                  <div className="run-list">
                    {[...selected.agent_runs].reverse().slice(0, 16).map((run) => (
                      <div className="run-row" key={run.id}>
                        <span className={`run-dot ${run.status}`} />
                        <div>
                          <strong>{titleize(run.role)}</strong>
                          <small>{titleize(run.stage)} · {run.runtime}</small>
                        </div>
                        <span>{run.status}</span>
                      </div>
                    ))}
                  </div>
                </section>
              </div>

              {selected.actions.length > 0 && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">SIDE-EFFECT LEDGER</p>
                      <h2>Approval queue and conversation ownership</h2>
                    </div>
                    <span>{pendingActions} pending</span>
                  </div>
                  <div className="action-grid">
                    {selected.actions.map((action) => (
                      <article className="action-card" key={action.id}>
                        <div className="status-row">
                          <span className={`status-pill action-${action.status}`}>{titleize(action.status)}</span>
                          <span>{action.organization_name}</span>
                        </div>
                        <strong>{action.subject}</strong>
                        <small>{action.recipient}</small>
                        <details>
                          <summary>Inspect exact proposed message</summary>
                          <pre>{action.body}</pre>
                        </details>
                      </article>
                    ))}
                  </div>
                </section>
              )}

              {selected.quotes.length > 0 && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">QUOTE INTELLIGENCE</p>
                      <h2>Comparable direct-source results</h2>
                    </div>
                    <span>{selected.quotes.length} live response(s)</span>
                  </div>
                  <div className="quote-table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Supplier</th>
                          <th>Line items</th>
                          <th>Normalized visible total</th>
                          <th>Confidence</th>
                          <th>Unresolved</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selected.quotes.map((quote) => (
                          <tr key={quote.id}>
                            <td><strong>{quote.supplier_name}</strong></td>
                            <td>
                              {quote.line_items.map((line) => (
                                <div key={`${line.description}-${line.unit_price}`}>
                                  {line.description}: {line.currency} {line.unit_price.toFixed(2)} / {line.unit}
                                </div>
                              ))}
                            </td>
                            <td>${quoteTotal(quote).toFixed(2)}</td>
                            <td>{Math.round(quote.extraction_confidence * 100)}%</td>
                            <td>{quote.unresolved_fields.join(", ") || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {selected.claims.length > 0 && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">CLAIM LEDGER</p>
                      <h2>Evidence-scoped assertions</h2>
                    </div>
                    <span>{selected.claims.length} claims</span>
                  </div>
                  <div className="claim-grid">
                    {selected.claims.slice(-12).map((claim) => (
                      <article className="claim-card" key={claim.id}>
                        <span>{titleize(claim.kind)}</span>
                        <strong>{titleize(claim.predicate)}</strong>
                        <p>{typeof claim.value === "string" ? claim.value : JSON.stringify(claim.value)}</p>
                        <small>{Math.round(claim.confidence * 100)}% · {titleize(claim.corroboration_status)}</small>
                      </article>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </section>
      </main>
    </div>
  );
}

function GeoMap({ features }: { features: Feature[] }) {
  if (features.length === 0) {
    return <div className="map empty-map">No geocoded entities in this case.</div>;
  }
  const lons = features.map((feature) => feature.geometry.coordinates[0]);
  const lats = features.map((feature) => feature.geometry.coordinates[1]);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const project = ([lon, lat]: [number, number]): [number, number] => {
    const x = 45 + ((lon - minLon) / Math.max(maxLon - minLon, 0.01)) * 510;
    const y = 295 - ((lat - minLat) / Math.max(maxLat - minLat, 0.01)) * 250;
    return [x, y];
  };
  const caseFeature = features.find((feature) => feature.properties.node_type === "case");
  const casePoint = caseFeature ? project(caseFeature.geometry.coordinates) : undefined;

  return (
    <div className="map">
      <svg viewBox="0 0 600 340" role="img" aria-label="Geographic case and contact routes">
        <defs>
          <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
            <path d="M 30 0 L 0 0 0 30" fill="none" stroke="currentColor" strokeOpacity="0.08" />
          </pattern>
        </defs>
        <rect width="600" height="340" fill="url(#grid)" />
        {casePoint && features.filter((feature) => feature.id !== caseFeature?.id).map((feature) => {
          const [x, y] = project(feature.geometry.coordinates);
          return <line key={`line-${feature.id}`} x1={casePoint[0]} y1={casePoint[1]} x2={x} y2={y} className="map-link" />;
        })}
        {features.map((feature) => {
          const [x, y] = project(feature.geometry.coordinates);
          const isCase = feature.properties.node_type === "case";
          return (
            <g key={feature.id} transform={`translate(${x}, ${y})`}>
              <circle r={isCase ? 12 : 8} className={isCase ? "map-case" : "map-contact"} />
              <text x="14" y="4">{String(feature.properties.label).slice(0, 28)}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
