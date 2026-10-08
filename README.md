# fleet

Agent skills shared by my machines: the MacBook, `workbox`, and `devbox`.

## Layout

- `skills/<name>/`: my own skills. Each one has a single `SKILL.md`, which Claude Code, Codex, OpenCode, and Cursor all read. Codex-only metadata lives in `agents/openai.yaml` next to it.
- `third-party.json`: skills from other repositories, grouped by source. Their files stay out of this repo. Each machine installs them with `npx skills add <source> -g -s <skill>`.

## Machine dependencies

Some skills read files that live on each machine rather than in this repo:

| File | Used by |
| --- | --- |
| `~/.config/t3-orchestration.md` | architect, how, why, delegate, review-loop, split-stacked-prs, update-t3-tools, principle-make-operations-idempotent, pedro-best-practices |
| `~/.config/host-validation.md`, `~/.local/bin/host-check` | delegate, review-loop, split-stacked-prs, suzuka-review-fix; optional for pre-commit and pedro-best-practices |
| `~/.local/bin/axe-review` | axe-review |
| `~/.codex/AGENTS.md` ("PR and stack size") | split-stacked-prs, pedro-best-practices |
