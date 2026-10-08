#!/usr/bin/env bash

set -euo pipefail

ROOT="${1:-$(pwd)}"
if [ "$#" -gt 0 ]; then
  shift
fi

REQUESTED_STEP="all"
if [ "${1:-}" = "--step" ]; then
  REQUESTED_STEP="${2:-}"
  shift 2 || true
fi
if [ "$#" -ne 0 ]; then
  echo "ERROR: usage: $0 [repository] [--step format|lint|typecheck|tests]" >&2
  exit 2
fi
case "$REQUESTED_STEP" in
  all|format|lint|typecheck|tests) ;;
  *)
    echo "ERROR: unknown quality-check step: $REQUESTED_STEP" >&2
    exit 2
    ;;
esac

cd "$ROOT"

# Discover a repository environment here so the deterministic check behaves
# consistently in primary and linked worktrees.
COMMON_GIT_DIR="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
PRIMARY_ROOT=""
if [ -n "$COMMON_GIT_DIR" ]; then
  PRIMARY_ROOT="$(dirname "$COMMON_GIT_DIR")"
fi
if [ -d "$ROOT/.venv/bin" ]; then
  export PATH="$ROOT/.venv/bin:$PATH"
elif [ -n "$PRIMARY_ROOT" ] && [ -d "$PRIMARY_ROOT/.venv/bin" ]; then
  export PATH="$PRIMARY_ROOT/.venv/bin:$PATH"
fi

FAILED=0
ATTEMPTED=0
HAVE_PKG_JSON=false
if [ -f package.json ]; then
  HAVE_PKG_JSON=true
fi

should_run() {
  [ "$REQUESTED_STEP" = "all" ] || [ "$REQUESTED_STEP" = "$1" ]
}

run_step() {
  local name="$1"
  local cmd="$2"

  ATTEMPTED=$((ATTEMPTED + 1))
  echo "--- $name"
  echo "COMMAND: $cmd"
  if "${SHELL:-/bin/bash}" -lc "$cmd"; then
    echo "PASS: $name"
  else
    echo "FAIL: $name"
    FAILED=$((FAILED + 1))
  fi
}

package_script_exists() {
  local script_name="$1"
  node -e "const fs = require('fs'); try { const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8')); process.exit(pkg.scripts && Object.prototype.hasOwnProperty.call(pkg.scripts, '$script_name') ? 0 : 1); } catch { process.exit(1); }"
}

run_node_script() {
  local name="$1"
  shift
  local script
  for script in "$@"; do
    if package_script_exists "$script"; then
      run_step "$name" "$PKG_MGR run $script"
      return
    fi
  done
  echo "INFO: no Node $name script"
}

make_target_exists() {
  local target="$1"
  grep -Eq "^${target}([[:space:]]*):" Makefile
}

# Node / JS projects
if [ "$HAVE_PKG_JSON" = true ]; then
  PKG_MGR="npm"
  if [ -f pnpm-lock.yaml ] && command -v pnpm >/dev/null 2>&1; then
    PKG_MGR="pnpm"
  elif [ -f yarn.lock ] && command -v yarn >/dev/null 2>&1; then
    PKG_MGR="yarn"
  elif { [ -f bun.lockb ] || [ -f bun.lock ]; } && command -v bun >/dev/null 2>&1; then
    PKG_MGR="bun"
  elif ! command -v npm >/dev/null 2>&1; then
    if command -v yarn >/dev/null 2>&1; then
      PKG_MGR="yarn"
    elif command -v pnpm >/dev/null 2>&1; then
      PKG_MGR="pnpm"
    elif command -v bun >/dev/null 2>&1; then
      PKG_MGR="bun"
    else
      PKG_MGR=""
    fi
  fi

  if [ -n "$PKG_MGR" ]; then
    should_run format && run_node_script format format fmt
    should_run lint && run_node_script lint lint
    should_run typecheck && run_node_script typecheck typecheck type-check
    should_run tests && run_node_script tests test
  else
    echo "INFO: no Node package manager available"
  fi
fi

# Makefile-based projects
if [ -f Makefile ]; then
  if should_run format && make_target_exists format; then
    run_step format "make format"
  fi
  if should_run lint && make_target_exists lint; then
    run_step lint "make lint"
  fi
  if should_run typecheck && make_target_exists typecheck; then
    run_step typecheck "make typecheck"
  fi
  if should_run tests && make_target_exists test; then
    run_step tests "make test"
  fi
fi

# Python projects
if [ -f pyproject.toml ] || [ -f setup.py ]; then
  if should_run format; then
    if command -v ruff >/dev/null 2>&1; then
      run_step format "ruff format ."
    else
      echo "INFO: ruff is not installed"
    fi
  fi
  if should_run lint; then
    if command -v ruff >/dev/null 2>&1; then
      run_step lint "ruff check ."
    else
      echo "INFO: ruff is not installed"
    fi
  fi
  if should_run typecheck; then
    if command -v mypy >/dev/null 2>&1; then
      run_step typecheck "mypy ."
    elif command -v pyright >/dev/null 2>&1; then
      run_step typecheck "pyright ."
    else
      echo "INFO: mypy and pyright are not installed"
    fi
  fi
  if should_run tests; then
    if command -v pytest >/dev/null 2>&1; then
      run_step tests "PYTHONPATH=\"${PYTHONPATH:-.}\" pytest"
    else
      echo "INFO: pytest is not installed"
    fi
  fi
fi

if [ "$FAILED" -ne 0 ]; then
  echo "FAILED: $FAILED check(s) failed"
  exit 1
fi
if [ "$ATTEMPTED" -eq 0 ]; then
  echo "SKIP: $REQUESTED_STEP (no runnable repository check found)"
  exit 3
fi

if [ "$REQUESTED_STEP" = "all" ]; then
  echo "PASS: all available checks succeeded"
else
  echo "PASS: $REQUESTED_STEP"
fi
