# MemberOps — Discover Once, Replay Deterministically

MemberOps is a browser-based computer-use agent that learns a workflow from an LLM-guided discovery run, saves that workflow as a structured capability artifact, and replays it deterministically without calling the LLM again.

The project demonstrates:

- LLM-guided browser workflow discovery
- Structured, parameterized capability artifacts
- Deterministic browser replay
- Browser-DOM result verification
- Bounded deterministic recovery
- Safe failure and escalation
- Human-in-the-loop browser takeover and resume
- Reuse of one learned capability across different runtime inputs

---

## Core Idea

Instead of asking an LLM to reason through the same browser workflow every time:

```text
Natural-language task
        |
        v
+-------------------+
| LLM Discovery     |
| Observe / Plan    |
| Validate / Act    |
+-------------------+
        |
        v
+-------------------+
| Capability        |
| Artifact          |
+-------------------+
        |
        v
+-------------------+
| Deterministic     |
| Replay            |
| LLM = OFF         |
+-------------------+
        |
        v
+-------------------+
| Browser DOM       |
| Verification      |
+-------------------+
```

The LLM is used for **discovery**.

Once the workflow has been learned, normal execution uses the saved artifact and deterministic browser actions.

---

## Example Capability

The included evidence demonstrates:

```text
pending_claims_lookup
```

Example request:

```text
How many pending claims do I have?
```

The discovered workflow is approximately:

```text
1. Fill the Member ID input
2. Click Search member
3. Wait for the member record to render
4. Read claim statuses from the browser DOM
5. Count claims with status "Pending"
6. Verify the semantic result
```

The saved workflow parameterizes the member identifier:

```text
{{member_id}}
```

so the same capability can be replayed for different members.

---

## Discovery vs Replay

### Discovery

During discovery the browser agent follows an iterative loop:

```text
Observe
   ↓
LLM Plan
   ↓
Validate
   ↓
Safety Check
   ↓
Execute
   ↓
Record Action
   ↓
Observe Again
```

Successful browser actions are converted into a structured capability artifact.

### Replay

Replay does not ask the LLM to rediscover the workflow.

```text
Load artifact
    ↓
Resolve runtime parameters
    ↓
Execute recorded actions
    ↓
Wait for browser result
    ↓
Capture DOM evidence
    ↓
Run semantic checkpoint
```

Replay results explicitly report:

```json
"llm_used": false
```

---

## Parameterized Generalization

A discovered capability is not tied to the member used during discovery.

For example, the same artifact was replayed for:

```text
Member 10002 → 2 pending claims
Member 10003 → 0 pending claims
```

Both results were extracted from the rendered browser DOM using the same saved capability.

---

## Browser-DOM Verification

Replay does not treat an internal database response as proof that the browser workflow succeeded.

The replay engine verifies the rendered UI.

For the pending-claims capability it checks information such as:

```text
Rendered member ID
Claims container presence
Claim status elements
Pending claim count
```

Example replay output:

```json
{
  "member_id": "10002",
  "claim_statuses": [
    "Pending",
    "Pending",
    "Approved"
  ],
  "total_claims": 3,
  "pending_claim_count": 2,
  "source": "browser_dom"
}
```

This separates:

```text
Action executed
```

from:

```text
Business outcome verified
```

---

## Deterministic Recovery

Recorded browser selectors can become stale.

When an action fails, replay performs a bounded recovery attempt using known deterministic strategies.

Example tested failure:

```text
Recorded selector:
#search-button-broken
```

Replay detects the timeout and attempts a safe known alternative:

```text
#search-button
```

Successful recovery produces:

```json
{
  "mode": "recovered_replay",
  "recovery_attempted": true,
  "recovery_succeeded": true,
  "llm_used": false
}
```

The LLM is not invoked for deterministic recovery.

---

## Safe Escalation

If the recorded action fails and bounded recovery also fails, replay does not blindly continue.

It stops and returns a structured escalation:

```json
{
  "success": false,
  "mode": "escalated",
  "recovery_attempted": true,
  "recovery_succeeded": false,
  "human_escalation": {
    "required": true,
    "status": "human_review_required"
  },
  "llm_used": false
}
```

This creates a clear boundary between deterministic automation and actions requiring human review.

---

## Human-in-the-Loop Recovery

MemberOps also supports live human intervention.

If deterministic recovery fails:

```text
Recorded action fails
        ↓
Deterministic recovery attempted
        ↓
Recovery fails
        ↓
Human intervention created
        ↓
Same Chromium session remains open
        ↓
Human completes failed action
        ↓
Replay resumes
        ↓
Semantic DOM checkpoint
        ↓
Completed
```

A successful HITL run produces:

```json
{
  "success": true,
  "mode": "human_resumed_replay",
  "human_intervention": {
    "used": true,
    "transferred": true,
    "resumed": true
  },
  "intervention_status": "completed",
  "llm_used": false
}
```

The important property is that the human completes the failed action in the **same live browser session** before deterministic execution resumes.

---

## Project Structure

