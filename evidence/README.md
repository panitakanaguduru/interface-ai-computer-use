# MemberOps Agent — Evidence

This directory contains reproducible evidence for the discovery, artifact, deterministic replay, recovery, safety escalation, generalization, and human-in-the-loop behavior of the MemberOps browser agent.

## Architecture

Natural-language task
→ LLM-guided discovery
→ structured capability artifact
→ deterministic replay (no LLM)
→ semantic browser-DOM verification
→ bounded recovery
→ safe escalation / human intervention when required

## Evidence

### `discovery_run.jsonl`
Original discovery run that produced the reusable `pending_claims_lookup` capability.

The LLM is used during discovery to determine browser actions.

### `pending_claims_capability.json`
Structured capability artifact produced from discovery.

The recorded workflow is parameterized by `member_id` so it can be reused for different members.

### `deterministic_replay_10002.txt`
Normal deterministic replay for member `10002`.

Result:
- Replay succeeded
- 2 pending claims
- Result verified from rendered browser DOM
- No recovery required
- No human intervention
- LLM used: false

### `deterministic_replay_10003.txt`
Same capability replayed for member `10003`.

Result:
- Replay succeeded
- 0 pending claims
- Result verified from rendered browser DOM
- LLM used: false

This demonstrates parameterized capability reuse rather than a workflow hardcoded to one member.

### `deterministic_recovery.txt`
A stale selector is intentionally injected at replay step 2.

Result:
- Recorded action fails
- Bounded deterministic recovery runs
- Known safe selector is found
- Replay completes successfully
- Semantic DOM checkpoint passes
- No human intervention
- LLM used: false

### `safe_escalation.txt`
The same selector failure is injected, but deterministic recovery is intentionally forced to fail.

Result:
- Replay does not continue blindly
- Execution stops safely
- Mode becomes `escalated`
- Human review is required
- LLM used: false

### `hitl_recovery_resume.txt`
End-to-end human-in-the-loop recovery demonstration.

Result:
- Recorded action fails
- Deterministic recovery fails
- Human intervention is created
- The same live Chromium session remains open
- Human completes the failed action
- Deterministic replay resumes
- Browser-DOM semantic checkpoint succeeds
- Intervention reaches `completed`
- LLM used: false

## Key Design Principle

The LLM is used to discover a capability, not to repeatedly execute a known workflow.

Once a capability has been recorded, replay is deterministic and policy-bounded. Browser output is verified from the rendered UI rather than trusted from an internal database response.

When deterministic execution cannot safely continue, the system either escalates for human review or transfers the live browser session to a human and resumes afterward.
