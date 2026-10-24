// Pitch step 7. Nothing on this screen runs today; it is labelled "Roadmap" throughout.

type Tier = "S" | "M" | "L";

const LADDER: { tier: Tier; name: string; note: string; width: number }[] = [
  { tier: "L", name: "Mistral Large", note: "Strategy, final answer, escalations", width: 100 },
  { tier: "M", name: "Gemma · Granite", note: "Mid-size fallback, harder verdicts", width: 78 },
  { tier: "S", name: "Ministral 14B", note: "Step verdicts", width: 58 },
  { tier: "S", name: "Ministral 8B", note: "Step verdicts", width: 46 },
  { tier: "S", name: "Ministral 3B", note: "Step verdicts on small frontiers", width: 34 },
];

// Systems of record feed the graph directly; AI extractions and links still wait for approval.
const SYSTEMS: { name: string; text: string }[] = [
  { name: "MES", text: "Live machine states, alarms and orders from the shop floor instead of a CSV export." },
  { name: "ERP", text: "Orders, materials and suppliers from the system of record instead of a hand-kept file." },
  { name: "IBM Maximo / SAP PM", text: "Maintenance plans, work orders and spare parts linked to the stations they belong to." },
  { name: "Document ingestion", text: "Any PDF, SOP or datasheet: parsed, chunked and linked, with its version and validity." },
  { name: "SharePoint", text: "Existing document libraries indexed in place, permissions respected." },
  { name: "Jira", text: "Maintenance tickets and incidents as evidence: what broke, what was done." },
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
      <section className="sheet glass roadmap" aria-label="Roadmap">
        <div className="sheet-head">
          <div>
            <div className="eyebrow">Next · not running today</div>
            <h2>Right-sized models, guarded and access-aware.</h2>
          </div>
          <span className="tag mock">Roadmap</span>
        </div>

        <h5 className="group">Models and routing · all on-prem</h5>
        <div className="cols">
          <div className="col">
            <h3>Model ladder</h3>
            <div className="how">Open-weight models of different sizes, running in-house.</div>
            <ol className="ladder">
              {LADDER.map((r) => (
                <li key={r.name}>
                  <div className={"rung t-" + r.tier} style={{ width: `${r.width * 0.58}%` }}>
                    <span className="rung-name">{r.name}</span>
                  </div>
                  <span className="rung-note">{r.note}</span>
                </li>
              ))}
            </ol>
            <ul className="perks">
              <li><b>Sovereignty.</b> Data and graph stay in the plant network.</li>
              <li><b>Cost and latency.</b> Most calls are step verdicts on small models.</li>
              <li><b>One config switch.</b> LiteLLM makes IBM watsonx / Granite a config change: <code>model: watsonx/&lt;granite-model&gt;</code></li>
            </ul>
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

        <h5 className="group">Connected to your systems</h5>
        <p className="group-note">Systems of record feed the graph directly. Anything an AI extracts or links waits for human approval.</p>
        <div className="tiles three">
          {SYSTEMS.map((x) => (
            <div className="tile" key={x.name}>
              <h4>{x.name}</h4>
              <p>{x.text}</p>
            </div>
          ))}
        </div>

        <h5 className="group">Trust and reach</h5>
        <div className="tiles three">
          <div className="tile">
            <h4>Guardrails</h4>
            <p>Checks on input and output, e.g. IBM Granite Guardian.</p>
            <div className="chips">
              <span className="chip">Prompt injection</span><span className="chip">PII</span><span className="chip">Ungrounded claims</span>
            </div>
          </div>
          <div className="tile">
            <h4>Feedback loop</h4>
            <p>Thumbs and corrections in the chat flow back as proposals.</p>
            <Chain items={["Correction", "Proposal", "Analyst review"]} />
          </div>
          <div className="tile">
            <h4>Forward navigation</h4>
            <p>From a citation to the passage to the record in DMS, ERP or SharePoint.</p>
            <Chain items={["Citation", "Chunk", "Source system"]} />
          </div>
          <div className="tile">
            <h4>Access control</h4>
            <p>Seed search and traversal only see what the user may see.</p>
            <dl className="acl">
              <dt>Vectors</dt><dd>payload filter on chunks</dd>
              <dt>Graph</dt><dd>node and graph ACLs</dd>
            </dl>
          </div>
          <div className="tile">
            <h4>Versions and validity</h4>
            <p>Which SOP applies to which station, from when. A new version flags every fact it touches for re-approval.</p>
          </div>
          <div className="tile">
            <h4>Measured quality</h4>
            <p>A fixed question set runs on every change: correctness, faithfulness to sources, graph vs. plain vector search.</p>
          </div>
        </div>
        <div className="foot">Today: one model per run (Mistral Large 4, or Granite 4 H Small via IBM ICA) through a LiteLLM gateway, no guardrails, no ACLs; company data comes from CSV and YAML files.</div>
      </section>
    </div>
  );
}

function Chain({ items }: { items: string[] }) {
  return (
    <div className="chain">
      {items.map((x, i) => (
        <span key={x}>{i > 0 && <span className="arrow" aria-hidden="true">→</span>}<span className="chip">{x}</span></span>
      ))}
    </div>
  );
}
