# Thurbox Extension: Debate + Adversarial Loop

Build a Thurbox extension with two distinct workflows:

```text
1. debate
2. adversarial
```

They may share infrastructure, agent adapters, state persistence, reporting, worktree helpers, and UI components, but they are separate product features with different semantics.

Do not implement them as aliases for the same workflow.

---

# 1. Feature: Debate

## Purpose

`debate` is for architectural, technical, design, planning, implementation-strategy, and decision-making questions.

It is not primarily a code-writing workflow.

Two agents independently form positions, inspect the available project context if relevant, challenge each other's claims, and converge on a final decision or clearly unresolved disagreement.

Examples:

```bash
thurbox debate "Should this service use LangGraph or a deterministic state machine?"

thurbox debate "Should we use Postgres or Firestore for this workload?"

thurbox debate "Review the proposed auth architecture."

thurbox debate "What is the safest migration strategy for this API?"
```

Default participants:

```text
Agent A: Claude
Agent B: Codex
```

Do not hardcode the orchestration to those model names.

---

## Debate principle

The agents should not simply chat freely.

Use structured rounds:

```text
QUESTION
   ↓
INDEPENDENT POSITIONS
   ↓
CROSS-EXAMINATION
   ↓
REBUTTAL
   ↓
FINAL POSITIONS
   ↓
SYNTHESIS
```

The most important property is that the initial positions are independent.

Agent B must not see Agent A's initial reasoning before producing its own initial position, and vice versa.

This prevents anchoring.

---

## Debate lifecycle

Suggested states:

```text
INITIALIZED
    ↓
POSITIONING
    ↓
POSITIONS_COMPLETE
    ↓
CROSS_EXAMINATION
    ↓
REBUTTAL
    ↓
FINAL_POSITIONS
    ↓
SYNTHESIS
    ↓
COMPLETE
```

The exact implementation may be adapted to Thurbox conventions.

Use explicit state transitions.

---

## Debate round 1: Independent positions

Both agents receive:

```text
- original question
- user-provided constraints
- relevant repository/project context
- explicit decision criteria
```

They do not receive each other's answer.

Each agent produces:

```text
POSITION
RECOMMENDATION
KEY ARGUMENTS
ASSUMPTIONS
RISKS
WHAT WOULD CHANGE MY MIND
```

Example:

```markdown
## Claude Initial Position

### Recommendation

Use a deterministic Python state machine.

### Arguments

1. The workflow has a small fixed state space.
2. LangGraph adds runtime and conceptual complexity.
3. State persistence can be implemented directly.

### Assumptions

- No dynamic agent graph is required.
- Workflow transitions remain bounded.

### Risks

...

### What would change my mind

If runtime graph mutation or complex checkpoint branching becomes necessary.
```

---

## Debate round 2: Cross-examination

After both independent positions exist, expose them to the opposite agent.

Each agent should challenge the other.

Prompt principles:

```text
Do not merely summarize the opposing position.

Identify:
- unsupported assumptions
- factual errors
- missing constraints
- architectural weaknesses
- unnecessary complexity
- underestimated risks
- better ideas in the opposing proposal
- evidence that would falsify the opposing proposal
```

The output should be structured as claims.

Example:

```markdown
## Codex Cross-Examination

### D-001

Claim:
Claude underestimates the value of checkpoint persistence.

Evidence:
...

Impact:
...

Question:
How would the proposed state machine recover midway through a long-running tool operation?
```

---

## Debate round 3: Rebuttal

Each agent responds to the challenges directed at it.

For every material challenge, use:

```text
ACCEPT
REJECT
PARTIALLY_ACCEPT
```

Example:

```markdown
### Response to D-001

Decision: PARTIALLY_ACCEPT

Reason:
Checkpointing is necessary, but it does not require LangGraph.

Updated position:
Use persisted state transitions in SQLite/Postgres.
```

The purpose is not to force agreement.

Changing one's position should be treated as valid.

---

## Debate round 4: Final positions

Each agent produces a concise final position after seeing:

```text
- both initial positions
- both critiques
- both rebuttals
```

Each final position should include:

```text
FINAL RECOMMENDATION
STRONGEST SUPPORTING ARGUMENT
BIGGEST REMAINING RISK
CONFIDENCE
```

---

## Debate synthesis

Generate a standard output document:

```text
DEBATE_REPORT.md
```

It should contain:

```markdown
# Debate Report

## Question

...

## Context

...

## Decision Criteria

...

## Claude Initial Position

...

## Codex Initial Position

...

## Cross-Examination

...

## Rebuttals

...

## Final Positions

### Claude

...

### Codex

...

## Agreements

...

## Disagreements

...

## Recommended Decision

...

## Why

...

## Remaining Risks

...

## Open Questions

...
```

