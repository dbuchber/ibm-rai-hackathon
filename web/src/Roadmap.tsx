// Pitch step 7. Nothing on this screen runs today; it is labelled "Roadmap" throughout.

type Tier = "S" | "M" | "L";

const LADDER: { tier: Tier; name: string; note: string; width: number }[] = [
  { tier: "L", name: "Mistral Large", note: "Strategy, final answer, escalations", width: 100 },
  { tier: "M", name: "Gemma · Granite", note: "Mid-size fallback, harder verdicts", width: 78 },
  { tier: "S", name: "Ministral 14B", note: "Step verdicts", width: 58 },
  { tier: "S", name: "Ministral 8B", note: "Step verdicts", width: 46 },
  { tier: "S", name: "Ministral 3B", note: "Step verdicts on small frontiers", width: 34 },
];

const TIERS: { tier: Tier; label: string }[] = [
  { tier: "S", label: "Small" }, { tier: "M", label: "Mid" }, { tier: "L", label: "Large" },
];

export default function Roadmap({ steps }: { steps: number }) {
  const tasks: { name: string; to: Tier; from?: Tier; why?: string }[] = [
    { name: "Strategy", to: "L" },
    ...Array.from({ length: steps }, (_, i) => ({ name: `Step ${i + 1} verdicts`, to: "S" as Tier })),
    { name: "Contradiction found", to: "L", from: "S", why: "escalate" },
    { name: "Answer", to: "L" },
  ];
  return (
    <div className="sheet-wrap">
      <section className="sheet glass roadmap" aria-label="Roadmap: local models with routing">
        <div className="sheet-head">
          <div>
            <div className="eyebrow">Next · not running today</div>
            <h2>The smallest model that is good enough, for every step. All on-prem.</h2>
          </div>
          <span className="tag mock">Roadmap</span>
        </div>

        <div className="cols">
          <div className="col">
            <h3>Model ladder</h3>
            <div className="how">Open-weight models of different sizes, running in-house.</div>
            <ol className="ladder">
              {LADDER.map((r) => (
                <li key={r.name}>
                  <div className={"rung t-" + r.tier} style={{ width: `${r.width}%` }}>
                    <span className="rung-name">{r.name}</span>
                  </div>
                  <span className="rung-note">{r.note}</span>
                </li>
              ))}
            </ol>
          </div>

          <div className="col">
            <h3>Router</h3>
            <div className="how">One run of the demo question, task by task.</div>
            <div className="route" role="table" aria-label="Task routing">
              <div className="route-row head" role="row">
                <span role="columnheader">Task</span>
                {TIERS.map((t) => <span key={t.tier} role="columnheader">{t.label}</span>)}
              </div>
              {tasks.map((t, i) => (
                <div className={"route-row" + (t.why ? " esc" : "")} key={i} role="row">
                  <span role="cell">{t.name}</span>
                  {TIERS.map((c) => (
                    <span key={c.tier} role="cell" className="cell">
                      {t.to === c.tier && <i className={"dot" + (t.why ? " esc" : "")} aria-label="routed here" />}
                      {t.from === c.tier && <i className="dot from" aria-label="escalated from here" />}
                    </span>
                  ))}
                </div>
              ))}
            </div>
            <ul className="rules">
              <li><b>Many small calls go small.</b> Per-step verdicts on a short frontier.</li>
              <li><b>Planning and answering go large.</b> Strategy and the final cited answer.</li>
              <li><b>Doubt goes up.</b> A contradiction or low confidence escalates to a larger model.</li>
            </ul>
          </div>
        </div>

        <div className="benefits">
          <div className="benefit">
            <h4>Sovereignty</h4>
            <p>Company data and the graph never leave the plant network.</p>
          </div>
          <div className="benefit">
            <h4>Cost and latency</h4>
            <p>Most calls are step verdicts, and those run on the smallest models.</p>
          </div>
          <div className="benefit">
            <h4>One config switch</h4>
            <p>Every call goes through LiteLLM, so IBM watsonx / Granite is a config change.</p>
            <code>model: watsonx/&lt;granite-model&gt;</code>
          </div>
        </div>
        <div className="foot">Today every call runs on one model (gemma-4-31b) through a LiteLLM gateway.</div>
      </section>
    </div>
  );
}
