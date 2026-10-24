// Display only: text chunks live one level below the graph. Chunk nodes are hidden, and every edge
// that touches a chunk is lifted to the chunk's document (Chunk mentions X -> Document mentions X).
// Run highlights, focus and citations are mapped through the same function, so data stays untouched.
import type { Edge, Node } from "./contracts";

export interface DisplayEdge extends Edge {
  /** number of distinct chunks behind a lifted edge */
  chunks?: number;
}

export interface Folded {
  nodes: Node[];
  edges: DisplayEdge[];
  /** chunk id -> document id */
  docOf: Map<string, string>;
  /** document id -> its chunks, in reading order */
  chunksOf: Map<string, Node[]>;
  /** entity id -> chunks that mention or define it */
  chunksAbout: Map<string, Node[]>;
  /** any element id (node, chunk, edge) -> the id drawn for it */
  mapId: (id: string) => string;
}

const RANK = { approved: 2, proposed: 1, rejected: 0 } as const;
const sectionNo = (n: Node) => Number(n.id.match(/-s(\d+)$/)?.[1] ?? 0);

export function fold(nodes: Node[], edges: Edge[]): Folded {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const isChunk = (id: string) => byId.get(id)?.cls === "Chunk";
  const docOf = new Map<string, string>();
  for (const e of edges) if (e.p.endsWith("#has_chunk") && isChunk(e.o)) docOf.set(e.o, e.s);
  // fallback for chunks without a has_chunk edge in view: kg:chunk/<DOC>-s<n> -> kg:document/<DOC>
  for (const n of nodes) {
    if (n.cls !== "Chunk" || docOf.has(n.id)) continue;
    const doc = n.id.replace(/\/chunk\/(.+)-s\d+$/, "/document/$1");
    if (doc !== n.id && byId.has(doc)) docOf.set(n.id, doc);
  }

  const chunksOf = new Map<string, Node[]>();
  for (const [c, d] of docOf) {
    if (!chunksOf.has(d)) chunksOf.set(d, []);
    chunksOf.get(d)!.push(byId.get(c)!);
  }
  chunksOf.forEach((cs) => cs.sort((a, b) => sectionNo(a) - sectionNo(b)));

  const chunksAbout = new Map<string, Node[]>();
  const edgeMap = new Map<string, string>();
  const lifted = new Map<string, DisplayEdge & { chunkSet: Set<string> }>();
  const out: DisplayEdge[] = [];
  for (const e of edges) {
    const s = docOf.get(e.s) ?? e.s;
    const o = docOf.get(e.o) ?? e.o;
    if (s === e.s && o === e.o) { out.push(e); continue; }
    // remember which entity a chunk talks about, for the inspector
    for (const [c, other] of [[e.s, e.o], [e.o, e.s]] as const) {
      if (docOf.has(c) && !isChunk(other) && !e.p.endsWith("#has_chunk")) {
        const list = chunksAbout.get(other) ?? [];
        if (!list.some((x) => x.id === c)) list.push(byId.get(c)!);
        chunksAbout.set(other, list);
      }
    }
    if (s === o) { edgeMap.set(e.id, s); continue; } // has_chunk, or a link inside one document
    const id = (e.id.startsWith("contra:") ? "contra:" : "fold:") + `${s}|${e.p}|${o}`;
    edgeMap.set(e.id, id);
    const cur = lifted.get(id);
    const chunk = [e.s, e.o].filter((x) => docOf.has(x));
    if (cur) {
      chunk.forEach((c) => cur.chunkSet.add(c));
      if (RANK[e.graph ?? "approved"] > RANK[cur.graph ?? "approved"]) cur.graph = e.graph;
    } else {
      lifted.set(id, { id, s, p: e.p, o, graph: e.graph, chunkSet: new Set(chunk) });
    }
  }
  for (const { chunkSet, ...e } of lifted.values()) out.push({ ...e, chunks: chunkSet.size });

  return {
    nodes: nodes.filter((n) => !docOf.has(n.id)),
    edges: out,
    docOf,
    chunksOf,
    chunksAbout,
    mapId: (id) => docOf.get(id) ?? edgeMap.get(id) ?? id,
  };
}

/** Lift run/curation highlight classes onto the drawn elements. */
export function foldClasses(classes: Map<string, string>, f: Folded): Map<string, string> {
  if (!classes.size) return classes;
  const out = new Map<string, Set<string>>();
  for (const [id, cls] of classes) {
    const to = f.mapId(id);
    const set = out.get(to) ?? new Set<string>();
    cls.split(" ").forEach((c) => c && set.add(c));
    out.set(to, set);
  }
  const res = new Map<string, string>();
  for (const [id, set] of out) {
    // a lifted edge is "followed" if any edge behind it was
    if (set.has("follow")) { set.delete("prune"); set.delete("frontier"); }
    res.set(id, [...set].join(" "));
  }
  return res;
}