Do not hide disagreements.

If both agents agree, report consensus.

If they remain materially split, report:

```text
OUTCOME: UNRESOLVED
```

and clearly describe what evidence or experiment would resolve the disagreement.

---

## Debate synthesis strategy

Do not use a third LLM judge in v0.1 unless necessary.

Prefer deterministic synthesis based on the two final positions.

If one agent materially changes position and consensus emerges, report that.

If disagreement remains, do not pretend there is consensus.

Optionally let one designated synthesizer produce prose, but preserve both final positions verbatim enough to prevent the synthesis from misrepresenting them.

---

## Debate storage

Use something like:

```text
.thurbox/debate/<id>/
├── state.json
├── question.md
├── claude-position.md
├── codex-position.md
├── cross-examination.md
├── rebuttals.md
└── DEBATE_REPORT.md
```

The exact paths may follow Thurbox extension conventions.

---

## Debate termination

Debate is bounded.

For v0.1 use exactly:

```text
1 independent-position round
1 cross-examination round
1 rebuttal round
1 final-position round
```

Do not let agents argue indefinitely.

Future versions may support:

```bash
--rounds 2
```

but v0.1 should remain deterministic.

---

# 2. Feature: Adversarial Loop

## Purpose

`adversarial` is an implementation workflow.

One agent owns implementation.

Another agent acts as an adversarial reviewer whose job is to break the implementation.

Default roles:

```text
Builder: Claude
Adversary: Codex
```

Example:

```bash
thurbox adversarial "Implement refresh-token rotation"
```

The conceptual loop is:

```text
Claude builds
    ↓
Codex attacks
    ↓
issues?
 ┌──┴───┐
no      yes
│        │
DONE   Claude repairs
         ↓
      Codex attacks again
         ↓
        ...
```

The normal semantic termination condition is:

```text
Codex is satisfied.
```

But there must still be a hard safety limit.

---

# Adversarial lifecycle

Suggested states:

```text
INITIALIZED
    ↓
BUILDING
    ↓
ATTACKING
    ↓
┌───────────────┐
│ SATISFIED     │ → COMPLETE
└───────────────┘

or

CHANGES_REQUIRED
    ↓
REPAIRING
    ↓
ATTACKING
    ↓
...
```

Additional terminal states:

```text
BLOCKED
MAX_ROUNDS_REACHED
FAILED
```

---

# Independence of first attack

This is important.

For its first review, Codex should receive:

```text
- original task
- repository
- resulting git diff
- tests/check results
```

It should not initially receive Claude's defence or detailed explanation of why the implementation is correct.

The goal is an independent adversarial inspection.

After the first attack, both agents may use the shared engineering log.

---

# Builder behavior

Claude owns implementation.

Builder instructions:

```text
- inspect project conventions
- implement the requested change
- avoid unnecessary refactoring
- add appropriate tests
- run relevant checks
- do not claim completion when required checks fail
- record implementation assumptions
```

Claude may modify source files.

---

# Adversary behavior

Codex should try to falsify the implementation.

Its instruction should be conceptually:

```text
Assume the implementation may contain subtle defects.

Your job is not to approve the implementation.

Try to find a material reason it should not be accepted.

Inspect:
- correctness
- regressions
- edge cases
- race conditions
- security
- error handling
- state consistency
- resource management
- validation
- API compatibility
- performance regressions
- test gaps
- hidden assumptions

Do not complain about style merely because you would have implemented it differently.

Prefer evidence over opinion.
```

Codex should inspect actual code and run relevant tests/checks.

---

# Adversary verdict

Every Codex attack must terminate with exactly one:

```text
VERDICT: SATISFIED
VERDICT: CHANGES_REQUIRED
VERDICT: BLOCKED
```

Meaning:

### SATISFIED

No remaining material defect was found.

This ends the loop successfully.

### CHANGES_REQUIRED

At least one material actionable issue remains.

Claude receives another turn.

### BLOCKED

Codex cannot make a responsible determination because required information or infrastructure is unavailable.

Examples:

```text
- credentials missing
- external service unavailable
- specification is ambiguous
- baseline tests are already irreparably broken
```

Stop and return control to the human.

---

# Shared engineering log

Use one human-readable document:

```text
ADVERSARIAL_LOG.md
```

Do not call this a chain-of-thought or reasoning log.

It is an engineering decision/evidence log.

It records:

```text
CLAIM
EVIDENCE
DECISION
ACTION
RESULT
```

Example:

