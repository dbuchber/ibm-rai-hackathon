// Turns a run's event list into presentable frames and derives the graph highlight state per frame.
import type {
  AnswerPayload, BaselinePayload, Edge, Event, EvidencePayload, Node, RunStarted,
  ScoredNode, StepPayload, StrategyPayload,
} from "./contracts";

export type FrameKind = "question" | "strategy" | "seeds" | "frontier" | "verdicts" | "answer" | "evidence";
export interface Frame { kind: FrameKind; event: number; step?: number }

export const CONTRA_PREFIX = "contra:";

export function frames(events: Event[]): Frame[] {
  const out: Frame[] = [];
  events.forEach((e, i) => {
    switch (e.type) {
      case "run.started": out.push({ kind: "question", event: i }); break;
      case "strategy": out.push({ kind: "strategy", event: i }); break;
      case "seeds": out.push({ kind: "seeds", event: i }); break;
      case "step":
        out.push({ kind: "frontier", event: i, step: e.payload.n });
        out.push({ kind: "verdicts", event: i, step: e.payload.n });
        break;
      case "answer": out.push({ kind: "answer", event: i }); break;
      case "evidence": out.push({ kind: "evidence", event: i }); break;
    }
  });
  return out;
}

export interface StepView { payload: StepPayload; verdicts: boolean }

export interface RunView {
  started?: RunStarted;
  strategy?: StrategyPayload;
  seeds: ScoredNode[];
  steps: StepView[];
  answer?: AnswerPayload;
  evidence?: EvidencePayload;
  baseline?: BaselinePayload;
  finished?: { status: "ok" | "error"; error?: string | null };
  /** element id -> space separated cytoscape classes */
  classes: Map<string, string>;
  /** true once the evidence frame is reached: everything not in `classes` as evidence is dimmed */
  evidenceMode: boolean;
  /** ids the camera should frame */
  focus: string[];
}

/** Everything a run will ever draw, so the layout can place it once. */
export function runElements(events: Event[]): { nodes: Node[]; edges: Edge[] } {
  const nodes = new Map<string, Node>();
  const edges = new Map<string, Edge>();
  for (const e of events) {
    if (e.type === "seeds") e.payload.nodes.forEach((n) => nodes.set(n.id, n));
    if (e.type === "step") {
      e.payload.nodes.forEach((n) => nodes.set(n.id, n));
      e.payload.frontier.forEach((x) => edges.set(x.id, x));
    }
    if (e.type === "evidence") {
      e.payload.nodes.forEach((n) => nodes.set(n.id, n));
      e.payload.edges.forEach((x) => edges.set(x.id, x));
    }
    if (e.type === "baseline") e.payload.chunks.forEach((n) => nodes.set(n.id, n));
    if (e.type === "answer") {
      for (const c of e.payload.contradictions ?? []) {
        edges.set(CONTRA_PREFIX + c.a + "|" + c.b, {
          id: CONTRA_PREFIX + c.a + "|" + c.b, s: c.a, o: c.b, p: "contradicts", graph: "approved",
        });
      }
    }
  }
  return { nodes: [...nodes.values()], edges: [...edges.values()] };
}

function add(m: Map<string, string>, id: string, cls: string) {
  const cur = m.get(id);
  m.set(id, cur ? (cur.split(" ").includes(cls) ? cur : cur + " " + cls) : cls);
}

function remove(m: Map<string, string>, id: string, cls: string) {
  const cur = m.get(id);
  if (!cur) return;
  const next = cur.split(" ").filter((c) => c !== cls).join(" ");
  if (next) m.set(id, next); else m.delete(id);
}

/** State after showing frames[0..upto] (inclusive). upto = -1 shows nothing. */
export function viewAt(events: Event[], fs: Frame[], upto: number): RunView {
  const v: RunView = { seeds: [], steps: [], classes: new Map(), evidenceMode: false, focus: [] };
  const c = v.classes;
  for (let i = 0; i <= upto && i < fs.length; i++) {
    const f = fs[i];
    const e = events[f.event];
    // the previous frame's transient highlight ("current frontier") ends when a new frame starts
    for (const [id, cls] of [...c]) if (cls.includes("current")) remove(c, id, "current");
    switch (e.type) {
      case "run.started": v.started = e.payload; break;
      case "strategy": v.strategy = e.payload; break;
      case "seeds":
        v.seeds = e.payload.nodes;
        e.payload.nodes.forEach((n) => { add(c, n.id, "seed"); add(c, n.id, "walked"); });
        v.focus = e.payload.nodes.map((n) => n.id);
        break;
      case "step": {
        const p = e.payload;
        if (f.kind === "frontier") {
          v.steps.push({ payload: p, verdicts: false });
          p.frontier.forEach((x) => { add(c, x.id, "frontier"); add(c, x.id, "current"); });
          p.nodes.forEach((n) => add(c, n.id, "explored"));
          v.focus = p.nodes.map((n) => n.id);
        } else {
          v.steps[v.steps.length - 1] = { payload: p, verdicts: true };
          const byId = new Map(p.frontier.map((x) => [x.id, x]));
          for (const d of p.decisions) {
            const edge = byId.get(d.edge_id);
            remove(c, d.edge_id, "frontier");
            add(c, d.edge_id, d.verdict);
            add(c, d.edge_id, "current");
            if (d.verdict === "follow" && edge) { add(c, edge.s, "walked"); add(c, edge.o, "walked"); }
          }
          v.focus = p.nodes.map((n) => n.id);
        }
        break;
      }
      case "answer": v.answer = e.payload; break;
      case "evidence": {
        v.evidence = e.payload;
        v.evidenceMode = true;
        e.payload.nodes.forEach((n) => add(c, n.id, "evidence"));
        e.payload.edges.forEach((x) => add(c, x.id, "evidence"));
        for (const k of v.answer?.contradictions ?? []) {
          add(c, CONTRA_PREFIX + k.a + "|" + k.b, "contra");
          add(c, k.a, "contra-node");
          add(c, k.b, "contra-node");
        }
        v.focus = e.payload.nodes.map((n) => n.id);
        break;
      }
    }
  }
  // Data that is not a frame of its own but belongs to the run once it exists.
  for (const e of events) {
    if (e.type === "baseline") v.baseline = e.payload;
    if (e.type === "run.finished") v.finished = e.payload;
  }
  return v;
}

/** Display label for any IRI the run or graph knows. */
export function labelIndex(nodes: Node[]): Map<string, Node> {
  return new Map(nodes.map((n) => [n.id, n]));
}

export const local = (iri: string) => iri.split("#").pop()!.split("/").pop()!;
export const pretty = (pred: string) => local(pred).replace(/_/g, " ");
