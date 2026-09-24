// Commit messages are the input to the release, not decoration: semantic-release
// reads the type and scope of every commit since the last tag to decide the
// version and to write the notes. A message it cannot parse does not fail
// anywhere -- it just releases nothing and appears in no note -- so the format
// is checked rather than trusted.
//
// One file, two places. The commit-msg hook in .pre-commit-config.yaml checks a
// message as it is written; .github/workflows/commit-conventions.yml checks
// every commit in a pull request. Both read this config, so a message that
// passes locally passes in CI.
export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    // The types .github/semantic-release.md documents, restated here so the
    // set stays put if the shared preset ever widens it. Anything outside the
    // list is a typo -- a "feature:" or "bugfix:" commit parses as no type at
    // all and drops out of the release.
    "type-enum": [
      2,
      "always",
      [
        "build",
        "chore",
        "ci",
        "docs",
        "feat",
        "fix",
        "perf",
        "refactor",
        "revert",
        "style",
        "test",
      ],
    ],

    // Bodies are written by tools as often as by hand: the "chore(release):"
    // commit carries the entire release notes, and a dependabot body carries
    // compare links. Neither wraps to a column, and neither is worth failing.
    "body-max-line-length": [0],
    "footer-max-line-length": [0],

    // The subject is prose and starts with whatever word it starts with --
    // "fix: Windows path handling" is not a style error. The type stays lower
    // case (type-case, from the shared preset), because that is what
    // semantic-release matches its release rules on.
    "subject-case": [0],
  },
};
