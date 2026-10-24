// Phone version, opened from the "Try it yourself" QR code: ask a question, read the answer and its sources,
// see the evidence graph small. Same event stream and canary rules as the desktop app, no projector chrome.
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChatCanaryReveal, Edge, Event, GraphExport, RunSummary } from "./contracts";
import { data } from "./data";
import Graph from "./Graph";
import { CONTRA_PREFIX, frames, labelIndex, pretty, runElements, viewAt, type RunView } from "./run";
import { fold, foldClasses } from "./fold";
import { labelOf, Mark, readable, Triple, type Index } from "./bits";
import { loadInvite, saveInvite } from "./TryIt";
import { HttpError } from "./data";
import "./presentation.css";
import { FlagIcon } from "./Curate";
import { Toast } from "./Oversight";
import { audit } from "./canary";
import Imprint from "./Imprint";

const STEP_MS = 650;
const NO_INSET = { top: 0, right: 0, bottom: 0, left: 0 };
/** What a visitor reads when startRun rejects. */
function startError(err: unknown): string {
  if (err instanceof HttpError) {
    if (err.status === 403) return "Invite code needed. Ask the presenter for one.";
    if (err.status === 429) {
      const s = err.retryAfter ?? 5;
      return `Busy, try again in ${s < 90 ? `${s} s` : `${Math.ceil(s / 60)} min`}.`;
    }
    if (err.status === 422) return "That question is too long. Shorten it a little.";
  }
  return "The live engine is not reachable. Watch a recorded run instead.";
}

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function inviteFromUrl(): string {
  const u = new URL(location.href);
  const code = u.searchParams.get("invite")?.trim();
  if (!code) return loadInvite();
  saveInvite(code);
  // drop the code from the address bar so a shared link or screenshot does not carry it on
  u.searchParams.delete("invite");
  history.replaceState(null, "", u.pathname + "?m");
  return code;
}

// same light/dark choice as the presentation (dark unless the visitor switched)
try { document.documentElement.dataset.presentationTheme = localStorage.getItem("graph-anchor-theme") === "light" ? "light" : "dark"; } catch { /* default */ }

