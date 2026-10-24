import { useEffect, useRef, useState } from "react";
import type { Edge, RunSummary } from "./contracts";
import { labelOf, readable, Triple, type Index } from "./bits";
import type { RunView } from "./run";
import { pretty } from "./run";
import { FlagIcon } from "./Curate";

interface PickerProps {
  runs: RunSummary[];
  live: boolean;
  onPick: (id: string) => void;
  onAsk: (q: string) => void;
}

export function Picker({ runs, live, onPick, onAsk }: PickerProps) {
  const [q, setQ] = useState("");
  return (
    <aside className="panel glass" aria-label="Ask a question">
      <div className="panel-head">
        <div className="eyebrow">Ask the twin</div>
        <h2 className="question">Pick a question. Watch which knowledge the model is given.</h2>
      </div>
      <div className="panel-body">
        <div className="pick">
          {runs.map((r) => (
            <button key={r.run_id} className="pick-q" onClick={() => onPick(r.run_id)}>
              <div className="q">{r.question}</div>
              <div className="row">
                <span className="tag neutral">Recorded run</span>
                {r.mock && <span className="tag mock">Mock</span>}
              </div>
            </button>
          ))}
        </div>
        <form
          style={{ marginTop: 22 }}
          onSubmit={(e) => {
            e.preventDefault();
            if (q.trim()) onAsk(q.trim());
          }}
        >
          <label className="eyebrow" htmlFor="ask">Or ask your own</label>
          <div className="ask-field">
            <input id="ask" value={q} onChange={(e) => setQ(e.target.value)} disabled={!live}
              placeholder={live ? "Ask about orders, stations, sensors…" : "Live mode is off"} />
            <button className="btn" disabled={!live || !q.trim()}>Ask</button>
          </div>
          {!live && <div className="hint">Offline replay. Live questions need the engine API.</div>}
        </form>
      </div>
    </aside>
  );
}

interface RunProps {
  view: RunView;
  idx: Index;
  edges: Map<string, Edge>;
  live: boolean;
  lost: boolean;
  onBack: () => void;
  onCite: (id: string) => void;
  reported: boolean;
  onReport: () => void;
  answerOnly?: boolean;
}

