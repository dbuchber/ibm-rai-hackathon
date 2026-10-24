// The one canvas: twin view, run walk and evidence graph are all states of the same Cytoscape graph.
import cytoscape, { type Core, type ElementDefinition, type StylesheetStyle } from "cytoscape";
import fcose from "cytoscape-fcose";
import { useEffect, useRef } from "react";
import type { Edge, Node } from "./contracts";
import { pretty } from "./run";

cytoscape.use(fcose);

export type GraphMode = "twin" | "run" | "evidence";

export const LAYER: Record<string, "company" | "plant" | "docs"> = {
  Company: "company", Customer: "company", Supplier: "company", ProductionOrder: "company", Role: "company",
  System: "plant", Zone: "plant", Station: "plant", Sensor: "plant", SensorModel: "plant", Person: "plant",
  Rule: "plant", AnomalyEvent: "plant", SafetyEvent: "plant", Maintenance: "plant",
  Document: "docs", Chunk: "docs",
};

const SIZE: Record<string, number> = {
  Company: 34, System: 30, Zone: 22, Station: 20, Document: 20, Supplier: 18, Customer: 18,
  ProductionOrder: 15, SensorModel: 15, Sensor: 13, Rule: 13, Person: 11, Role: 11, Chunk: 11,
};

interface Palette {
  bg: string; ink: string; ink2: string; edge: string; edgeQuiet: string;
  company: string; plant: string; docs: string; accent: string; accentSoft: string; contra: string;
}

const LIGHT: Palette = {
  bg: "#F5F5F7", ink: "#1D1D1F", ink2: "#6E6E73", edge: "#C7C7CC", edgeQuiet: "#D8D8DC",
  company: "#9C8BD9", plant: "#5FAE9B", docs: "#CFA866", accent: "#0071E3", accentSoft: "#0071E3", contra: "#D70015",
};
const DARK: Palette = {
  bg: "#000000", ink: "#F5F5F7", ink2: "#98989D", edge: "#48484A", edgeQuiet: "#38383A",
  company: "#9D8CE0", plant: "#5DB8A3", docs: "#D6AE6A", accent: "#0A84FF", accentSoft: "#0A84FF", contra: "#FF453A",
};

