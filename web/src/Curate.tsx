import type { Proposal } from "./contracts";
import { labelOf, Triple, type Index } from "./bits";

interface Props {
  proposals: Proposal[];
  idx: Index;
  onDecide: (id: string, d: "approve" | "reject") => void;
  onShow: (id: string) => void;
}

export default function Curate({ proposals, idx, onDecide, onShow }: Props) {
  const open = proposals.filter((p) => p.status === "proposed").length;
  return (
    <aside className="panel glass" aria-label="Curation">
      <div className="panel-head">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="eyebrow">Curation</div>
          <span className="tag mock" title="Click prototype: decisions are not persisted">Mock</span>
        </div>
        <h2 className="question">A new document arrived. The model proposes, an analyst decides.</h2>
        <p className="small muted" style={{ margin: "8px 0 0" }}>
          Proposals stay out of the anchor graph until approved. {open} open.
        </p>
      </div>
      <div className="panel-body">
        {proposals.length === 0 && <div className="empty">No proposals.</div>}
        {proposals.map((p) => (
          <section key={p.id} className={"card proposal " + p.status}>
            <button className="cite" style={{ width: "100%" }} onClick={() => onShow(p.id)}>
              <Triple edge={p.triple} idx={idx} />
            </button>
            <div className="q">“{p.quote}”</div>
            <p className="small">{p.rationale}</p>
            <div className="conf">
              <span>Confidence</span>
              <div className="bar"><i style={{ width: `${Math.round(p.confidence * 100)}%` }} /></div>
              <span>{Math.round(p.confidence * 100)}%</span>
            </div>
            <div className="small muted" style={{ marginTop: 6 }}>
              Proposed by {p.proposed_by.replace(/^llm:/, "").split("/").pop()} · source {labelOf(idx, p.evidence_chunk_id)}
            </div>
            {p.status === "proposed" ? (
              <div className="actions">
                <button className="btn secondary" onClick={() => onDecide(p.id, "reject")}>Reject</button>
                <button className="btn approve" onClick={() => onDecide(p.id, "approve")}>Approve</button>
              </div>
            ) : (
              <div className={"status-line " + p.status}>
                {p.status === "approved" ? "✓ Approved. Now part of the anchor graph." : "Rejected. Never used for answers."}
              </div>
            )}
          </section>
        ))}
      </div>
    </aside>
  );
}
