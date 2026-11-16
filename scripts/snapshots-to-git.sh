#!/bin/sh
# Turns the snapshots in .phase-snapshots/ into git history: one commit per snapshot, in order,
# and one tag per finished phase.
#
# Why this exists: the improvement work (ROADMAP.md) was done on a machine where the assistant was
# not allowed to commit, and this folder was not a git repository. Each unit of work was saved as a
# full copy of the project instead (.phase-snapshots/NN/tree, with its commit message in
# message.txt and, at the end of a phase, a tag name in tag.txt).
#
#   sh scripts/snapshots-to-git.sh --dry-run   # only lists what it would commit
#   sh scripts/snapshots-to-git.sh             # does it
#
# What it does:
#   - creates the repository (it refuses to run if this folder already is one)
#   - commits snapshot 00, the project before the improvement work, on `main`
#   - commits every later snapshot on the branch named below, tagging the end of each phase
#   - never touches your working files: it reads the snapshot folders, nothing else
#
# Nothing is pushed. Real .env files are never committed: the snapshots don't contain them, and
# .gitignore excludes them.
#
# NOT RUN YET: it could not be tested where it was written (commits need your approval there).
# The dry run is safe to try first. If a real run stops half-way, delete the .git folder it made
# and nothing else has changed.
set -eu

BRANCH="improve/reliability-accuracy-readiness"
TRAILER="Co-Authored-By: Claude <noreply@anthropic.com>"

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SNAPSHOTS="$ROOT/.phase-snapshots"
DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
elif [ -n "${1:-}" ]; then
  echo "Unknown option: $1 (the only option is --dry-run)" >&2
  exit 2
fi

command -v git >/dev/null 2>&1 || { echo "git is not installed." >&2; exit 1; }
[ -d "$SNAPSHOTS/00/tree" ] || { echo "No snapshots found in $SNAPSHOTS." >&2; exit 1; }

for dir in "$SNAPSHOTS"/[0-9][0-9]; do
  [ -d "$dir/tree" ] || { echo "$dir has no tree folder." >&2; exit 1; }
  [ -s "$dir/message.txt" ] || { echo "$dir has no message.txt." >&2; exit 1; }
  # A real settings file must never be committed. (.env.example is the documented template.)
  leaked=$(find "$dir/tree" -name '.env*' ! -name '.env.example' | head -1)
  [ -z "$leaked" ] || { echo "Refusing: a real settings file is in a snapshot: $leaked" >&2; exit 1; }
done

if [ "$DRY_RUN" = 1 ]; then
  echo "Dry run: nothing is changed. This is what would be committed, in order:"
  for dir in "$SNAPSHOTS"/[0-9][0-9]; do
    n=$(basename "$dir")
    if [ "$n" = 00 ]; then where="main"; else where="$BRANCH"; fi
    echo ""
    echo "  $n on $where ($(find "$dir/tree" -type f | wc -l | tr -d ' ') files)"
    echo "     $(head -1 "$dir/message.txt")"
    [ -f "$dir/tag.txt" ] && echo "     tag: $(head -1 "$dir/tag.txt")"
  done
  exit 0
fi

if [ -e "$ROOT/.git" ]; then
  echo "This folder is already a git repository, so nothing was done." >&2
  echo "The snapshots are still in .phase-snapshots/ if you want to commit them by hand." >&2
  exit 1
fi

GIT_DIR="$ROOT/.git"
export GIT_DIR
git init -q -b main

for dir in "$SNAPSHOTS"/[0-9][0-9]; do
  n=$(basename "$dir")
  # The snapshot folder is the work tree for this one commit; the real project files are not read.
  cd "$dir/tree"
  git --work-tree=. add -A
  if [ "$n" != 00 ] && git --work-tree=. diff --cached --quiet; then
    echo "$n: no change from the snapshot before it, skipped"
    continue
  fi
  git --work-tree=. commit -q -m "$(cat "$dir/message.txt")" -m "$TRAILER"
  echo "$n: committed: $(head -1 "$dir/message.txt")"
  if [ "$n" = 00 ]; then
    # Everything after the baseline goes on the improvement branch. This moves HEAD only.
    git branch "$BRANCH"
    git symbolic-ref HEAD "refs/heads/$BRANCH"
  fi
  if [ -f "$dir/tag.txt" ]; then
    tag=$(head -1 "$dir/tag.txt")
    git tag "$tag"
    echo "$n: tagged $tag"
  fi
done

cd "$ROOT"
echo ""
echo "Done. You are on the branch $BRANCH; main holds the project as it was before."
echo "Files that differ between your folder and the last commit (nothing listed = identical):"
git --work-tree="$ROOT" status --short
echo ""
echo "Look at the history with:  git log --oneline --decorate"
echo "When you are happy, merge it:  git switch main && git merge $BRANCH"