export default function Mobile() {
  const [invite, setInvite] = useState(inviteFromUrl);
  const [graph, setGraph] = useState<GraphExport>({ nodes: [], edges: [] });
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [pos, setPos] = useState(0);
  const [live, setLive] = useState(false);
  const [lost, setLost] = useState(false);
  const [reported, setReported] = useState<Set<string>>(new Set());
  const [reveal, setReveal] = useState<ChatCanaryReveal | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const stopStream = useRef<() => void>(() => {});

  useEffect(() => {
    data.getGraph().then(setGraph);
    data.listRuns().then(setRuns);
    return () => stopStream.current();
  }, []);

  const fs = useMemo(() => frames(events), [events]);
  // a live run shows each event as it arrives; a recorded one plays out quickly so it reads like one
  const shown = live ? fs.length - 1 : pos;
  useEffect(() => {
    if (live || !runId || pos >= fs.length - 1) return;
    const t = setTimeout(() => setPos((p) => p + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [live, runId, pos, fs.length]);
  const v = useMemo(() => viewAt(events, fs, shown), [events, fs, shown]);
  const runEls = useMemo(() => runElements(events), [events]);
  const idx = useMemo(() => labelIndex([...graph.nodes, ...runEls.nodes]), [graph, runEls]);
  const edges = useMemo(() => new Map([...graph.edges, ...runEls.edges].map((e) => [e.id, e])), [graph, runEls]);

  const back = () => {
    stopStream.current();
    // recorded chat-canary demo: leaving a planted false answer unreported shows what was missed
    const c = v.answer?.canary;
    if (!live && runId && c && !reported.has(runId)) {
      audit("canary_failed", `Planted false answer not reported: "${c.claim}"`);
      setReveal({ run_id: runId, claim: c.claim, truth: c.truth, outcome: "missed" });
    }
    setRunId(null); setEvents([]); setPos(0); setLive(false); setLost(false);
    window.scrollTo({ top: 0 });
  };

  const replay = async (id: string) => {
    const ev = await data.getRun(id);
    setLive(false); setLost(false); setRunId(id); setEvents(ev);
    setPos(reducedMotion() ? frames(ev).length - 1 : 0);
  };

  const ask = async (q: string): Promise<string | null> => {
    try {
      const { run_id, reveal: r } = await data.startRun(q, invite);
      if (r?.outcome === "missed") setReveal(r);
      stopStream.current();
      setLive(true); setLost(false); setRunId(run_id); setEvents([]);
      stopStream.current = data.streamRun(
        run_id,
        (e) => setEvents((xs) => (xs.some((x) => x.seq === e.seq) ? xs : [...xs, e])),
        () => setLost(true),
      );
      return null;
    } catch (err) {
      return startError(err);
    }
  };

  const report = async (text: string) => {
    if (!runId) return;
    setReported((r) => new Set(r).add(runId));
    if (live) {
      const res = await data.feedback(runId, text).catch(() => ({ reveal: null }));
      if (res.reveal?.outcome === "caught") setReveal(res.reveal);
      else setToast("Thanks, an analyst will review this answer.");
      return;
    }
    const c = v.answer?.canary;
    if (c) {
      audit("canary_passed", `Planted false answer reported: "${c.claim}"`);
      setReveal({ run_id: runId, claim: c.claim, truth: c.truth, outcome: "caught" });
    } else {
      audit("decision", `Answer reported for review: "${v.started?.question ?? runId}"`);
      setToast("Reported. An analyst will review this answer.");
    }
  };

  const opened = (target: string) => { if (live && runId) data.opened(runId, target).catch(() => {}); };

  return (
    <div className="m">
      <header className="m-bar">
        {runId
          ? <button className="link-btn" onClick={back}>‹ Questions</button>
          : <span className="m-brand"><Mark /> Graph Anchor</span>}
        <span className={"tag " + (data.live ? "live" : "neutral")}><span className="dot" />{data.live ? "Live" : "Offline"}</span>
      </header>
      {runId
        ? <RunScreen v={v} idx={idx} edges={edges} live={live} lost={lost} done={!live && pos >= fs.length - 1}
            reported={reported.has(runId)} onReport={report} onOpened={opened} />
        : <Home runs={runs} invite={invite} onInvite={(c) => { setInvite(c); saveInvite(c); }} onAsk={ask} onReplay={replay} />}
      {toast && <Toast text={toast} onDone={() => setToast(null)} />}
      {reveal && <RevealSheet r={reveal} onClose={() => setReveal(null)} />}
    </div>
  );
}

function Home({ runs, invite, onInvite, onAsk, onReplay }: {
  runs: RunSummary[]; invite: string; onInvite: (c: string) => void;
  onAsk: (q: string) => Promise<string | null>; onReplay: (id: string) => void;
}) {
  const [q, setQ] = useState("");
  const [editInvite, setEditInvite] = useState(!invite);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // one card per question; the first recorded run of it stands for the group
  const questions = [...new Map(runs.map((r) => [r.question, r] as const)).values()]
    .filter((r, _, all) => !r.mock || !all.some((x) => x.question === r.question && !x.mock));
  return (
    <main className="m-body">
      <h1 className="m-title">Ask the digital twin.</h1>
      <p className="muted">Every answer comes from one curated knowledge graph. You see which facts the model was given.</p>
      <form className="m-ask" onSubmit={async (e) => {
        e.preventDefault();
        if (!q.trim() || !invite) return;
        setBusy(true); setErr(null);
        const m = await onAsk(q.trim());
        setBusy(false); setErr(m);
        if (m?.startsWith("Invite")) setEditInvite(true);
      }}>
        <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={3} disabled={!data.live} enterKeyHint="send"
          placeholder={data.live ? "e.g. Which supplier delivers the film for order PO-1003?" : "Live mode is off"}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }} />
        {data.live && (editInvite
          ? <label className="field"><span>Invite code</span>
              <input value={invite} onChange={(e) => onInvite(e.target.value.trim())} placeholder="From the presenter"
                spellCheck={false} autoComplete="off" autoCapitalize="off" /></label>
          : <div className="hint">Invite code saved · <button type="button" className="link-btn small" onClick={() => setEditInvite(true)}>change</button></div>)}
        <button className="btn m-wide" disabled={!data.live || !q.trim() || !invite || busy}>{busy ? "Starting…" : "Ask"}</button>
        {err && <div className="hint error" role="alert">{err}</div>}
        {!err && <div className="hint">{data.live ? "A live answer takes about a minute." : "Offline replay. Pick a recorded run below."}</div>}
      </form>

      <div className="eyebrow m-section">Or watch a recorded run</div>
      <div className="pick">
        {questions.map((r) => (
          <button key={r.run_id} className="pick-q" onClick={() => onReplay(r.run_id)}>
            <div className="q">{r.question}</div>
            {r.mock && <div className="row"><span className="tag mock">Mock</span></div>}
          </button>
        ))}
      </div>
      <p className="m-foot"><a href="?full">Open the full version</a> · <Imprint /></p>
    </main>
  );
}

function RunScreen({ v, idx, edges, live, lost, done, reported, onReport, onOpened }: {
  v: RunView; idx: Index; edges: Map<string, Edge>; live: boolean; lost: boolean; done: boolean;
  reported: boolean; onReport: (text: string) => void; onOpened: (target: string) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  const cards = (v.strategy ? 1 : 0) + v.steps.length + (v.answer ? 1 : 0) + (v.evidence ? 1 : 0);
  // follow the run down the page until the answer lands; then the reader scrolls
  useEffect(() => {
    if (cards && !v.answer) end.current?.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "end" });
  }, [cards, v.answer]);

  return (
    <main className="m-body">
      <div className="meta-row" style={{ marginTop: 0 }}>
        <span className={"tag " + (live ? "live" : "neutral")}>{live ? "Live run" : "Replay"}</span>
        {v.started?.mock && <span className="tag mock">Mock run</span>}
      </div>
      <h1 className="m-question">{v.started?.question ?? "…"}</h1>
      {lost && <div className="banner">Connection lost. Showing what arrived so far.</div>}
      {v.finished?.status === "error" && <div className="banner">The model is not available right now. Try a recorded run.</div>}

      <ol className="m-steps">
        {v.strategy && (
          <li><b>Strategy</b> {v.strategy.question_type}
            <div className="chips">{v.strategy.allowed_predicates.map((p) => <span key={p} className="chip pred">{pretty(p)}</span>)}</div>
          </li>
        )}
        {v.seeds.length > 0 && <li><b>Entry points</b> {v.seeds.map((s) => s.label).join(", ")}</li>}
        {v.steps.map(({ payload: s, verdicts }) => {
          const follow = s.decisions.filter((d) => d.verdict === "follow").length;
          const byEdge = new Map(s.decisions.map((d) => [d.edge_id, d]));
          const local = new Map(idx);
          s.nodes.forEach((n) => local.set(n.id, n));
          return (
            <li key={s.n}>
              <details>
                <summary><b>Step {s.n}</b> {verdicts
                  ? `${follow} followed · ${s.frontier.length - follow} pruned${s.sufficient ? " · enough" : ""}`
                  : `${s.frontier.length} candidates…`}</summary>
                <ul className="decisions">
                  {s.frontier.map((e) => {
                    const d = verdicts ? byEdge.get(e.id) : undefined;
                    const vd = d?.verdict ?? (verdicts ? "prune" : "pending");
                    return (
                      <li key={e.id} className={"decision " + vd}>
                        <span className={"verdict " + vd}>{vd === "pending" ? "…" : vd}</span>
                        <div><Triple edge={e} idx={local} />{d && <div className="reason">{d.reason}</div>}</div>
                      </li>
                    );
                  })}
                </ul>
              </details>
            </li>
          );
        })}
      </ol>

      {live && !v.finished && !lost && (
        <div className="waiting" role="status"><span className="spinner" aria-hidden="true" />
          {!v.strategy ? "Choosing a strategy…" : !v.answer ? "Walking the graph…" : "Finishing…"}</div>
      )}
      {!live && !done && !v.answer && <div className="waiting" role="status"><span className="spinner" aria-hidden="true" />Replaying…</div>}

      {v.answer && <Answer v={v} idx={idx} edges={edges} reported={reported} onReport={onReport} onOpened={onOpened} />}
      {v.evidence && <MiniGraph v={v} onOpened={() => onOpened("evidence")} />}
      <div ref={end} />
    </main>
  );
}

