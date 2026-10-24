import { useMemo, useState } from "react";
import type { CreateProposal, Node, Proposal } from "./contracts";
import { labelOf, Triple, type Index } from "./bits";
import type { Decision, Ontology } from "./data";
import { nodeIri, predIri } from "./ids";

export type Kind = "edge" | "node" | "predicate";
const KINDS: [Kind | "all", string][] = [["all", "All"], ["edge", "Edges"], ["node", "Nodes"], ["predicate", "Predicates"]];
const KIND_LABEL: Record<Kind, string> = { edge: "Edge", node: "Node", predicate: "Predicate" };

export const kindOf = (p: Proposal): Kind => p.kind ?? "edge";

interface Props {
  proposals: Proposal[];
  idx: Index;
  ontology: Ontology;
  mock: boolean;
  /** false = the server has curation writes closed (no reviewer codes configured) */
  writable: boolean;
  reviewer: string;
  onReviewer: (v: string) => void;
  onDecide: (id: string, d: Decision) => void;
  onAudit: () => void;
  /** set after a failed canary: ids that went back to "proposed" */
  reverted: string[];
  onCreate: (body: CreateProposal) => Promise<void>;
  onShow: (p: Proposal) => void;
}

export default function Curate({ proposals, idx, ontology, mock, writable, reviewer, onReviewer, onDecide, onCreate, onShow, onAudit, reverted }: Props) {
  const [filter, setFilter] = useState<Kind | "all">("all");
  const [adding, setAdding] = useState(false);
  // open items first, decided ones below, otherwise in server order
  const shown = proposals
    .filter((p) => filter === "all" || kindOf(p) === filter)
    .map((p, i) => [p, i] as const)
    .sort(([a, i], [b, j]) => Number(a.status !== "proposed") - Number(b.status !== "proposed") || i - j)
    .map(([p]) => p);
  const stillReverted = reverted.filter((id) => proposals.find((p) => p.id === id)?.status === "proposed").length;
  const open = proposals.filter((p) => p.status === "proposed").length;
  const count = (k: Kind | "all") => (k === "all" ? proposals.length : proposals.filter((p) => kindOf(p) === k).length);

  return (
    <aside className="panel glass" aria-label="Curation">
      <div className="panel-head">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="eyebrow">Curation</div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {!writable && <span className="tag mock" title="The server has curation writes closed">Read-only</span>}
            {mock && <span className="tag mock" title="Static mode: proposals and decisions stay in this browser">Mock · in memory</span>}
            <button className="link-btn" onClick={onAudit}>Audit log</button>
          </div>
        </div>
        <h2 className="question">Models and people propose. An analyst decides.</h2>
        <p className="small muted" style={{ margin: "8px 0 0" }}>
          Nothing enters the anchor graph until approved. {open} open.
        </p>
        {writable && !mock && (
          <label className="field invite">
            <span>Reviewer code</span>
            <input value={reviewer} onChange={(e) => onReviewer(e.target.value.trim())} placeholder="From the presenter"
              spellCheck={false} autoComplete="off" />
          </label>
        )}
        <div className="curate-bar">
          <div className="segmented mini" role="group" aria-label="Filter by kind">
            {KINDS.map(([k, label]) => (
              <button key={k} aria-pressed={filter === k} onClick={() => setFilter(k)}>
                {label} <span className="count">{count(k)}</span>
              </button>
            ))}
          </div>
          <button className={"add-btn" + (adding ? " open" : "")} disabled={!writable} onClick={() => setAdding((a) => !a)}
            aria-expanded={adding} aria-label={adding ? "Cancel new proposal" : "Add proposal"} title={adding ? "Cancel" : "Add proposal"}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" /></svg>
          </button>
        </div>
      </div>
      <div className="panel-body">
        {stillReverted > 0 && (
          <div className="revert-note" role="status">
            {stillReverted} approval{stillReverted === 1 ? "" : "s"} went back to review after a missed test proposal. They are marked below.
          </div>
        )}
        {adding && (
          <AddForm
            initial={filter === "all" ? "edge" : filter}
            idx={idx}
            ontology={ontology}
            onCancel={() => setAdding(false)}
            onSubmit={async (b) => {
              await onCreate(b);
              setAdding(false);
              setFilter("all");
            }}
          />
        )}
        {shown.length === 0 && !adding && (
          <div className="empty">No {filter === "all" ? "" : KIND_LABEL[filter as Kind].toLowerCase() + " "}proposals yet. Add one.</div>
        )}
        {shown.map((p) => (
          <ProposalCard key={p.id} p={p} idx={idx} onDecide={writable ? onDecide : () => {}} onShow={onShow} readOnly={!writable}
            again={reverted.includes(p.id) && p.status === "proposed"} />
        ))}
      </div>
    </aside>
  );
}

