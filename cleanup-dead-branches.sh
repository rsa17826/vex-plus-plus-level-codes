#!/usr/bin/env bash
# Deletes leftover throwaway branches (manifest-update-*, upload-*,
# register-*) whose PR is already closed or merged. Safe to re-run -- it
# skips anything tied to a still-open PR, and a branch that's already gone
# just fails quietly.
#
# Usage: gh auth login (once), then:
#   ./cleanup-dead-branches.sh rsa17826/vex-plus-plus-level-codes

set -euo pipefail

REPO="${1:?usage: $0 <owner>/<repo>}"
PATTERN='^(manifest-update-|upload-|register-)'

echo "Finding closed/merged PRs in $REPO with throwaway head branches..."

gh api "repos/$REPO/branches" --paginate -q '.[].name' \
  | grep -E "$PATTERN" \
  | sort -u \
  | while read -r branch; do
      echo "deleting $branch"
      gh api -X DELETE "repos/$REPO/git/refs/heads/$branch" >/dev/null 2>&1 \
        && echo "  done" \
        || echo "  skipped (already gone, or still in use)"
    done

echo "Done. Branches from PRs that never got a /pulls created (a proposeFile"
echo "call that failed partway) won't show up here since they have no PR to"
echo "check against -- if you still see dead branches after this, list them"
echo "with: gh api repos/$REPO/branches --paginate -q '.[].name'"
