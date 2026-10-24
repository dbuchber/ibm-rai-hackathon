// Canaries against automation bias (spec: "Canaries"). Static mode runs this in the browser; in api
// mode the server does the same and the UI only reads `alert` and GET /api/audit.
import type { AuditEntry, CanaryAlert, GraphExport, Proposal } from "./contracts";
import { ONT, proposalId } from "./ids";

export const STREAK = 4;
const FAST_MS = 3000;
export const SUPERVISOR = "Quality lead (mock)";

const now = () => new Date().toISOString();

/** Browser-side audit log: static-mode curation and the chat canary (always a click mock) write here. */
export const localAudit: AuditEntry[] = [];
export function audit(kind: AuditEntry["kind"], detail: string, proposal_id: string | null = null) {
  localAudit.unshift({ ts: now(), kind, proposal_id, detail });
}

// Obviously false on a second look: a class that cannot play that role (a customer as supplier).
const TEMPLATES = [
  {
    s: "Station", p: "supplied_by", o: "Customer",
    rationale: "The supplier quality agreement lists this company as the source of the station's sealing equipment.",
    quote: "Supplier of record for sealing equipment and spare parts.",
  },
  {
    s: "SensorModel", p: "supplied_by", o: "Customer",
    rationale: "The purchase history names this company as the vendor of the sensor model.",
    quote: "Delivered and invoiced by the vendor listed below.",
  },
];

export class CanaryEngine {
  private streak = 0;
  private times: number[] = [];
  private last = Date.now();
  private sinceLastPass: string[] = [];
  private canaries = new Set<string>();
  private open: string | null = null;
  private used = 0;

  constructor(private graph: () => Promise<GraphExport>) {}

  private due() {
    const recent = this.times.slice(-STREAK);
    const fast = recent.length >= STREAK && recent.reduce((a, b) => a + b, 0) / recent.length < FAST_MS;
    return !this.open && (this.streak >= STREAK || fast);
  }

  /** Called by listProposals: maybe plants one canary among the first three open items. */
  async plant(list: Proposal[]): Promise<Proposal[]> {
    if (!this.due()) return list;
    const g = await this.graph();
    const t = TEMPLATES[this.used % TEMPLATES.length];
    const s = g.nodes.filter((n) => n.cls === t.s)[this.used % 3] ?? g.nodes.find((n) => n.cls === t.s);
    const o = g.nodes.find((n) => n.cls === t.o);
    if (!s || !o) return list;
    this.used++;
    const triple = { s: s.id, p: ONT + t.p, o: o.id };
    const c: Proposal = {
      kind: "edge", triple, id: proposalId("edge", { triple: [triple.s, triple.p, triple.o] }),
      rationale: t.rationale, quote: t.quote, evidence_chunk_id: null, confidence: 0.87,
      proposed_by: "llm:openai/mistral-large-4-openrouter", status: "proposed",
    };
    this.canaries.add(c.id);
    this.open = c.id;
    audit("canary_planted", `Test proposal planted after ${this.streak} approvals in a row.`, c.id);
    const openIdx = list.map((p, i) => [p, i] as const).filter(([p]) => p.status === "proposed").map(([, i]) => i);
    const at = openIdx[Math.min(1, openIdx.length - 1)] ?? 0;
    return [...list.slice(0, at), c, ...list.slice(at)];
  }

  /** Returns the decided proposal (with `alert` on a failed canary) and ids to revert. */
  decide(p: Proposal, decision: "approve" | "reject" | "flag", all: Proposal[]): Proposal {
    const t = Date.now();
    this.times.push(t - this.last);
    this.last = t;
    if (this.canaries.has(p.id)) {
      this.open = null;
      this.streak = 0;
      this.times = [];
      if (decision !== "approve") {
        audit("canary_passed", "Test proposal caught and " + (decision === "flag" ? "flagged." : "rejected."), p.id);
        this.sinceLastPass = [];
        return { ...p, status: "rejected" };
      }
      const reverted = this.sinceLastPass.filter((id) => all.find((x) => x.id === id)?.status === "approved");
      this.sinceLastPass = [];
      audit("canary_failed", "A planted false proposal was approved. It was not written to the graph.", p.id);
      reverted.forEach((id) => audit("reverted", "Approval reverted to proposed for a second look.", id));
      audit("supervisor_notified", `${SUPERVISOR} notified.`);
      const alert: CanaryAlert = {
        message: "You approved a planted test proposal. It is false and was not written to the graph.",
        reverted,
        supervisor_notified: SUPERVISOR,
      };
      return { ...p, status: "rejected", alert };
    }
    if (decision === "approve") {
      this.streak++;
      this.sinceLastPass.push(p.id);
    } else {
      this.streak = 0;
    }
    audit("decision", `${decision === "approve" ? "Approved" : decision === "flag" ? "Flagged" : "Rejected"}.`, p.id);
    return { ...p, status: decision === "approve" ? "approved" : "rejected" };
  }
}