const prefersDark = () => window.matchMedia("(prefers-color-scheme: dark)").matches;
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function stylesheet(c: Palette): StylesheetStyle[] {
  const font = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif';
  return [
    {
      selector: "node",
      style: {
        width: "data(size)", height: "data(size)",
        "background-color": c.plant, "border-width": 0,
        label: "data(label)", "font-family": font, "font-size": 11, "font-weight": 500,
        color: c.ink2, "text-valign": "bottom", "text-margin-y": 5,
        "min-zoomed-font-size": 9, "text-max-width": "140px", "text-wrap": "ellipsis",
        "transition-property": "opacity, background-color, border-width, border-color, width, height",
        "transition-duration": 450,
      } as any,
    },
    { selector: 'node[layer = "company"]', style: { "background-color": c.company } },
    { selector: 'node[layer = "docs"]', style: { "background-color": c.docs, shape: "round-rectangle" } },
    {
      selector: "edge",
      style: {
        width: 1, "line-color": c.edge, "curve-style": "bezier",
        "target-arrow-shape": "triangle", "target-arrow-color": c.edge, "arrow-scale": 0.6,
        "font-family": font, "font-size": 10, color: c.ink2, "text-rotation": "autorotate",
        "text-background-color": c.bg, "text-background-opacity": 0.9, "text-background-padding": "2px",
        "text-background-shape": "roundrectangle", "min-zoomed-font-size": 8,
        "transition-property": "opacity, line-color, width, target-arrow-color",
        "transition-duration": 450,
      } as any,
    },
    { selector: 'edge[graph = "proposed"]', style: { "line-style": "dashed", "line-dash-pattern": [5, 4], "line-color": c.ink2, "target-arrow-color": c.ink2, width: 1.5, label: "proposed", color: c.ink2 } as any },
    { selector: ".hover", style: { "font-weight": 600, color: c.ink, "z-index": 30 } as any },
    { selector: "edge.hover", style: { label: "data(pred)" } },

    // --- run walk ---
    { selector: ".quiet", style: { opacity: 0.3 } },
    { selector: "node.explored", style: { opacity: 1 } },
    { selector: "node.walked", style: { opacity: 1, color: c.ink, "font-weight": 600, "min-zoomed-font-size": 0 } as any },
    { selector: "node.seed", style: { "border-width": 3, "border-color": c.ink, "border-opacity": 0.85 } as any },
    { selector: "edge.frontier", style: { opacity: 1, width: 2.5, "line-color": c.ink, "target-arrow-color": c.ink, "line-style": "dashed", "line-dash-pattern": [6, 4], label: "data(pred)", color: c.ink } as any },
    { selector: "edge.follow", style: { opacity: 1, width: 3, "line-style": "solid", "line-color": c.accent, "target-arrow-color": c.accent, label: "data(pred)", color: c.accent } as any },
    { selector: "edge.prune", style: { opacity: 0.45, width: 1.5, "line-color": c.ink2, "target-arrow-color": c.ink2, "line-style": "dotted" } as any },
    { selector: "edge.prune.current", style: { label: "pruned", color: c.ink2 } },

    // --- evidence: the graph that led to the answer ---
    { selector: ".dim", style: { opacity: 0.08 } },
    { selector: "edge.prune.dim", style: { opacity: 0.12 } },
    {
      selector: "node.evidence",
      style: {
        opacity: 1, "border-width": 3, "border-color": c.accent, "border-opacity": 1,
        "underlay-color": c.accentSoft, "underlay-opacity": 0.16, "underlay-padding": 9, "underlay-shape": "ellipse",
        color: c.ink, "font-size": 12, "font-weight": 600, "min-zoomed-font-size": 0, "z-index": 20,
      } as any,
    },
    {
      selector: "edge.evidence",
      style: {
        opacity: 1, width: 4.5, "line-color": c.accent, "target-arrow-color": c.accent, "arrow-scale": 0.9,
        "line-style": "solid", label: "data(pred)", color: c.accent, "font-weight": 600, "font-size": 11,
        "min-zoomed-font-size": 0, "z-index": 20,
        "underlay-color": c.accentSoft, "underlay-opacity": 0.14, "underlay-padding": 5,
      } as any,
    },
    { selector: "edge.contra-virtual", style: { display: "none" } },
    {
      selector: "edge.contra",
      style: {
        display: "element", opacity: 1, width: 3.5, "line-color": c.contra, "target-arrow-shape": "none",
        "line-style": "dashed", "line-dash-pattern": [8, 5], "curve-style": "unbundled-bezier",
        "control-point-distances": [-110], "control-point-weights": [0.5],
        label: "contradicts", color: c.contra, "font-weight": 700, "font-size": 12, "min-zoomed-font-size": 0, "z-index": 25,
      } as any,
    },
    { selector: "node.contra-node", style: { "border-color": c.contra, "underlay-color": c.contra, "underlay-opacity": 0.16 } as any },
    { selector: ".flash", style: { "underlay-color": c.accent, "underlay-opacity": 0.35, "underlay-padding": 14, "z-index": 40 } as any },
    { selector: "node:selected", style: { "border-width": 3, "border-color": c.ink } },
  ];
}

function toElements(nodes: Node[], edges: Edge[]): ElementDefinition[] {
  const ids = new Set(nodes.map((n) => n.id));
  return [
    ...nodes.map((n) => ({
      group: "nodes" as const,
      data: { id: n.id, label: n.label, cls: n.cls, layer: LAYER[n.cls] ?? "plant", size: SIZE[n.cls] ?? 13 },
    })),
    ...edges
      .filter((e) => ids.has(e.s) && ids.has(e.o))
      .map((e) => ({
        group: "edges" as const,
        data: { id: e.id, source: e.s, target: e.o, pred: pretty(e.p), graph: e.graph },
        classes: e.id.startsWith("contra:") ? "contra-virtual" : "",
      })),
  ];
}

const LAYOUT = {
  name: "fcose", quality: "proof", animate: false, randomize: true, nodeSeparation: 90,
  idealEdgeLength: 80, nodeRepulsion: 9000, gravity: 0.25, numIter: 3000, padding: 40,
};

interface Props {
  nodes: Node[];
  edges: Edge[];
  classes: Map<string, string>;
  mode: GraphMode;
  focus: string[];
  focusKey: string;
  /** px covered by floating chrome; the camera frames the remaining area */
  inset: { top: number; right: number; bottom: number; left: number };
  flash: string | null;
  onSelect: (id: string | null) => void;
}

