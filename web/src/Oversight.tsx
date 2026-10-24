// Human-oversight surfaces for the canaries: a quiet toast, an unmistakable alert, the audit drawer.
import { useEffect, useRef } from "react";
import type { AuditEntry, Canary, CanaryAlert, Proposal } from "./contracts";
import { labelOf, Triple, type Index } from "./bits";

export type OversightAlert =
  | { kind: "curation"; alert: CanaryAlert; canary: Proposal; reverted: Proposal[] }
  | { kind: "chat"; canary: Canary; question: string; supervisor: string };

export function Toast({ text, onDone }: { text: string; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 4200);
    return () => clearTimeout(t);
  }, [text, onDone]);
  return <div className="toast glass" role="status">{text}</div>;
}

export function AlertDialog({ a, idx, onReview, onAudit, onClose }: {
  a: OversightAlert; idx: Index; onReview: () => void; onAudit: () => void; onClose: () => void;
}) {
  const btn = useRef<HTMLButtonElement>(null);
  useEffect(() => btn.current?.focus(), []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="scrim" onClick={onClose}>
      <section className="alert-sheet" role="alertdialog" aria-modal="true" aria-labelledby="alert-title" onClick={(e) => e.stopPropagation()}>
        <div className="alert-icon" aria-hidden="true">!</div>
        <div className="eyebrow">Oversight check</div>
        {a.kind === "curation" ? (
          <>
            <h2 id="alert-title">That was a test proposal, and it was approved.</h2>
            <p className="muted">{a.alert.message}</p>
            <div className="alert-claim">
              <span className="label">Planted, false</span>
              {a.canary.triple && <Triple edge={a.canary.triple} idx={idx} />}
            </div>
            <h5>Back to review · {a.reverted.length}</h5>
            {a.reverted.length ? (
              <ul className="path">
                {a.reverted.map((p) => (
                  <li key={p.id}>
                    {p.triple ? <Triple edge={p.triple} idx={idx} /> : p.node?.label ?? p.predicate?.name}
                  </li>
                ))}
              </ul>
            ) : <p className="small muted">No earlier approvals to revert.</p>}
            <p className="small notify">● {a.alert.supervisor_notified} notified · logged in the audit trail</p>
          </>
        ) : (
          <>
            <h2 id="alert-title">You moved on from a planted false answer.</h2>
            <p className="muted">One answer in this session was a test. It stated something the approved graph contradicts, and it was not reported.</p>
            <div className="alert-claim"><span className="label">Planted, false</span>{a.canary.claim}</div>
            <div className="alert-claim truth"><span className="label">What the graph says</span>{a.canary.truth}</div>
            <p className="small notify">● {a.supervisor} notified · logged in the audit trail</p>
          </>
        )}
        <div className="actions">
          <button className="btn secondary" onClick={onAudit}>Audit log</button>
          <button className="btn" ref={btn} onClick={a.kind === "curation" ? onReview : onClose}>
            {a.kind === "curation" ? "Review items" : "Understood"}
          </button>
        </div>
      </section>
    </div>
  );
}

const KIND: Record<AuditEntry["kind"], string> = {
  decision: "Decision", canary_planted: "Test planted", canary_passed: "Test caught",
  canary_failed: "Test missed", reverted: "Reverted", supervisor_notified: "Supervisor",
};

export function AuditDrawer({ entries, proposals, idx, onClose }: {
  entries: AuditEntry[]; proposals: Proposal[]; idx: Index; onClose: () => void;
}) {
  const what = (id?: string | null) => {
    const p = id ? proposals.find((x) => x.id === id) : undefined;
    if (!p) return null;
    if (p.triple) return `${labelOf(idx, p.triple.s)} → ${labelOf(idx, p.triple.o)}`;
    return p.node?.label ?? p.predicate?.name ?? null;
  };
  return (
    <aside className="panel left glass" aria-label="Audit log">
      <div className="panel-head">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="eyebrow">Audit log</div>
          <button className="link-btn" onClick={onClose}>Close</button>
        </div>
        <h2 className="question">Every decision, every test.</h2>
        <p className="small muted" style={{ margin: "6px 0 0" }}>Planted test items check that reviewers still read what they approve.</p>
      </div>
      <div className="panel-body">
        {entries.length === 0 && <div className="empty">Nothing logged yet.</div>}
        <ol className="audit">
          {entries.map((e, i) => (
            <li key={i} className={"a-" + e.kind}>
              <div className="a-top">
                <span className="a-kind">{KIND[e.kind]}</span>
                <time>{new Date(e.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time>
              </div>
              <div className="a-detail">{e.detail}</div>
              {what(e.proposal_id) && <div className="a-what">{what(e.proposal_id)}</div>}
            </li>
          ))}
        </ol>
      </div>
    </aside>
  );
}
