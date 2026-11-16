#!/usr/bin/env bash
set -euo pipefail

bump="${1:-patch}"
if [[ $# -gt 1 || ! "$bump" =~ ^(patch|minor|major)$ ]]; then
  echo 'Usage: scripts/release.sh [patch|minor|major]' >&2
  exit 2
fi

if [[ "$(git config user.name)" != 'Kyxie' || "$(git config user.email)" != 'kyriexie@outlook.com' ]]; then
  echo 'Git identity must be Kyxie <kyriexie@outlook.com>.' >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Commit or remove working tree changes before releasing.' >&2
  exit 1
fi

branch="$(git symbolic-ref --quiet --short HEAD)" || {
  echo 'Release from a branch, not detached HEAD.' >&2
  exit 1
}

git fetch --quiet origin "$branch" --tags
remote_head="$(git ls-remote origin "refs/heads/$branch" | awk '{print $1}')"
if [[ -z "$remote_head" ]] || ! git merge-base --is-ancestor "$remote_head" HEAD; then
  echo "Local $branch is behind or diverged from origin/$branch; pull first." >&2
  exit 1
fi

latest="$(git tag --list 'v*.*.*' --sort=-version:refname | grep -Em1 '^v[0-9]+\.[0-9]+\.[0-9]+$' || true)"
version="${latest:-v0.0.0}"
IFS=. read -r major minor patch <<< "${version#v}"
case "$bump" in
  patch) patch=$((patch + 1)) ;;
  minor) minor=$((minor + 1)); patch=0 ;;
  major) major=$((major + 1)); minor=0; patch=0 ;;
esac
new_tag="v$major.$minor.$patch"

git tag "$new_tag"
if ! git push --atomic origin "HEAD:refs/heads/$branch" "refs/tags/$new_tag" >&2; then
  git tag --delete "$new_tag" >/dev/null
  echo 'Release push failed; local release tag was removed.' >&2
  exit 1
fi

echo "$new_tag"