export default function Graph(p: Props) {
  const box = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const known = useRef<Set<string>>(new Set());
  const onSelect = useRef(p.onSelect);
  onSelect.current = p.onSelect;

  // mount
  useEffect(() => {
    const cy = cytoscape({
      container: box.current!, elements: [], style: stylesheet(prefersDark() ? DARK : LIGHT),
      minZoom: 0.15, maxZoom: 3, wheelSensitivity: 0.25, boxSelectionEnabled: false,
    });
    cyRef.current = cy;
    cy.on("mouseover", "node, edge", (e) => e.target.addClass("hover"));
    cy.on("mouseout", "node, edge", (e) => e.target.removeClass("hover"));
    cy.on("tap", "node", (e) => onSelect.current(e.target.id()));
    cy.on("tap", (e) => { if (e.target === cy) onSelect.current(null); });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const restyle = () => cy.style(stylesheet(mq.matches ? DARK : LIGHT));
    mq.addEventListener("change", restyle);
    return () => { mq.removeEventListener("change", restyle); cy.destroy(); };
  }, []);

  // elements: add what is new, keep positions of what exists, lay out once (and again when new nodes arrive)
  useEffect(() => {
    const cy = cyRef.current!;
    const els = toElements(p.nodes, p.edges);
    const wanted = new Set(els.map((e) => e.data.id!));
    cy.elements().filter((e) => !wanted.has(e.id())).remove();
    // keep data of existing elements current (e.g. a proposal approved: graph proposed -> approved)
    cy.batch(() => {
      for (const el of els) {
        const ex = cy.getElementById(el.data.id!);
        if (ex.nonempty() && el.group === "edges" && ex.data("graph") !== el.data.graph) ex.data("graph", el.data.graph);
      }
    });
    const fresh = els.filter((e) => !known.current.has(e.data.id!) || cy.getElementById(e.data.id!).empty());
    if (!fresh.length) return;
    const first = cy.nodes().empty();
    cy.batch(() => {
      for (const el of fresh) {
        if (el.group === "nodes") {
          // start new nodes next to an existing neighbour so the relayout stays calm
          const nb = p.edges.find((e) => e.s === el.data.id || e.o === el.data.id);
          const other = nb && cy.getElementById(nb.s === el.data.id ? nb.o : nb.s);
          const at = other && other.nonempty() ? other.position() : { x: 0, y: 0 };
          cy.add({ ...el, position: { x: at.x + Math.random() * 40 - 20, y: at.y + Math.random() * 40 - 20 } });
        }
      }
      for (const el of fresh) if (el.group === "edges") cy.add(el);
    });
    fresh.forEach((e) => known.current.add(e.data.id!));
    const newNodes = fresh.some((e) => e.group === "nodes");
    if (newNodes) {
      cy.layout({ ...LAYOUT, randomize: first, animate: !first && !reducedMotion(), animationDuration: 600 } as any).run();
      if (first) fitTo(cy, cy.elements(), p.inset, false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.nodes, p.edges]);

  // highlight classes
  useEffect(() => {
    const cy = cyRef.current!;
    cy.batch(() => {
      cy.elements().removeClass("quiet dim seed walked explored frontier follow prune current evidence contra contra-node");
      for (const [id, cls] of p.classes) cy.getElementById(id).addClass(cls);
      if (p.mode === "run") cy.elements().filter((e) => !p.classes.has(e.id())).addClass("quiet");
      if (p.mode === "evidence") {
        cy.elements().filter((e) => !/\b(evidence|contra)\b/.test(p.classes.get(e.id()) ?? "")).addClass("dim");
      }
    });
  }, [p.classes, p.mode]);

  // camera
  useEffect(() => {
    const cy = cyRef.current!;
    const eles = p.focus.length
      ? cy.collection(p.focus.map((id) => cy.getElementById(id)).filter((e) => e.nonempty()))
      : cy.elements();
    if (eles.nonempty()) fitTo(cy, eles, p.inset, !reducedMotion());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.focusKey]);

  // citation flash
  useEffect(() => {
    const cy = cyRef.current!;
    cy.elements(".flash").removeClass("flash");
    if (!p.flash) return;
    const el = cy.getElementById(p.flash);
    if (el.empty()) return;
    const eles = el.isEdge() ? el.union(el.connectedNodes()) : el;
    eles.addClass("flash");
    fitTo(cy, el.isEdge() ? eles : (el as cytoscape.NodeSingular).closedNeighborhood(), p.inset, !reducedMotion(), 2);
    const t = setTimeout(() => eles.removeClass("flash"), 1800);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.flash]);

  return <div ref={box} className="graph" aria-label="Knowledge graph" role="img" />;
}

/** Like cy.fit, but frames the area not covered by floating panels. */
function fitTo(cy: Core, eles: cytoscape.Collection, inset: Props["inset"], animate: boolean, maxZoom = 1.8) {
  const bb = eles.boundingBox({});
  const w = cy.width() - inset.left - inset.right;
  const h = cy.height() - inset.top - inset.bottom;
  const pad = 56;
  const zoom = Math.max(0.2, Math.min(maxZoom, (w - 2 * pad) / Math.max(bb.w, 1), (h - 2 * pad) / Math.max(bb.h, 1)));
  const cx = inset.left + w / 2;
  const cyy = inset.top + h / 2;
  const pan = { x: cx - zoom * (bb.x1 + bb.w / 2), y: cyy - zoom * (bb.y1 + bb.h / 2) };
  if (animate) cy.animate({ zoom, pan }, { duration: 700, easing: "ease-in-out-cubic" });
  else cy.viewport({ zoom, pan });
}
