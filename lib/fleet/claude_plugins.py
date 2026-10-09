"""Install, enable, and update the Claude Code plugins in claude-plugins.json.

    python3 claude_plugins.py MANIFEST [--apply]

Prints one plan line per change, in bin/sync's format. With --apply, makes
the changes and then updates every listed marketplace and plugin, so each
machine runs the latest version. Plugins not in the manifest are left alone.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Non-interactive ssh shells often lack ~/.local/bin, where the native
# installer puts claude.
CLAUDE = shutil.which("claude") or next(
    (str(p) for p in [Path.home() / ".local" / "bin" / "claude"] if p.exists()), None)


def say(verb, text):
    print(f"  {verb:<10} {text}", flush=True)


def claude(*args, check=True):
    result = subprocess.run([CLAUDE, "plugin", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise SystemExit(f"claude plugin {' '.join(args)} failed: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def main(argv):
    manifest, apply = json.load(open(argv[0])), "--apply" in argv
    if not CLAUDE:
        say("warning", "claude not found on PATH or in ~/.local/bin; skipping Claude Code plugins")
        return
    known = {m["name"] for m in json.loads(claude("marketplace", "list", "--json"))}
    plugins = {p["id"]: p for p in json.loads(claude("list", "--json"))}
    for name, repo in manifest["marketplaces"].items():
        if name not in known:
            say("market", f"add {name} ({repo})")
            if apply:
                claude("marketplace", "add", repo)
    for plugin in manifest["plugins"]:
        state = plugins.get(plugin)
        if state is None:
            say("plugin", f"install {plugin}")
            if apply:
                claude("install", plugin, "--scope", "user")
        elif not state.get("enabled"):
            say("plugin", f"enable {plugin}")
            if apply:
                claude("enable", plugin)
    if not apply:
        return
    for name in manifest["marketplaces"]:
        claude("marketplace", "update", name)
    for plugin in manifest["plugins"]:
        before = plugins.get(plugin, {}).get("version")
        claude("update", plugin, check=False)
        after = next((p.get("version") for p in json.loads(claude("list", "--json")) if p["id"] == plugin), None)
        if before and after and before != after:
            say("updated", f"{plugin} {before} -> {after} (restart Claude Code to load it)")


if __name__ == "__main__":
    main(sys.argv[1:])
