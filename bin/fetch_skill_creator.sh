#!/usr/bin/env bash
# Materialize anthropics/skills @ pinned SHA into third_party/skill-creator/.
# Idempotent. Same script local and in CI.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
sha="$(tr -d '[:space:]' < "$repo_root/.skill-creator-version")"
dest="$repo_root/third_party/skill-creator"
marker="$dest/.fetched-sha"

if [[ -f "$marker" && "$(cat "$marker")" == "$sha" ]]; then
  echo "skill-creator @ $sha already present"
  exit 0
fi

rm -rf "$dest"
mkdir -p "$dest"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git clone --quiet --filter=blob:none --no-checkout https://github.com/anthropics/skills.git "$tmp/skills"
git -C "$tmp/skills" sparse-checkout init --cone
git -C "$tmp/skills" sparse-checkout set skills/skill-creator
git -C "$tmp/skills" checkout --quiet "$sha"

cp -a "$tmp/skills/skills/skill-creator/." "$dest/"
echo "$sha" > "$marker"
echo "skill-creator fetched @ $sha → $dest"
