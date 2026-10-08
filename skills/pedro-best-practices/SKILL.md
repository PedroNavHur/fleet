---
name: pedro-best-practices
description: Manually audit React repositories or PRs against Pedro's eight-prop cap, complexity limits, component ownership and readability preferences, and Vercel React and Next.js best practices. Report evidence-backed findings and coverage gaps in the conversation and on the matching GitHub pull request.
---

# Pedro best practices

Audit React code without modifying it, combining Pedro's interface and readability preferences with Vercel's performance guidance. Return findings in the conversation and publish one summary comment on the matching GitHub PR. Explicit invocation authorizes that comment unless the user requests a local-only audit. Code changes, commits, pushes, and review approval or change-request submissions remain outside this workflow.

## PR size requests

For an audit or explanation of Pedro's PR or layer size rule, read the "PR and
stack size" section in `~/.codex/AGENTS.md` and the installed
`split-stacked-prs` skill and its `scripts/diff_budget.py`. This is a separate
personal policy from the React audit below. For a policy-only request, return
findings in the conversation without running the React audit or posting a PR
comment. Claude's installed wrapper reads this same canonical skill.

## Scope and sources

With no scope argument, audit the current repository's first-party React application code, including relevant working-tree changes. Accept a path, explicit base, or PR scope; use a PR's actual base and follow changed shared contracts to affected consumers. Record the scope, revisions, and working-tree state reviewed. Exclude dependencies, generated output, and fixtures unless requested.

Read these installed sources as reference documents before auditing:

- [Prop counting](references/prop-counting.md): authoritative counting semantics for Pedro's cap. Apply its counting and uncertainty guidance; use the combined report below.
- [Vercel React best practices](~/.agents/skills/vercel-react-best-practices/SKILL.md): category and rule index. Read the relevant `rules/*.md` files relative to that directory before validating findings. Use its compiled `AGENTS.md` when a full expanded reference is useful.

These references inform this combined audit, not separate review runs. If a source is missing, look for the installed skill by name. If unavailable, complete the available portion and identify the missing coverage.

When the user requests a reviewer model or agent, follow `~/.config/t3-orchestration.md` and include the applicable audit instructions, references, scope, and requested role in its complete brief. Delegate read-only investigation; the invoking thread validates findings and owns any authorized PR comment. Preserve requested model and effort choices.

## Audit

1. Inspect repository instructions, framework versions, React Compiler settings, and existing data-fetching and caching patterns. Inventory the components, routes, hooks, and React-related utilities in scope. Track inspected files/components and unresolved contracts; a name-based search alone is not a complete inventory.
2. Check the public prop contract of every scoped component using the prop-audit reference. More than eight application-defined top-level props is a violation. Seven and eight are allowed, with no warning tier. This limit concerns React props, not ordinary helper-function parameter counts. Trace declarations and callers before reporting a count. Assess interface quality using the criteria below, including components already within the cap; a compliant count does not establish a good design.
3. Inspect every scoped JavaScript, TypeScript, JSX, and TSX conditional expression for nested ternaries using the rule below. Record each outer expression once.
4. Measure cognitive and cyclomatic complexity in scoped first-party JavaScript, TypeScript, JSX, and TSX code, and check the diff for ways around the limits, using the rules below. Include functions in non-React utilities within the requested scope. For a diff scope, run `scripts/measure_complexity.py BASE HEAD` once from the checkout (details under "Complexity limits").
5. Consider every Vercel category in order: waterfalls, bundle size, server performance, client fetching, rerenders, rendering, JavaScript performance, and advanced patterns. Mark categories inapplicable where the repository lacks those features, such as Next.js server features in a client-only React app. Read relevant detailed rules and trace the affected execution paths. Settled fact, do not re-check: Next.js optimizes `lucide-react` barrel imports by default (its built-in `optimizePackageImports` list in `next/dist/server/config.js`, line ~1125 in Next 16.3 and ~988 in 16.2), so `import { X } from "lucide-react"` is not a bundle-size finding in NJ Homes Next or Receipt Hub.
6. Validate candidates against actual code and configuration. Pedro's explicit preferences govern the audit; Vercel guidance informs applicable recommendations. A category's impact label is an investigation priority, not automatic finding severity. Account for existing compiler optimizations, bundler configuration, cache scope, and framework support. Distinguish measured costs from inferred costs. Performance and ownership findings need a concrete consequence or justified opportunity. A syntactically confirmed nested ternary is sufficient for its readability finding, and a measured complexity excess is sufficient for a complexity violation.

