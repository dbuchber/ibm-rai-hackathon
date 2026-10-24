import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import "./presentation.css";
import Imprint from "./Imprint";
import Roadmap from "./Roadmap";

const App = lazy(() => import("./App"));
const initialTheme = (() => {
  try { return localStorage.getItem("graph-anchor-theme") === "light" ? "light" : "dark"; }
  catch { return "dark"; }
})();
document.documentElement.dataset.presentationTheme = initialTheme;
const labels = ["Logo", "Problem", "Walkthrough", "Demo", "Roadmap"];
const [LOGO, PROBLEM, WALK, DEMO, ROADMAP] = [0, 1, 2, 3, 4];
const captions = [
  ["Start in chat", "An alarm starts the question. Evidence guides the response."],
  ["Step 1 · Question sent", "Can sealing continue? Check the operating limits."],
  ["Step 2 · Search", "Connect the station, its sensor and the applicable sources."],
  ["Step 3 · Answer", "Read the answer. Inspect the evidence behind it."],
  ["Step 4 · Check the sources", "An alarm threshold is not an operating limit."],
];

function Mark() {
  return <svg className="presentation-mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
    <circle cx="5" cy="4" r="2" fill="currentColor" stroke="none" />
    <circle cx="19" cy="4" r="2" fill="currentColor" stroke="none" />
    <circle cx="12" cy="20" r="2" fill="currentColor" stroke="none" />
    <path d="M5 4l7 8 7-8M12 12v8" />
  </svg>;
}

