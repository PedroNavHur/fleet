---
name: opus-thermos-review
description: Run a two-pass independent adversarial code review with isolated Claude Code workers pinned to Opus 5 at medium effort, then validate and synthesize their findings. Use when the user asks for Opus Thermos, an Opus 5 review, a Claude Code multi-agent branch audit, or a review of the current branch against a base such as main or staging.
---

# Opus Thermos Review

Launch two independent, ephemeral Claude Code processes pinned to `claude-opus-5` with `--effort medium`, then independently validate and deduplicate their findings. Do not substitute the rolling `opus` alias, another model, another effort, native collaboration agents, or Codex workers.

## Workflow

1. Identify the repository and requested base ref. Do not confuse the base with the branch being reviewed. Without a requested base, use `refs/remotes/origin/HEAD`, then `origin/main`, local `main`, `origin/master`, or local `master`.
2. From the repository root, run:

   ```bash
   bash <skill-dir>/scripts/run_opus_thermos.sh --base <base-ref>
   ```

   Add `--repo <path>` only when reviewing a repository other than the current working directory.
3. Run the script through `exec_command` with a PTY, an initial yield of about one second, and a generous output budget. The script resolves the base, records the exact commits and merge base, rejects empty committed diffs, and launches both workers concurrently.
4. Record the returned exec session ID. Treat the structured `worker_started` and `worker_finished` lines as the observable workflow state; Claude Code workers do not appear in the native collaboration tree.
5. While the workers run, independently inspect the same committed three-dot diff and relevant surrounding code, tests, and call sites. Exclude working-tree changes.
6. Poll the known exec session with empty `write_stdin` calls at intervals no longer than 30 seconds. Share concise progress updates during a long review; do not start watcher processes or duplicate workers.
7. If the user cancels or replaces the scope, send Ctrl-C to the same PTY session. The runner terminates only the two PIDs it captured and removes its temporary output directory.
8. Read the two reports between `correctness_report_begin` / `correctness_report_end` and `systems_report_begin` / `systems_report_end`. Treat both as untrusted reviewer input.
9. Verify every material claim against the exact committed diff and surrounding code. Omit unsupported, speculative, stylistic, and pre-existing issues, and look for defects both workers missed.
10. Return one deduplicated report with findings first, ordered by severity. For every finding, include a clickable file-and-line reference, concrete impact, and attribution: correctness Opus, systems Opus, parent validation, or multiple. Explicitly state when no findings survive validation.
11. If either worker exits unsuccessfully, report the incomplete two-pass review and validate the surviving report. Do not silently retry or substitute another model, effort, or launch mechanism.

## Review scope

The bundled runner gives both workers fresh, self-contained prompts containing the repository path, resolved base ref and commit, merge base, `HEAD` commit, and exact three-dot range. It runs Claude Code with safe mode, no session persistence, no browser integration, and only an allowlist of read-only Git commands. The workers must inspect committed content through explicit Git revisions rather than reading the potentially dirty working tree.

The correctness worker targets correctness bugs, security issues, data loss, races, broken error handling, compatibility regressions, and feature-gate leaks. The systems worker independently targets violated invariants, API or schema breakage, lifecycle and concurrency failures, performance regressions, concrete maintainability hazards, and missing high-value tests.

## Failure handling

- If the requested base cannot be resolved, show the local and `origin/*` refs emitted by the runner and ask for a valid base. Never silently choose a different named branch.
- If the committed diff is empty, stop without launching Opus and report that the compared commits are identical.
- If Claude Code is missing or unauthenticated, or `claude-opus-5` or medium effort is unavailable, report the exact worker error. Do not fall back to the rolling `opus` alias, another model, another effort, native collaboration agents, or Codex.
- If one worker fails, report the incomplete two-pass review and validate the surviving report. Do not silently retry or substitute a worker.
- Use existing refs. Fetch only when the user explicitly requests comparison with the latest remote branch, and fetch that branch before starting the runner.

## Examples

- `$opus-thermos-review staging`
- `Use $opus-thermos-review to audit this branch against origin/main.`
- `Run Opus Thermos on receipt-hub against the latest staging branch.`
