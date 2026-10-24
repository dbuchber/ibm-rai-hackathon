import { lazy, Suspense, useEffect, useRef, useState } from "react";

import "./presentation.css";

const App = lazy(() => import("./App"));
document.documentElement.dataset.presentationTheme = "dark";
const labels = ["Logo", "Use case", "Demo"];

function Mark() {
  return <svg className="presentation-mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
    <circle cx="5" cy="4" r="2" fill="currentColor" stroke="none" />
    <circle cx="19" cy="4" r="2" fill="currentColor" stroke="none" />
    <circle cx="12" cy="20" r="2" fill="currentColor" stroke="none" />
    <path d="M5 4l7 8 7-8M12 12v8" />
  </svg>;
}

export default function Presentation() {
  const [screen, setScreen] = useState(0);
  const [auto, setAuto] = useState(false);
  const [visited, setVisited] = useState(false);
  const headings = useRef<(HTMLHeadingElement | null)[]>([]);
  const go = (next: number) => setScreen(Math.max(0, Math.min(2, next)));

  useEffect(() => {
    if (screen === 2) { setAuto(false); setVisited(true); }
    document.title = `Graph Anchor · ${labels[screen]}`;
    headings.current[screen]?.focus({ preventScroll: true });
  }, [screen]);

  useEffect(() => {
    if (!auto || screen === 2) return;
    const timer = window.setTimeout(() => setScreen(s => Math.min(2, s + 1)), 4000);
    return () => window.clearTimeout(timer);
  }, [auto, screen]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (target.closest("input, textarea, select, button, a, [contenteditable], [role='dialog']")) return;
      // The existing app owns playback keys on the demo screen. Escape returns to the slides.
      if (screen === 2) {
        if (event.key === "Escape") { event.preventDefault(); go(1); }
        return;
      }
      if (["ArrowRight", "ArrowDown", " ", "PageDown"].includes(event.key)) {
        event.preventDefault(); go(screen + 1);
      }
      if (["ArrowLeft", "ArrowUp", "PageUp"].includes(event.key)) {
        event.preventDefault(); go(screen - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [screen]);

  return <main className={`presentation screen-${screen}`}>
    <section className={`slide logo-slide ${screen === 0 ? "active" : ""}`} aria-label="Logo" aria-hidden={screen !== 0} {...(screen !== 0 ? { inert: "" } : {})} onClick={() => go(1)}>
      <button className="autoplay" role="switch" aria-checked={auto} onClick={event => { event.stopPropagation(); setAuto(value => !value); }}>
        Auto-play <span className={`toggle ${auto ? "on" : ""}`}><span /></span>
      </button>
      <div className="logo-content">
        <Mark />
        <h1 ref={element => { headings.current[0] = element; }} tabIndex={-1}>Graph Anchor</h1>
        <p>Knowledge graphs that ground your AI.</p>
      </div>
      <button className="continue" onClick={event => { event.stopPropagation(); go(1); }}>Click to continue <span>↓</span></button>
    </section>

    <section className={`slide use-case ${screen === 1 ? "active" : ""}`} aria-label="Use case" aria-hidden={screen !== 1} {...(screen !== 1 ? { inert: "" } : {})} onClick={() => go(2)}>
      <div className="slide-content">
        <div className="slide-eyebrow">The problem</div>
        <h2 ref={element => { headings.current[1] = element; }} tabIndex={-1}>Similar text.<br />Different answers.<br /><span>Which one do you trust?</span></h2>
        <p>On a factory floor, a procedure and a sensor datasheet can disagree. An AI assistant needs more than matching words to give an answer you can trust.</p>
        <div className="slide-principle"><span className="principle-line" />Approved knowledge. Visible reasoning. Cited evidence.</div>
      </div>
      <button className="continue" onClick={event => { event.stopPropagation(); go(2); }}>Explore the demo <span>↓</span></button>
    </section>

    <section className={`slide demo-slide ${screen === 2 ? "active" : ""}`} aria-label="Interactive demo" aria-hidden={screen !== 2} {...(screen !== 2 ? { inert: "" } : {})}>
      {(visited || screen === 2) && <Suspense fallback={<div className="demo-loading" role="status">Opening the knowledge graph…</div>}><App active={screen === 2} /></Suspense>}
    </section>

    <nav className="presentation-nav" aria-label="Presentation screens">
      {labels.map((label, index) => <button key={label} aria-label={label} aria-current={screen === index ? "step" : undefined} onClick={() => go(index)}><span /></button>)}
    </nav>
    <div className="screen-reader-status" aria-live="polite">Screen {screen + 1} of 3: {labels[screen]}</div>
  </main>;
}

