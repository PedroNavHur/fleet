# Shared host validation policy

Codex, OpenCode, Cursor, and Claude Code on this machine share one validation
queue, so checks leave capacity for interactive work and previews. The last
section describes this machine: its limits and how they are enforced.

## Run checks

- Run full builds, test suites, lint, typechecks, formatting checks, and
  benchmarks with `~/.local/bin/host-check COMMAND [ARGS...]` from the
  repository directory. Example: `host-check pnpm build`.
- Queue a complete pipeline once:
  `host-check bash -lc 'pnpm lint && pnpm typecheck && pnpm test'`. Wrap only
  once: a pipeline whose scripts already invoke host-check must not be wrapped
  again, and host-check refuses nested calls.
- Route targeted tests through the wrapper too. Browser-driven scripts count:
  axe page gates, smoke runs, visual or screenshot captures (`tsx`/`node` on a
  path with `a11y`, `smoke`, `visual`, `shots`, `screenshot`, `e2e`, or
  `playwright` in it), and `playwright test`. A server you start in the
  background for later runs stays outside the queue, because a queued job holds
  its worktree lock until it exits.
- Wait for queued jobs instead of starting duplicates. Keep reads and edits
  outside the queue. The queue changes scheduling, not which checks are
  required: pre-commit gates still need every prescribed check to pass.
- Run benchmarks only when requested. Start with one measured run and no
  warmup, with a timeout inside the queue:
  `host-check timeout --kill-after=10s 10m pnpm test`. Inspect failures before
  repeating. Do not wait for an artifact after its producer has failed.
- Leave application services running. Route the builds of existing preview and
  production workflows through host-check.

## How the queue works

- One job per physical Git worktree. Subdirectories and symlinks share their
  worktree's lock; separate Git worktrees have separate locks. Outside Git, the
  physical working directory is the key. A wrapped pipeline must stay in its
  worktree; commands writing shared output elsewhere need that output's own lock.
- Host-wide caps apply to all jobs, to heavy jobs (builds, a full `check`, and
  whole test suites: `test` or `vitest run` without file or directory
  arguments), and to builds. A heavy job waits for its class without holding a
  global slot, so targeted tests, lint, format, and typecheck keep running.
  Target tests at files or directories while iterating; that is light.
- The wrapper detects the class from the command, reading package scripts and
  shell scripts for the strongest command inside. A script it cannot read, or
  one that runs hidden commands (`"$@"`, `$cmd`, `eval`), is heavy. Set
  `HOST_CHECK_CLASS=build|heavy|light` before `host-check` to override;
  `host-check env HOST_CHECK_CLASS=…` has no effect.
- The wrapper sets `VITEST_MAX_WORKERS` to this machine's default unless it is
  already set. Keep Vitest at or below it; pass `--maxWorkers=N` if the
  installed version ignores the variable. Lower is fine.
- `host-check --help` prints this machine's limits.

This is cooperative scheduling: commands run directly bypass it. Waiters take
their worktree lock before a global slot, so worktree waiters consume no global
capacity. Slot acquisition is not FIFO. Locks release when the command and
every child that inherited them exit. The owner files under
`~/.cache/host-check/` describe the last holders and may be stale when idle.
Never delete active lock files to clear the queue.

## Long jobs

A job expected to outlast about ten minutes (per-layer gates, a full `check`, a
build plus restart) runs through `~/.local/bin/bg-job`, so it survives the
session that started it. Launch it as one background command:
`bg-job start NAME -- host-check pnpm check && bg-job wait NAME`. After a
restart or a lost notification, `bg-job status NAME` reports running or the exit
code, and `bg-job log NAME` shows the tail. Then arm the fallback wake in
`~/.config/t3-orchestration.md` ("Background jobs").

## Command guards

Hooks for Claude Code, Codex, Cursor, and OpenCode run
`~/.local/lib/host-check/guard.py`, which rejects common unwrapped validation
commands. On rejection, wrap the whole check and retry. Include this policy path
when delegating validation to subagents. Start new tool sessions after hook
configuration changes; in Codex, use `/hooks` to review and trust the
shared-CPU hook before relying on it.

The guard recognizes package scripts (by their package.json bodies, through
workspace filters), shell scripts, validation executables, pipelines, and
benchmark or debug harnesses (`tsx`/`node` on `bench*`, `perf*`, `debug-*`). It
trusts scripts that call host-check themselves. It does not see aliases,
generated commands, or commands sent to an already-open interactive shell. Hooks
prevent common mistakes, not deliberate bypasses; the policy still applies to
commands the guard cannot recognize.