For difficult prop types, use the repository's installed TypeScript compiler if useful, loading a project once per audit rather than once per file. Keep unresolved contracts visible instead of guessing counts. Use focused checks when they resolve a candidate; do not turn a static audit into a full build, benchmark, or browser run without a concrete need.

## Nested ternaries

Flag `pedro/no-nested-ternary` whenever one conditional expression contains
another conditional expression in its condition, true branch, or false branch.
This includes chained forms such as `a ? b : c ? d : e`, nested JSX expressions,
and nesting hidden by parentheses. Multiple independent ternaries in one
statement are not nested unless one contains another.

This is Pedro's readability preference, not a repository standard or a claim
about the team's conventions. Report it as Low-priority advisory feedback and
never call it a merge blocker. If the expression also causes incorrect behavior
or a measured performance problem, report that separately under the applicable
rule.

Recommend the smallest clearer form for the surrounding code: an early return,
named helper, `if`/`else`, `switch`, or lookup table. Preserve branch laziness,
evaluation order, type narrowing, and rendered JSX. Record one finding for the
outer expression rather than one finding per nested node.

## Complexity limits

Cognitive complexity above **8** and cyclomatic complexity above **16** are violations; eight and sixteen pass. These are enforced standards, not suggestions: NJ Homes Next (`apps/web/.oxlintrc.json`) and Receipt Hub (`.oxlintrc.json`) fail lint on `dca/cognitive-complexity` max 8 and classic `complexity` max 16. Never call an excess advisory or optional. Use the repository's configured metric definitions and file scope where available, including their treatment of nested functions and colocated tests. Measure with the bundled script instead of building a lint configuration by hand:

```sh
<this skill's directory>/scripts/measure_complexity.py BASE HEAD   # committed range
<this skill's directory>/scripts/measure_complexity.py BASE        # working tree vs BASE
```

