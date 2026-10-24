import { useEffect, useRef } from "react";
import type { Node } from "./contracts";
import type { Folded } from "./fold";
import type { Index } from "./bits";
import { labelOf } from "./bits";

interface Props {
  node: Node;
  folded: Folded;
  idx: Index;
  /** chunk ids the current answer cites or the evidence contains */
  cited: Set<string>;
  /** chunk to scroll to and ring, e.g. after clicking a citation */
  focusChunk: string | null;
  onClose: () => void;
}

export default function Inspector({ node, folded, idx, cited, focusChunk, onClose }: Props) {
  const isDoc = node.cls === "Document";
  const chunks = node.cls === "Chunk" ? [node] : (isDoc ? folded.chunksOf.get(node.id) : folded.chunksAbout.get(node.id)) ?? [];
  // cited passages first, then reading order
  const ordered = [...chunks].sort((a, b) => Number(cited.has(b.id)) - Number(cited.has(a.id)));
  const nCited = chunks.filter((c) => cited.has(c.id)).length;
  const body = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!focusChunk) return;
    const el = body.current?.querySelector(`[data-chunk="${CSS.escape(focusChunk)}"]`);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [focusChunk, node.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const props = Object.entries(node.props ?? {});
  return (
    <aside className="panel left glass" aria-label={`Details: ${node.label}`}>
      <div className="panel-head">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="eyebrow">{node.cls}</div>
          <button className="link-btn" onClick={onClose}>Close</button>
        </div>
        <h2 className="question">{node.label}</h2>
        {node.description && <p className="small muted" style={{ margin: "6px 0 0" }}>{node.description}</p>}
        {props.length > 0 && (
          <dl className="props">
            {props.map(([k, v]) => [<dt key={k}>{k}</dt>, <dd key={k + "v"}>{String(v)}</dd>])}
          </dl>
        )}
      </div>
      <div className="panel-body" ref={body}>
        <div className="eyebrow" style={{ margin: "4px 4px 10px" }}>
          {chunks.length === 0
            ? "No text passages"
            : `${chunks.length} passage${chunks.length === 1 ? "" : "s"}${isDoc ? "" : " about this"}${nCited ? ` · ${nCited} cited` : ""}`}
        </div>
        {ordered.map((c) => {
          const doc = folded.docOf.get(c.id);
          return (
            <section key={c.id} data-chunk={c.id}
              className={"chunk-item" + (cited.has(c.id) ? " cited" : "") + (focusChunk === c.id ? " focus" : "")}>
              <div className="chunk-top">
                <span className="chunk-title">{c.label}</span>
                {cited.has(c.id) && <span className="tag live">Cited</span>}
              </div>
              <div className="chunk-meta">
                {!isDoc && doc && <>{labelOf(idx, doc)} · </>}
                {c.props?.page != null ? `page ${c.props.page}` : "page n/a"}
              </div>
              {c.text && <p className="chunk-text">{c.text}</p>}
            </section>
          );
        })}
      </div>
    </aside>
  );
}
