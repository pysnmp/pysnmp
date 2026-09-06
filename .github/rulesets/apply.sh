#!/usr/bin/env bash
#
# Apply every ruleset in this directory to the repository on GitHub, and the
# repository settings in repo-settings.json alongside them.
#
# Rulesets are matched to what is already on the repository by name: a ruleset
# whose name is not there yet is created, one that is gets overwritten. Running
# this twice in a row is a no-op, so it is safe to re-run after every edit.
#
# Needs a token with administration:write on the repository -- either the one
# `gh auth login` holds, or GH_TOKEN/GITHUB_TOKEN in the environment. The
# token that GitHub Actions hands a workflow cannot do this; the rulesets are
# what stops a workflow from rewriting the branches it is gated by.
#
# Rulesets on the repository that this directory does not define are left
# alone and listed at the end. GitHub applies every ruleset that matches a
# branch, so a leftover one still binds: a stray "require 1 approval" rule
# blocks a lone maintainer no matter what is written here. --prune deletes
# them once you have read the list.
#
#   ./.github/rulesets/apply.sh              # this repository, from `origin`
#   ./.github/rulesets/apply.sh --dry-run    # print what would be sent
#   ./.github/rulesets/apply.sh --prune      # also delete the ones listed
#   ./.github/rulesets/apply.sh owner/repo   # somewhere else
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=0
PRUNE=0
REPO=""

usage() { sed -n '2,/^[^#]/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'; }

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --prune) PRUNE=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "unknown option: $arg" >&2; exit 2 ;;
    *) REPO="$arg" ;;
  esac
done

if [ -z "$REPO" ]; then
  # Both the ssh and https forms of the remote, with or without the .git suffix.
  remote="$(git -C "$DIR" remote get-url origin)"
  REPO="$(printf '%s\n' "$remote" | sed -E 's#^(git@|https://)[^:/]+[:/]##; s#\.git$##')"
fi

case "$REPO" in
  */*) ;;
  *) echo "could not work out owner/repo from '$REPO'" >&2; exit 1 ;;
esac

command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }

if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  USE_GH=1
else
  USE_GH=0
  TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
  [ -n "$TOKEN" ] || {
    echo "no gh login and no GH_TOKEN/GITHUB_TOKEN; need administration:write" >&2
    exit 1
  }
fi

api() { # api METHOD PATH [BODY_FILE]
  local method="$1" path="$2" body="${3:-}"
  if [ "$USE_GH" = 1 ]; then
    if [ -n "$body" ]; then
      gh api -X "$method" -H "Accept: application/vnd.github+json" "$path" --input "$body"
    else
      gh api -X "$method" -H "Accept: application/vnd.github+json" "$path"
    fi
  else
    local -a args=(
      -sS --fail-with-body -X "$method"
      -H "Authorization: Bearer $TOKEN"
      -H "Accept: application/vnd.github+json"
      -H "X-GitHub-Api-Version: 2022-11-28"
    )
    # The API rejects a body sent as form data, so name the type even when
    # there is no body: curl labels an empty POST as form-encoded otherwise.
    args+=(-H "Content-Type: application/json")
    [ -n "$body" ] && args+=(--data-binary "@$body")
    curl "${args[@]}" "https://api.github.com/$path"
  fi
}

echo "repository: $REPO"
existing="$(api GET "repos/$REPO/rulesets?per_page=100")"

managed=()
for file in "$DIR"/*.json; do
  [ -e "$file" ] || continue
  # Everything here is a ruleset except the repository settings, applied below
  # against a different endpoint.
  [ "$(basename "$file")" = repo-settings.json ] && continue
  name="$(jq -r '.name' "$file")"
  managed+=("$name")
  id="$(jq -r --arg n "$name" 'map(select(.name == $n)) | first | .id // empty' <<<"$existing")"

  if [ "$DRY_RUN" = 1 ]; then
    if [ -n "$id" ]; then
      echo "would update '$name' (id $id) from $(basename "$file")"
    else
      echo "would create '$name' from $(basename "$file")"
    fi
    continue
  fi

  if [ -n "$id" ]; then
    api PUT "repos/$REPO/rulesets/$id" "$file" | jq -r '"updated  \(.name) (id \(.id), \(.enforcement))"'
  else
    api POST "repos/$REPO/rulesets" "$file" | jq -r '"created  \(.name) (id \(.id), \(.enforcement))"'
  fi
done

# A required check that never reports is indistinguishable, to a pull request,
# from one that is failing, and GitHub disables a workflow carrying a schedule
# trigger after sixty days of repository inactivity. Say so before the rules
# start depending on it.
inactive="$(api GET "repos/$REPO/actions/workflows?per_page=100" |
  jq -r '.workflows[] | select(.state != "active") | "  \(.name) (\(.path)): \(.state)"')"
if [ -n "$inactive" ]; then
  echo
  echo "warning: these workflows are not active and report no checks:"
  echo "$inactive"
  echo "a required check from one of them would block every pull request."
fi

settings="$DIR/repo-settings.json"
if [ -f "$settings" ]; then
  if [ "$DRY_RUN" = 1 ]; then
    echo "would set repository settings $(jq -c . "$settings")"
  else
    api PATCH "repos/$REPO" "$settings" |
      jq -r '"settings delete_branch_on_merge=\(.delete_branch_on_merge) allow_auto_merge=\(.allow_auto_merge)"'
  fi
fi

# Anything else on the repository was made by hand and is not tracked here.
# Left alone rather than deleted -- say so, and let a human decide.
unmanaged="$(jq -r --argjson m "$(printf '%s\n' "${managed[@]}" | jq -R . | jq -s .)" \
  '.[] | select(.source_type == "Repository") | select(.name as $n | $m | index($n) | not)
   | "  \(.name) (id \(.id), \(.enforcement))"' <<<"$existing")"

if [ -z "$unmanaged" ]; then
  exit 0
fi

echo
echo "rulesets on this repository that are not defined here:"
echo "$unmanaged"

if [ "$PRUNE" != 1 ]; then
  # Every matching ruleset applies, so one of these can still block a merge no
  # matter what this directory says. Listing beats deleting something a human
  # added on purpose.
  echo "re-run with --prune to delete them, once you have read the list."
  exit 0
fi

while read -r id; do
  [ -n "$id" ] || continue
  if [ "$DRY_RUN" = 1 ]; then
    echo "would delete ruleset $id"
  else
    api DELETE "repos/$REPO/rulesets/$id" >/dev/null
    echo "deleted  ruleset $id"
  fi
done <<<"$(printf '%s\n' "$unmanaged" | sed -E 's/.*\(id ([0-9]+),.*/\1/')"