function WalkthroughPreview({ stage }: { stage: number }) {
  const frame = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);
  useEffect(() => {
    const element = frame.current;
    if (!element) return;
    const resize = () => setScale(Math.min(element.clientWidth / 1280, element.clientHeight / 740));
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return <div className="walkthrough-frame" ref={frame} role="img" aria-label={`Recorded app preview: ${captions[stage][1]}`}>
    <div className={`walkthrough-tool${stage < 3 ? " chat-intro" : ""}`} style={{ transform: `translate(-50%, -50%) scale(${scale})` }} aria-hidden="true" {...{ inert: "" }}>
      <Suspense fallback={<div className="walkthrough-loading">Opening the knowledge graph…</div>}>
        <App active={false} walkthroughStage={stage} />
      </Suspense>
    </div>
  </div>;
}

export default function Presentation() {
  const [theme, setTheme] = useState(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.presentationTheme = theme;
    try { localStorage.setItem("graph-anchor-theme", theme); } catch { /* Private storage can be unavailable. */ }
  }, [theme]);
  const [screen, setScreen] = useState(0);
  const [sub, setSub] = useState(0);
  const [auto, setAuto] = useState(false);
  const [visited, setVisited] = useState(false);
  const headings = useRef<(HTMLHeadingElement | null)[]>([]);
  const go = useCallback((next: number, back = false) => {
    const target = Math.max(LOGO, Math.min(ROADMAP, next));
    setSub(target === WALK && back ? captions.length - 1 : 0);
    setScreen(target);
  }, []);
  const next = useCallback(() => {
    if (screen === WALK && sub < captions.length - 1) setSub(value => value + 1);
    else go(screen + 1);
  }, [screen, sub, go]);
  const previous = useCallback(() => {
    if (screen === WALK && sub > 0) setSub(value => value - 1);
    else go(screen - 1, true);
  }, [screen, sub, go]);

  useEffect(() => {
    if (screen === DEMO) { setAuto(false); setVisited(true); }
    document.title = `Graph Anchor · ${labels[screen]}`;
    headings.current[screen]?.focus({ preventScroll: true });
  }, [screen]);

  useEffect(() => {
    if (!auto || screen >= DEMO) return;
    const timer = window.setTimeout(next, 3500);
    return () => window.clearTimeout(timer);
  }, [auto, screen, next]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (target.closest("input, textarea, select, a, [contenteditable], [role='dialog']")) return;
      // The interactive app owns playback keys; Escape returns to the final walkthrough scene.
      if (screen === DEMO) {
        if (event.key === "Escape") { event.preventDefault(); go(WALK, true); }
        return;
      }
      if (event.key === " " && target.closest("button")) return;
      if (["ArrowRight", "ArrowDown", " ", "PageDown"].includes(event.key)) {
        event.preventDefault(); next();
      }
      if (["ArrowLeft", "ArrowUp", "PageUp"].includes(event.key)) {
        event.preventDefault(); previous();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [screen, go, next, previous]);

  return <main className={`presentation screen-${screen}`}>
    <button className="theme-toggle" aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} aria-pressed={theme === "light"} title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} onClick={() => setTheme(value => value === "dark" ? "light" : "dark")}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {theme === "dark" ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" /></> : <path d="M20.5 14A8.5 8.5 0 0 1 10 3.5 8.5 8.5 0 1 0 20.5 14Z" />}
      </svg>
      <span className="theme-label">{theme === "dark" ? "Light mode" : "Dark mode"}</span>
    </button>
    <section className={`slide logo-slide ${screen === LOGO ? "active" : ""}`} aria-label="Logo" aria-hidden={screen !== LOGO} {...(screen !== LOGO ? { inert: "" } : {})} onClick={next}>
      <button className="autoplay" role="switch" aria-checked={auto} onClick={event => { event.stopPropagation(); setAuto(value => !value); }}>
        Auto-play <span className={`toggle ${auto ? "on" : ""}`}><span /></span>
      </button>
      <div className="logo-content">
        <Mark />
        <h1 ref={element => { headings.current[LOGO] = element; }} tabIndex={-1}>Graph Anchor</h1>
        <p>Knowledge graphs that ground your AI.</p>
      </div>
      <button className="continue" onClick={event => { event.stopPropagation(); next(); }}>Click to continue <span>↓</span></button>
    </section>

    <section className={`slide problem-slide ${screen === PROBLEM ? "active" : ""}`} aria-label="The problem" aria-hidden={screen !== PROBLEM} {...(screen !== PROBLEM ? { inert: "" } : {})} onClick={next}>
      <div className="problem-content">
        <div className="slide-eyebrow">The problem</div>
        <div className="problem-number" aria-hidden="true">60%</div>
        <h2 ref={element => { headings.current[PROBLEM] = element; }} tabIndex={-1}>
          <span className="sr-only">60% </span>of AI projects without AI‑ready data will be abandoned.
        </h2>
        <p>On a production line, a wrong answer is not a typo. It is a stopped line, a recalled batch, or an injured worker.</p>
        <p className="problem-answer">Graph Anchor: the model proposes, <b>people approve</b>, every answer shows its path.</p>
      </div>
      <a className="problem-source" href="https://www.gartner.com/en/newsroom/press-releases/2025-02-26-lack-of-ai-ready-data-puts-ai-projects-at-risk" target="_blank" rel="noreferrer" onClick={event => event.stopPropagation()}>
        Gartner, press release 26 Feb 2025
      </a>
      <button className="continue" onClick={event => { event.stopPropagation(); next(); }}>Click to continue <span>↓</span></button>
    </section>

    <section className={`slide walkthrough-slide ${screen === WALK ? "active" : ""}`} aria-label="Walkthrough" aria-hidden={screen !== WALK} {...(screen !== WALK ? { inert: "" } : {})} onClick={next}>
      <div className="walkthrough-layout">
        <div className="walkthrough-captions" aria-live="polite">
          {captions.map(([eyebrow, title], index) => <div key={eyebrow} className={`walkthrough-caption${index === sub ? " current" : ""}${index < sub ? " before" : ""}`} aria-hidden={index !== sub}>
            <div className="slide-eyebrow">{eyebrow}</div>
            <h2 ref={element => { if (index === sub) headings.current[WALK] = element; }} tabIndex={-1}>{title}</h2>
          </div>)}
        </div>
        <p className="walkthrough-context">{sub === 0 ? "Current dataset: filling pressure · sealing temperature · packaging vibration. Synthetic incident replays." : "Earlier recorded sealing example · the rebuilt maintenance graph is available in the interactive app."}</p>
        {screen === WALK && <WalkthroughPreview stage={sub} />}
      </div>
      <button className="walkthrough-back" aria-label="Previous walkthrough scene" onClick={event => { event.stopPropagation(); previous(); }}>← Back</button>
      <button className="continue" onClick={event => { event.stopPropagation(); next(); }}>{sub < captions.length - 1 ? "Click to continue" : "Click to try it yourself"} <span>↓</span></button>
      <span className="walkthrough-progress" aria-label={`Walkthrough scene ${sub + 1} of ${captions.length}`}>{sub + 1} / {captions.length}</span>
    </section>

    <section className={`slide demo-slide ${screen === DEMO ? "active" : ""}`} aria-label="Interactive demo" aria-hidden={screen !== DEMO} {...(screen !== DEMO ? { inert: "" } : {})}>
      {(visited || screen === DEMO) && <Suspense fallback={<div className="demo-loading" role="status">Opening the knowledge graph…</div>}><App active={screen === DEMO} /></Suspense>}
    </section>

    <section className={`slide roadmap-slide ${screen === ROADMAP ? "active" : ""}`} aria-label="Roadmap" aria-hidden={screen !== ROADMAP} {...(screen !== ROADMAP ? { inert: "" } : {})}>
      {screen === ROADMAP && <Roadmap steps={3} />}
    </section>

    <nav className="presentation-nav" aria-label="Presentation screens">
      {labels.map((label, index) => <button key={label} aria-label={label} aria-current={screen === index ? "step" : undefined} onClick={() => go(index)}><span /></button>)}
    </nav>
    <Imprint className="imprint-corner" />
    <div className="screen-reader-status" aria-live="polite">Screen {screen + 1} of {labels.length}: {labels[screen]}</div>
  </main>;
}
