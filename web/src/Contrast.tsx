import type { Edge } from "./contracts";
import { labelOf, Triple, type Index } from "./bits";
import type { RunView } from "./run";

export default function Contrast({ v, idx, edges }: { v: RunView; idx: Index; edges: Map<string, Edge> }) {
  const b = v.baseline;
  const cited = (v.answer?.citations ?? []).map((c) => c.edge_id && edges.get(c.edge_id)).filter(Boolean) as Edge[];
  const contra = v.answer?.contradictions ?? [];
  const seen = new Set(b?.chunks.map((c) => c.id));
  const missed = contra.filter((c) => !(seen.has(c.a) && seen.has(c.b)));
  return (
    <div className="sheet-wrap">
      <section className="sheet glass" aria-label="Contrast with vector RAG">
        <div className="sheet-head">
          <div>
            <div className="eyebrow">Same question, two ways to build context</div>
            <h2>{v.started?.question}</h2>
          </div>
          <div className="meta-row" style={{ marginTop: 0 }}>
            {v.started?.mock && <span className="tag mock">Mock run</span>}
            {b?.illustrative && <span className="tag mock" title="Hand-written example of a typical vector-RAG failure">Illustrative example</span>}
          </div>
        </div>
        <div className="cols">
          <div className="col">
            <h3>Vector RAG</h3>
            <div className="how">Top {b?.chunks.length ?? 3} {b?.chunks.length === 1 ? "chunk" : "chunks"} by text similarity. Relations are ignored.</div>
            {b ? (
              <>
                <p className="ans">{b.answer}</p>
                <h5>Context it was given</h5>
                {b.chunks.map((c) => (
                  <div className="chunk-card" key={c.id}>
                    <div className="top"><span>{c.label}</span><span className="muted">{c.score.toFixed(2)}</span></div>
                    {c.text}
                    <div className="bar"><i style={{ width: `${Math.round(c.score * 100)}%` }} /></div>
                  </div>
                ))}
                {missed.map((c, i) => (
                  <div key={i} className="verdict-line bad">
                    ⚠︎ Never sees {labelOf(idx, seen.has(c.a) ? c.b : c.a)}. The contradiction stays invisible.
                  </div>
                ))}
              </>
            ) : (
              <p className="muted">No baseline in this run.</p>
            )}
          </div>
          <div className="col graph-side">
            <h3>Graph Anchor</h3>
            <div className="how">Walks analyst-approved relations from the question's entities.</div>
            <p className="ans">{v.answer?.text}</p>
            {contra.map((c, i) => (
              <div className="contra-box" key={i}>
                <span aria-hidden="true">⚠︎</span>
                <div><strong>Contradiction flagged.</strong> {c.note}</div>
              </div>
            ))}
            <h5>Context it was given: the evidence path</h5>
            <ul className="path">
              {cited.map((e) => <li key={e.id}><Triple edge={e} idx={idx} /></li>)}
            </ul>
            <h5>Linked passages</h5>
            {(v.answer?.citations ?? []).filter((c) => c.chunk_id).map((c) => (
              <div className="chunk-card" key={c.chunk_id!}>
                <div className="top"><span>{labelOf(idx, c.chunk_id!)}</span></div>
                {idx.get(c.chunk_id!)?.text}
              </div>
            ))}
          </div>
        </div>
        <div className="foot">Similar text is not the same as related knowledge.</div>
      </section>
    </div>
  );
}
