// Data source abstraction (plan, stream C). VITE_DATA=static reads public/data; api talks to C4.
// The api source falls back to static files for reads, so a dead API never breaks replay.
import type { Event, GraphExport, Proposal, RunSummary } from "./contracts";

export interface DataSource {
  kind: "static" | "api";
  live: boolean;
  getGraph(): Promise<GraphExport>;
  listRuns(): Promise<RunSummary[]>;
  getRun(id: string): Promise<Event[]>;
  startRun(question: string): Promise<{ run_id: string }>;
  streamRun(id: string, onEvent: (e: Event) => void, onLost: () => void): () => void;
  listProposals(): Promise<Proposal[]>;
  decide(id: string, decision: "approve" | "reject"): Promise<Proposal>;
}

const BASE = import.meta.env.BASE_URL + "data/";

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json() as Promise<T>;
}

function parseJsonl(text: string): Event[] {
  return text.split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l) as Event);
}

function staticSource(): DataSource {
  let proposals: Proposal[] | null = null;
  return {
    kind: "static",
    live: false,
    getGraph: () => json<GraphExport>(BASE + "graph_export.json"),
    listRuns: () => json<RunSummary[]>(BASE + "runs/index.json"),
    getRun: async (id) => parseJsonl(await (await fetch(BASE + `runs/${id}.jsonl`)).text()),
    startRun: () => Promise.reject(new Error("Live mode needs the API.")),
    streamRun: (_id, _on, onLost) => {
      onLost();
      return () => {};
    },
    listProposals: async () => (proposals ??= await json<Proposal[]>(BASE + "proposals.json")),
    decide: async (id, decision) => {
      const p = (proposals ?? []).find((x) => x.id === id);
      if (!p) throw new Error(`unknown proposal ${id}`);
      p.status = decision === "approve" ? "approved" : "rejected";
      return { ...p };
    },
  };
}

function apiSource(): DataSource {
  const fallback = staticSource();
  const orStatic = <T,>(p: Promise<T>, f: () => Promise<T>) => p.catch(f);
  return {
    kind: "api",
    live: true,
    getGraph: () => orStatic(json("/api/graph"), fallback.getGraph),
    listRuns: () => orStatic(json("/api/runs"), fallback.listRuns),
    getRun: (id) => orStatic(json(`/api/runs/${id}`), () => fallback.getRun(id)),
    startRun: (question) =>
      json("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
      orStatic(
        json(`/api/proposals/${id}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decision }),
        }),
        () => fallback.decide(id, decision),
      ),
  };
}

export const data: DataSource = import.meta.env.VITE_DATA === "api" ? apiSource() : staticSource();
