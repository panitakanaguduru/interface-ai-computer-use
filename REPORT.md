# Design Report

## 1. Architecture

The system implements a discover-once, replay-many computer-use architecture for a simulated financial institution back-office application.

A natural-language goal is first handled by an LLM-driven discovery agent. The agent observes the current browser state, plans an action, validates that action against safety policy, executes it through Playwright, observes the resulting state, and repeats until the goal is complete or a stopping condition is reached.

The main discovery loop is:

Goal → Observe → Plan → Validate → Safety Check → Execute → Observe → Complete

A successful discovery run is converted into a structured capability artifact. Concrete runtime values, such as a member ID, are replaced with parameters such as `{{member_id}}`. This separates the reusable workflow from the specific discovery example.

Subsequent invocations use the deterministic replay engine rather than the LLM. Replay loads the approved artifact, resolves runtime parameters, executes the recorded browser actions, extracts results from the rendered application, verifies a semantic checkpoint, and returns a structured result.

The implementation is intentionally divided into small components:

- `browser_agent.py` — LLM-driven discovery orchestration

- `observer.py` — browser-state observation

- `planner.py` / `llm_planner.py` — action planning

- `executor.py` — browser action execution

- `action_validator.py` / `safety.py` — policy enforcement

- `artifact_store.py` — capability persistence and lookup

- `replay_engine.py` — deterministic execution

- `error_handler.py` — failure classification and recovery planning

- `intervention_manager.py` — persistent intervention lifecycle

- `session_manager.py` — live-session abstraction

- `run_logger.py` — structured observability

The target is a local MemberOps application backed by synthetic data. It represents the type of internal servicing application that may not expose an integration API.

A customer-facing interface was also implemented as an additional demonstration layer. It can route a customer request to capability discovery or deterministic reuse, but it is not required by the core computer-use architecture.

The primary trade-off was to keep the implementation synchronous and local. This makes the complete control flow easy to inspect and demonstrate while avoiding premature infrastructure such as queues, distributed workers, or multi-tenant orchestration.

## 2. Artifact schema

A successful discovery produces a versioned JSON capability artifact rather than storing or replaying the raw LLM transcript.

The artifact contains:

- artifact identifier and schema version

- creation timestamp

- capability name

- typed runtime inputs

- ordered actions

- parameterized action values

- declared outputs

- success/checkpoint definition

- approval and replayability metadata

For example, a discovery performed with member `10002` does not permanently encode that member into the reusable workflow. The recorded value is transformed into `{{member_id}}`. The same artifact can therefore be invoked with `10003` or another valid member.

This was verified by replaying the same pending-claims capability for multiple members and obtaining different results from the application without rediscovery.

The artifact is deliberately decoupled from the model transcript. Replay therefore depends on an explicit contract rather than model reasoning.

The schema is intended to answer four questions for both a human reviewer and a calling agent:

1. What capability does this artifact provide?

2. What parameters must the caller supply?

3. What deterministic actions will execute?

4. What output and success condition should the caller expect?

Artifacts also contain approval/replayability metadata so that discovery and production execution are separate concepts. In a production implementation, this seam could support review workflows, confidence thresholds, and version promotion.

## 3. Determinism & error handling

Deterministic replay does not invoke the LLM for action decisions.

The replay engine:

1. loads a saved capability,

2. validates required parameters,

3. substitutes runtime values,

4. executes recorded actions in order,

5. waits for the expected application state,

6. extracts output from the rendered browser UI,

7. verifies the semantic checkpoint, and

8. returns a structured result.

For the pending-claims capability, replay verifies that the rendered member matches the requested member and reads claim statuses from the browser DOM. It does not use the database directly to manufacture the answer. This keeps the browser surface as the source of truth for computer-use execution.

The implementation uses explicit timeouts and post-action waits instead of assuming that a click immediately succeeded.

Failures are classified rather than blindly retried. The design distinguishes among successful outcomes, recoverable automation conditions, and hard failures requiring escalation.

A bounded deterministic recovery mechanism is included for known locator failures. For example, if a recorded Search button selector fails, replay may attempt a small set of predefined safe alternatives such as the known button ID or accessible role/name. Recovery is bounded and does not turn into an open-ended LLM loop.

The evidence includes an injected stale-selector failure where deterministic recovery successfully found the known Search control and completed the capability.

A second injected failure forces deterministic recovery to fail. In that case replay stops rather than guessing and creates a human intervention request containing the failed step, attempted action, error, browser state, and recovery information.

The result contract reports whether execution was a normal replay, recovered replay, escalated run, or human-resumed replay. It also records whether an LLM was used.

## 4. Heterogeneity & multi-tenant

The implementation uses Playwright and DOM-based interaction for the concrete demonstration surface, but the capability model is intended to remain separate from the underlying control technology.