```text
interface-ai-computer-use/
├── backend/
│   ├── server.py
│   └── seed_database.py
│
├── demo_app/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── customer_app/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── src/
│   └── agent/
│       ├── browser_agent.py
│       ├── observer.py
│       ├── planner.py
│       ├── llm_planner.py
│       ├── executor.py
│       ├── action_validator.py
│       ├── action_history.py
│       ├── loop_guard.py
│       ├── safety.py
│       ├── run_logger.py
│       ├── error_handler.py
│       ├── result_reporter.py
│       ├── artifact_store.py
│       ├── replay_engine.py
│       ├── intervention_manager.py
│       └── session_manager.py
│
├── artifacts/
├── evidence/
├── data/
└── README.md
```

---

## Running the Project

### 1. Activate the environment

```bash
source .venv/bin/activate
```

### 2. Configure the OpenAI API key

Discovery requires an OpenAI API key.

```bash
export OPENAI_API_KEY="YOUR_KEY"
```

Do not commit API keys to the repository.

### 3. Seed the demo database

```bash
python backend/seed_database.py
```

### 4. Start the local server

```bash
python backend/server.py
```

The application runs at:

```text
http://localhost:8000
```

Customer experience:

```text
http://localhost:8000/customer/
```

### 5. Check server health

```bash
curl http://localhost:8000/api/health
```

Expected:

```json
{
  "status": "ok",
  "service": "MemberOps Agent API"
}
```

---

## Run Discovery

Start the browser agent:

```bash
python src/agent/browser_agent.py
```

A successful discovery run can produce a reusable capability artifact under:

```text
artifacts/
```

---

## Run Deterministic Replay

Example:

```bash
python src/agent/replay_engine.py \
  artifact_20261004_231554_044486 \
  --member-id 10002
```

Expected characteristics:

```text
success = true
mode = replay
pending_claim_count = 2
source = browser_dom
llm_used = false
```

---

## Test Cross-Member Reuse

```bash
python src/agent/replay_engine.py \
  artifact_20261004_231554_044486 \
  --member-id 10003
```

The same saved capability executes with a different runtime member ID.

---

## Test Deterministic Recovery

Inject a stale selector during replay:

```bash
python src/agent/replay_engine.py \
  artifact_20261004_231554_044486 \
  --member-id 10002 \
  --simulate-selector-failure-step 2
```

Expected:

```text
mode = recovered_replay
recovery_attempted = true
recovery_succeeded = true
llm_used = false
```

---

## Test Safe Escalation

Force deterministic recovery to fail:

```bash
python src/agent/replay_engine.py \
  artifact_20261004_231554_044486 \
  --member-id 10002 \
  --simulate-selector-failure-step 2 \
  --force-recovery-failure
```

Expected:

```text
success = false
mode = escalated
human_review_required
llm_used = false
```

This failure is intentional.

---

## Test Human Intervention and Resume

Run:

```bash
python src/agent/replay_engine.py \
  artifact_20261004_231554_044486 \
  --member-id 10002 \
  --simulate-selector-failure-step 2 \
  --force-recovery-failure \
  --human-intervention \
  --headed
```

When the terminal displays:

```text
HUMAN INTERVENTION REQUIRED
```

use the same Chromium window to manually click:

```text
Search member
```

Wait for the member information and claims to load, return to the terminal, and press Enter.

Expected:

```text
mode = human_resumed_replay
transferred = true
resumed = true
intervention_status = completed
llm_used = false
```

---

## Evidence

Reproducible evidence is stored under:

```text
evidence/
```

Included evidence:

```text
README.md
discovery_run.jsonl
pending_claims_capability.json
deterministic_replay_10002.txt
deterministic_replay_10003.txt
deterministic_recovery.txt
safe_escalation.txt
hitl_recovery_resume.txt
```

See:

```text
evidence/README.md
```

for a description of what each file demonstrates.

---

## Safety Model

The system deliberately separates discovery from execution.

During discovery:

```text
LLM proposes action
→ action validation
→ safety policy
→ browser execution
```

During replay:

```text
Saved action
→ parameter resolution
→ deterministic execution
→ bounded recovery
→ semantic verification
```

If safe deterministic execution cannot continue:

```text
Stop
→ escalate
→ human review/intervention
```

Replay does not silently fall back to unrestricted LLM control.

---

## Design Trade-Offs

This project intentionally favors a small, inspectable replay contract over a fully autonomous browser agent.

The goal is not to claim that arbitrary websites can always be recovered automatically.

Instead, the system demonstrates a bounded architecture where:

- LLM reasoning discovers workflows.
- Successful workflows become inspectable artifacts.
- Known workflows replay without LLM reasoning.
- Runtime inputs are parameterized.
- Browser outcomes are semantically verified.
- Recovery is bounded and observable.
- Unsafe or unresolved states stop execution.
- Humans can take over and return control.

This keeps execution behavior easier to audit, reproduce, and reason about.

---

## Demo Data

The local synthetic database contains:

```text
100 members
120 accounts
928 transactions
249 claims
```

Demo member IDs range from:

```text
10001 through 10100
```

The data is synthetic and intended only for demonstrating the agent workflow.

---

## Current Scope

This is a demonstration system, not a production deployment.

Production hardening would additionally require areas such as:

- authenticated user/session identity
- stronger authorization boundaries
- persistent distributed browser sessions
- secrets management
- production observability
- concurrency controls
- expanded policy enforcement
- artifact versioning and migration
- broader automated testing

The current implementation focuses on demonstrating the discovery-to-artifact-to-deterministic-replay architecture and its failure-handling contract.
