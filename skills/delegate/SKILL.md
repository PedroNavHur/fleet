---
name: delegate
description: Delegate scoped implementation, codebase research, or review through T3 app-owned child tasks, then verify the result. Use for delegate requests or a requested worker model/provider.
---

# Delegate

Read `~/.config/t3-orchestration.md` before dispatch. Use its live
catalog, complete brief, workspace ownership, and task lifecycle contract.

Muse Spark Contributor remains the default for scoped execution when no model
was requested. Resolve its exact provider/model ID and reasoning option from
`orchestrator_capabilities`; keep the user's explicit model and effort.
Keep ambiguous requirements and design decisions in the parent until the brief
has a clear finish line.

Launch directly with `delegate_task`, `role: "implementation"` (or research or
review), and `mode: "async"`. Store the taskId. Give workers disjoint ownership
in the bound checkout; serialize tasks that need the same files. Continue other
work, or end the turn while waiting for automatic completion.

After delivery, inspect the diff or research artifact against the brief.
Verify the meaningful completion criterion through host-check when it matters.
Report actual changes, validation results, and unfinished work. For another
attempt, create a fresh delegated task carrying the full prior context.
Take over if a second scoped attempt still misses the finish line.