```markdown
# Adversarial Engineering Log

## Task

Implement refresh-token rotation.

---

## Initial Build — Claude

### Changes

- Added TokenManager
- Added refresh-token rotation
- Added expiry tests

### Validation

pytest: PASS
ruff: PASS

### Assumptions

- Refresh tokens are single-use.
- Concurrent refresh calls are possible.

---

## Attack 1 — Codex

### C-001 — HIGH — Concurrency

Claim:
Concurrent callers may trigger duplicate upstream refreshes.

Evidence:
Expiry is checked before the refresh lock.

Reproduction:
Start 20 concurrent calls to refresh_if_needed().

Expected:
One provider refresh.

Observed:
Multiple refreshes.

Status:
OPEN

### Verdict

CHANGES_REQUIRED

---

## Repair 1 — Claude

### C-001

Decision:
ACCEPTED

Action:
Moved the expiry check inside the lock.

Added:
test_concurrent_refresh_single_provider_call

Validation:
pytest: PASS

---

## Attack 2 — Codex

### C-001

Status:
RESOLVED

Evidence:
Regression test passes and the expiry check is now protected.

### New Findings

None.

### Verdict

SATISFIED
```

---

# Claude response to findings

Claude must address each material Codex finding.

Allowed decisions:

```text
ACCEPTED
REJECTED
PARTIALLY_ACCEPTED
```

For rejected findings Claude must provide evidence.

Example:

```markdown
### C-002

Decision:
REJECTED

Reason:
The API contract explicitly allows duplicate reads.

Evidence:
tests/contracts/test_refresh.py::test_duplicate_read_allowed
```

Codex evaluates this in the next attack.

---

# Codex attacks again — not just verifies

Do not prompt Codex merely with:

```text
Verify Claude fixed the issue.
```

Instead:

```text
Re-evaluate the current implementation adversarially.

Check:
- whether previous findings are actually resolved
- whether rejected findings were validly rejected
- whether the repairs introduced regressions
- whether additional defects are now visible

Your goal remains to find a material reason not to accept the implementation.
```

This avoids rubber-stamping.

---

# Stop conditions

Normal:

```text
Codex returns SATISFIED
```

Abnormal:

```text
Codex returns BLOCKED
```

Safety:

```text
MAX_ROUNDS reached
```

Also stop if the orchestrator detects no meaningful progress across repeated rounds.

Default:

```text
MAX_ROUNDS = 5
```

Make it configurable:

```bash
thurbox adversarial \
    --max-rounds 3 \
    "Implement refresh-token rotation"
```

Typical successful runs should finish in 1–3 attacks.

---

# Objective checks

The adversarial workflow should support repository-defined checks.

Examples:

```text
pytest
ruff
mypy
vitest
eslint
cargo test
go test
```

Do not hardcode Python.

Support explicit configuration:

```toml
[adversarial.checks]
commands = [
    "uv run pytest",
    "uv run ruff check .",
    "uv run mypy src"
]
```

Auto-detection may be added carefully.

Objective failures outrank model claims.

If Claude claims a finding is invalid but Codex demonstrates a reproducible failure, surface the failure prominently.

---

# Worktree behavior

Adversarial mode should use an isolated worktree if Thurbox provides that capability.

Desired model:

```text
main
 │
 └── adversarial/<run-id>
         │
         ├── Claude modifies
         └── Codex inspects
```

Never modify the user's main branch automatically.

Never auto-merge.

Preserve the worktree at completion.

Show the user:

```text
branch
worktree path
final commit
```

if applicable.

---

# Standard adversarial output

Generate:

```text
ADVERSARIAL_REPORT.md
```

Structure:

```markdown
# Adversarial Engineering Report

## Task

...

## Outcome

PASS

## Builder

Claude

## Adversarial Reviewer

Codex

## Rounds

2

## Final Codex Verdict

SATISFIED

## Validation

| Check | Result |
|---|---|
| Tests | PASS |
| Lint | PASS |
| Types | PASS |

## Findings

### C-001

Severity:
HIGH

Issue:
...

Resolution:
...

Result:
RESOLVED

## Rejected Findings

...

## Remaining Issues

None.

## Changed Files

...

## Worktree

...

## Full Engineering Log

See ADVERSARIAL_LOG.md
```

Possible outcomes:

```text
PASS
PASS_WITH_WARNINGS
BLOCKED
MAX_ROUNDS_REACHED
FAILED
```

---

# Shared infrastructure

Both features should share common primitives where useful.

Suggested layout:

