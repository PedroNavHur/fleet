---
name: principle-reach-for-what-exists
description: "Apply before writing new code or adding a dependency. Take the first rung that holds: this codebase, the standard library, the platform, an installed dependency, then new code. Mark a deliberate shortcut with a `ceiling:` comment naming its limit and upgrade path."
disable-model-invocation: true
---

# Reach for What Exists

Before writing code, climb the ladder and stop at the first rung that holds.

**Why:** Existing code is already written, tested, and maintained by someone. Reimplementing a helper that lives a few files over is the most common duplicate, and a new dependency for a few lines adds an install, upgrades, and supply-chain surface in exchange for one function.

**The ladder:**

1. **This codebase.** A helper, type, hook, or pattern that already lives here. Search before you write.
2. **The standard library.**
3. **The platform.** `<input type="date">` over a picker library, CSS over JavaScript, a database constraint over application checks.
4. **An installed dependency.**
5. **New code.** Write the few lines yourself. Add a dependency only when it replaces substantial code you would otherwise own and test: parsing, cryptography, time zones.

A rung holds when it meets the whole requirement: correct on edge cases, validated at trust boundaries ([Boundary Discipline](../principle-boundary-discipline/SKILL.md)), and good to use ([Experience First](../principle-experience-first/SKILL.md)). A native control that degrades the experience does not hold. When two rungs hold, take the higher one.

## Name the ceiling

When you deliberately choose a simpler solution with a known limit (a global lock, an O(n²) scan, a naive heuristic, an unbounded in-memory cache), mark it where it lives with one line naming the limit and the upgrade:

```python
# ceiling: global lock; per-account locks if throughput matters
```

The next reader learns the shortcut was a choice and what to change when the limit bites. The `ceiling:` tag keeps every such choice greppable. Code with no known limit carries no comment.

**The test:** Could a higher rung have done the job? Does every shortcut with a known limit carry a `ceiling:` comment?
