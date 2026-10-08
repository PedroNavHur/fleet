#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s --base <ref> [--repo <path>]\n' "${0##*/}"
}

base_ref=""
repo_arg="."

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      base_ref=$2
      shift 2
      ;;
    --repo)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      repo_arg=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ -n "$base_ref" ]] || { printf '%s\n' 'Missing required --base ref.' >&2; usage >&2; exit 2; }
command -v git >/dev/null 2>&1 || { printf '%s\n' 'git is required.' >&2; exit 127; }

repo_root=$(git -C "$repo_arg" rev-parse --show-toplevel 2>/dev/null) || {
  printf 'Not a Git repository: %s\n' "$repo_arg" >&2
  exit 2
}

prefer_direct=false
case "$base_ref" in
  HEAD|@|*HEAD|*^*|*~*|*@\{*|[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]*)
    prefer_direct=true
    ;;
esac
if git -C "$repo_root" show-ref --verify --quiet "refs/tags/$base_ref"; then
  prefer_direct=true
fi

if [[ "$prefer_direct" == false && "$base_ref" != */* ]] && git -C "$repo_root" show-ref --verify --quiet "refs/remotes/origin/$base_ref"; then
  resolved_ref="refs/remotes/origin/$base_ref"
elif git -C "$repo_root" rev-parse --verify --quiet "${base_ref}^{commit}" >/dev/null; then
  resolved_ref=$base_ref
else
  printf 'Unable to resolve base ref: %s\n' "$base_ref" >&2
  printf '%s\n' 'Available local and origin refs:' >&2
  git -C "$repo_root" for-each-ref --format='  %(refname:short)' refs/heads refs/remotes/origin >&2
  exit 2
fi

base_commit=$(git -C "$repo_root" rev-parse --verify "${resolved_ref}^{commit}")
head_commit=$(git -C "$repo_root" rev-parse --verify 'HEAD^{commit}')
merge_base=$(git -C "$repo_root" merge-base "$base_commit" "$head_commit")
review_range="${base_commit}...${head_commit}"

printf 'scope_resolved repo=%q requested_base=%q resolved_base=%q base_commit=%s merge_base=%s head_commit=%s range=%s\n' \
  "$repo_root" "$base_ref" "$resolved_ref" "$base_commit" "$merge_base" "$head_commit" "$review_range"

diff_status=0
git -C "$repo_root" diff --quiet "$review_range" -- || diff_status=$?
if [[ $diff_status -eq 0 ]]; then
  printf 'scope_empty base_commit=%s head_commit=%s\n' "$base_commit" "$head_commit"
  exit 3
fi
if [[ $diff_status -ne 1 ]]; then
  printf 'Unable to inspect committed diff for range %s\n' "$review_range" >&2
  exit "$diff_status"
fi

printf '%s\n' 'scope_ready'
