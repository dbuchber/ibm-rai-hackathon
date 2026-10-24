// Data source abstraction (plan, stream C). VITE_DATA=static reads public/data; api talks to C4.
// The api source falls back to static files for reads, so a dead API never breaks replay.
import type {
  AuditEntry, CreateProposal, CreateRunResponse, Event, FeedbackResponse, GraphExport, Proposal, RunSummary,
} from "./contracts";
import { audit, CanaryEngine, localAudit } from "./canary";
import { nodeIri, predIri, proposalId } from "./ids";

export interface Ontology {
  classes: { name: string; description: string }[];
  predicates: { iri: string; name: string; description: string }[];
}

export type Decision = "approve" | "reject" | "flag";

export interface DataSource {
  kind: "static" | "api";
  live: boolean;
  getGraph(): Promise<GraphExport>;
  listRuns(): Promise<RunSummary[]>;
  getRun(id: string): Promise<Event[]>;
  /** Live questions need an invitation code; the API answers 403 "invite code required" without a valid one. */
  startRun(question: string, invite?: string): Promise<CreateRunResponse>;
  /** Flag an answer (thumbs down, optional text). `reveal` is set when it was the session's chat canary. */
  feedback(runId: string, text?: string): Promise<FeedbackResponse>;
  /** Tell the server the user looked at a source: an edge id, a chunk IRI or "evidence". */
  opened(runId: string, target: string): Promise<void>;
  streamRun(id: string, onEvent: (e: Event) => void, onLost: () => void): () => void;
  listProposals(): Promise<Proposal[]>;
  /** On a failed canary the result carries `alert`; its `reverted` ids are back to "proposed". */
  decide(id: string, decision: Decision): Promise<Proposal>;
  getAudit(): Promise<AuditEntry[]>;
  createProposal(body: CreateProposal): Promise<Proposal>;
  /** Not part of C4: shipped as a static file next to the graph export in both modes. */
  getOntology(): Promise<Ontology>;
}

/** What POST /api/proposals does, for static mode. */
export function localProposal(body: CreateProposal): Proposal {
  const kind = body.kind ?? "edge";
  const id =
    kind === "edge" ? proposalId("edge", { triple: [body.triple!.s, body.triple!.p, body.triple!.o] })
    : kind === "node" ? proposalId("node", { iri: nodeIri(body.node!.cls, body.node!.local_id) })
    : proposalId("predicate", { iri: predIri(body.predicate!.name) });
  return { ...body, kind, id, confidence: null, proposed_by: "user", status: "proposed" };
}

const BASE = import.meta.env.BASE_URL + "data/";

// One chat session per browser tab: chat canary state on the server is kept per session.
const SESSION_KEY = "ga-chat-session";
let memorySession: string | null = null;
function chatSession(): string {
  try {
    const s = sessionStorage.getItem(SESSION_KEY);
    if (s) return s;
  } catch { /* storage blocked: fall back to memory */ }
  memorySession ??= crypto.randomUUID();
  try { sessionStorage.setItem(SESSION_KEY, memorySession); } catch { /* ignore */ }
  return memorySession;
}

/** An HTTP error answer from the API; `retryAfter` in seconds when the server sent one (429). */
export class HttpError extends Error {
  constructor(message: string, readonly status: number, readonly retryAfter: number | null) { super(message); }
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    const detail = body?.detail;
    const retry = Number(r.headers.get("Retry-After"));
    throw new HttpError(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : `${r.status} ${url}`,
      r.status, Number.isFinite(retry) && retry > 0 ? retry : null);
  }
  return r.json() as Promise<T>;
}

function parseJsonl(text: string): Event[] {
  return text.split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l) as Event);
}

