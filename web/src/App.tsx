import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CreateProposal, Edge, Event, GraphExport, Node, Proposal, RunSummary } from "./contracts";
import { data, type Ontology } from "./data";
import { nodeIri, predIri } from "./ids";
import TraversalGuide from "./TraversalGuide";
import Graph, { type GraphMode } from "./Graph";
import { frames, labelIndex, runElements, viewAt, type FrameKind } from "./run";
import { RunPanel } from "./RunPanel";
import Contrast from "./Contrast";
import Curate, { kindOf } from "./Curate";
import Roadmap from "./Roadmap";
import Inspector from "./Inspector";
import { fold, foldClasses } from "./fold";
import { AlertDialog, AuditDrawer, Toast, type OversightAlert } from "./Oversight";
import { audit, SUPERVISOR } from "./canary";
import type { AuditEntry } from "./contracts";
import type { Decision } from "./data";
import { Icon } from "./bits";

type View = "twin" | "ask" | "contrast" | "curate" | "roadmap";
const VIEWS: [View, string][] = [["twin", "Twin"], ["ask", "Ask"], ["contrast", "Contrast"], ["curate", "Curate"], ["roadmap", "Roadmap"]];

const HOLD: Record<FrameKind, number> = {
  question: 1400, strategy: 3200, seeds: 2200, frontier: 2000, verdicts: 3000, answer: 3400, evidence: 0,
};


const EMPTY = new Map<string, string>();

