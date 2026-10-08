#!/usr/bin/env python3
"""Score every changed function against Pedro's complexity limits.

Usage: measure_complexity.py BASE [HEAD] [--all | --over-only] [--repo DIR]

  BASE         base revision; the diff starts at merge-base(BASE, HEAD).
               EMPTY measures every tracked file (whole-repository scope).
  HEAD         revision to measure. Omit it to measure the working tree,
               including uncommitted and untracked files.
  --all        list every function in the changed files, not only changed ones.
  --over-only  list only functions over a limit (summary counts still print).
  --repo       repository or worktree to measure (default: current directory).

The script finds each changed file's .oxlintrc.json, copies only its complexity
rules (classic `complexity` and any `*/cognitive-complexity` plugin rule, with
their file overrides and jsPlugins) into a temporary config with max 0, and runs
the repository's own oxlint with --format json through host-check. It never
edits the repository: files are copied (or extracted from HEAD) into a
temporary tree. Limits: cognitive above 8 and cyclomatic above 16 are over;
8 and 16 pass. When a function is over, a second pass runs the same rules with
the repository's real levels and maxes and tags it `[lint: error]`,
`[lint: warning]`, or `[lint passes]`, so the report can tell a lint failure
from an excess the repository's lint lets through. Exit status is 0 whenever
measurement succeeds, over or not; 2 means the measurement itself failed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

COGNITIVE_LIMIT = 8
CYCLOMATIC_LIMIT = 16
HOST_CHECK = os.path.expanduser("~/.local/bin/host-check")
SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}
CATEGORIES = ("correctness", "suspicious", "pedantic", "perf", "style", "restriction", "nursery")
SCORE = re.compile(r"complexity (?:of )?(\d+)")
NAME = re.compile(r"`([^`]*)`")


@dataclass
class Function:
    path: str
    name: str
    line: int
    end_line: int
    cognitive: int | None = None
    cyclomatic: int | None = None
    lint: dict[str, str] | None = None  # metric -> severity under the repo's real rules

    def lint_tag(self) -> str:
        """How the repository's own lint treats this function's excess."""
        if self.lint is None:
            return ""
        metrics = [note.split()[0] for note in self.over()]
        severities = {self.lint.get(metric) for metric in metrics}
        if None in severities:
            return " [lint passes]"
        return " [lint: error]" if severities == {"error"} else " [lint: warning]"

    def over(self) -> list[str]:
        notes = []
        if self.cognitive is not None and self.cognitive > COGNITIVE_LIMIT:
            notes.append(f"cognitive {self.cognitive} > {COGNITIVE_LIMIT}")
        if self.cyclomatic is not None and self.cyclomatic > CYCLOMATIC_LIMIT:
            notes.append(f"cyclomatic {self.cyclomatic} > {CYCLOMATIC_LIMIT}")
        return notes


def git(root: Path, *args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {result.stderr.decode().strip()}")
    return result.stdout if binary else result.stdout.decode()


def strip_jsonc(text: str) -> str:
    """Drop // and /* */ comments outside strings, then trailing commas."""
    out, i, in_string = [], 0, False
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\":
                out.append(text[i + 1])
                i += 1
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
            out.append(ch)
        elif text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                break
            continue
        elif text.startswith("/*", i):
            i = text.find("*/", i) + 2
            continue
        else:
            out.append(ch)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def is_complexity_rule(name: str) -> bool:
    return name in ("complexity", "eslint/complexity") or name.endswith("cognitive-complexity")


def is_off(value: object) -> bool:
    level = value[0] if isinstance(value, list) and value else value
    return level in ("off", 0, "allow")


def measuring(value: object) -> object:
    if is_off(value):
        return "off"
    options = value[1] if isinstance(value, list) and len(value) > 1 and isinstance(value[1], dict) else {}
    return ["warn", {**options, "max": 0}]


def complexity_rules(rules: dict, transform=measuring) -> dict:
    return {name: transform(value) for name, value in rules.items() if is_complexity_rule(name)}


def looser_than_limits(name: str, value: object) -> str | None:
    """Describe how a repo rule definition lets a Pedro-limit excess through."""
    if is_off(value):
        return "turns it off"
    level = value[0] if isinstance(value, list) and value else value
    options = value[1] if isinstance(value, list) and len(value) > 1 and isinstance(value[1], dict) else {}
    limit = COGNITIVE_LIMIT if name.endswith("cognitive-complexity") else CYCLOMATIC_LIMIT
    reasons = []
    if level not in ("error", 2, "deny"):
        reasons.append(f"level {level!r}")
    if not isinstance(options.get("max"), int):
        reasons.append("no explicit max (rule default)")
    elif options["max"] > limit:
        reasons.append(f"max {options['max']} > {limit}")
    return ", ".join(reasons) or None