function staticSource(): DataSource {
  let proposals: Proposal[] | null = null;
  let graph: Promise<GraphExport> | null = null;
  const getGraph = () => (graph ??= json<GraphExport>(BASE + "graph_export.json"));
  const canary = new CanaryEngine(getGraph);
  return {
    kind: "static",
    live: false,
    getGraph,
    listRuns: () => json<RunSummary[]>(BASE + "runs/index.json"),
    getRun: async (id) => parseJsonl(await (await fetch(BASE + `runs/${id}.jsonl`)).text()),
    startRun: () => Promise.reject(new Error("Live mode needs the API.")),
    feedback: async (runId, text) => {
      audit("feedback", `run ${runId}: ${text || "(no text)"}`);
      return { reveal: null };
    },
    opened: async () => {},
    streamRun: (_id, _on, onLost) => {
      onLost();
      return () => {};
    },
    listProposals: async () => {
      proposals ??= await json<Proposal[]>(BASE + "proposals.json");
      proposals = await canary.plant(proposals);
      return proposals.map((p) => ({ ...p }));
    },
    decide: async (id, decision) => {
      const p = (proposals ?? []).find((x) => x.id === id);
      if (!p) throw new Error(`unknown proposal ${id}`);
      const res = canary.decide(p, decision, proposals!);
      if (res.alert) {
        // a failed canary is never kept; approvals since the last passed canary go back for review
        proposals = proposals!.filter((x) => x.id !== id);
        for (const x of proposals) if (res.alert.reverted.includes(x.id)) x.status = "proposed";
      } else {
        p.status = res.status;
      }
      return res;
    },
    getAudit: async () => [...localAudit],
    createProposal: async (body) => {
      const p = localProposal(body);
      proposals = [...(proposals ?? []).filter((x) => x.id !== p.id), p];
      return { ...p };
    },
    getOntology: () => json<Ontology>(BASE + "ontology.json"),
  };
}

function apiSource(): DataSource {
  const fallback = staticSource();
  const orStatic = <T,>(p: Promise<T>, f: () => Promise<T>) => p.catch(f);
  // writes fall back only when the API is unreachable; an HTTP error (e.g. 422) must reach the user
  const orOffline = <T,>(p: Promise<T>, f: () => Promise<T>) =>
    p.catch((e) => (e instanceof TypeError ? f() : Promise.reject(e)));
  return {
    kind: "api",
    live: true,
    getGraph: () => orStatic(json("/api/graph"), fallback.getGraph),
    listRuns: () => orStatic(json("/api/runs"), fallback.listRuns),
    getRun: (id) => orStatic(json(`/api/runs/${id}`), () => fallback.getRun(id)),
    startRun: (question, invite = "") =>
      json("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Invite-Code": invite, "X-Chat-Session": chatSession() },
        body: JSON.stringify({ question }),
      }),
    streamRun: (id, onEvent, onLost) => {
      const es = new EventSource(`/api/runs/${id}/stream`);
      let done = false;
      es.onmessage = (m) => {
        const e = JSON.parse(m.data) as Event;
        onEvent(e);
        if (e.type === "run.finished") {
          done = true;
          es.close();
        }
      };
      es.onerror = () => {
        if (!done) onLost();
        es.close();
      };
      return () => es.close();
    },
    listProposals: () => orStatic(json("/api/proposals"), fallback.listProposals),
    decide: (id, decision) =>
      orOffline(
        json(`/api/proposals/${id}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decision }),
        }),
        () => fallback.decide(id, decision),
      ),
    feedback: (runId, text) =>
      json(`/api/runs/${runId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Chat-Session": chatSession() },
        body: JSON.stringify({ text: text || null }),
      }),
    opened: async (runId, target) => {
      const r = await fetch(`/api/runs/${runId}/opened`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Chat-Session": chatSession() },
        body: JSON.stringify({ target }),
      });
      if (!r.ok) throw new Error(`${r.status} opened`);
    },
    createProposal: (body) =>
      orOffline(
        json("/api/proposals", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
        () => fallback.createProposal(body),
      ),
    getOntology: fallback.getOntology,
    // server log plus the browser-side entries of the chat canary click mock
    getAudit: () =>
      json<AuditEntry[]>("/api/audit")
        // the server lists oldest first; reverse before the stable sort so same-second entries stay newest first
        .then((xs) => [...localAudit, ...[...xs].reverse()].sort((a, b) => b.ts.localeCompare(a.ts)))
        .catch(() => [...localAudit]),
  };
}

export const data: DataSource = import.meta.env.VITE_DATA === "api" ? apiSource() : staticSource();
