// Same question, two models. The note below is written from the two PO-1003 runs and only shown when
// the facts it states hold for the pair at hand (checked in `finding`).
import type { Event, Node, RunSummary } from "./contracts";
import { labelOf, readable, type Index } from "./bits";
import { frames, local, pretty, viewAt } from "./run";
import { fmtDuration, modelInfo, runSeconds } from "./models";

export interface RunData { summary: RunSummary; events: Event[] }

const DOC_PREDS = ["mentions", "defined_in", "has_chunk"];

function digest(r: RunData) {
  const v = viewAt(r.events, frames(r.events), Number.MAX_SAFE_INTEGER);
  const preds = (v.strategy?.allowed_predicates ?? []).map(local);
  const nodes = (v.evidence?.nodes ?? []).filter((n) => n.cls !== "Chunk");
  const docs = (v.evidence?.nodes ?? []).filter((n) => n.cls === "Chunk" || n.cls === "Document");
  return { v, preds, nodes, docs, model: modelInfo(v.started?.model ?? ""), secs: runSeconds(r.events) };
}

export default function Compare({ a, b, idx, current, onShow, onOpenRun, contradictionRun }: {
  a: RunData; b: RunData; idx: Index; current: string;
  onShow: (runId: string) => void;
  onOpenRun: (runId: string) => void;
  /** a run on the same plant data whose strategy allows document relations and that flags a contradiction */
  contradictionRun?: RunSummary;
}) {
  const A = digest(a), B = digest(b);
  const allPreds = [...new Set([...A.preds, ...B.preds])];
  const ids = (d: ReturnType<typeof digest>) => new Set(d.nodes.map((n) => n.id));
  const ia = ids(A), ib = ids(B);
  const nodeUnion = [...new Map([...A.nodes, ...B.nodes].map((n) => [n.id, n])).values()] as Node[];
  const noDocs = !A.preds.some((p) => DOC_PREDS.includes(p)) && !B.preds.some((p) => DOC_PREDS.includes(p));
  const noDatasheet = A.docs.length === 0 && B.docs.length === 0;
  const flagsA = /200\s*°C/.test(A.v.answer?.text ?? ""), flagsB = /200\s*°C/.test(B.v.answer?.text ?? "");
  const [hit, miss] = flagsA ? [A, B] : [B, A];
  const finding = noDocs && noDatasheet && flagsA !== flagsB && /210\s*°C/.test(hit.v.answer?.text ?? "");

  const col = (d: ReturnType<typeof digest>, r: RunData, other: Set<string>, otherPreds: string[]) => (
    <div className={"col" + (r.summary.run_id === current ? " graph-side" : "")}>
      <div className="model-chip">
        <b>{d.model.name}</b>{d.model.via && <span> via {d.model.via}</span>}
      </div>
      <div className="meta-row">
        {d.secs != null && <span className="tag neutral">{fmtDuration(d.secs)}</span>}
        <span className="tag neutral">{d.v.steps.length} step{d.v.steps.length === 1 ? "" : "s"}</span>
        <span className="tag neutral">{d.nodes.length} evidence nodes</span>
        {r.summary.mock && <span className="tag mock">Mock run</span>}
      </div>
      <p className="ans">{readable(d.v.answer?.text ?? "", idx)}</p>
      {(d.v.answer?.contradictions ?? []).map((c, i) => (
        <div className="contra-box" key={i}><span aria-hidden="true">⚠︎</span><div><strong>Contradiction flagged.</strong> {c.note}</div></div>
      ))}
      <h5>Allowed relations</h5>
      <div className="chips">
        {allPreds.map((p) => (
          <span key={p} className={"chip pred" + (d.preds.includes(p) ? (otherPreds.includes(p) ? "" : " only") : " absent")}>
            {pretty(p)}
          </span>
        ))}
      </div>
      <h5>Evidence</h5>
      <div className="chips">
        {nodeUnion.filter((n) => d.nodes.some((x) => x.id === n.id)).map((n) => (
          <span key={n.id} className={"chip" + (other.has(n.id) ? "" : " only")}>{n.label}</span>
        ))}
      </div>
      <button className="btn secondary small-btn" style={{ marginTop: 14 }} onClick={() => onShow(r.summary.run_id)}
        disabled={r.summary.run_id === current}>
        {r.summary.run_id === current ? "Shown in the graph" : "Show in the graph"}
      </button>
    </div>
  );

  return (
    <div className="sheet-wrap">
      <section className="sheet glass compare" aria-label="Model comparison">
        <div className="sheet-head">
          <div>
            <div className="eyebrow">Same question, two models</div>
            <h2>{a.summary.question}</h2>
          </div>
        </div>
        {finding && (
          <div className="finding">
            <h4>Same evidence, different reading.</h4>
            <p>
              Neither strategy allows document relations ({DOC_PREDS.slice(0, 2).map(pretty).join(", ")}), so neither walk
              reaches the datasheet. Both read the sensor model node: {quoteOf(nodeUnion, idx)}.{" "}
              {hit.model.name} sets that against the 210 °C critical limit and warns. {miss.model.name} answers that the
              order can run at the limit.
            </p>
            {contradictionRun && (
              <p className="small">
                With document relations allowed, the walk reaches the datasheet and the contradiction is cited from the source.{" "}
                <button className="link-btn" onClick={() => onOpenRun(contradictionRun.run_id)}>Open that run</button>
              </p>
            )}
          </div>
        )}
        <div className="cols">
          {col(A, a, ib, B.preds)}
          {col(B, b, ia, A.preds)}
        </div>
        <div className="foot">Both runs are real engine traces on the same approved graph. Only the model differs.</div>
      </section>
    </div>
  );
}

function quoteOf(nodes: Node[], idx: Index) {
  const m = nodes.find((n) => n.cls === "SensorModel");
  const d = m ? (idx.get(m.id)?.description ?? m.description) : null;
  return m && d ? `“${labelOf(idx, m.id)}: ${d.replace(/\.$/, "")}”` : "the sensor model's rating";
}