def measure_config(config: dict) -> tuple[dict, dict, list[str], list[str]]:
    """Return the max-0 config, the repo-rules config, the plugin paths they need, and coverage notes."""
    notes: list[str] = []
    top = complexity_rules(config.get("rules", {}))
    lint_top = complexity_rules(config.get("rules", {}), transform=lambda value: value)
    overrides, lint_overrides = [], []
    for name, value in lint_top.items():
        if reason := looser_than_limits(name, value):
            notes.append(f"top-level `{name}` {reason}; lint does not enforce Pedro's limit there")
    for override in config.get("overrides", []):
        rules = complexity_rules(override.get("rules", {}))
        if rules:
            overrides.append({"files": override["files"], "rules": rules})
            lint_rules = complexity_rules(override["rules"], transform=lambda value: value)
            lint_overrides.append({"files": override["files"], "rules": lint_rules})
            for name, value in lint_rules.items():
                if reason := looser_than_limits(name, value):
                    notes.append(f"override {override['files']} `{name}` {reason}; "
                                 "lint does not enforce Pedro's limit for those files")
    names = set(top) | {name for o in overrides for name in o["rules"]}
    if not names:
        top["complexity"] = ["warn", {"max": 0, "variant": "classic"}]
        names.add("complexity")
        notes.append("config has no complexity rule; used oxlint classic `complexity` everywhere")
    if not any(name.endswith("cognitive-complexity") for name in names):
        notes.append("config has no cognitive-complexity rule; cognitive scores are NOT measured (coverage incomplete)")
    if "extends" in config:
        notes.append("config uses `extends`; complexity rules defined in extended files were not copied")
    prefixes = {name.split("/")[0] for name in names if "/" in name}
    plugins, plugin_paths = [], []
    for plugin in config.get("jsPlugins", []):
        specifier = plugin if isinstance(plugin, str) else plugin.get("specifier", "")
        if isinstance(plugin, dict) and plugin.get("name") not in prefixes:
            continue
        plugins.append(plugin)
        if specifier.startswith("."):
            plugin_paths.append(specifier)
    measured = {
        "categories": {category: "off" for category in CATEGORIES},
        "ignorePatterns": config.get("ignorePatterns", []),
        "rules": top,
        "overrides": overrides,
    }
    enforced = {**measured, "rules": lint_top, "overrides": lint_overrides}
    if plugins:
        measured["jsPlugins"] = enforced["jsPlugins"] = plugins
    return measured, enforced, plugin_paths, notes


def changed_files(root: Path, base: str, head: str | None) -> list[str]:
    files = git(root, "diff", "--name-only", "--diff-filter=d", "-z", base, *([head] if head else [])).split("\0")
    if head is None:
        files += git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    return sorted({f for f in files if f and PurePosixPath(f).suffix in SOURCE_SUFFIXES})


def changed_lines(root: Path, base: str, head: str | None, files: list[str]) -> dict[str, set[int] | None]:
    """Map each file to its added or modified lines; None means the whole file."""
    lines: dict[str, set[int] | None] = {}
    current = None
    diff = git(root, "diff", "-U0", "--no-color", "--no-ext-diff", base, *([head] if head else []), "--", *files)
    for row in diff.splitlines():
        if row.startswith("+++ "):
            current = row[6:] if row.startswith("+++ b/") else None
            if current:
                lines.setdefault(current, set())
        elif row.startswith("@@") and current:
            match = re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", row)
            start, count = int(match.group(1)), int(match.group(2) or 1)
            target = lines[current]
            if target is not None:
                target.update(range(start, start + count) if count else (start, start + 1))
    for path in files:
        lines.setdefault(path, None)  # untracked: every line is new
    return lines


def owning_config(path: str, configs: list[str]) -> str | None:
    best = None
    for config in configs:
        directory = str(PurePosixPath(config).parent)
        if directory == "." or path.startswith(directory + "/"):
            if best is None or len(directory) > len(str(PurePosixPath(best).parent)):
                best = config
    return best


