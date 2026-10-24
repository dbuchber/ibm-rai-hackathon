import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CreateProposal, Edge, Event, GraphExport, Node, Proposal, RunSummary } from "./contracts";
import { data, type Ontology } from "./data";
import { nodeIri, predIri } from "./ids";
import Graph, { type GraphMode } from "./Graph";
import { frames, labelIndex, runElements, viewAt, type FrameKind } from "./run";
import { Picker, RunPanel } from "./RunPanel";
import Contrast from "./Contrast";
import Curate, { kindOf } from "./Curate";
import Roadmap from "./Roadmap";
import Compare from "./Compare";
import { runSeconds } from "./models";
import type { RunMeta } from "./RunPanel";
import Inspector from "./Inspector";
import { fold, foldClasses } from "./fold";
import { AlertDialog, AuditDrawer, Toast, type OversightAlert } from "./Oversight";
import { audit, SUPERVISOR } from "./canary";
import type { AuditEntry } from "./contracts";
import type { Decision } from "./data";
import { Icon, Mark } from "./bits";

type View = "twin" | "ask" | "contrast" | "curate" | "roadmap";
const VIEWS: [View, string][] = [["twin", "Twin"], ["ask", "Ask"], ["contrast", "Contrast"], ["curate", "Curate"], ["roadmap", "Roadmap"]];

const HOLD: Record<FrameKind, number> = {
  question: 1400, strategy: 3200, seeds: 2200, frontier: 2000, verdicts: 3000, answer: 3400, evidence: 0,
};
const FRAME_LABEL: Record<FrameKind, string> = {
  question: "Question", strategy: "Strategy", seeds: "Entry points", frontier: "Candidates",
  verdicts: "Verdicts", answer: "Answer", evidence: "Evidence graph",
};

const EMPTY = new Map<string, string>();

