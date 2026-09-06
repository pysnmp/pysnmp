#!/usr/bin/env python3
"""Maintain the version index of the published documentation site.

Called after the freshly built HTML has been copied into ``<root>/<version>``.
Rewrites the ``stable`` and ``latest`` aliases, the root redirect and
``versions.json`` from whatever version directories are present, so a re-run
repairs the site rather than depending on previous runs.

Usage: docs-publish.py <site root> <project name>

The project name only titles the redirect pages, which is what lets pyasn1,
pysmi and pysnmp share one copy of this script.
"""

import json
import pathlib
import shutil
import sys

from packaging.version import InvalidVersion, Version

ALIASES = ("stable", "latest")

REDIRECT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{project} documentation</title>
<meta http-equiv="refresh" content="0; url=./{target}/">
<link rel="canonical" href="./{target}/">
</head>
<body>
<p>Redirecting to <a href="./{target}/">the {target} documentation</a>.</p>
</body>
</html>
"""

VERSION_REDIRECT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{project} documentation</title>
<meta http-equiv="refresh" content="0; url=./{target}">
<link rel="canonical" href="./{target}">
</head>
<body>
<p>Redirecting to <a href="./{target}">the documentation</a>.</p>
</body>
</html>
"""


def discover(root: pathlib.Path) -> list[tuple[Version, pathlib.Path]]:
    """Return every version directory under *root*, newest first."""
    found = []

    for entry in root.iterdir():
        if not entry.is_dir() or entry.name in ALIASES or entry.name.startswith("."):
            continue

        try:
            found.append((Version(entry.name), entry))
        except InvalidVersion:
            continue

    found.sort(key=lambda pair: pair[0], reverse=True)

    return found


def ensure_index(directory: pathlib.Path, project: str) -> None:
    """Give *directory* an index.html when Sphinx named the root page otherwise.

    conf.py sets ``master_doc = "contents"``, so a build leaves contents.html
    rather than index.html and a bare directory URL would 404.
    """
    if (directory / "index.html").exists():
        return

    for candidate in ("contents.html", "genindex.html"):
        if (directory / candidate).exists():
            (directory / "index.html").write_text(
                VERSION_REDIRECT.format(target=candidate, project=project)
            )
            return


def main() -> int:
    """Rebuild the aliases, root redirect and version index under the site root."""
    root = pathlib.Path(sys.argv[1])
    project = sys.argv[2] if len(sys.argv) > 2 else "project"

    versions = discover(root)
    if not versions:
        print("no version directories found", file=sys.stderr)
        return 1

    for _, path in versions:
        ensure_index(path, project)

    latest = versions[0]
    finals = [pair for pair in versions if not pair[0].is_prerelease]
    stable = finals[0] if finals else latest

    for name, (_, source) in (("latest", latest), ("stable", stable)):
        target = root / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        print(f"{name} -> {source.name}")

    (root / "index.html").write_text(
        REDIRECT.format(target="stable" if finals else "latest", project=project)
    )

    # Jekyll would otherwise drop Sphinx's _static and _sources directories.
    (root / ".nojekyll").touch()

    (root / "versions.json").write_text(
        json.dumps(
            [
                {
                    "version": path.name,
                    "url": f"../{path.name}/",
                    "prerelease": version.is_prerelease,
                }
                for version, path in versions
            ],
            indent=2,
        )
        + "\n"
    )

    print(f"{len(versions)} versions indexed, newest {latest[1].name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