def find_oxlint(root: Path, config_dir: Path) -> Path | None:
    directory = config_dir
    while True:
        candidate = directory / "node_modules/.bin/oxlint"
        if candidate.exists():
            return candidate
        if directory == root or directory == directory.parent:
            return None
        directory = directory.parent


def materialize(root: Path, head: str | None, paths: list[str], tree: Path) -> None:
    if head:
        archive = subprocess.run(
            ["git", "-C", str(root), "archive", "--format=tar", head, "--", *paths],
            capture_output=True,
            check=True,
        )
        subprocess.run(["tar", "-x", "-C", str(tree)], input=archive.stdout, check=True)
        return
    for path in paths:
        source, target = root / path, tree / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("node_modules"))
        elif source.exists():
            shutil.copy2(source, target)


def run_oxlint(root: Path, oxlint: Path, config: Path, files: list[Path]) -> list[dict]:
    command = [str(oxlint), "-c", str(config), "--format", "json", *map(str, files)]
    if os.environ.get("HOST_CHECK_ACTIVE") != "1" and os.access(HOST_CHECK, os.X_OK):
        command.insert(0, HOST_CHECK)
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    try:
        return json.loads(result.stdout)["diagnostics"]
    except (json.JSONDecodeError, KeyError):
        sys.stderr.write(result.stdout + result.stderr)
        sys.exit(f"oxlint did not return JSON (exit {result.returncode}); command: {' '.join(command)}")


