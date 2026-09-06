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