It diffs from `merge-base(BASE, HEAD)`, copies each changed file's `.oxlintrc.json` complexity rules (with their overrides, ignore patterns, and the repo's `dca` jsPlugin) into a temporary config with max 0, runs the repository's own oxlint (through `~/.local/bin/host-check` when that exists) with `--format json`, and prints every changed function's cognitive and cyclomatic score against 8 and 16. For each function over a limit, a second pass with the repository's real rule values tags it `[lint: error]`, `[lint: warning]`, or `[lint passes]`. Do not call it inside another host-check. It ends with `Result: N functions over threshold among M changed functions … (X fail the repository's lint, Y pass it)`; `0 functions over threshold` is a clean, complete measurement. Use `--over-only` for a large range and `--all` to include unchanged functions in changed files. For a whole-repository scope, pass `EMPTY` as BASE. Do not re-derive the setup: oxlint 1.80 prints nothing on a clean default-format run, and the repo plugin reports a function only when its score exceeds `max`, so scores of 0 are absent by design. If the script fails, report its error and mark complexity coverage incomplete rather than estimating a score.

Classify each excess by its tag, recording the actual score, limit, function, and location. If both limits are exceeded in one function, report one finding naming both rules and scores.

- `[lint: error]`, or `[lint: warning]` where the lint script runs `--deny-warnings` (NJ Homes Next does): a **High / lint failure**. The PR fails lint until it is fixed; name the failing rule and point to the lint result rather than re-arguing the score.
- `[lint passes]`: a **Medium / violation** that the repository's lint lets through. The script's coverage notes name the cause, such as a config that sets a looser max (DCAid uses 12 and 24) or keeps a rule at warning level. Report the gap in the config alongside the finding.
- Files the script could not score are not passes. A repository's deliberate scope exclusion, such as Receipt Hub turning both rules off for tests, evals, and generated code, is listed as out of scope in coverage. A file with no owning config, or a config without a cognitive rule, is a coverage gap.

Lint guarantees the number, so the audit's main job in an enforced repository is the ways around it. Inspect the diff for each, and report each as `pedro/complexity-evasion` at the priority of the excess it hides:

- New `oxlint-disable`, `oxlint-disable-next-line`, or `eslint-disable` comments naming `complexity`, `*/cognitive-complexity`, or `max-lines`, including a file-level disable or one that names no rule.
- `.oxlintrc.json` changes that raise a complexity `max`, lower its level, turn it off, remove paths from an override's `files`, or add `ignorePatterns` covering application code.
- Splits made only to pass lint: a helper that receives the caller's state and returns a flag the caller branches on again, branches that move into a lookup or callback map without becoming simpler, or one-use functions whose names restate their bodies. Compare the before and after control flow; a split that leaves the reader tracing the same decisions across more functions is evasion even though both scores pass.

Recommend a smaller named function or flatter control flow (early returns, a domain helper that owns a decision, a lookup that replaces a real case analysis) that preserves behavior, branch laziness, and type narrowing. Do not suggest a split that only lowers a number.

## Component ownership and composition

Keep prop counting and interface quality separate. A nested object still counts as one top-level prop. Do not recommend grouping fields solely to reach eight, or approve a refactor solely because its count fell. Assess whether callers have fewer decisions to make and less implementation detail to coordinate.

Trace object creation at callers and consumption in the component. For a refactor, compare both sides before and after when history is available. For an existing interface, ground the assessment in its current callers rather than guessing why it was written.

- Keep cohesive values such as income amount plus period, a link's label plus destination, or an existing domain entity. Presentation models and copy/style groups can also be useful when they provide a clear contract. Object creation at a call site or immediate destructuring alone is not a defect.
- Investigate bags that merely regroup independent fields while callers still coordinate the same callbacks, refs, IDs, or matching visual settings. Names such as `actions`, `options`, and `appearance` neither prove nor disprove cohesion. Report the concrete burden, not the name or nesting depth.
- Prefer removing dependencies: derive internal IDs and settings inside their owner, pass a field's resolved error instead of whole-form validation, combine operations that must happen together, and use explicit variants for fixed combinations. Use children or focused slots when the caller owns the rendered content.
- Move behavior with its lifecycle. If a component takes ownership of timers, subscriptions, focus, or interaction state, explain how cancellation, cleanup, navigation, and accessibility remain correct. Introduce hooks, context, or compound components only when they reduce actual coordination; moving the same bag into context is not sufficient.

Before recommending an interface change, answer: **Would we choose this interface without the eight-prop limit?** Name the responsibility that moves, the caller work that disappears, or the meaningful concept the object models. If none applies, report the excessive contract as an unresolved design issue rather than proposing a cosmetic fix. Keep the cap and no-warning policy; do not flatten nested fields into a second numerical limit.

Examples: replacing `ctaLabel` and `ctaHref` with a cohesive `cta` is reasonable; replacing seventeen independent inputs with eight bags is insufficient. A dialog that owns its refs, focus handling, and motion removes real caller obligations. A seasonal card that derives its icon and colors from `season` removes decisions that an `appearance` bag merely transports.

When a candidate needs deeper composition guidance, read the installed [Vercel composition patterns](~/.agents/skills/vercel-composition-patterns/SKILL.md) and the relevant detailed rules. Preserve application behavior when recommending changes.

## Combined report

Lead with the most consequential confirmed findings. For each, include:

- Category and rule ID, using `pedro/eight-prop-cap` for count violations, `pedro/component-ownership` for evidenced interface design findings, `pedro/cognitive-complexity` and `pedro/cyclomatic-complexity` for complexity violations (naming the repository rule, such as `dca/cognitive-complexity`, when lint fails), `pedro/complexity-evasion` for suppressions, loosened config, or splits made only to pass, and `pedro/no-nested-ternary` for the advisory readability preference.
- Clickable file and line, component or function, and concrete evidence.
- Impact and a focused recommendation; distinguish policy violations from performance defects or optimization opportunities.

For prop violations, include the exact count and counted application prop names, or a proven lower bound when the complete contract is unknown. Order prop violations by count within that category. For interface recommendations, show a concise proposed caller or before/after contract and explain what responsibility or coordination it removes. Distinguish a count violation from an ownership finding even when they concern the same component; combine their explanation when the root cause is shared.

Finish with inspected file/component counts, a compact status for all eight Vercel categories, checks actually performed, and unresolved contracts or coverage gaps. Categories may be reviewed with no findings, have findings, be inapplicable, or remain incomplete. Claim a clean audit only for fully inspected scope with no confirmed findings and no unresolved relevant contracts. An agent audit is not a deterministic enforcement guarantee.

## GitHub publication

Use an explicit PR target when supplied; otherwise resolve the open PR for the current branch in its actual GitHub repository. Verify the repository, PR number, base, and head SHA before publishing. If no matching PR exists, return the audit locally and state that no comment was posted. If multiple targets remain plausible, prepare the report and ask which PR to use. Do not create a PR as part of an audit.

Publish the combined report as a normal PR conversation comment after validating findings. Preserve the requested audit scope: a whole-repository audit attached to a PR is still a whole-repository audit. Clearly separate findings in the PR changes from existing issues elsewhere. Record the reviewed commit, base when relevant, and working-tree state. Label findings that depend on uncommitted changes as local-only evidence; never present them as findings in the pushed PR. Use GitHub source permalinks at the reviewed SHA for committed evidence, not local filesystem links. For local-only evidence, provide the path and line as text with a brief excerpt.

Recheck the remote head before posting. If it changed, label the report as reviewing the earlier snapshot, or review the new changes before claiming current coverage. Do not silently attribute results to an unreviewed commit.

Use this comment structure, replacing the placeholders with actual results:

```markdown
## Pedro best practices