function Answer({ v, idx, edges, reported, onReport, onOpened }: {
  v: RunView; idx: Index; edges: Map<string, Edge>; reported: boolean;
  onReport: (text: string) => void; onOpened: (target: string) => void;
}) {
  const a = v.answer!;
  const [flagging, setFlagging] = useState(false);
  const [text, setText] = useState("");
  const [openChunk, setOpenChunk] = useState<string | null>(null);
  const chunkText = (id: string) => v.evidence?.nodes.find((n) => n.id === id)?.text ?? idx.get(id)?.text ?? null;
  return (
    <section className="card answer">
      <div className="m-answer-head">
        <h3>Answer</h3>
        <button className={"report-btn" + (reported ? " done" : "")} disabled={reported} onClick={() => setFlagging((f) => !f)}>
          <FlagIcon /> {reported ? "Reported" : "Report"}
        </button>
      </div>
      {flagging && !reported && (
        <form className="m-flag" onSubmit={(e) => { e.preventDefault(); onReport(text.trim()); setFlagging(false); }}>
          <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="What is wrong? (optional)" />
          <button className="btn">Send report</button>
        </form>
      )}
      <p className="answer-text">{readable(a.text, idx)}</p>
      {a.contradictions?.map((c, i) => (
        <div className="contra-box" key={i} role="note">
          <span aria-hidden="true">⚠︎</span>
          <div><strong>Contradiction flagged.</strong> {c.note}
            <div className="small" style={{ opacity: 0.85, marginTop: 2 }}>{labelOf(idx, c.a)} ↔ {labelOf(idx, c.b)}</div>
          </div>
        </div>
      ))}
      <p className="justification">{readable(a.justification, idx)}</p>
      <div className="eyebrow" style={{ marginTop: 14 }}>Cited · tap a passage to read it</div>
      <div className="cites">
        {a.citations.map((c, i) => {
          if (c.edge_id) {
            const e = edges.get(c.edge_id);
            return <div key={i} className="cite">{e ? <Triple edge={e} idx={idx} /> : c.edge_id}</div>;
          }
          if (c.chunk_id) {
            const id = c.chunk_id;
            const open = openChunk === id;
            return (
              <button key={i} className="cite chunk" aria-expanded={open}
                onClick={() => { setOpenChunk(open ? null : id); if (!open) onOpened(id); }}>
                {labelOf(idx, id)}
                {open && <span className="m-passage">{chunkText(id) ?? "Passage text not available."}</span>}
              </button>
            );
          }
          return null;
        })}
      </div>
    </section>
  );
}

