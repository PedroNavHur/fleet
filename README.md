# fleet

Agent skills shared by my machines: the MacBook, `workbox`, and `devbox`.

## Layout

- `skills/<name>/`: my own skills. Each one has a single `SKILL.md`, which Claude Code, Codex, OpenCode, and Cursor all read. Codex-only metadata lives in `agents/openai.yaml` next to it.
- `third-party.json`: skills from other repositories, grouped by source. Their files stay out of this repo. Each machine installs them with `npx skills add <source> -g -s <skill>`.

## Principles

The `principle-*` skills come from [pstack](https://github.com/backnotprop/pstack) (a mirror of `cursor/plugins/pstack`), listed in `third-party.json`. Upstream marks them `disable-model-invocation: true`, so agents don't load them on their own. After each install, `bin/sync`:

- gives each such skill an `agents/openai.yaml` with `allow_implicit_invocation: false`, because Codex ignores the frontmatter key;
- writes `~/.config/principles.md`, one line per principle with when it applies and its path;
- adds a marked block to `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, and `~/.config/opencode/AGENTS.md` telling agents to read that index before nontrivial code work.

Skills in this repo cite principles by path (`~/.agents/skills/principle-x/SKILL.md`), not by name, because a principle hidden from the model cannot be found by name.

## Sync a machine

```sh
git clone https://github.com/PedroNavHur/fleet   # once: ~/dev on the Mac, ~/code on workbox, ~/src on devbox
fleet/bin/sync            # show the plan
fleet/bin/sync --apply    # pull, link own skills, install and update third-party skills
```

`bin/sync` links each skill in `skills/` into `~/.agents/skills` (read by Codex, Cursor, and OpenCode) and `~/.claude/skills` (read by Claude Code). Any other entry in those folders, or a copy in `~/.codex/skills`, `~/.cursor/skills`, or `~/.config/opencode/skills`, is moved to `~/.skills-backups/fleet-<timestamp>/`. To add or change a skill, edit it here, push, and run `bin/sync --apply` on each machine.

## Shared host files

`bin/sync` also installs the machine-level tooling that skills rely on:

| On each machine | From this repo |
| --- | --- |
| `~/.local/bin/host-check` | `bin/host-check`: the shared validation queue |
| `~/.local/bin/bg-job` | `bin/bg-job`: long jobs that outlive the agent session |
| `~/.local/lib/host-check/` | `lib/host-check/`: `guard.py` (command guard and job classes), tests, OpenCode plugin |
| `~/.config/t3-orchestration.md` | `config/t3-orchestration.md` |
| `~/.config/host-validation.md` | generated from `config/host-validation.md` plus `hosts/<machine>/host-validation.md` |
| `~/.config/fleet/host.json` | `hosts/<machine>/host.json`: queue limits and CPU policy |
| `~/.config/systemd/user/builds.slice` | `hosts/<machine>/builds.slice` (Linux) |

The full list of links is in `links`. `bin/sync` also adds the guard to Claude Code, Codex, Cursor, and OpenCode as a pre-command hook. On Linux, host-check runs jobs in `builds.slice`; on macOS it runs them under `taskpolicy -c utility`, which yields the CPU to interactive work and does not limit memory.

Run the tests on any machine with:

```sh
cd lib/host-check && python3 -m unittest test_guard test_scheduler test_bg_job
```
