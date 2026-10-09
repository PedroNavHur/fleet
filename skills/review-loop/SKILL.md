---
name: review-loop
description: Review, fix, and re-review a PR or stack until it converges, with no user prompt between rounds.
disable-model-invocation: true
---

# Review loop

Run `code-review` and `pedro-best-practices` in rounds, fix what they confirm,
and re-review only the **delta**, until a round comes back clean. The user is
asked only for the decisions that are theirs. Everything stays local until the
publish step.

Set `SKILL_DIR` to this skill's absolute directory. Read before starting:
`~/.config/t3-orchestration.md` (dispatch),
`~/.config/host-validation.md` (checks, `bg-job`), and for a stack
`split-stacked-prs` section 7, which owns carrying fixes and publishing.

## Invocation

Take from the user's message, else from the ledger of an earlier run on the
same target, else ask once:

- **Target**: a PR, a stack (its top PR or branch), or a local branch with its base.
- **Reviewer** model and effort, and **worker** model and effort for fixes.
- **Publish**: whether a converged loop pushes (default: stop locally and report).
- **Round cap**: default 5, the first full round included.

## The ledger

`~/.cache/review-loop/<target-slug>/ledger.md` is the single source of truth
for the loop's history; reviewers get it every round, and round directories
`r1/`, `r2/`, ... sit beside it. It holds:

- **Settled**: every finding fixed (with its commit) or declined (with the
  reason), and every user ruling. Reviewers never re-raise a settled item.
- **Open decisions** for the user, each with your recommendation.
- **Heads** per round: `rN/heads.tsv`, one line per PR bottom to top,
  `PR<TAB>LAYER<TAB>BASE_SHA<TAB>HEAD_SHA` (layer = manifest name; for a single
  branch, one line).

Update the ledger at the end of every step that changes it, so a lost session
resumes from the file, not from memory.

## Steps

### 1. Pin the round

Record `rN/heads.tsv` from the local branches. Round 1, or any PR new since the
last round, is reviewed whole. Later rounds compute the delta:

```bash
bash "$SKILL_DIR/scripts/delta.sh" --prev rN-1/heads.tsv --heads rN/heads.tsv \
  --out rN [--manifests "$plan/layers"] --repo "$checkout"
```

A PR with no delta is skipped this round. Done when every PR is marked whole,
delta, or skipped.

### 2. Dispatch reviewers

Write one shared packet (`rN/common.md`): read-only rules (write only to the
named output file under `rN/`; no edits, commits, pushes, or GitHub/Linear
changes), the checkout path and the instruction to read code at pinned SHAs
with `git show`/`git diff`, the base, the spec path, the gates already passed,
standing decisions, and the ledger. Standards and delta reviewers also get the
principles from `~/.config/principles.md` that match the diff, as standards
ranked below the repo's documented ones. Then launch every reviewer at once through
`delegate_task`, `mode: "async"`, `clientRequestId` `<slug>-rN-<role>-<pr>`:

- **Whole**: per stack (or branch), one `code-review` Standards and one Spec
  reviewer; per PR, one `pedro-best-practices` audit, local-only.
- **Delta**: per stack, one reviewer covering Standards and Spec on the delta
  diffs; per PR whose delta has `audit=yes`, one local-only audit. The
  brief: confirm each fix in the delta is correct and complete, then look for
  regressions it causes in the code around it (callers, tests, sibling
  layers). The rest of the PR was reviewed in an earlier round.

Done when every reviewer is launched and its `taskId` is in `rN/tasks.tsv`.
End the turn; completions wake you.

### 3. Triage

Verify every finding against the code at its pinned SHA before it counts, and
give it one class in `rN/validated.md`:

- **Fix**: a confirmed bug (any P1 or P2), or any confirmed P3 that needs no
  design or architecture decision.
- **Decline**: unconfirmed, settled, pre-existing outside the change, or
  contradicted by a ledger ruling. Record the reason in the ledger.
- **Decision**: product behavior, copy, scope, or a design or architecture
  choice (including a P3 whose fix needs one). Add it to the ledger's open decisions with a recommendation, and
  keep going with the rest.

Done when every reviewer has reported and every finding has a class.

### 4. Converge or fix

The round is **clean** when it has no Fix items. Clean, or at the round cap:
go to step 5. Otherwise:

1. Brief workers (worker model, `delegate_task`) to edit the fixed source:
   the stack's source branch, or the branch itself. Give each disjoint file
   ownership, its findings, and the ledger; workers run no checks.
2. Read each worker's diff as a reviewer would, then run the light check from
   `split-stacked-prs` section 7 step 4 (for a single branch, the same check
   on that branch).
3. Commit. For a stack, carry the fixes into their layers with
   `fix_layers.sh`. Record each fix in the ledger with its commit, then start
   the next round at step 1.

Post one short progress line to the user per round: round number, reviewers,
confirmed findings, and fixes made.

### 5. Finish

- **Open decisions**: ask them all in one `AskUserQuestion`, recommendation
  first. A ruling that changes code reopens the loop at step 4 with one more
  delta round, without counting against the cap.
- **Publish** (when authorized, or when the user approves now): follow
  `split-stacked-prs` section 7 step 5, then post each PR's most recent audit
  per `pedro-best-practices`, stating which head it reviewed.
- **Report**: a table of rounds (reviewers, confirmed, fixed, declined),
  what's still open, and whether the loop converged or hit the cap; then local
  versus pushed heads and the gate results.

Merging and marking PRs ready stay with the user.
