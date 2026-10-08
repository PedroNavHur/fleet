---
name: react-prop-audit
description: Manually audit React components for more than eight application-defined props before a pull request. Report confirmed violations and unresolved contracts without editing code.
---

# React prop audit

Review React component contracts in the current working tree. Flag more than eight application-defined top-level props. Seven and eight are allowed; there is no warning tier. This is an on-demand code review, not a deterministic lint guarantee.

## Scope

With no arguments, audit all first-party React components in the repository. With an explicit base, branch, PR, or path scope, audit that scope and follow referenced prop declarations and affected consumers. For a PR, use its actual base. Include relevant working-tree edits and state the revisions and scope reviewed.

Use tracked source files and relevant untracked application source. Exclude dependencies, generated/build output, and fixtures unless requested. Find declarations, function expressions, wrappers, classes, and JSX consumers; a naming regex alone is not a component inventory. Ordinary helper function parameters are outside this React audit unless the user explicitly expands the scope.

## Counting

Count the public contract, not the attributes present at one JSX call site or just the fields destructured by the implementation.

- Count required and optional application props, including declared children and ref. A nested object is one top-level prop.
- Resolve aliases, imports, intersections, inheritance, utility types, and generic substitutions before counting; deduplicate property names. For variant unions, count the distinct application prop names across variants, consistent with DCAid's cap.
- Exclude members inherited from HTML/React or third-party contracts. Count application-added members and application redeclarations.
- Determine the public contract of memo, forwardRef, HOCs, and class components from their types and consumers. Do not assume the first argument of an arbitrary generic alias is its props type.
- Use complete annotations or other contract evidence for untyped components. Treat rest/spread, open index signatures, unresolved imports, and unconstrained generics as potentially unknown; do not report a guessed exact count. Nine individually proven application prop names are sufficient to establish a violation even when additional members are unknown.

Read each candidate's declaration and relevant callers to validate it. For complex contracts, use the repository's installed TypeScript compiler if helpful. Any temporary analysis should load each project once per invocation, rather than rebuilding it per file. Existing lint output can inform discovery but does not establish the count on its own.

Track inspected components and unresolved contracts so a partial review cannot become a claim that the whole repository passed.

## Report

List confirmed violations by descending count in a table: component, prop count, file/line, and counted prop names. Report a component once even when several callers expose it. For each violation, suggest a concrete ownership or composition improvement based on its callers; avoid recommending arbitrary bags solely to lower the number.

State the number of components inspected, the scope covered, and unresolved contracts or coverage gaps separately. If none violate the cap, say no confirmed violations were found within that scope. A review with unresolved contracts is incomplete, not a clean pass.

Return the audit in the conversation. Fixes, commits, and PR comments require a separate user instruction or existing explicit authorization.