> [!WARNING]
> Found N confirmed findings: X prop-cap violations, Y ownership findings, C complexity violations (L failing lint), E complexity evasions, Z readability advisories, and W performance findings. Coverage: complete/incomplete.

Reviewed `<sha>` · Scope: <repo/path/PR changes> · Base: <base if applicable>
Working tree: <clean or local changes included>

| ID | Priority / kind | Rule | Location | Finding and recommendation |
| --- | --- | --- | --- | --- |
| PBP-1 | Medium / ownership | `pedro/component-ownership` | [Component](permalink) | Concrete evidence and the responsibility the proposed change removes. |

### Evidence

<Counted prop names, focused before/after examples, and measured versus inferred performance costs, keyed to finding IDs. Omit this section if the table contains all necessary evidence.>

### Coverage

| Check | Result |
| --- | --- |
| Eight-prop cap | <result> |
| Component ownership | <result> |
| Nested ternaries | <result> |
| Cognitive complexity (limit 8) | <result; say whether the repo's lint enforces 8 or the audit measured it> |
| Cyclomatic complexity (limit 16) | <result; same> |
| Complexity evasion | <suppressions, config changes, and split-only refactors checked> |
| Waterfalls | <result> |
| Bundle size | <result> |
| Server performance | <result> |
| Client fetching | <result> |
| Rerenders | <result> |
| Rendering | <result> |
| JavaScript performance | <result> |
| Advanced patterns | <result> |

Inspected: <file/component counts>. Checks performed: <actual checks>.
Coverage gaps: <unresolved contracts, local-only evidence, or unmeasured costs>.
```

Choose the alert from the result: `[!CAUTION]` when a complexity excess fails the repository's lint; `[!WARNING]` when other confirmed policy, complexity, ownership, or performance findings exist; `[!NOTE]` when the only findings are nested-ternary advisories; `[!IMPORTANT]` for incomplete coverage with no findings; and `[!NOTE]` for no findings with complete static coverage. The warning alert is a report summary, not a seven/eight-prop warning tier. When no findings exist, say so and omit the findings table rather than inventing rows. Escape pipes inside table cells and keep long evidence outside the table. Avoid implying that a static audit is CI enforcement or a runtime performance measurement.

Use the available GitHub connector or `gh` to post. For `gh`, write the exact Markdown to a temporary file and use `--body-file` with the verified repository and PR number. On an uncertain response or retry, read the PR comments first and reuse the already-published comment for this run rather than duplicating it. A later intentional audit gets a new comment; preserve previous audit history. Verify the published body and return its URL with the main findings in the conversation. If publication fails, retain the prepared report, explain the failure, and do not claim it was posted.
