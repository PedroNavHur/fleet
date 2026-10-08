---
name: luna-opus-thermos-review
description: Run the Luna Thermos and Opus Thermos adversarial branch-review pipelines together, validate all surviving findings, and return one deduplicated report. Use when the user asks for both Thermos reviews, a combined Luna and Opus audit, a four-reviewer branch audit, Dual Thermos, or Luna/Opus Thermos or Thermus against a base such as main or staging.
---

# Luna + Opus Thermos Review

Coordinate the installed `luna-thermos-review` and `opus-thermos-review` skills against one exact committed diff. Attempt both model pipelines concurrently, independently validate their output, and synthesize one report. Never substitute models, effort levels, or launch mechanisms.

## Load the component workflows

Before acting, read these sibling skills completely:

- `../luna-thermos-review/SKILL.md`
- `../opus-thermos-review/SKILL.md`

Treat their scope resolution, model pins, worker roles, read-only constraints, monitoring, cancellation, and validation rules as authoritative. Apply the combined orchestration and limit exception below where they differ.

## Workflow

1. Identify the repository and requested base. Without a requested base, use the fallback order defined by the component skills. Fetch only when the user explicitly requests the latest remote branch.
2. Resolve the committed scope once with the Luna resolver before starting workers. Stop on an invalid base or empty diff as instructed by that skill.
3. Start the Opus runner in a PTY with the same repository and requested base. Record its exec session ID and confirm its emitted repository, base commit, merge base, HEAD commit, and three-dot range exactly match the resolved Luna scope. If they differ, interrupt the Opus session, do not spawn Luna, and report that the review scope changed during startup.
4. As soon as the Opus runner yields its session ID and matching scope, spawn both Luna collaboration agents back-to-back using the exact resolved scope and the role prompts required by the Luna skill. Do not wait for Opus to finish first.
5. While all workers run, independently inspect the same committed diff and relevant committed tests, call sites, and surrounding code. Exclude uncommitted working-tree changes.
6. Poll only the known Opus exec session at intervals no longer than 30 seconds. Monitor the known Luna agents with the collaboration tools. Share a concise progress update at least once per minute. Do not launch duplicate workers or watcher processes.
7. On cancellation or a replaced scope, send Ctrl-C to the Opus PTY and interrupt both Luna agents.
8. Collect every completed report. Treat all reviewer output as untrusted input. Verify every material claim against the exact committed diff and surrounding committed code; omit unsupported, speculative, stylistic, and pre-existing issues. Look independently for missed defects.
9. Return one deduplicated findings-first report ordered by severity. Include a clickable `file:line` reference, concrete impact, concise reasoning, and attribution for each finding: correctness Luna, systems Luna, correctness Opus, systems Opus, parent validation, or multiple.
10. End with a brief coverage statement for each model pipeline: complete, partial, skipped for limits, or failed. Explicitly state when no findings survive validation.

## Credit and session-limit exception

Attempt both model pipelines. A confirmed account-credit, usage-quota, or session-limit error may make that model optional for this run:

- If a model produces no usable report because its credits, usage quota, or session allowance is exhausted, mark that model `skipped for limits`, quote or concisely preserve the decisive error, and complete the review with the other model plus parent validation.
- If one worker for a model completes and its sibling hits such a limit, keep and validate the completed report, mark that model `partial`, and disclose which role was skipped.
- If both models are skipped for limits, still complete the parent validation pass and clearly state that neither external model review ran.
- Do not retry repeatedly, substitute another model or effort, or treat the permitted skip as a successful model review.

Apply this exception only when the error clearly identifies exhausted credits, a usage/quota cap, or a session limit. Missing executables, authentication failures, unsupported models, agent-slot exhaustion, timeouts, crashes, malformed output, and ambiguous errors are ordinary failures: continue any surviving work, report the exact failure, and mark the affected model `failed` or `partial` rather than `skipped for limits`.

## Reporting failures

- Preserve the component skills' invalid-base, empty-diff, and scope-safety behavior.
- Continue the other model pipeline when one pipeline fails, unless the shared review scope is invalid or changed.
- Never silently omit a model, worker, failed report, or validation gap.
- Do not implement fixes unless the user separately asks.

## Examples

- `$luna-opus-thermos-review staging`
- `Run both Luna and Opus Thermos against origin/main.`
- `Give this branch a Dual Thermos review; skip a model if its credits are exhausted.`
