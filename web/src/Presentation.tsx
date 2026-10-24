import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import "./presentation.css";
import Imprint from "./Imprint";

const App = lazy(() => import("./App"));
const initialTheme = (() => {
  try { return localStorage.getItem("graph-anchor-theme") === "light" ? "light" : "dark"; }
  catch { return "dark"; }
})();
document.documentElement.dataset.presentationTheme = initialTheme;
const labels = ["Logo", "Walkthrough", "Demo"];
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
    const target = Math.max(0, Math.min(2, next));
    setSub(target === 1 && back ? captions.length - 1 : 0);
    setScreen(target);
  }, []);
  const next = useCallback(() => {
    if (screen === 1 && sub < captions.length - 1) setSub(value => value + 1);
    else go(screen + 1);
  }, [screen, sub, go]);
  const previous = useCallback(() => {
    if (screen === 1 && sub > 0) setSub(value => value - 1);
    else go(screen - 1, true);
  }, [screen, sub, go]);

  useEffect(() => {
    if (screen === 2) { setAuto(false); setVisited(true); }
    document.title = `Graph Anchor · ${labels[screen]}`;
    headings.current[screen]?.focus({ preventScroll: true });
  }, [screen]);

  useEffect(() => {
    if (!auto || screen === 2) return;
    const timer = window.setTimeout(next, 3500);
    return () => window.clearTimeout(timer);
  }, [auto, screen, next]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (target.closest("input, textarea, select, a, [contenteditable], [role='dialog']")) return;
      // The interactive app owns playback keys; Escape returns to the final walkthrough scene.
      if (screen === 2) {
        if (event.key === "Escape") { event.preventDefault(); go(1, true); }
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
    <section className={`slide logo-slide ${screen === 0 ? "active" : ""}`} aria-label="Logo" aria-hidden={screen !== 0} {...(screen !== 0 ? { inert: "" } : {})} onClick={next}>
      <button className="autoplay" role="switch" aria-checked={auto} onClick={event => { event.stopPropagation(); setAuto(value => !value); }}>
        Auto-play <span className={`toggle ${auto ? "on" : ""}`}><span /></span>
      </button>
      <div className="logo-content">
        <Mark />
        <h1 ref={element => { headings.current[0] = element; }} tabIndex={-1}>Graph Anchor</h1>
        <p>Knowledge graphs that ground your AI.</p>
      </div>
      <button className="continue" onClick={event => { event.stopPropagation(); next(); }}>Click to continue <span>↓</span></button>
    </section>

    <section className={`slide walkthrough-slide ${screen === 1 ? "active" : ""}`} aria-label="Walkthrough" aria-hidden={screen !== 1} {...(screen !== 1 ? { inert: "" } : {})} onClick={next}>
      <div className="walkthrough-layout">
        <div className="walkthrough-captions" aria-live="polite">
          {captions.map(([eyebrow, title], index) => <div key={eyebrow} className={`walkthrough-caption${index === sub ? " current" : ""}${index < sub ? " before" : ""}`} aria-hidden={index !== sub}>
            <div className="slide-eyebrow">{eyebrow}</div>
            <h2 ref={element => { if (index === sub) headings.current[1] = element; }} tabIndex={-1}>{title}</h2>
          </div>)}
        </div>
        <p className="walkthrough-context">{sub === 0 ? "Current dataset: filling pressure · sealing temperature · packaging vibration. Synthetic incident replays." : "Earlier recorded sealing example · the rebuilt maintenance graph is available in the interactive app."}</p>
        {screen === 1 && <WalkthroughPreview stage={sub} />}
      </div>
      <button className="walkthrough-back" aria-label="Previous walkthrough scene" onClick={event => { event.stopPropagation(); previous(); }}>← Back</button>
      <button className="continue" onClick={event => { event.stopPropagation(); next(); }}>{sub < captions.length - 1 ? "Click to continue" : "Click to try it yourself"} <span>↓</span></button>
      <span className="walkthrough-progress" aria-label={`Walkthrough scene ${sub + 1} of ${captions.length}`}>{sub + 1} / {captions.length}</span>
    </section>

    <section className={`slide demo-slide ${screen === 2 ? "active" : ""}`} aria-label="Interactive demo" aria-hidden={screen !== 2} {...(screen !== 2 ? { inert: "" } : {})}>
      {(visited || screen === 2) && <Suspense fallback={<div className="demo-loading" role="status">Opening the knowledge graph…</div>}><App active={screen === 2} /></Suspense>}
    </section>

    <nav className="presentation-nav" aria-label="Presentation screens">
      {labels.map((label, index) => <button key={label} aria-label={label} aria-current={screen === index ? "step" : undefined} onClick={() => go(index)}><span /></button>)}
    </nav>
    <Imprint className="imprint-corner" />
    <div className="screen-reader-status" aria-live="polite">Screen {screen + 1} of 3: {labels[screen]}</div>
  </main>;
}