function MiniGraph({ v, onOpened }: { v: RunView; onOpened: () => void }) {
  const ev = v.evidence!;
  const [picked, setPicked] = useState<string | null>(null);
  const seen = useRef(false);
  const touch = () => { if (!seen.current) { seen.current = true; onOpened(); } };
  const { folded, classes } = useMemo(() => {
    const ids = new Set(ev.nodes.map((n) => n.id));
    const contra = (v.answer?.contradictions ?? []).filter((c) => ids.has(c.a) && ids.has(c.b))
      .map((c) => ({ id: CONTRA_PREFIX + c.a + "|" + c.b, s: c.a, o: c.b, p: "contradicts", graph: "approved" as const }));
    const folded = fold(ev.nodes, [...ev.edges, ...contra]);
    return { folded, classes: foldClasses(v.classes, folded) };
  }, [ev, v.answer, v.classes]);
  const focus = useMemo(() => folded.nodes.map((n) => n.id), [folded]);
  // frame again once the card has its final size and the layout has settled
  const [settled, setSettled] = useState(false);
  useEffect(() => { const t = setTimeout(() => setSettled(true), 600); return () => clearTimeout(t); }, []);
  const label = picked ? folded.nodes.find((n) => n.id === picked) : undefined;
  return (
    <section className="card m-evidence" onTouchStart={touch} onMouseDown={touch}>
      <h3>Evidence graph</h3>
      <p className="small muted">
        {ev.nodes.filter((n) => n.cls !== "Chunk").length} entities and {ev.edges.length} relations: the context the model was given.
        Pinch to zoom, tap a node.
      </p>
      <Graph className="mini-graph" nodes={folded.nodes} edges={folded.edges} classes={classes} mode="evidence"
        focus={focus} focusKey={`m:${focus.length}:${settled}`} inset={NO_INSET} flash={null} onSelect={setPicked} />
      <div className="small m-picked" aria-live="polite">
        {label ? <><b>{label.label}</b> <span className="muted">{label.cls}</span></> : <span className="muted">Nothing selected</span>}
      </div>
    </section>
  );
}

function RevealSheet({ r, onClose }: { r: ChatCanaryReveal; onClose: () => void }) {
  const caught = r.outcome === "caught";
  return (
    <div className="scrim" onClick={onClose}>
      <section className="alert-sheet" role="alertdialog" aria-modal="true" aria-labelledby="reveal-title" onClick={(e) => e.stopPropagation()}>
        <div className="alert-icon" aria-hidden="true">{caught ? "✓" : "!"}</div>
        <div className="eyebrow">Oversight check</div>
        <h2 id="reveal-title">{caught ? "Good catch." : "Your last answer contained a deliberately false fact."}</h2>
        <p className="muted">{caught
          ? "That answer was a test. One cited detail was swapped to see whether anyone checks the sources."
          : "One detail was swapped on purpose. The cited sources still showed the true fact."}</p>
        <div className="alert-claim"><span className="label">Planted, false</span>{r.claim}</div>
        <div className="alert-claim truth"><span className="label">True, per the sources</span>{r.truth}</div>
        <button className="btn m-wide" style={{ marginTop: 18 }} onClick={onClose}>Got it</button>
      </section>
    </div>
  );
}