function origin(p: Proposal) {
  if (p.proposed_by === "user") return { label: "User", cls: "user" };
  if (p.proposed_by === "analyst-seed") return { label: "Analyst seed", cls: "user" };
  return { label: "LLM · " + p.proposed_by.replace(/^llm:/, "").split("/").pop(), cls: "llm" };
}

function ProposalCard({ p, idx, onDecide, onShow, again, readOnly }: {
  p: Proposal; idx: Index; onDecide: Props["onDecide"]; onShow: Props["onShow"]; again: boolean; readOnly: boolean;
}) {
  const k = kindOf(p);
  const o = origin(p);
  return (
    <section className={"card proposal " + p.status + (again ? " again" : "")}>
      <div className="prop-head">
        <span className={"kind k-" + k}>{KIND_LABEL[k]}{again && <span className="again-tag">Review again</span>}</span>
        <span className={"origin " + o.cls}>{o.label}</span>
      </div>
      <button className="prop-body" onClick={() => onShow(p)} title="Show in graph">
        {k === "edge" && p.triple && <Triple edge={p.triple} idx={idx} />}
        {k === "node" && p.node && (
          <>
            <div className="prop-title">{p.node.label}</div>
            <div className="mono-line">{p.node.cls} · {p.node.local_id}</div>
            {p.node.description && <div className="small muted">{p.node.description}</div>}
          </>
        )}
        {k === "predicate" && p.predicate && (
          <>
            <div className="prop-title mono">{p.predicate.name}</div>
            <div className="mono-line">{p.predicate.domain ?? "any"} → {p.predicate.range ?? "any"}</div>
            <div className="small muted">{p.predicate.description}</div>
          </>
        )}
      </button>
      {p.quote && <div className="q">“{p.quote}”</div>}
      <p className="small">{p.rationale}</p>
      {p.confidence != null && (
        <div className="conf">
          <span>Confidence</span>
          <div className="bar"><i style={{ width: `${Math.round(p.confidence * 100)}%` }} /></div>
          <span>{Math.round(p.confidence * 100)}%</span>
        </div>
      )}
      {p.evidence_chunk_id && <div className="small muted" style={{ marginTop: 6 }}>Source: {labelOf(idx, p.evidence_chunk_id)}</div>}
      {p.status === "proposed" ? (
        <div className="actions">
          <button className="btn secondary" disabled={readOnly} onClick={() => onDecide(p.id, "reject")}>Reject</button>
          <button className="btn secondary flag" disabled={readOnly} onClick={() => onDecide(p.id, "flag")} title="This is wrong: report it" aria-label="Flag as wrong">
            <FlagIcon />
          </button>
          <button className="btn approve" disabled={readOnly} onClick={() => onDecide(p.id, "approve")}>Approve</button>
        </div>
      ) : (
        <div className={"status-line " + p.status} role="status">
          {p.status === "approved"
            ? k === "predicate" ? "✓ Approved. Available to strategy and curation." : "✓ Approved. Now part of the anchor graph."
            : "Rejected. Never used for answers."}
        </div>
      )}
    </section>
  );
}

// ---------- add form ----------

// Real-world entities only, as kg.propose offers them; plant, document and event nodes come from the source systems.
const NODE_CLASSES = ["SensorModel", "Supplier", "Customer", "Company", "Role"];

