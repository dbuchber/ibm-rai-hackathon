// Impressum: Offenlegung gemäß § 25 Mediengesetz (Austria). A link that opens the disclosure in a dialog.
import { useEffect, useRef, useState } from "react";

export default function Imprint({ className = "" }: { className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className={"imprint-link " + className} onClick={(e) => { e.stopPropagation(); setOpen(true); }}>Impressum</button>
      {open && <ImprintDialog onClose={() => setOpen(false)} />}
    </>
  );
}

function ImprintDialog({ onClose }: { onClose: () => void }) {
  const btn = useRef<HTMLButtonElement>(null);
  useEffect(() => btn.current?.focus(), []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="scrim" onClick={(e) => { e.stopPropagation(); onClose(); }}>
      <section className="alert-sheet imprint" role="dialog" aria-modal="true" aria-labelledby="imprint-title" lang="de"
        onClick={(e) => e.stopPropagation()}>
        <h2 id="imprint-title">Impressum</h2>
        <p className="muted">Offenlegung gemäß § 25 Mediengesetz</p>
        <h5>Medieninhaber und Herausgeber</h5>
        <p>Daniel Buchberger<br />Wien, Österreich</p>
        <h5>Grundlegende Richtung</h5>
        <p>
          Nicht-kommerzielle Demonstration des Prototyps „Graph Anchor“, entstanden beim IBM Responsible AI Hackathon
          (WU Wien &amp; Universität Wien) am 24. Oktober 2026. Die Website zeigt, wie ein kuratierter Wissensgraph
          KI-Antworten nachvollziehbar macht. Die gezeigten Daten dienen ausschließlich Demonstrationszwecken.
        </p>
        <button ref={btn} className="btn imprint-close" onClick={onClose}>Schließen</button>
      </section>
    </div>
  );
}
