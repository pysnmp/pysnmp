# Branch rulesets

The protection on `main` and `next` for this repository, kept here as JSON so
that all four pysnmp repositories can be given the same policy and so that a
change to it is reviewable like any other change.

Apply it with [`apply.sh`](apply.sh), which needs a token carrying
`administration:write`:

```console
$ ./.github/rulesets/apply.sh --dry-run
$ ./.github/rulesets/apply.sh
```

Every ruleset that matches a branch applies, so a leftover one still binds
even after this one is in place -- a stray "require 1 approval" rule blocks a
lone maintainer whatever is written here. `apply.sh` lists anything on the
repository it does not define; `--prune` deletes those, once you have read the
list.

Nothing applies these automatically. A workflow cannot: the token GitHub gives
a workflow run has no administration scope, and handing one that does to CI
would let any workflow change the rules that gate it.

## What `protected-branches.json` does

It targets `refs/heads/main` and `refs/heads/next`.

| Rule | Effect |
| --- | --- |
| `deletion` | The branch cannot be deleted. |
| `non_fast_forward` | No force pushes; history cannot be rewritten. |
| `pull_request` | Every change arrives through a pull request. |
| `required_status_checks` | The checks below must pass before merging. |

The pull request rule is set for a single maintainer:

- **`required_approving_review_count: 0`.** GitHub does not let anyone approve
  their own pull request, so any number above zero would make it impossible to
  merge anything alone. Zero still forces the change through a pull request,
  which is where the checks run and where the diff is on the record.
- **`dismiss_stale_reviews_on_push: true`** and
  **`required_review_thread_resolution: true`.** These are what make a review
  worth something when one does happen -- from a human, from Copilot, or from a
  review bot. A new push drops the old approval, and every thread has to be
  answered rather than merged past.
- **`require_last_push_approval: false`.** With one maintainer this would be
  the same deadlock as requiring an approval.

## Repository settings

`repo-settings.json` carries the two repository settings that go with a
pull-request-only workflow, applied by the same script:

- **`allow_auto_merge`.** With merging gated on checks rather than on a review,
  auto-merge is what makes that bearable alone: open the pull request, arm it,
  and it lands when CI goes green instead of being watched.
- **`delete_branch_on_merge`.** Branches cannot be deleted while a ruleset
  protects them, so the ones that are not protected should not accumulate.

## Required checks

| Check | Workflow | Covers |
| --- | --- | --- |
| `ci-gate` | `build-test-release.yml` | pre-commit, ruff, mypy, docs, build and the unit-test matrix |
| `net-snmp-gate` | `net-snmp-integration.yml` | the integration suite against a real Net-SNMP agent, over every SNMP version and security profile |
| `commitlint` | `commit-conventions.yml` | conventional-commit subjects, which is what semantic-release reads to work out a version |
| `Analyze (python)` | `codeql-analysis.yml` | CodeQL |

`ci-gate` is one job in `build-test-release.yml` that depends on every gating
job in it. It exists so that this file does not have to name the test matrix
entry by entry: those names carry the Python version and the runner
(`test-unit (py3.14 ubuntu-latest)`), the set of them changes with the labels
on a pull request, and dropping a Python version would otherwise leave a
required check that can never report again -- which is indistinguishable, to a
pull request, from a check that is failing. `ci-gate` fails if anything it
depends on failed *or was skipped*, so a matrix that never ran cannot pass as
green. `net-snmp-gate` does the same for the Net-SNMP integration matrix in
`net-snmp-integration.yml`.

Each check is pinned to `integration_id` 15368, GitHub Actions, so that only
Actions can satisfy it. Without the pin any app or token with `checks:write`
on the repository could post a passing check under the same name.

### When CI job names change

Renaming a job, or removing it, breaks the ruleset: the old name stays
required and never reports again, and pull requests to `main` and `next` stop
being mergeable. Change `protected-branches.json` in the same pull request as
the workflow, and re-run `apply.sh` once it has merged.

## Bypass

Organization owners and repository admins bypass all of it (`bypass_mode:
always`). That is not decoration -- releases depend on it.
`@semantic-release/git` pushes the `chore(release):` commit that carries the
changelog and the version bump straight to `main` or `next`, using
`SEMREL_TOKEN`. Without a bypass for whoever owns that token, every release
would fail on the pull request rule.

It doubles as the escape hatch for the maintainer. Bypassing is a deliberate
act -- pushing to the branch, or choosing to merge past the rules in the web
UI -- so the rules still apply to ordinary work, and the bypass is recorded in
the repository's rule insights.

If `SEMREL_TOKEN` is ever moved to a GitHub App rather than a personal token,
replace the two `bypass_actors` entries with the app:

```json
{"actor_id": <the app's id>, "actor_type": "Integration", "bypass_mode": "always"}
```

## What is deliberately not here

- **Tag protection.** Blocking tag deletion and non-fast-forward updates on
  `refs/tags/v*` would be worth having, but the semver alias tags are *moved*
  on purpose after each release, and a `non_fast_forward` rule on tags would
  stop that.
- **`required_linear_history`.** `next` is promoted into `main` as a merge
  commit.
- **`required_signatures`.** `@semantic-release/git` pushes over plain git and
  does not sign; requiring signatures would break every release.
- **`strict_required_status_checks_policy`** (the "branches must be up to
  date" setting) is off. Every release lands a commit on `main`, which would
  put every open pull request out of date and demand a rebase for a commit that
  only touches the changelog and the version. The checks re-run on the push to
  `main` regardless, so a semantic conflict still surfaces immediately.