function AddForm({ initial, idx, ontology, onSubmit, onCancel }: {
  initial: Kind; idx: Index; ontology: Ontology;
  onSubmit: (b: CreateProposal) => Promise<void>; onCancel: () => void;
}) {
  const [kind, setKind] = useState<Kind>(initial);
  const [s, setS] = useState<Node | null>(null);
  const [o, setO] = useState<Node | null>(null);
  const [pred, setPred] = useState("");
  const [cls, setCls] = useState("");
  const [localId, setLocalId] = useState("");
  const [label, setLabel] = useState("");
  const [desc, setDesc] = useState("");
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [range, setRange] = useState("");
  const [rationale, setRationale] = useState("");
  const [quote, setQuote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const problem = (() => {
    if (kind === "edge") {
      if (!s || !o) return "Pick a subject and an object.";
      if (!pred) return "Pick a relation.";
    }
    if (kind === "node") {
      if (!cls) return "Choose a class.";
      if (!/^[A-Za-z0-9_.-]+$/.test(localId)) return "ID: letters, digits, _ . - only.";
      if (idx.has(nodeIri(cls, localId))) return "A node with this ID already exists.";
      if (!label.trim()) return "Add a label.";
    }
    if (kind === "predicate") {
      if (!/^[a-z][a-z0-9_]*$/.test(name)) return "Name: snake_case, e.g. recommended_replacement.";
      if (ontology.predicates.some((p) => p.iri === predIri(name))) return "This predicate already exists.";
      if (!desc.trim()) return "Add a description.";
    }
    if (!rationale.trim()) return "Say why.";
    return null;
  })();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (problem) return;
    const base = { kind, rationale: rationale.trim(), quote: quote.trim() || null, evidence_chunk_id: null };
    const body: CreateProposal =
      kind === "edge" ? { ...base, triple: { s: s!.id, p: pred, o: o!.id } }
      : kind === "node" ? { ...base, node: { cls, local_id: localId, label: label.trim(), description: desc.trim() || null } }
      : { ...base, predicate: { name, description: desc.trim(), domain: domain || null, range: range || null } };
    setBusy(true);
    setErr(null);
    try { await onSubmit(body); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };

  return (
    <form className="card add-form" onSubmit={submit}>
      <h3>New proposal</h3>
      <div className="segmented mini" role="group" aria-label="Kind" style={{ marginTop: 10 }}>
        {(["edge", "node", "predicate"] as Kind[]).map((k) => (
          <button type="button" key={k} aria-pressed={kind === k} onClick={() => setKind(k)}>{KIND_LABEL[k]}</button>
        ))}
      </div>

      {kind === "edge" && (
        <>
          <NodePicker label="Subject" value={s} onChange={setS} idx={idx} />
          <label className="field">
            <span>Relation</span>
            <select value={pred} onChange={(e) => setPred(e.target.value)}>
              <option value="">Choose…</option>
              {ontology.predicates.map((p) => <option key={p.iri} value={p.iri}>{p.name}</option>)}
            </select>
            {pred && <em>{ontology.predicates.find((p) => p.iri === pred)?.description}</em>}
          </label>
          <NodePicker label="Object" value={o} onChange={setO} idx={idx} />
        </>
      )}

      {kind === "node" && (
        <>
          <label className="field">
            <span>Class</span>
            <select value={cls} onChange={(e) => setCls(e.target.value)}>
              <option value="">Choose…</option>
              {ontology.classes.filter((c) => NODE_CLASSES.includes(c.name)).map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
          </label>
          <div className="field-row">
            <label className="field"><span>ID</span>
              <input value={localId} onChange={(e) => setLocalId(e.target.value)} placeholder="RTD-2400" spellCheck={false} /></label>
            <label className="field"><span>Label</span>
              <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="RTD-2400 Pt100" /></label>
          </div>
          <label className="field"><span>Description</span>
            <input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Optional" /></label>
        </>
      )}

      {kind === "predicate" && (
        <>
          <label className="field"><span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="recommended_replacement" spellCheck={false} /></label>
          <div className="field-row">
            <label className="field"><span>Domain</span>
              <select value={domain} onChange={(e) => setDomain(e.target.value)}>
                <option value="">Any</option>
                {ontology.classes.map((c) => <option key={c.name}>{c.name}</option>)}
              </select></label>
            <label className="field"><span>Range</span>
              <select value={range} onChange={(e) => setRange(e.target.value)}>
                <option value="">Any</option>
                {ontology.classes.map((c) => <option key={c.name}>{c.name}</option>)}
              </select></label>
          </div>
          <label className="field"><span>Description</span>
            <input value={desc} onChange={(e) => setDesc(e.target.value)}
              placeholder={`${domain || "Domain"} ${name || "name"} ${range || "Range"}.`} /></label>
        </>
      )}

      <label className="field"><span>Why</span>
        <textarea rows={2} value={rationale} onChange={(e) => setRationale(e.target.value)} placeholder="What makes this true?" /></label>
      <label className="field"><span>Quote</span>
        <input value={quote} onChange={(e) => setQuote(e.target.value)} placeholder="Optional, from a document" /></label>

      {err && <div className="banner" role="alert">{err}</div>}
      <div className="actions">
        <button type="button" className="btn secondary" onClick={onCancel}>Cancel</button>
        <button className="btn approve" disabled={!!problem || busy} title={problem ?? ""}>Propose</button>
      </div>
      {problem && <div className="hint">{problem}</div>}
    </form>
  );
}

function NodePicker({ label, value, onChange, idx }: {
  label: string; value: Node | null; onChange: (n: Node | null) => void; idx: Index;
}) {
  const [q, setQ] = useState("");
  const hits = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return [];
    return [...idx.values()]
      .filter((n) => n.label.toLowerCase().includes(t) || n.id.toLowerCase().endsWith("/" + t))
      .sort((a, b) => a.label.length - b.label.length)
      .slice(0, 6);
  }, [q, idx]);
  if (value) {
    return (
      <div className="field">
        <span>{label}</span>
        <div className="picked">
          <span><b>{value.label}</b> <span className="muted small">{value.cls}</span></span>
          <button type="button" className="link-btn" onClick={() => { onChange(null); setQ(""); }}>Change</button>
        </div>
      </div>
    );
  }
  return (
    <label className="field picker">
      <span>{label}</span>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search nodes…" autoComplete="off" />
      {hits.length > 0 && (
        <ul className="hits" role="listbox">
          {hits.map((n) => (
            <li key={n.id}>
              <button type="button" role="option" onClick={() => onChange(n)}>
                {n.label} <span className="muted small">{n.cls}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </label>
  );
}

export function FlagIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
      <path d="M5 21V4m0 0h11l-2 4 2 4H5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
