import { useEffect, useRef } from "react";
import type { Edge, Event, Node, RunSummary } from "./contracts";
import type { Frame } from "./run";
import { pretty } from "./run";
import { labelOf, readable, Triple, type Index } from "./bits";

export const FRAME_TITLES = {
  question: "Question", strategy: "Traversal strategy", seeds: "Entry points",
  frontier: "Candidate relations", verdicts: "Follow or prune", answer: "Grounded answer", evidence: "Evidence graph",
};

interface Props {
  runs: RunSummary[];
  runId: string | null;
  events: Event[];
  frames: Frame[];
  position: number;
  idx: Index;
  contextNode?: Node;
  contextEdges: Edge[];
  onPick: (id: string) => void;
  onStep: (position: number) => void;
  onCite: (id: string) => void;
}

export default function TraversalGuide(p: Props) {
  const body = useRef<HTMLDivElement>(null);
  const current = useRef<HTMLElement>(null);
  useEffect(() => {
    if (body.current && current.current) {
      const panel = body.current;
      const panelBox = panel.getBoundingClientRect();
      const scale = panelBox.height > 0 ? panel.clientHeight / panelBox.height : 1;
      const top = panel.scrollTop + (current.current.getBoundingClientRect().top - panelBox.top) * scale - 12;
      panel.scrollTo({ top: Math.max(0, top), behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
    }
  }, [p.position]);

  useEffect(() => {
    if (p.contextNode) body.current?.scrollTo({ top: 0, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  }, [p.contextNode?.id]);

  // Keep the engine's frame positions, but group the UI around the information discovered.
  const trail = p.frames.flatMap((frame, index) => {
    if (frame.kind === "strategy") return [];
    if (frame.kind === "frontier") return p.frames[index + 1]?.kind === "verdicts" ? [] : [{ frame, index }];
    if (frame.kind === "verdicts" && p.position === index - 1) return [{ frame: p.frames[index - 1], index: index - 1 }];
    return [{ frame, index }];
  });
  const scope = p.events.find(event => event.type === "strategy");

  return <div className="guide-body" ref={body}>
    {p.contextNode && <section className="graph-context">
      <div className="eyebrow">Selected in the graph · {p.contextNode.cls}</div>
      <h3>{p.contextNode.label}</h3>
      {p.contextNode.description && <p>{p.contextNode.description}</p>}
      <div className="context-facts">{p.contextEdges.map(edge => <button key={edge.id} className="context-fact" onClick={() => p.onCite(edge.id)}><Triple edge={edge} idx={p.idx} /><span className="fact-status">{edge.graph}</span></button>)}</div>
      {!p.contextEdges.length && <p>No visible relations for this entity.</p>}
    </section>}
    <details className="question-picker" open={!p.runId}>
      <summary>{p.runId ? "Explore another question" : "Explore the graph’s evidence"}</summary>
      <div className="guide-questions">{p.runs.map(run => <button key={run.run_id} className={p.runId === run.run_id ? "chosen" : ""} onClick={() => p.onPick(run.run_id)}>{run.question}{run.mock && <span className="tag mock">Mock canary</span>}</button>)}</div>
    </details>
    {!p.runId && !p.contextNode && <div className="guide-welcome">
      <span className="guide-path" aria-hidden="true">● ── ● ── ●</span>
      <h3>How does the evidence connect?</h3>
      <p>Orders connect to stations. Stations connect to sensors. Procedures and datasheets define what those sensors can do.</p>
      <p>Select an entity in the graph to inspect its relationships, or explore a question to trace the supporting evidence.</p>
    </div>}
    {scope?.type === "strategy" && <details className="evidence-scope"><summary>Question scope · {scope.payload.question_type}</summary><p>{scope.payload.rationale}</p><div className="chips">{scope.payload.allowed_predicates.map(predicate => <span className="chip pred" key={predicate}>{pretty(predicate)}</span>)}</div></details>}
    {p.runId && !p.frames.length && <p className="muted small" role="status">Gathering evidence…</p>}
    <ol className="traversal-timeline">
      {trail.map(({ frame, index }, trailIndex) => {
        const event = p.events[frame.event];
        const active = index === p.position || (frame.kind === "question" && p.frames[p.position]?.kind === "strategy");
        const done = index < p.position && !active;
        const title = evidenceTitle(event, frame, p.idx);
        return <li key={`${frame.event}:${frame.kind}`}>
          <section ref={active ? current : undefined} className={`guide-step${active ? " current" : ""}${done ? " completed" : ""}`} aria-label={title}>
            <button className="timeline-step" aria-current={active ? "step" : undefined} onClick={() => p.onStep(index)}>
              <span className={`step-number${done ? " done" : ""}`}>{done ? "✓" : trailIndex + 1}</span>
              <span>{title}</span>
              <span className="timeline-state">{active ? "In view" : "Explore"}</span>
            </button>
            {(active || done) && <div className="frame-content">
              <FrameContent event={event} frame={frame} idx={p.idx} onCite={p.onCite} />
            </div>}
          </section>
        </li>;
      })}
    </ol>
  </div>;
}

function evidenceTitle(event: Event, frame: Frame, idx: Index): string {
  switch (event.type) {
    case "run.started": return "The question";
    case "seeds": return event.payload.nodes.slice(0, 2).map(node => node.label).join(" · ") || "Starting entities";
    case "step": {
      const followed = new Set(event.payload.decisions.filter(decision => decision.verdict === "follow").map(decision => decision.edge_id));
      const relations = event.payload.frontier.filter(edge => followed.has(edge.id));
      if (frame.kind === "frontier") return `Related knowledge · ${event.payload.frontier.length} links`;
      const labels = [...new Set(relations.flatMap(edge => [labelOf(idx, edge.s), labelOf(idx, edge.o)]))];
      return labels.slice(0, 2).join(" ↔ ") || `Evidence examined · hop ${event.payload.n}`;
    }
    case "answer": return event.payload.contradictions?.length ? "Conflicting sources" : "Conclusion and sources";
    case "evidence": return "Supporting evidence";
    default: return FRAME_TITLES[frame.kind];
  }
}

function FrameContent({ event, frame, idx, onCite }: { event: Event; frame: Frame; idx: Index; onCite: (id: string) => void }) {
  switch (event.type) {
    case "run.started":
      return <><p>{event.payload.question}</p></>;
    case "strategy":
      return <><p><strong>{event.payload.question_type}</strong></p><p>{event.payload.rationale}</p><div className="eyebrow">Allowed relations · depth {event.payload.max_depth}</div><div className="chips">{event.payload.allowed_predicates.map(predicate => <span className="chip pred" key={predicate}>{pretty(predicate)}</span>)}</div><div className="frame-note">These relations constrain which graph paths the engine can explore.</div></>;
    case "seeds":
      return <><p>Entities relevant to this question:</p><div className="chips">{event.payload.nodes.map(node => <button className="chip" key={node.id} onClick={() => onCite(node.id)}>{node.label}<span className="score">{node.score.toFixed(2)}</span></button>)}</div></>;
    case "step": {
      const step = event.payload;
      const verdicts = frame.kind === "verdicts";
      const decisions = new Map(step.decisions.map(decision => [decision.edge_id, decision]));
      return <><p>{verdicts ? "Relationships retained as relevant evidence:" : `${step.frontier.length} relationships connect these entities to further knowledge.`}</p>
        <ul className="decisions">{step.frontier.filter(edge => !verdicts || decisions.get(edge.id)?.verdict === "follow").map(edge => {
          const decision = verdicts ? decisions.get(edge.id) : undefined;
          return <li className={`decision ${decision?.verdict ?? "pending"}`} key={edge.id}>
            <span className={`verdict ${decision?.verdict ?? "pending"}`}>{decision ? "relevant" : "related"}</span>
            <div><button className="graph-relation" onClick={() => onCite(edge.id)}><Triple edge={edge} idx={idx} /></button>{decision && <div className="reason">{decision.reason}</div>}</div>
          </li>;
        })}</ul>
        {verdicts && step.decisions.some(decision => decision.verdict === "prune") && <details className="excluded-evidence"><summary>Excluded relationships · {step.decisions.filter(decision => decision.verdict === "prune").length}</summary><ul className="decisions">{step.frontier.filter(edge => decisions.get(edge.id)?.verdict === "prune").map(edge => <li key={edge.id}><button className="graph-relation" onClick={() => onCite(edge.id)}><Triple edge={edge} idx={idx} /></button><div className="reason">{decisions.get(edge.id)?.reason}</div></li>)}</ul></details>}
        {verdicts && !step.decisions.some(decision => decision.verdict === "follow") && <div className="frame-note">No additional relationships were retained at this hop.</div>}
        {verdicts && step.sufficient && <div className="sufficient">● Sufficient evidence for the answer.</div>}
      </>;
    }
    case "answer":
      return <><p>{readable(event.payload.justification, idx)}</p>{event.payload.contradictions?.map((contradiction, index) => <div className="contra-box" key={index}><div><strong>Contradiction flagged.</strong> {contradiction.note}<div className="chips"><button className="chip" onClick={() => onCite(contradiction.a)}>{labelOf(idx, contradiction.a)}</button><button className="chip" onClick={() => onCite(contradiction.b)}>{labelOf(idx, contradiction.b)}</button></div></div></div>)}</>;
    case "evidence":
      return <><p>{event.payload.nodes.filter(node => node.cls !== "Chunk").length} entities, {event.payload.nodes.filter(node => node.cls === "Chunk").length} passages and {event.payload.edges.length} relations in the context given to the model.</p><div className="frame-note">These entities and their source passages form the context supplied for the answer.</div><div className="chips">{event.payload.nodes.filter(node => node.cls !== "Chunk").map(node => <button key={node.id} className="chip" onClick={() => onCite(node.id)}>{node.label}</button>)}</div><div className="eyebrow">Source passages</div><div className="chips">{event.payload.nodes.filter(node => node.cls === "Chunk").map(node => <button key={node.id} className="chip" onClick={() => onCite(node.id)}>{node.label}</button>)}</div></>;
    default: return null;
  }
}
