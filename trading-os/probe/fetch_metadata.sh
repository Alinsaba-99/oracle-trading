#!/usr/bin/env bash
# BL-719 pre-step: probe GitHub metadata for every repo slug in repo_slugs.txt
# Output: metadata.tsv (slug<TAB>stars<TAB>pushed_at<TAB>license<TAB>archived<TAB>language)
set -uo pipefail
cd "$(dirname "$0")"
: > metadata.tsv
while read -r slug; do
  gh api "repos/$slug" --jq '[.full_name, (.stargazers_count|tostring), .pushed_at, (.license.spdx_id // "NONE"), (.archived|tostring), (.language // "?")] | @tsv' 2>/dev/null >> metadata.tsv || printf '%s\tAPI_ERROR\t\t\t\t\n' "$slug" >> metadata.tsv
done < repo_slugs.txt
wc -l metadata.tsv
