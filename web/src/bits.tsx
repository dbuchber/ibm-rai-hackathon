import type { Edge, Node } from "./contracts";
import { local, pretty } from "./run";

export type Index = Map<string, Node>;

export const labelOf = (idx: Index, iri: string) => idx.get(iri)?.label ?? local(iri);

export function Triple({ edge, idx }: { edge: Pick<Edge, "s" | "p" | "o">; idx: Index }) {
  return (
    <span className="triple">
      {labelOf(idx, edge.s)} <span className="p">{pretty(edge.p)} →</span> {labelOf(idx, edge.o)}
    </span>
  );
}

export function Mark() {
  // Brand glyph: a small graph whose highlighted path is the anchor.
  return (
    <svg className="brand-mark" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 6 L12 12 L19 7 M12 12 L12 19 M5 6 L5 16" stroke="var(--ink3)" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M5 6 L12 12 L12 19" stroke="var(--accent)" strokeWidth="2.2" fill="none" strokeLinecap="round" />
      <circle cx="5" cy="6" r="2.4" fill="var(--accent)" />
      <circle cx="12" cy="12" r="2.4" fill="var(--accent)" />
      <circle cx="12" cy="19" r="2.4" fill="var(--accent)" />
      <circle cx="19" cy="7" r="2" fill="var(--ink3)" />
      <circle cx="5" cy="16" r="2" fill="var(--ink3)" />
    </svg>
  );
}

const paths: Record<string, string> = {
  play: "M7 4.5v15l12.5-7.5z",
  pause: "M6.5 4.5h4v15h-4zM13.5 4.5h4v15h-4z",
  next: "M5 4.5v15l10-7.5zM16.5 4.5h3v15h-3z",
  prev: "M19 4.5v15L9 12zM4.5 4.5h3v15h-3z",
  restart: "M12 5V2L7 6l5 4V7a5 5 0 1 1-5 5H5a7 7 0 1 0 7-7z",
  end: "M4.5 4.5v15l8-7.5zM12.5 4.5v15l8-7.5z",
};

export function Icon({ name }: { name: keyof typeof paths }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d={paths[name]} fill="currentColor" />
    </svg>
  );
}