```text
thurbox-extension/
├── core/
│   ├── agents
│   ├── execution
│   ├── state
│   ├── persistence
│   └── reporting
│
├── debate/
│   ├── orchestrator
│   ├── prompts
│   ├── models
│   └── report
│
├── adversarial/
│   ├── orchestrator
│   ├── prompts
│   ├── models
│   └── report
│
└── tests/
```

Do not create a generic multi-agent framework unless the existing Thurbox architecture naturally provides one.

Prefer small interfaces.

Conceptually:

```python
class Agent(Protocol):
    name: str

    async def run(
        self,
        *,
        prompt: str,
        cwd: Path,
        mode: AgentMode,
    ) -> AgentResult:
        ...
```

Reuse Thurbox's own abstraction instead if one exists.

---

# Commands

Target user experience:

```bash
thurbox debate \
    "Should we use LangGraph for this orchestration?"

thurbox adversarial \
    "Implement idempotent payment creation"
```

Optional:

```bash
thurbox debate \
    --agent-a claude \
    --agent-b codex \
    "..."

thurbox adversarial \
    --builder claude \
    --adversary codex \
    --max-rounds 5 \
    "..."
```

Naming may be adapted to Thurbox extension conventions.

---

# UI

Do not make UI a prerequisite for the MVP.

First make both commands work end-to-end.

If Thurbox supports extension panes, later expose:

```text
DEBATE

Claude     final position ready
Codex      rebuttal ready

Outcome:
CONSENSUS
```

and:

```text
ADVERSARIAL

Claude     repaired
Codex      attacking

Round 2 / 5

HIGH  C-001 resolved
MED   C-002 open

pytest PASS
ruff   PASS
```

Keep workflow logic outside UI code.

---

# Testing — Debate

Use fake agents.

Test:

```text
1. agents initially do not see each other's position
2. both positions are persisted
3. cross-examination receives both positions
4. rebuttals map to actual challenges
5. consensus is represented correctly
6. disagreement is not falsely converted into consensus
7. reports are generated
8. invalid state transitions fail
9. agent crash is persisted and surfaced
```

---

# Testing — Adversarial

Use fake builder/adversary implementations.

Test:

```text
1. builder → SATISFIED
2. builder → finding → repair → SATISFIED
3. multiple repair rounds
4. rejected finding
5. Codex finds a new issue after a repair
6. BLOCKED verdict
7. MAX_ROUNDS termination
8. failing objective check
9. agent crash
10. malformed verdict
11. state persistence
12. report generation
```

Do not make automated tests require actual Claude or Codex credentials.

---

# Safety and robustness

Treat agent output as untrusted.

Do not construct shell commands from arbitrary model-generated strings.

Only run checks from:

```text
trusted configuration
explicit CLI parameters
known auto-detection rules
```

Do not expose secrets in logs.

Do not destroy dirty working trees.

Do not silently continue after malformed workflow output.

---

# Implementation order

Before coding:

1. inspect the actual Thurbox source
2. inspect extension APIs
3. inspect agent/session abstractions
4. inspect worktree support
5. inspect lifecycle hooks
6. document the actual integration design

Do not invent Thurbox APIs.

Then implement:

```text
1. common agent adapter
2. state persistence
3. Debate workflow
4. Debate tests
5. Adversarial workflow
6. Adversarial tests
7. worktree integration
8. objective check runner
9. standard reports
10. CLI integration
11. optional minimal UI
```

---

# Important conceptual distinction

Do not blur these two features.

## Debate

```text
question
 ↓
independent opinions
 ↓
critique
 ↓
rebuttal
 ↓
decision / unresolved disagreement
```

Primary artifact:

```text
DEBATE_REPORT.md
```

No code changes are required.

---

## Adversarial

```text
task
 ↓
builder changes code
 ↓
adversary attacks code
 ↓
builder repairs
 ↓
adversary attacks again
 ↓
SATISFIED
```

Primary artifacts:

```text
ADVERSARIAL_LOG.md
ADVERSARIAL_REPORT.md
code changes
```

Codex satisfaction is the semantic completion condition.

`MAX_ROUNDS` remains the mechanical safety condition.

---

# Completion requirements

Do not stop at scaffolding.

At completion provide:

1. exact Thurbox integration points used
2. architecture
3. files created/modified
4. test results
5. example command for `debate`
6. example command for `adversarial`
7. example `DEBATE_REPORT.md`
8. example `ADVERSARIAL_REPORT.md`
9. known limitations
10. assumptions made

Run fake-agent smoke tests demonstrating both workflows:

```text
DEBATE:
question
→ independent positions
→ challenge
→ rebuttal
→ report

ADVERSARIAL:
task
→ Claude builds
→ Codex finds issue
→ Claude fixes
→ Codex attacks again
→ SATISFIED
→ report
```