export default function App() {
  const [view, setView] = useState<View>("twin");
  const [graph, setGraph] = useState<GraphExport>({ nodes: [], edges: [] });
  const [runs, setRuns] = useState<RunSummary[]>([]);
  // all recorded runs are small: load them once for model names, durations and the comparison
  const [runCache, setRunCache] = useState<Map<string, Event[]>>(new Map());
  const [compareOpen, setCompareOpen] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [pos, setPos] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [liveRun, setLiveRun] = useState(false);
  const [lost, setLost] = useState(false);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [focusChunk, setFocusChunk] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [alertBox, setAlertBox] = useState<OversightAlert | null>(null);
  const [auditOpen, setAuditOpen] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [reverted, setReverted] = useState<string[]>([]);
  const [ghosts, setGhosts] = useState<Proposal[]>([]); // failed canaries, kept only to label the audit log
  const [reported, setReported] = useState<Set<string>>(new Set());
  const chatPending = useRef<{ runId: string; question: string; canary: NonNullable<ReturnType<typeof canaryOf>> } | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [curFocus, setCurFocus] = useState<string[]>([]);
  const [baseOntology, setOntology] = useState<Ontology>({ classes: [], predicates: [] });
  const stopStream = useRef<() => void>(() => {});

  useEffect(() => {
    data.getGraph().then(setGraph);
    data.listRuns().then(async (rs) => {
      setRuns(rs);
      const all = await Promise.all(rs.map(async (r) => [r.run_id, await data.getRun(r.run_id).catch(() => [])] as const));
      setRunCache(new Map(all));
    });
    data.listProposals().then((p) => setProposals(p.map((x) => ({ ...x, kind: kindOf(x) }))));
    data.getOntology().then(setOntology).catch(() => {});
  }, []);

  // ---- run derivation ----
  const fs = useMemo(() => frames(events), [events]);
  const rv = useMemo(() => viewAt(events, fs, pos), [events, fs, pos]);
  const full = useMemo(() => viewAt(events, fs, fs.length - 1), [events, fs]);
  const runEls = useMemo(() => runElements(events), [events]);

  // proposal decisions override the graph state of their edge
  const status = useMemo(() => new Map(proposals.map((p) => [p.id, p.status])), [proposals]);
  // node and edge proposals are drawn in the graph (dashed until approved; rejected ones fade out)
  const prop = useMemo(() => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];
    const anchors = new Map<string, string>();
    for (const p of proposals) {
      if (p.status === "rejected") continue;
      if (kindOf(p) === "node" && p.node) {
        const id = nodeIri(p.node.cls, p.node.local_id);
        nodes.push({ id, cls: p.node.cls, label: p.node.label, description: p.node.description ?? null, text: null, props: {} });
        const near = p.evidence_chunk_id ?? graph.nodes.find((n) => n.cls === p.node!.cls)?.id;
        if (near) anchors.set(id, near);
      }
      if (kindOf(p) === "edge" && p.triple) edges.push({ id: p.id, ...p.triple, graph: p.status ?? "proposed" });
    }
    return { nodes, edges, anchors };
  }, [proposals, graph]);
  const ontology = useMemo<Ontology>(() => {
    const known = new Set(baseOntology.predicates.map((p) => p.iri));
    const added = proposals
      .filter((p) => kindOf(p) === "predicate" && p.status === "approved" && p.predicate && !known.has(predIri(p.predicate.name)))
      .map((p) => ({ iri: predIri(p.predicate!.name), name: p.predicate!.name, description: p.predicate!.description }));
    return { ...baseOntology, predicates: [...baseOntology.predicates, ...added] };
  }, [baseOntology, proposals]);

  const { nodes, edges } = useMemo(() => {
    const n = new Map<string, Node>();
    // people (badge holders) only add a hairball of zone access edges; no run walks them
    graph.nodes.forEach((x) => { if (x.cls !== "Person") n.set(x.id, x); });
    prop.nodes.forEach((x) => { if (!n.has(x.id)) n.set(x.id, x); });
    // run events embed nodes in full; they win so the run shows exactly what the model was given
    runEls.nodes.forEach((x) => n.set(x.id, x));
    const e = new Map<string, Edge>();
    for (const x of [...prop.edges, ...graph.edges, ...runEls.edges]) e.set(x.id, { ...x, graph: status.get(x.id) ?? x.graph });
    return { nodes: [...n.values()], edges: [...e.values()].filter((x) => x.graph !== "rejected" && n.has(x.s) && n.has(x.o)) };
  }, [graph, runEls, status, prop]);
  const idx = useMemo(() => labelIndex(nodes), [nodes]);
  // chunks are drawn one level down: hidden in the graph, lifted onto their documents (fold.ts)
  const folded = useMemo(() => fold(nodes, edges), [nodes, edges]);
  const edgeIdx = useMemo(() => new Map(edges.map((e) => [e.id, e])), [edges]);

  // ---- playback ----
  useEffect(() => {
    if (!playing || view !== "ask") return;
    if (pos >= fs.length - 1) {
      if (!liveRun || full.finished) setPlaying(false);
      return;
    }
    const t = setTimeout(() => setPos((p) => p + 1), pos < 0 ? 200 : HOLD[fs[pos].kind]);
    return () => clearTimeout(t);
  }, [playing, pos, fs, view, liveRun, full.finished]);

  // Chat canary (click mock): leaving a planted false answer without reporting it raises the alert.
  const moveOn = useCallback(() => {
    const c = chatPending.current;
    chatPending.current = null;
    if (!c) return;
    audit("canary_failed", `Planted false answer not reported: "${c.canary.claim}"`);
    audit("supervisor_notified", `${SUPERVISOR} notified.`);
    setAlertBox({ kind: "chat", canary: c.canary, question: c.question, supervisor: SUPERVISOR });
  }, []);
  const go = (v: View) => { if (v !== view) { moveOn(); setAuditOpen(false); setCompareOpen(false); } setView(v); };

  const pick = useCallback(async (id: string) => {
    moveOn();
    stopStream.current();
    setCompareOpen(false);
    const ev = await data.getRun(id);
    setLiveRun(false); setLost(false);
    setRunId(id); setEvents(ev); setPos(0); setPlaying(true); setView("ask"); setSelected(null);
  }, []);

  const ask = useCallback(async (q: string, invite: string): Promise<string | null> => {
    moveOn();
    try {
      const { run_id } = await data.startRun(q, invite);
      stopStream.current();
      setLiveRun(true); setLost(false); setRunId(run_id); setEvents([]); setPos(-1); setPlaying(true);
      stopStream.current = data.streamRun(
        run_id,
        (e) => setEvents((xs) => (xs.some((x) => x.seq === e.seq) ? xs : [...xs, e])),
        () => setLost(true),
      );
      return null;
    } catch (err) {
      const m = (err as Error).message;
      if (/invite/i.test(m)) return "That invite code is not valid.";
      if (/in progress/i.test(m)) return "Another live run is in progress. Try again in a minute.";
      if (/limit|slow down/i.test(m)) return "Live run limit reached. Replay a recorded run instead.";
      if (/longer than/i.test(m)) return "That question is too long. Shorten it a little.";
      return "The live engine is not reachable. Replay a recorded run instead.";
    }
  }, []);

  // Contrast needs a run; default to the first recorded one.
  useEffect(() => {
    if (view === "contrast" && !runId && runs[0]) {
      data.getRun(runs[0].run_id).then((ev) => {
        setRunId(runs[0].run_id); setEvents(ev); setPos(frames(ev).length - 1);
      });
    }
  }, [view, runId, runs]);

  // keyboard: space play/pause, arrows step, 1-4 views
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === "INPUT") return;
      if (e.key >= "1" && e.key <= "5") go(VIEWS[+e.key - 1][0]);
      if (view !== "ask" || !runId) return;
      if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
      if (e.key === "ArrowRight") { setPlaying(false); setPos((p) => Math.min(fs.length - 1, p + 1)); }
      if (e.key === "ArrowLeft") { setPlaying(false); setPos((p) => Math.max(0, p - 1)); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const decide = async (id: string, d: Decision) => {
    const before = proposals;
    const p = await data.decide(id, d);
    if (p.alert) {
      const rev = p.alert.reverted;
      setReverted(rev);
      setGhosts((g) => [...g, p]);
      setAlertBox({ kind: "curation", alert: p.alert, canary: p, reverted: before.filter((x) => rev.includes(x.id)) });
    } else if (d !== "approve") {
      const log = await data.getAudit();
      if (log.some((e) => e.kind === "canary_passed" && e.proposal_id === id)) setToast("Good catch. That was a test proposal.");
    }
    // the server (or the static engine) may revert items or plant a test proposal: take its list
    const fresh = await data.listProposals();
    setProposals(fresh.map((x) => ({ ...x, kind: kindOf(x) })));
    if (auditOpen) setAuditLog(await data.getAudit());
  };

  const openAudit = async () => {
    setSelected(null);
    setAuditLog(await data.getAudit());
    setAuditOpen(true);
  };

  const targets = (p: Proposal): string[] => {
    if (kindOf(p) === "edge" && p.triple) return [p.triple.s, p.triple.o];
    if (kindOf(p) === "node" && p.node) {
      const id = nodeIri(p.node.cls, p.node.local_id);
      return p.evidence_chunk_id ? [id, p.evidence_chunk_id] : [id];
    }
    return [];
  };

  const showProposal = (p: Proposal) => {
    const t = targets(p);
    if (!t.length) return;
    setCurFocus(t);
    cite(kindOf(p) === "edge" ? p.id : t[0]);
  };

  const create = async (body: CreateProposal) => {
    const p = await data.createProposal(body);
    const full = { ...p, kind: kindOf(p) };
    setProposals((xs) => [full, ...xs.filter((x) => x.id !== p.id)]);
    // let the new element land in the graph before the camera moves to it
    setTimeout(() => showProposal(full), 350);
  };

  // citations and chips: a chunk opens its document in the inspector, anything else flashes in the graph
  const cite = (id: string) => {
    const doc = folded.docOf.get(id);
    if (doc) { setSelected(doc); setFocusChunk(id); }
    setFlash(null);
    requestAnimationFrame(() => setFlash(folded.mapId(id)));
  };

  // the answer card's Report action; on a planted chat canary this is the "good catch"
  const report = () => {
    if (!runId) return;
    setReported((r) => new Set(r).add(runId));
    const c = canaryOf(full);
    if (c && chatPending.current?.runId === runId) {
      chatPending.current = null;
      audit("canary_passed", `Planted false answer reported: "${c.claim}"`);
      setToast("Good catch. That answer was a test: " + c.truth);
    } else {
      audit("decision", `Answer reported for review: "${full.started?.question ?? runId}"`);
      setToast("Reported. An analyst will review this answer.");
    }
  };
  useEffect(() => {
    const c = canaryOf(rv);
    if (view === "ask" && runId && c && !reported.has(runId) && !chatPending.current) {
      chatPending.current = { runId, question: rv.started?.question ?? "", canary: c };
    }
  }, [rv, view, runId, reported]);

  // ---- model comparison: recorded runs of the same question ----
  const runMeta = useMemo(() => {
    const m = new Map<string, RunMeta>();
    for (const [id, ev] of runCache) {
      const st = ev.find((e) => e.type === "run.started");
      m.set(id, { model: st?.type === "run.started" ? st.payload.model : "", secs: runSeconds(ev) });
    }
    return m;
  }, [runCache]);
  const siblings = useMemo(() => {
    const q = runs.find((r) => r.run_id === runId)?.question;
    return q ? runs.filter((r) => r.question === q && !r.mock) : [];
  }, [runs, runId]);
  const contradictionRun = useMemo(() => runs.find((r) => {
    const ev = runCache.get(r.run_id) ?? [];
    return !r.mock && ev.some((e) => e.type === "answer" && (e.payload.contradictions ?? []).length > 0)
      && ev.some((e) => e.type === "strategy" && e.payload.allowed_predicates.some((p) => /#(mentions|defined_in)$/.test(p)));
  }), [runs, runCache]);
  const switchModel = (id: string) => {
    if (id === runId) return;
    const ev = runCache.get(id);
    if (!ev) return;
    const atEnd = pos >= fs.length - 1;
    setRunId(id); setEvents(ev);
    setPos(atEnd ? frames(ev).length - 1 : 0);
    setPlaying(!atEnd);
  };

  // ---- what the graph shows ----
  const showRun = (view === "ask" || view === "contrast") && runId;
  const panelOpen = view === "ask" || view === "curate";
  let mode: GraphMode = "twin";
  let classes = EMPTY;
  let focus: string[] = [];
  let focusKey: string = view;
  const curClasses = useMemo(() => {
    const m = new Map<string, string>();
    for (const p of proposals) {
      if (p.status === "rejected") continue;
      if (kindOf(p) === "edge" && p.triple) {
        m.set(p.id, p.status === "approved" ? "follow" : "frontier");
        m.set(p.triple.s, "walked");
        m.set(p.triple.o, "walked");
      }
      if (kindOf(p) === "node" && p.node) {
        m.set(nodeIri(p.node.cls, p.node.local_id), "walked " + (p.status === "approved" ? "approved-node" : "proposed-node"));
        if (p.evidence_chunk_id) m.set(p.evidence_chunk_id, "walked");
      }
    }
    return m;
  }, [proposals]);
  if (showRun) {
    const v = view === "contrast" ? full : rv;
    mode = v.evidenceMode ? "evidence" : "run";
    classes = v.classes;
    focus = v.focus;
    focusKey = `${view}:${runId}:${view === "contrast" ? "end" : pos}`;
  } else if (view === "curate") {
    mode = "run";
    classes = curClasses;
    focus = curFocus.length ? curFocus : proposals.filter((p) => p.status !== "rejected").flatMap(targets);
    focusKey = "curate:" + curFocus.join();
  }
  const sel = selected && !auditOpen ? idx.get(selected) : undefined;
  const inset = { top: 84, right: panelOpen ? 452 : 16, bottom: view === "ask" && runId ? 92 : 16, left: sel || auditOpen ? 412 : 16 };
  const shownClasses = useMemo(() => foldClasses(classes, folded), [classes, folded]);
  const shownFocus = [...new Set(focus.map(folded.mapId))];
  const shownAnchors = useMemo(
    () => new Map([...prop.anchors].map(([k, v]) => [k, folded.mapId(v)])), [prop.anchors, folded]);
  const cited = useMemo(() => {
    const v = view === "contrast" ? full : rv;
    const ids = new Set<string>();
    if (!showRun) return ids;
    v.answer?.citations.forEach((c) => c.chunk_id && ids.add(c.chunk_id));
    v.evidence?.nodes.forEach((n) => n.cls === "Chunk" && ids.add(n.id));
    return ids;
  }, [view, full, rv, showRun]);

  const stats = useMemo(() => {
    const approved = graph.edges.filter((e) => (status.get(e.id) ?? e.graph) === "approved").length;
    const docs = graph.nodes.filter((n) => n.cls === "Document").length;
    const chunks = graph.nodes.filter((n) => n.cls === "Chunk").length;
    const people = graph.nodes.filter((n) => n.cls === "Person").length;
    return { nodes: graph.nodes.length - chunks, approved, docs, chunks, people };
  }, [graph, status]);

  const current = pos >= 0 ? fs[pos] : undefined;

  return (
    <>
      <Graph nodes={folded.nodes} edges={folded.edges} classes={shownClasses} mode={mode} focus={shownFocus} focusKey={focusKey}
        inset={inset} flash={flash} onSelect={(id) => { setAuditOpen(false); setSelected(id); setFocusChunk(null); }} anchors={shownAnchors} />
      {auditOpen && (
        <AuditDrawer entries={auditLog} proposals={[...proposals, ...ghosts]} idx={idx} onClose={() => setAuditOpen(false)} />
      )}
      {sel && (
        <Inspector node={sel} folded={folded} idx={idx} cited={cited} focusChunk={focusChunk}
          onClose={() => { setSelected(null); setFocusChunk(null); }} />
      )}

      <header className="topbar">
        <div className="brand glass">
          <Mark />
          <span className="brand-name">Graph Anchor</span>
          <span className="brand-sub">Kelvara Packaging · digital twin</span>
        </div>
        <nav className="segmented glass" aria-label="Views">
          {VIEWS.map(([k, label]) => (
            <button key={k} aria-pressed={view === k} onClick={() => go(k)}>{label}</button>
          ))}
        </nav>
        <div className="top-right">
          {showRun && full.started?.mock && <span className="tag mock glass">Mock run</span>}
          <span className={"tag glass " + (data.live ? "live" : "neutral")}>
            <span className="dot" />{data.live ? "Live engine" : "Offline replay"}
          </span>
        </div>
      </header>

      {view === "ask" && !runId && <Picker runs={runs} meta={runMeta} live={data.live} onPick={pick} onAsk={ask} />}
      {view === "ask" && runId && compareOpen && siblings.length > 1 && (
        <Compare
          a={{ summary: siblings[0], events: runCache.get(siblings[0].run_id) ?? [] }}
          b={{ summary: siblings[1], events: runCache.get(siblings[1].run_id) ?? [] }}
          idx={idx} current={runId}
          onShow={(id) => { switchModel(id); setCompareOpen(false); }}
          onOpenRun={(id) => pick(id)}
          contradictionRun={contradictionRun} />
      )}
      {view === "ask" && runId && !compareOpen && (
        <RunPanel view={rv} idx={idx} edges={edgeIdx} live={liveRun} lost={lost}
          onBack={() => { moveOn(); stopStream.current(); setRunId(null); setEvents([]); setPos(-1); setPlaying(false); }}
          onCite={cite} reported={!!runId && reported.has(runId)} onReport={report}
          models={siblings.map((r) => ({ run_id: r.run_id, ...(runMeta.get(r.run_id) ?? { model: "", secs: null }) }))}
          current={runId} onSwitch={switchModel} onCompare={() => setCompareOpen(true)} />
      )}
      {view === "contrast" && runId && <Contrast v={full} idx={idx} edges={edgeIdx} />}
      {view === "curate" && (
        <Curate proposals={proposals} idx={idx} ontology={ontology} mock={data.kind === "static"}
          onDecide={decide} onCreate={create} onShow={showProposal} onAudit={openAudit} reverted={reverted} />
      )}

      {view === "roadmap" && <Roadmap steps={full.steps.length || 3} />}

      {view === "ask" && runId && !compareOpen && (
        <div className="player glass" style={{ left: `calc(${inset.left}px + (100% - ${inset.left + inset.right}px) / 2)` }} role="toolbar" aria-label="Playback">
          <button className="icon-btn" aria-label="Restart" onClick={() => { setPos(0); setPlaying(true); }}><Icon name="restart" /></button>
          <button className="icon-btn" aria-label="Previous step" disabled={pos <= 0}
            onClick={() => { setPlaying(false); setPos((p) => Math.max(0, p - 1)); }}><Icon name="prev" /></button>
          <button className="icon-btn primary" aria-label={playing ? "Pause" : "Play"}
            onClick={() => { if (pos >= fs.length - 1 && !liveRun) setPos(0); setPlaying((p) => !p); }}>
            <Icon name={playing ? "pause" : "play"} />
          </button>
          <button className="icon-btn" aria-label="Next step" disabled={pos >= fs.length - 1}
            onClick={() => { setPlaying(false); setPos((p) => Math.min(fs.length - 1, p + 1)); }}><Icon name="next" /></button>
          <button className="icon-btn" aria-label="Jump to evidence graph" disabled={pos >= fs.length - 1}
            onClick={() => { setPlaying(false); setPos(fs.length - 1); }}><Icon name="end" /></button>
          <div className="track">
            {fs.map((f, i) => (
              <button key={i} aria-label={FRAME_LABEL[f.kind] + (f.step ? " " + f.step : "")}
                className={"seg" + (i <= pos ? " on" : "") + (i === pos ? " current" : "") + (f.kind === "evidence" ? " evidence" : "")}
                onClick={() => { setPlaying(false); setPos(i); }} />
            ))}
          </div>
          <div className="frame-label" aria-live="polite">
            {current ? FRAME_LABEL[current.kind] + (current.step ? ` ${current.step}` : "") : liveRun ? "Waiting…" : ""}
          </div>
        </div>
      )}

      <div className="corner" style={{ bottom: view === "ask" && runId ? 92 : 16 }}>
        {view === "twin" && !sel && (
          <div className="intro glass">
            <div className="eyebrow">The anchor</div>
            <h1>One curated graph grounds every answer.</h1>
            <p>Company, plant and documents in one knowledge graph. Every relation here is approved. Models only propose.</p>
            <div className="stats">
              <div className="stat"><b>{stats.nodes}</b><span>entities</span></div>
              <div className="stat"><b>{stats.approved}</b><span>approved relations</span></div>
              <div className="stat"><b>{stats.docs}</b><span>documents</span></div>
              <div className="stat"><b>{stats.chunks}</b><span>passages</span></div>
            </div>
          </div>
        )}
        {!sel && !auditOpen && !compareOpen && <Legend mode={mode} view={view} people={stats.people} />}
      </div>
      {toast && <Toast text={toast} onDone={() => setToast(null)} />}
      {alertBox && (
        <AlertDialog a={alertBox} idx={idx}
          onClose={() => setAlertBox(null)}
          onAudit={() => { setAlertBox(null); openAudit(); }}
          onReview={() => { setAlertBox(null); setView("curate"); }} />
      )}
    </>
  );
}

function Legend({ mode, view, people }: { mode: GraphMode; view: View; people: number }) {
  if (view === "contrast" || view === "roadmap") return null;
  if (mode === "twin" || view === "curate") {
    return (
      <div className="legend glass">
        <span><i className="sw" style={{ background: "var(--company)" }} />Company</span>
        <span><i className="sw" style={{ background: "var(--plant)" }} />Plant</span>
        <span><i className="sw sq" style={{ background: "var(--docs)" }} />Documents</span>
        <span><i className="ln" style={{ borderColor: "var(--ink2)", borderTopStyle: "dashed" }} />Proposed</span>
        {people > 0 && <span className="muted">{people} people not drawn</span>}
      </div>
    );
  }
  return (
    <div className="legend glass">
      {mode === "run" && <span><i className="ln" style={{ borderColor: "var(--ink)", borderTopStyle: "dashed" }} />Candidate</span>}
      <span><i className="ln" style={{ borderColor: "var(--accent)" }} />{mode === "evidence" ? "Evidence" : "Followed"}</span>
      <span><i className="ln" style={{ borderColor: "var(--ink3)", borderTopStyle: "dotted" }} />Pruned</span>
      <span><i className="ln" style={{ borderColor: "var(--contra)", borderTopStyle: "dashed" }} />Contradiction</span>
    </div>
  );
}

function canaryOf(v: { answer?: { canary?: { claim: string; truth: string } | null } }) {
  return v.answer?.canary ?? null;
}
