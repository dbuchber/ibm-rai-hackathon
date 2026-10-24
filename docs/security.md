# Security notes

Scope: the findings of the security review (issue #1). This is a hackathon demo; the list below says what the code
guarantees, what only lowers risk, and what is not covered. It does not claim complete protection against prompt injection.

## Enforced in code

| Property | Where | Test |
|---|---|---|
| Only the approved graph is visible to the engine: edges, **and nodes**. A node exists in an export only if the requested named graph declares it; properties come from the requested graphs only (approved wins over proposed over rejected). | `contracts/rdf_store.py` (`_merge`, `export`, `search`) | `tests/test_node_graphs.py` |
| Traversal follows only approved edges, only predicates the strategy allowed (resolved against the ontology in code), and only edge ids that were actually offered. | `contracts/rdf_store.py` (`neighbors`), `engine/strategy.py`, `engine/traverse.py` | `tests/engine/test_traverse.py` |
| Citations are validated against the walked edges and chunks; unknown ids are dropped. An answer without any valid citation is replaced by the insufficient-evidence answer. | `engine/answer.py` | `tests/engine/test_answer_evidence.py` |
| Curation writes (`POST /api/proposals`, `POST /api/proposals/{id}`) need `X-Reviewer-Code` matching `RAI_REVIEWER_CODES` (constant-time compare). No codes configured = writes closed. A refused request changes no state and costs no write budget. Reads stay open. | `api/main.py` (`reviewer_only`) | `tests/api/test_reviewer_auth.py` |
| Admin reset needs `ADMIN_TOKEN`; live runs need an invite code and are rate limited. | `api/main.py` | `tests/api/test_api.py` |

Canary proposals and the chat canary are an attention check for reviewers, not an authorization control.

## Mitigated (lowers risk, no guarantee)

Indirect prompt injection: any text the models read (document passages, node labels and descriptions, relation
descriptions, the strategy note, the user question) can contain instructions.

* Every LLM call (strategy, traversal, answer, RAG baseline, contradiction proposals in `kg/propose.py`) is built by
  `engine/prompt.py`: trusted instructions only in the system message; all source content in blocks
  `<<<DATA name nonce>>> ... <<<END nonce>>>` with a random per-call nonce. The system message declares block content
  untrusted data, never instructions. Delimiter-like sequences inside source text are neutralised.
* No keyword filter: a legitimate imperative sentence in a SOP ("recalibrate every 6 months, do not exceed 14 A") is
  evidence and reaches the model unchanged (`test_legitimate_maintenance_instruction_is_not_filtered`).
* What an injected instruction can still reach is bounded by code: the model cannot add edges, leave the approved
  graph, cite ids it was not shown, or write to the graph. Worst case it distorts a verdict or the wording of an answer.
* Tests: stub model asserts the prompt structure for injected chunk, node description, predicate description,
  strategy note and question (`tests/engine/test_prompt_injection.py`); one real run with `openai/ibm/granite-4-h-small`
  via ICA (`tests/engine/test_prompt_injection_live.py`, skipped without `ICA_API_KEY`).

## Remaining

* The live run is not stable on a small model: in one of three runs granite partly obeyed the injection ("cite nothing") and the citation guard replaced the answer by the insufficient-evidence text. The test accepts either a grounded answer or that refusal, never the injected one.
* Models may still follow injected text inside a data block, especially small ones. A single passing live run is an
  observation, not a proof. Answers rely on human curation of the graph and on the visible citations.
* A passage that is *approved* but lies (wrong values) is a curation problem, not caught here.
* An approved edge whose endpoint node is not itself approved would still surface that node through `store.node()`;
  curation currently approves edges between existing nodes only, so this needs a future guard if that changes.
* The reviewer code is a shared secret sent in a header: no per-user identity, no audit of who decided. Use HTTPS only.
* The invite/reviewer codes and ICA/gateway keys live in `.env`; rotate after the event.
* Rate limits are per process and per client IP as seen by the proxy.