export function RunPanel({ view: v, idx, edges, live, lost, onBack, onCite, reported, onReport, answerOnly = false }: RunProps) {
  const body = useRef<HTMLDivElement>(null);
  const cards = (v.strategy ? 1 : 0) + (v.seeds.length ? 1 : 0) + v.steps.length * 2 + (v.answer ? 1 : 0) + (v.evidence ? 1 : 0);
  useEffect(() => {
    const el = body.current;
    if (el) el.scrollTo({ top: answerOnly ? 0 : el.scrollHeight, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  }, [cards, answerOnly]);

  return (
    <aside className="panel glass" aria-label="Run">
      <div className="panel-head">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="eyebrow">Question</div>
          <button className="link-btn" onClick={onBack}>Change</button>
        </div>
        <h2 className="question">{v.started?.question ?? "…"}</h2>
        <div className="meta-row">
          <span className={"tag " + (live ? "live" : "neutral")}>{live ? "Live run" : "Replay"}</span>
          {v.started?.mock && <span className="tag mock" title="Hand-curated run, not produced by the engine">Mock run</span>}
          {v.started && <span className="tag neutral">{v.started.model.split("/").pop()}</span>}
        </div>
      </div>
      <div className="panel-body" ref={body} aria-live="polite">
        {lost && <div className="banner">Connection lost. Showing the events received so far.</div>}
        {v.finished?.status === "error" && <div className="banner">Run failed: {v.finished.error}</div>}

        {!live && !v.started?.mock && <p className="replay-note">Earlier recorded example. The maintenance dataset has since been rebuilt; this answer retains its original evidence.</p>}

        {!answerOnly && <>
        {v.strategy && (
          <section className="card">
            <h3>Strategy</h3>
            <p><strong>{v.strategy.question_type}</strong></p>
            <p className="muted small">{v.strategy.rationale}</p>
            <div className="eyebrow" style={{ marginTop: 12 }}>
              Allowed relations · depth {v.strategy.max_depth}
            </div>
            <div className="chips">
              {v.strategy.allowed_predicates.map((p) => <span key={p} className="chip pred">{pretty(p)}</span>)}
            </div>
          </section>
        )}

        {v.seeds.length > 0 && (
          <section className="card">
            <h3>Entry points</h3>
            <p className="muted small">Found by similarity to the question. The walk starts here.</p>
            <div className="chips">
              {v.seeds.map((s) => (
                <button key={s.id} className="chip" onClick={() => onCite(s.id)}>
                  {s.label}<span className="score">{s.score.toFixed(2)}</span>
                </button>
              ))}
            </div>
          </section>
        )}

        {v.steps.map(({ payload: s, verdicts }) => {
          const byEdge = new Map(s.decisions.map((d) => [d.edge_id, d]));
          const local = new Map(idx);
          s.nodes.forEach((n) => local.set(n.id, n));
          return (
            <section className="card" key={s.n}>
              <h3>Step <span className="n">{s.n}</span>
                <span className="muted small" style={{ fontWeight: 400 }}>
                  {s.frontier.length} candidate relation{s.frontier.length === 1 ? "" : "s"}
                </span>
              </h3>
              <ul className="decisions">
                {s.frontier.map((e) => {
                  const d = verdicts ? byEdge.get(e.id) : undefined;
                  const vd = d?.verdict ?? (verdicts ? "prune" : "pending");
                  return (
                    <li key={e.id} className={"decision " + vd}>
                      <span className={"verdict " + vd}>{vd === "pending" ? "…" : vd}</span>
                      <div>
                        <Triple edge={e} idx={local} />
                        {d && <div className="reason">{d.reason}</div>}
                      </div>
                    </li>
                  );
                })}
              </ul>
              {verdicts && s.sufficient && <div className="sufficient">● Enough evidence. Stop walking.</div>}
            </section>
          );
        })}

        </>}

        {answerOnly && !v.answer && <div className="chat-traversing" role="status"><span className="traversing-dot" />{v.steps.length ? `Checking relationships · hop ${v.steps[v.steps.length - 1]?.payload.n}` : v.seeds.length ? "Locating relevant entities…" : v.strategy ? "Preparing the evidence search…" : "Opening the recorded question…"}<p>The graph and evidence trail appear with the answer.</p></div>}

        {v.answer && (
          <section className="card answer">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3>Answer</h3>
              <button className={"report-btn" + (reported ? " done" : "")} onClick={onReport} disabled={reported}
                title="Something in this answer is wrong">
                <FlagIcon /> {reported ? "Reported" : "Report"}
              </button>
            </div>
            <p className="answer-text">{readable(v.answer.text, idx)}</p>
            {v.answer.contradictions?.map((c, i) => (
              <div className="contra-box" key={i} role="note">
                <span aria-hidden="true">⚠︎</span>
                <div><strong>Contradiction flagged.</strong> {c.note}
                  <div className="small" style={{ opacity: 0.85, marginTop: 2 }}>
                    {labelOf(idx, c.a)} ↔ {labelOf(idx, c.b)}
                  </div>
                </div>
              </div>
            ))}
            <p className="justification">{readable(v.answer.justification, idx)}</p>
            <div className="eyebrow" style={{ marginTop: 14 }}>Cited</div>
            <div className="cites">
              {v.answer.citations.map((c, i) => {
                if (c.edge_id) {
                  const e = edges.get(c.edge_id);
                  return (
                    <button key={i} className="cite" onClick={() => onCite(c.edge_id!)}>
                      {e ? <Triple edge={e} idx={idx} /> : c.edge_id}
                    </button>
                  );
                }
                if (c.chunk_id) {
                  return (
                    <button key={i} className="cite chunk" onClick={() => onCite(c.chunk_id!)}>
                      {labelOf(idx, c.chunk_id)}
                    </button>
                  );
                }
                return null;
              })}
            </div>
          </section>
        )}

        {v.evidence && (
          <section className="card evidence-card">
            <h3>Evidence graph</h3>
            <p className="small">
              {v.evidence.nodes.filter((n) => n.cls !== "Chunk").length} entities,{" "}
              {v.evidence.nodes.filter((n) => n.cls === "Chunk").length} text passages and {v.evidence.edges.length} relations led to this answer.
              Click a document to read its passages.
              Everything else the walk looked at is dimmed. This is the context the model was given, not a claim about what it thought.
            </p>
          </section>
        )}
      </div>
    </aside>
  );
}
