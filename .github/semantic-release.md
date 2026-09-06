# Releases and commit conventions

Versions are cut by [semantic-release](https://semantic-release.gitbook.io/) from
the commit history. Nothing is versioned by hand: `.releaserc` writes the version
into `pyproject.toml` and `__init__.py`, generates `CHANGELOG.md`, tags, and
publishes. What decides the version is the type and scope of the commits since
the last release, so the commit message is the release note and the release
trigger at once.

`next` is where work integrates and where the rc is cut; merging `next` into
`main` cuts the GA. Both are cut by dispatching the CI workflow by hand — every
other push is a dry run.

## Types

The `conventionalcommits` preset is in use, so `<type>(<scope>): <subject>`:

| Type | Release | Appears in the notes |
| --- | --- | --- |
| `fix` | patch | Bug Fixes |
| `feat` | minor | Features |
| `perf` | patch | Performance Improvements |
| any type with `!` or a `BREAKING CHANGE:` footer | major | Breaking Changes |
| `build`, `chore`, `ci`, `docs`, `refactor`, `style`, `test` | none | no |

A commit whose type releases nothing is not lost -- it ships with the next
release that something else triggers. It just cannot cause one on its own.

## Dependencies

A dependency bump is the one case where the scope, not the type, decides:

| Scope | Means | Release |
| --- | --- | --- |
| `deps` | a dependency in `[project].dependencies` moved | patch, whatever the type |
| `deps-dev` | a dependency in `[dependency-groups]` moved | none, whatever the type |

Write runtime bumps as **`fix(deps):`** and development-only bumps as
**`chore(deps-dev):`**. Those are the messages
[`.github/dependabot.yml`](dependabot.yml) is configured to produce, and the
ones that read correctly in the release notes.

The reason for the split is what a bump changes for someone who is not working
in this repository. `[project].dependencies` is published metadata: raising a
floor there changes what every installer resolves, and until a release carries
it to PyPI the change may as well not exist. `[dependency-groups]` is not
published at all -- it is how this repository tests itself, and no released
artifact mentions it. CI plumbing (workflow actions, pre-commit hooks) is the
same: `ci:`, and no `deps` scope.

`.releaserc` enforces this with explicit `releaseRules` rather than trusting the
type alone, so a runtime bump written as `chore(deps):` still cuts a patch
instead of sitting unreleased until an unrelated commit lands, and a dev bump
written as `fix(deps-dev):` still cuts nothing. Prefer the right type anyway:
release rules control the version, but the notes are grouped by type, and a
`chore` is not printed in them at all.

Breaking changes and `feat(deps)` keep their normal meaning -- the rules restate
them, because a custom rule that matches short-circuits the built-in ones.

## Examples

```
fix(deps): require pysnmp-pyasn1 >=1.3.0          # patch, published
chore(deps-dev): bump ruff from 0.8.0 to 0.9.0    # nothing
ci(actions): bump actions/checkout from 7 to 8    # nothing
feat(deps): support the pure-Python crypto backend # minor
fix(deps)!: drop Python 3.9                       # major
```

## Enforcement

None of the above works if the message is not conventional in the first place,
so the format is checked rather than assumed. Both checks read the same
[`commitlint.config.mjs`](../commitlint.config.mjs) at the repository root:

| Where | What it checks |
| --- | --- |
| the `commit-msg` hook, from [`.pre-commit-config.yaml`](../.pre-commit-config.yaml) | the message being written, before the commit exists |
| the `Commit conventions` workflow, on every pull request | every commit in the pull request |

Install the hook once per checkout:

```console
$ pre-commit install
pre-commit installed at .git/hooks/pre-commit
pre-commit installed at .git/hooks/commit-msg
```

`default_install_hook_types` is what adds the second line. A checkout that ran
`pre-commit install` before that setting existed has to run it again, or the
`commit-msg` hook is configured and never runs. The hook does not run under
`pre-commit run --all-files`, so the `pre-commit` CI job does not duplicate the
workflow.

The rules are `@commitlint/config-conventional` with three deliberate changes:

- the type list is restated in the config, so it cannot drift if the shared
  preset widens it;
- body and footer line lengths are unlimited -- the `chore(release):` commit
  carries the entire release notes, and a dependabot body carries compare
  links, neither of which wraps to a column;
- subject case is not checked. `fix: Windows path handling` is prose, not a
  style error. The *type* is still lower case, because `Fix:` is not what the
  release rules match on and would release nothing.

Merge commits, `fixup!` commits and git's own `Revert "..."` subjects are
ignored, as they are by every conventional-commits parser. The pull request
title is not checked: pull requests here are merged, not squashed, so the title
never enters the history. Turning squash merging on would make the title the
commit subject, and would need a check of its own.

To lint a range by hand, the way the workflow does:

```console
$ npm install --no-save @commitlint/cli@21 @commitlint/config-conventional@21
$ npx commitlint --verbose --from origin/next --to HEAD
```

The workflow is the gate only if the branch requires it: add **Commit
conventions / commitlint** to the required status checks for `main` and `next`
in the repository's branch protection, or a red check can still be merged past.