export default function App({ active = true }: { active?: boolean }) {
  const [demoPlaying, setDemoPlaying] = useState(false);
  const [showGraph, setShowGraph] = useState(true);
  const [draft, setDraft] = useState("");
  const [invite, setInvite] = useState("");
  const [questionError, setQuestionError] = useState("");
  const [view, setView] = useState<View>("twin");
  const [graph, setGraph] = useState<GraphExport>({ nodes: [], edges: [] });
  const [runs, setRuns] = useState<RunSummary[]>([]);
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
    data.listRuns().then(setRuns);
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
    graph.nodes.forEach((x) => n.set(x.id, x));
    prop.nodes.forEach((x) => { if (!n.has(x.id)) n.set(x.id, x); });
    // run events embed nodes in full; they win so the run shows exactly what the model was given
    runEls.nodes.forEach((x) => n.set(x.id, x));
    const e = new Map<string, Edge>();
    for (const x of [...prop.edges, ...graph.edges, ...runEls.edges]) e.set(x.id, { ...x, graph: status.get(x.id) ?? x.graph });
    return { nodes: [...n.values()], edges: [...e.values()].filter((x) => x.graph !== "rejected") };
  }, [graph, runEls, status, prop]);
  const idx = useMemo(() => labelIndex(nodes), [nodes]);
  // chunks are drawn one level down: hidden in the graph, lifted onto their documents (fold.ts)
  const folded = useMemo(() => fold(nodes, edges), [nodes, edges]);
  const edgeIdx = useMemo(() => new Map(edges.map((e) => [e.id, e])), [edges]);

  // ---- playback ----
  useEffect(() => {
    if (!playing || view !== "ask" || !active) return;
    if (pos >= fs.length - 1) {
      if (!liveRun || full.finished) setPlaying(false);
      return;
    }
    const t = setTimeout(() => setPos((p) => p + 1), pos < 0 ? 200 : HOLD[fs[pos].kind]);
    return () => clearTimeout(t);
  }, [playing, pos, fs, view, liveRun, full.finished, active]);

  // Chat canary (click mock): leaving a planted false answer without reporting it raises the alert.
  const moveOn = useCallback(() => {
    const c = chatPending.current;
    chatPending.current = null;
    if (!c) return;
    audit("canary_failed", `Planted false answer not reported: "${c.canary.claim}"`);
    audit("supervisor_notified", `${SUPERVISOR} notified.`);
    setAlertBox({ kind: "chat", canary: c.canary, question: c.question, supervisor: SUPERVISOR });
  }, []);
  const go = (v: View) => { if (v !== view) { moveOn(); setAuditOpen(false); } setView(v); };

  const pick = useCallback(async (id: string) => {
    moveOn();
    stopStream.current();
    const ev = await data.getRun(id);
    setLiveRun(false); setLost(false);
    setRunId(id); setEvents(ev); setPos(0); setPlaying(true); setView("ask"); setSelected(null);
  }, []);

  const demoRuns = useMemo(() => runs.filter(run => !run.mock), [runs]);
  const scenarioIndex = demoRuns.findIndex(run => run.run_id === runId);
  useEffect(() => {
    if (!active || !demoPlaying || !runId || pos < fs.length - 1 || !fs.length || (liveRun && !full.finished)) return;
    const timer = window.setTimeout(() => {
      const next = demoRuns[scenarioIndex + 1];
      if (next) void pick(next.run_id);
      else { setDemoPlaying(false); setPlaying(false); }
    }, 4000);
    return () => window.clearTimeout(timer);
  }, [active, demoPlaying, runId, pos, fs.length, liveRun, full.finished, demoRuns, scenarioIndex, pick]);

  const playDemo = () => {
    if (demoPlaying || playing) { setDemoPlaying(false); setPlaying(false); return; }
    setDemoPlaying(true);
    if (scenarioIndex < 0 || (scenarioIndex === demoRuns.length - 1 && pos >= fs.length - 1)) {
      if (demoRuns[0]) void pick(demoRuns[0].run_id);
    } else setPlaying(true);
  };
  const changeScenario = async (index: number) => {
    const next = demoRuns[Math.max(0, Math.min(demoRuns.length - 1, index))];
    if (!next) return;
    await pick(next.run_id);
    if (!demoPlaying) setPlaying(false);
  };

  const ask = useCallback(async (q: string) => {
    moveOn();
    stopStream.current();
    try {
      setDemoPlaying(false);
      setQuestionError("");
      const { run_id } = await data.startRun(q, invite || undefined);
      setView("ask"); setDraft("");
      setLiveRun(true); setLost(false); setRunId(run_id); setEvents([]); setPos(-1); setPlaying(true);
      stopStream.current = data.streamRun(
        run_id,
        (e) => setEvents((xs) => (xs.some((x) => x.seq === e.seq) ? xs : [...xs, e])),
        () => setLost(true),
      );
    } catch (err) {
      setQuestionError(err instanceof Error ? err.message : "The engine could not answer. Please try again.");
    }
  }, [invite]);

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
      if (!active || (e.target as HTMLElement).closest("input, textarea, select, button, [contenteditable]")) return;
      if (e.key >= "1" && e.key <= "5") go(VIEWS[+e.key - 1][0]);
      if (e.key === " ") { e.preventDefault(); playDemo(); }
      if (e.key === "ArrowRight") { e.preventDefault(); void changeScenario(scenarioIndex + 1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); void changeScenario(scenarioIndex - 1); }
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

  // ---- what the graph shows ----
  const showRun = (view === "ask" || view === "contrast") && runId;
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
  const inset = { top: 30, right: 24, bottom: view === "ask" && runId ? 100 : 65, left: 24 };
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

  return (
    <div className={"demo-workspace" + (showGraph ? "" : " graph-collapsed")}>
      <div className="graph-pane">
      <Graph nodes={folded.nodes} edges={folded.edges} classes={shownClasses} mode={mode} focus={shownFocus} focusKey={focusKey}
        inset={inset} flash={flash} onSelect={(id) => { setAuditOpen(false); setSelected(id); setFocusChunk(null); }} anchors={shownAnchors} />
      <Legend mode={mode} view={view} />
      {auditOpen && (
        <AuditDrawer entries={auditLog} proposals={[...proposals, ...ghosts]} idx={idx} onClose={() => setAuditOpen(false)} />
      )}
      {sel && (
        <Inspector node={sel} folded={folded} idx={idx} cited={cited} focusChunk={focusChunk}
          onClose={() => { setSelected(null); setFocusChunk(null); }} />
      )}

      </div>
      <aside className="guide-pane">
        <button className="graph-toggle" aria-label="Toggle knowledge graph" aria-pressed={showGraph} onClick={() => setShowGraph(value => !value)}>{showGraph ? "‹" : "›"}</button>
        <div className="workspace-heading"><div className="eyebrow">Connected knowledge</div><h2>Evidence trail</h2></div>
        <TraversalGuide runs={runs} runId={runId} events={events} frames={fs} position={pos} idx={idx}
          contextNode={sel} contextEdges={selected ? folded.edges.filter(edge => edge.s === selected || edge.o === selected) : []}
          onPick={id => { setDemoPlaying(!runs.find(run => run.run_id === id)?.mock); void pick(id); }} onStep={index => { setDemoPlaying(false); setPlaying(false); setPos(index); setView("ask"); }} onCite={cite} />

      </aside>
      <section className="chat-pane" aria-label="Ask the twin">
        <div className="workspace-heading"><div><div className="eyebrow">Ask the twin</div><h2>Open chat</h2></div><button className="clear-chat" onClick={() => { moveOn(); stopStream.current(); setRunId(null); setEvents([]); setPos(-1); setPlaying(false); setDemoPlaying(false); setDraft(""); setQuestionError(""); setSelected(null); setFocusChunk(null); setView("twin"); }}>Clear</button></div>
        {!runId && <div className="chat-empty"><strong>No questions yet</strong><span>Explore a question from the evidence trail.</span></div>}
        {runId && <RunPanel answerOnly view={rv} idx={idx} edges={edgeIdx} live={liveRun} lost={lost}
          onBack={() => { setDemoPlaying(false); moveOn(); stopStream.current(); setRunId(null); setEvents([]); setPos(-1); setPlaying(false); }}
          onCite={cite} reported={reported.has(runId)} onReport={report} />}
        <form className="chat-form" onSubmit={event => { event.preventDefault(); if (draft.trim() && data.live) ask(draft.trim()); }}>
          {data.live && <input className="invite-field" aria-label="Invitation code" placeholder="Invitation code" value={invite} onChange={event => setInvite(event.target.value)} />}
          {questionError && <div className="chat-error" role="alert">{questionError}</div>}
          <div className="chat-compose"><input aria-label="Your question" value={draft} onChange={event => setDraft(event.target.value)} disabled={!data.live} placeholder="Ask about stations, sensors, suppliers…" /><button type="submit" disabled={!data.live || !draft.trim() || playing}>Send</button></div>
          {!data.live && <div className="offline-note">Offline replay · Live questions need the engine API.</div>}
        </form>
      </section>
      {view === "contrast" && runId && <Contrast v={full} idx={idx} edges={edgeIdx} />}
      {view === "curate" && (
        <Curate proposals={proposals} idx={idx} ontology={ontology} mock={data.kind === "static"}
          onDecide={decide} onCreate={create} onShow={showProposal} onAudit={openAudit} reverted={reverted} />
      )}

      {view === "roadmap" && <Roadmap steps={full.steps.length || 3} />}


      <div className="demo-controller glass" role="toolbar" aria-label="Demo playback">
        <button className="icon-btn" aria-label="Restart demo" disabled={!demoRuns.length} onClick={() => { setDemoPlaying(true); if (demoRuns[0]) void pick(demoRuns[0].run_id); }}><Icon name="restart" /></button>
        <button className="icon-btn" aria-label="Previous scenario" disabled={scenarioIndex <= 0} onClick={() => void changeScenario(scenarioIndex - 1)}><Icon name="prev" /></button>
        <button className="icon-btn primary" aria-label={demoPlaying || playing ? "Pause demo" : "Play demo"} disabled={!demoRuns.length} onClick={playDemo}><Icon name={demoPlaying || playing ? "pause" : "play"} /></button>
        <button className="icon-btn" aria-label="Next scenario" disabled={!demoRuns.length || scenarioIndex >= demoRuns.length - 1} onClick={() => void changeScenario(scenarioIndex + 1)}><Icon name="next" /></button>
        <div className="demo-scenarios" aria-label="Demo scenarios">
          {demoRuns.map((run, index) => <button key={run.run_id} aria-label={`Scenario ${index + 1}: ${run.question}`} aria-current={runId === run.run_id ? "step" : undefined} onClick={() => void changeScenario(index)}><span style={{ transform: `scaleX(${runId === run.run_id ? (pos + 1) / Math.max(fs.length, 1) : scenarioIndex > index ? 1 : 0})` }} /></button>)}
        </div>
        <span className="demo-progress" aria-live="polite">{scenarioIndex >= 0 ? `${scenarioIndex + 1} / ${demoRuns.length}` : "Recorded demo"}</span>
      </div>

      {toast && <Toast text={toast} onDone={() => setToast(null)} />}
      {alertBox && (
        <AlertDialog a={alertBox} idx={idx}
          onClose={() => setAlertBox(null)}
          onAudit={() => { setAlertBox(null); openAudit(); }}
          onReview={() => { setAlertBox(null); setView("curate"); }} />
      )}
    </div>
  );
}

function Legend({ mode, view }: { mode: GraphMode; view: View }) {
  if (view === "contrast" || view === "roadmap") return null;
  if (mode === "twin" || view === "curate") {
    return (
      <div className="legend glass">
        <span><i className="sw" style={{ background: "var(--company)" }} />Company</span>
        <span><i className="sw" style={{ background: "var(--plant)" }} />Plant</span>
        <span><i className="sw sq" style={{ background: "var(--docs)" }} />Documents</span>
        <span><i className="ln" style={{ borderColor: "var(--ink2)", borderTopStyle: "dashed" }} />Proposed</span>
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
