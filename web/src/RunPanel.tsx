import { useEffect, useRef, useState } from "react";
import type { Edge, ModelInfo, RunSummary } from "./contracts";
import { labelOf, readable, Triple, type Index } from "./bits";
import type { RunView } from "./run";
import { pretty } from "./run";
import { FlagIcon } from "./Curate";
import { fmtDuration, modelInfo } from "./models";

export interface RunMeta { model: string; secs: number | null }

interface PickerProps {
  runs: RunSummary[];
  meta: Map<string, RunMeta>;
  live: boolean;
  onPick: (id: string) => void;
  /** resolves to an error message for the visitor, or null once the run started */
  onAsk: (q: string, invite: string, model?: string) => Promise<string | null>;
  /** live models to choose from; fewer than two means no choice is shown and the server default runs */
  models: ModelInfo[];
}

const INVITE_KEY = "graph-anchor.invite";
const loadInvite = () => { try { return localStorage.getItem(INVITE_KEY) ?? ""; } catch { return ""; } };
const saveInvite = (v: string) => { try { localStorage.setItem(INVITE_KEY, v); } catch { /* private window */ } };
const PROVIDER: Record<string, string> = { gateway: "gateway", "ibm-ica": "IBM ICA" };
const MODEL_KEY = "graph-anchor.model";
const loadModel = () => { try { return localStorage.getItem(MODEL_KEY) ?? ""; } catch { return ""; } };
const saveModel = (v: string) => { try { localStorage.setItem(MODEL_KEY, v); } catch { /* private window */ } };

export function Picker({ runs, meta, live, models, onPick, onAsk }: PickerProps) {
  const [q, setQ] = useState("");
  const [invite, setInvite] = useState(loadInvite);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState(loadModel);
  const choice = models.length > 1;
  const model = choice ? (models.find((m) => m.id === picked) ?? models[0]).id : undefined;
  // runs of the same question with different models share one card
  const groups = [...runs.reduce((m, r) => m.set(r.question, [...(m.get(r.question) ?? []), r]), new Map<string, RunSummary[]>()).values()];
  const askForm = (
    <form
      style={{ marginTop: live ? 0 : 22, marginBottom: live ? 22 : 0 }}
      onSubmit={async (e) => {
        e.preventDefault();
        if (!q.trim() || !invite.trim()) return;
        saveInvite(invite.trim());
        setBusy(true); setErr(null);
        const m = await onAsk(q.trim(), invite.trim(), model);
        setBusy(false); setErr(m);
      }}
    >
      <label className="eyebrow" htmlFor="ask">{live ? "Ask your own question" : "Or ask your own"}</label>
      <div className="ask-field">
        <input id="ask" value={q} onChange={(e) => setQ(e.target.value)} disabled={!live}
          placeholder={live ? "Ask about orders, stations, sensors…" : "Live mode is off"} />
        <button className="btn" disabled={!live || !q.trim() || !invite.trim() || busy}>{busy ? "Starting…" : "Ask"}</button>
      </div>
      {live && choice && (
        <label className="field model">
          <span>Model</span>
          <select value={model} onChange={(e) => { setPicked(e.target.value); saveModel(e.target.value); }}>
            {models.map((m) => <option key={m.id} value={m.id}>{m.label} · {PROVIDER[m.provider] ?? m.provider}</option>)}
          </select>
          <em>Granite ~30 s · Mistral Large via gateway: several minutes today</em>
        </label>
      )}
      {live && (
        <label className="field invite">
          <span>Invite code</span>
          <input value={invite} onChange={(e) => setInvite(e.target.value)} placeholder="From the presenter" spellCheck={false} autoComplete="off" />
        </label>
      )}
      {err && <div className="hint error" role="alert">{err}</div>}
      {live && !err && <div className="hint">{choice ? "" : "A live run takes a minute or more. "}The recorded runs below replay instantly.</div>}
      {!live && <div className="hint">Offline replay. Live questions need the engine API.</div>}
    </form>
  );
  return (
    <aside className="panel glass" aria-label="Ask a question">
      <div className="panel-head">
        <div className="eyebrow">Ask the twin</div>
        <h2 className="question">{live ? "Ask a question" : "Pick a question"}. Watch which knowledge the model is given.</h2>
      </div>
      <div className="panel-body">
        {live && askForm}
        {live && <div className="eyebrow" style={{ marginBottom: 8 }}>Or replay a recorded run</div>}
        <div className="pick">
          {groups.map((g) => (
            <button key={g[0].run_id} className="pick-q" onClick={() => onPick(g[0].run_id)}>
              <div className="q">{g[0].question}</div>
              <div className="row">
                {g.length > 1
                  ? g.map((r) => <span key={r.run_id} className="tag neutral">{modelInfo(meta.get(r.run_id)?.model ?? "").name}</span>)
                  : <span className="tag neutral">Recorded run</span>}
                {g.some((r) => r.mock) && <span className="tag mock">Mock</span>}
              </div>
            </button>
          ))}
        </div>
        {!live && askForm}
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
  /** other runs of the same question with a different model */
  models: { run_id: string; model: string; secs: number | null }[];
  current: string;
  onSwitch: (runId: string) => void;
  onCompare: () => void;
}

export function RunPanel({ view: v, idx, edges, live, lost, onBack, onCite, reported, onReport, models, current, onSwitch, onCompare }: RunProps) {
  const body = useRef<HTMLDivElement>(null);
  const cards = (v.strategy ? 1 : 0) + (v.seeds.length ? 1 : 0) + v.steps.length * 2 + (v.answer ? 1 : 0) + (v.evidence ? 1 : 0);
  useEffect(() => {
    const el = body.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [cards]);

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
          {v.started && models.length < 2 && <span className="tag neutral">{modelInfo(v.started.model).name}</span>}
        </div>
        {models.length > 1 && (
          <div className="model-switch">
            <div className="segmented mini" role="group" aria-label="Model">
              {models.map((m) => (
                <button key={m.run_id} aria-pressed={m.run_id === current} onClick={() => onSwitch(m.run_id)}>
                  {modelInfo(m.model).name}{m.secs != null && <span className="count"> {fmtDuration(m.secs)}</span>}
                </button>
              ))}
            </div>
            <button className="link-btn" onClick={onCompare}>Compare</button>
          </div>
        )}
      </div>
      <div className="panel-body" ref={body} aria-live="polite">
        {lost && <div className="banner">Connection lost. Showing the events received so far.</div>}
        {v.finished?.status === "error" && (
          <div className="banner" title={v.finished.error ?? undefined}>The model is not available right now. Replay one of the recorded runs.</div>
        )}

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
        {live && !v.finished && !lost && (
          <Waiting key={cards}
            text={!v.strategy ? "Waiting for the model to choose a strategy…" : !v.answer ? "Waiting for the model to walk the graph…" : "Finishing…"} />
        )}
      </div>
    </aside>
  );
}

/** Shown while a live run is quiet; the clock restarts with each new card (remounted by key). */
function Waiting({ text }: { text: string }) {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    const t0 = Date.now();
    const t = setInterval(() => setSecs(Math.floor((Date.now() - t0) / 1000)), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="waiting" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{text}</span>
      <span className="secs" aria-hidden="true">{secs} s</span>
    </div>
  );
}
