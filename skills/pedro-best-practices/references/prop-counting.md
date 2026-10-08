# Prop counting

Count the public contract, not the attributes present at one JSX call site or just the fields destructured by the implementation.

- Count required and optional application props, including declared children and ref. A nested object is one top-level prop.
- Resolve aliases, imports, intersections, inheritance, utility types, and generic substitutions before counting; deduplicate property names. For variant unions, count the distinct application prop names across variants, consistent with DCAid's cap.
- Exclude members inherited from HTML/React or third-party contracts. Count application-added members and application redeclarations.
- Determine the public contract of memo, forwardRef, HOCs, and class components from their types and consumers. Do not assume the first argument of an arbitrary generic alias is its props type.
- Use complete annotations or other contract evidence for untyped components. Treat rest/spread, open index signatures, unresolved imports, and unconstrained generics as potentially unknown; do not report a guessed exact count. Nine individually proven application prop names are sufficient to establish a violation even when additional members are unknown.

Read each candidate's declaration and relevant callers to validate it. For complex contracts, use the repository's installed TypeScript compiler if helpful. Any temporary analysis should load each project once per invocation, rather than rebuilding it per file. Existing lint output can inform discovery but does not establish the count on its own.

Track inspected components and unresolved contracts so a partial review cannot become a claim that the whole repository passed.

