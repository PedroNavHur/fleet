---
name: axe-review
description: Automated axe review of rendered pages and interactive UI states. Use for accessibility, a11y, WCAG, or axe audits. Do not use for general visual review or non-UI changes.
---

# Axe review

Use `~/.local/bin/axe-review` for deterministic scans. It uses one
shared Playwright and axe installation, so repositories do not need their own
browser dependencies.

## Workflow

1. **Choose rendered states.** Use every URL or route the user named. For
   `changed`, inspect the diff and select the affected pages plus any state that
   renders changed shared components. State the selected coverage before the
   scan. Coverage is ready when every selected page has an exact URL and every
   non-default UI state has a reproducible interaction sequence.

2. **Prepare the application.** For a mapped local repository, follow its
   production-preview instructions: build, restart the existing production
   service, verify the unit and local origin, then scan the mapped public HTTPS
   hostname. Scan an already deployed external URL directly. Use an existing
   Playwright storage-state file for authenticated pages. Ask for authentication
   help when no usable state exists.

3. **Run axe.** Run all selected pages in one command. Use the default desktop
   viewport unless responsive markup changed or the user requested mobile
   coverage. For authentication or interactive states, read
   [configuration](references/configuration.md) and use `--config`. Run
   `axe-review --help` for the current CLI contract.

   Exit code `0` means no violations, `1` means axe found violations, and `2`
   means at least one scan failed. Findings are a successful audit result, not a
   command failure.

4. **Validate findings.** Reproduce each violation in the rendered state and
   inspect the owning code. Deduplicate the same rule and component across
   routes while preserving every affected route. Keep `incomplete` results in a
   separate manual-review list. Axe-clean means no automatically detected
   violations in the scanned states, not WCAG conformance.

5. **Report.** Lead with validated violations ordered by impact. Include the
   route and state, axe rule, affected selector, concrete failure, source code
   location when found, and help URL. Then list incomplete checks and the exact
   coverage. If the user asked for fixes, make focused changes, rebuild and
   restart once, then rerun the same scan until clean or blocked.

## Guardrails

- Keep the shared scanner outside application repositories. Do not add browser
  dependencies, generated reports, or E2E tests to a repository unless the user
  asks for CI integration.
- Prefer explicit routes over crawling. Avoid following destructive links or
  mutating production data.
- Treat exclusions as temporary, narrow exceptions. Report every exclusion and
  its reason.
- Never suppress a rule merely to make the scan pass.