A production design would introduce a surface adapter boundary with operations such as observe, locate, act, capture evidence, and verify state. A web adapter could implement those operations using DOM/accessibility information, while a legacy or desktop adapter could use accessibility trees, screenshots and coordinates, OCR where unavoidable, or OS-level automation.

The artifact should describe the logical operation and target strategy without requiring every capability to know how the underlying surface is controlled.

For multi-tenant reuse, I would separate a base capability from tenant/application-specific configuration. A capability could be associated with a vendor/application family and version range, while tenant overrides contain only the locators, routes, or behaviors that differ for that institution.

For example:

Base capability → vendor application/version → tenant-specific overrides

Before unattended execution, the system could fingerprint the application using URL patterns, visible controls, version indicators, and lightweight checkpoints. A compatible fingerprint would allow reuse of the base artifact. A mismatch could select a known override, require validation, or trigger rediscovery rather than silently executing against an unknown surface.

This avoids recording an entirely independent capability for every institution while still allowing controlled specialization where vendor configuration differs.

The current project demonstrates parameter reuse across members rather than implementing full cross-tenant infrastructure. Multi-tenant storage, artifact inheritance, and drift management are intentionally left as design extensions.

## 5. Escalation & handoff

Replay must stop when it cannot safely determine the next action.

When deterministic execution fails and bounded recovery cannot resolve the condition, the system creates a structured intervention record. It includes the capability, runtime parameters, failed step, failed action, reason for stopping, recovery attempt, browser state, and intervention status.

The intervention lifecycle models ownership explicitly:

`waiting_for_human → human_in_control → ready_to_resume → resumed → completed`

The project demonstrates a real same-session handoff.

During the HITL test, a selector failure was injected and deterministic recovery was intentionally forced to fail. Automation paused while the same headed Chromium session remained open. A human took control of that existing browser session, manually performed the required Search action, and signaled completion. Automation then resumed against that same page, executed the semantic checkpoint, extracted the browser result, and completed successfully.

The resumed run remained deterministic; the human resolved the blocked step rather than handing control to an unrestricted LLM.

This is intentionally a minimal operator mechanism rather than a full co-browsing console. In production, the same control-transfer model could sit behind an operator dashboard and dedicated browser worker. A worker-owned session is preferable to moving synchronous Playwright objects across server threads because browser automation objects have thread-affinity constraints.

## 6. Safety

Safety is enforced before execution rather than relying only on prompting the LLM.

The system restricts the permitted action types and target application. Discovery actions pass through validation and safety checks before execution. Replay executes only actions contained in an approved/replayable artifact.

The demonstration focuses on reversible read-oriented actions: entering a synthetic member identifier, searching, and reading account/claim information. Risky or irreversible operations should require stronger policy treatment such as explicit confirmation or human approval before execution.

The project uses synthetic member data and does not require real financial credentials or real customer PII.

Secrets are excluded from source control through `.gitignore`; environment files and virtual environments are not committed. Runtime-generated artifacts are also ignored, while a deliberately curated, synthetic evidence set is stored under `/evidence/`.

Artifacts parameterize invocation-specific values rather than treating raw discovery transcripts as reusable execution plans. Production logging would additionally apply field-level redaction and institution-specific retention policies before persistence.

A key safety principle throughout the implementation is fail closed: if replay cannot identify a permitted deterministic recovery, it stops and escalates rather than allowing unrestricted autonomous exploration.

## 7. Cuts

I deliberately optimized for a small end-to-end vertical slice rather than production-scale infrastructure.

The project does not implement a distributed worker queue, production authentication, real bank connectivity, full multi-tenant artifact inheritance, desktop automation, or a production co-browsing operator console.

The current target application has a usable DOM. Playwright therefore provides the simplest reliable implementation for the concrete surface. A production system targeting hostile legacy applications would add accessibility- and vision-based adapters behind the same surface abstraction.

Human intervention is demonstrated through a minimal headed-browser handoff rather than a separate operator web console. This keeps the control-transfer mechanism real while avoiding UI work that does not materially improve the core assessment.

Recovery is intentionally bounded. I chose deterministic known-safe recovery followed by human escalation rather than an open-ended model fallback. A future extension could add the optional single-step, policy-checked LLM recovery path while preserving strict limits and evidence.

With additional time, the next priorities would be:

- formal JSON Schema or typed models for artifact validation,

- richer expected business outcomes such as member-not-found and permission-denied,

- automated integration tests around discovery/replay contracts,

- a dedicated browser-session worker for remote human intervention,

- screenshot/trace capture for every hard failure,

- capability versioning and approval workflows,

- application fingerprinting and tenant-specific overrides,

- accessibility/vision adapters for legacy and desktop surfaces, and

- multi-run stability metrics.

The intentionally narrow implementation demonstrates the complete core thread: a natural-language goal drives a genuine LLM discovery run against a live UI, the successful workflow becomes a reusable parameterized capability, that capability replays without the LLM, replay verifies its output from the application surface, failures recover or escalate deliberately, and a human can take control of the same live session before returning control to automation.