def collect(diagnostics: list[dict], tree: Path) -> dict[tuple[str, int, int], Function]:
    functions: dict[tuple[str, int, int], Function] = {}
    for diagnostic in diagnostics:
        code, message = diagnostic.get("code", ""), diagnostic.get("message", "")
        score, name, labels = SCORE.search(message), NAME.search(message), diagnostic.get("labels") or []
        if not score or not labels:
            continue
        span = labels[0]["span"]
        file = Path(diagnostic["filename"])
        path = str(file.relative_to(tree)) if file.is_absolute() else diagnostic["filename"]
        key = (path, span["offset"], span["length"])
        if key not in functions:
            body = (tree / path).read_bytes()[span["offset"] : span["offset"] + span["length"]]
            functions[key] = Function(path, name.group(1) if name else "<anonymous>", span["line"], span["line"] + body.count(b"\n"))
        if "cognitive-complexity" in code:
            functions[key].cognitive = int(score.group(1))
            functions[key].lint = {**(functions[key].lint or {}), "cognitive": diagnostic.get("severity", "")}
        elif code.endswith("(complexity)"):
            functions[key].cyclomatic = int(score.group(1))
            functions[key].lint = {**(functions[key].lint or {}), "cyclomatic": diagnostic.get("severity", "")}
    return functions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("base")
    parser.add_argument("head", nargs="?")
    listing = parser.add_mutually_exclusive_group()
    listing.add_argument("--all", action="store_true", help="list unchanged functions in changed files too")
    listing.add_argument("--over-only", action="store_true", help="list only functions over a limit")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()

    root = Path(git(Path(args.repo), "rev-parse", "--show-toplevel").strip())
    if args.base == "EMPTY":  # whole-repository scope: diff from the empty tree
        merge_base = git(root, "hash-object", "-t", "tree", "/dev/null").strip()
    else:
        merge_base = git(root, "merge-base", args.base, args.head or "HEAD").strip()
    head_label = args.head or "working tree"
    files = changed_files(root, merge_base, args.head)
    print(f"Complexity of {root} {args.base}..{head_label} (merge-base {merge_base[:10]})")
    print(f"Limits: cognitive > {COGNITIVE_LIMIT}, cyclomatic > {CYCLOMATIC_LIMIT} (equal passes)")
    if not files:
        print("No changed JS/TS files.\nResult: 0 functions over threshold (nothing to measure).")
        return 0

    if args.head:
        listing = git(root, "ls-tree", "-r", "--name-only", "-z", args.head).split("\0")
    else:
        listing = git(root, "ls-files", "-z").split("\0")
    configs = [p for p in listing if PurePosixPath(p).name == ".oxlintrc.json" and "node_modules/" not in p]
    groups: dict[str, list[str]] = {}
    unowned = []
    for path in files:
        config = owning_config(path, configs)
        (groups.setdefault(config, []) if config else unowned).append(path)

    lines = changed_lines(root, merge_base, args.head, files)
    functions: list[Function] = []
    notes: list[str] = []
    with tempfile.TemporaryDirectory(prefix="measure-complexity-") as tmp:
        tree = Path(tmp)
        for config_path, group in groups.items():
            config_dir = str(PurePosixPath(config_path).parent)
            text = git(root, "show", f"{args.head}:{config_path}") if args.head else (root / config_path).read_text()
            measured, enforced, plugin_paths, config_notes = measure_config(json.loads(strip_jsonc(text)))
            notes += [f"{config_path}: {note}" for note in config_notes]
            plugin_dirs = [str(PurePosixPath(config_dir, p).parent) for p in plugin_paths]
            materialize(root, args.head, group + [os.path.normpath(d) for d in plugin_dirs], tree)
            for directory in {".", config_dir}:
                if (root / directory / "node_modules").exists() and not (tree / directory / "node_modules").exists():
                    (tree / directory).mkdir(parents=True, exist_ok=True)
                    (tree / directory / "node_modules").symlink_to(root / directory / "node_modules")
            oxlint = find_oxlint(root, root / config_dir)
            if oxlint is None:
                sys.exit(f"No node_modules/.bin/oxlint at or above {root / config_dir}; install dependencies first.")
            temp_config = tree / config_dir / ".oxlintrc.json"
            temp_config.write_text(json.dumps(measured, indent=2))
            print(f"Config: {config_path} -> {len(group)} file(s); rules: "
                  + ", ".join(sorted({n for n in measured['rules']} | {n for o in measured['overrides'] for n in o['rules']})))
            found = collect(run_oxlint(root, oxlint, temp_config, [tree / p for p in group]), tree)
            for function in found.values():
                function.lint = None  # the max-0 pass says nothing about enforcement
            over_paths = sorted({f.path for f in found.values() if f.over()})
            if over_paths:  # second pass: the repository's real levels and maxes
                temp_config.write_text(json.dumps(enforced, indent=2))
                real = collect(run_oxlint(root, oxlint, temp_config, [tree / p for p in over_paths]), tree)
                for key, function in found.items():
                    if function.over():
                        function.lint = real[key].lint if key in real else {}
            functions += found.values()
            scored = {f.path for f in found.values()}
            unscored = [path for path in group if path not in scored]
            if unscored:
                notes.append(f"{len(unscored)} file(s) got no scores (outside the config's complexity scope, "
                             f"e.g. tests, or no functions): {', '.join(unscored)}")
        for path in unowned:
            notes.append(f"{path}: no .oxlintrc.json owns this file; not measured")

    def is_changed(function: Function) -> bool:
        touched = lines.get(function.path)
        return touched is None or any(function.line <= n <= function.end_line for n in touched)

    changed = [f for f in functions if is_changed(f)]
    shown = functions if args.all else changed
    if args.over_only:
        shown = [f for f in shown if f.over()]
    trivial = [f for f in shown if (f.cyclomatic or 0) <= 1 and not f.cognitive]
    shown = [f for f in shown if f not in trivial]
    print()
    current = None
    for function in sorted(shown, key=lambda f: (f.path, f.line)):
        if function.path != current:
            current = function.path
            print(current)
        cognitive = "-" if function.cognitive is None else str(function.cognitive)
        cyclomatic = "-" if function.cyclomatic is None else str(function.cyclomatic)
        flag = "  OVER: " + "; ".join(function.over()) + function.lint_tag() if function.over() else ""
        mark = "" if not args.all or is_changed(function) else " (unchanged)"
        print(f"  L{function.line}-{function.end_line} {function.name}{mark}: cognitive {cognitive}, cyclomatic {cyclomatic}{flag}")
    if not shown:
        print("(no functions to list)")
    if trivial:
        print(f"({len(trivial)} trivial functions with cyclomatic 1 and cognitive 0 not listed)")
    if notes:
        print("\nCoverage notes:")
        for note in notes:
            print(f"  {note}")
    print("\n'-' cognitive: score 0, or counted inside the enclosing function (nested callbacks).")
    over = [f for f in changed if f.over()]
    passing = [f for f in over if f.lint_tag() == " [lint passes]"]
    print(f"Result: {len(over)} function{'s' if len(over) != 1 else ''} over threshold "
          f"among {len(changed)} changed functions in {len(files)} changed JS/TS files"
          f" ({len(over) - len(passing)} fail the repository's lint, {len(passing)} pass it).")
    for function in over:
        print(f"  {function.path}:{function.line} {function.name}: {'; '.join(function.over())}{function.lint_tag()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
