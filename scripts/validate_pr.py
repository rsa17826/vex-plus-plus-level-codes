#!/usr/bin/env python3
"""Required status check for level-upload PRs. Run from a workflow with
`fetch-depth: 0` so full history is available for the re-registration check,
and with the PR head already checked out into the working tree (so
build_manifest_entries() reads the same levels/users files the PR proposes).

Enforces, per PR:
  - A PR is EITHER a manifest-only PR, OR a users/levels PR. Never both.
  - Manifest-only PR (the sole changed file is meta/manifest.json, not
    deleted): regenerates the manifest from the current working tree and
    requires the PR's submitted file to match that regeneration byte for
    byte. Anything hand-edited or stale gets rejected.
  - users/levels PR: may only touch users/<name>.pub or
    levels/<name>/<level>.json, all for the same <name> (one user per PR).
      - users/<name>.pub: creation only -- never modified, never deleted,
        and never re-created if that path has ever existed before (name is
        permanently claimed on first registration).
      - levels/<name>/<level>.json: never deleted; creatorName inside the
        file must match the <name> in its own path; signature must verify
        against the registry key for <name> as it stood on the PR's base
        commit (not the PR branch -- a PR can't register a key and use it
        in the same PR).

Exits non-zero (failing the check) on the first violation found.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from build_manifest import build_manifest_text
from common import verify_level

BASE_SHA = os.environ["BASE_SHA"]
HEAD_SHA = os.environ["HEAD_SHA"]

LEVEL_PATH_RE = re.compile(r"^levels/([^/]+)/[^/]+\.json$")
PUB_PATH_RE = re.compile(r"^users/([^/]+)\.pub$")
MANIFEST_PATH = "meta/manifest.json"


def sh(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def changed_files() -> list[tuple[str, str]]:
    out = sh("git", "diff", "--name-status", f"{BASE_SHA}...{HEAD_SHA}")
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        files.append((parts[0][0], parts[-1]))  # status letter, path
    return files


def path_existed_in_history(path: str) -> bool:
    out = sh("git", "log", "--all", "--oneline", "--follow", "--", path)
    return bool(out.strip())


def read_file_at(ref: str, path: str) -> str | None:
    try:
        return sh("git", "show", f"{ref}:{path}")
    except subprocess.CalledProcessError:
        return None


def fail(msg: str) -> None:
    print(f"::error::{msg}")
    sys.exit(1)


def validate_manifest_only_pr(status: str) -> None:
    if status == "D":
        fail(f"{MANIFEST_PATH}: deleting the manifest is not allowed")

    submitted = read_file_at(HEAD_SHA, MANIFEST_PATH)
    if submitted is None:
        fail(f"{MANIFEST_PATH}: could not read file from PR head")

    # Working tree is checked out at HEAD, and this PR touches nothing under
    # levels/ or users/, so regenerating here reflects exactly what the PR
    # claims the manifest should be.
    expected = build_manifest_text()
    if submitted != expected:
        fail(
            f"{MANIFEST_PATH} does not match a fresh regeneration from the current "
            f"levels/ and users/ files -- it must be exactly what "
            f"scripts/build_manifest.py produces, not hand-edited or stale"
        )

    print("manifest matches a clean regeneration -- all checks passed")


def validate_ownership_pr(files: list[tuple[str, str]]) -> None:
    touched_names: set[str] = set()

    for status, path in files:
        if path == MANIFEST_PATH:
            fail(f"{MANIFEST_PATH}: manifest changes must be the only change in a PR")

        pub_match = PUB_PATH_RE.match(path)
        level_match = LEVEL_PATH_RE.match(path)

        if pub_match:
            name = pub_match.group(1)
            touched_names.add(name)
            if status == "D":
                fail(f"{path}: deleting a registered public key is not allowed")
            if status == "M":
                fail(f"{path}: public keys are immutable once registered -- cannot modify")
            if status == "A" and path_existed_in_history(path):
                fail(f"{path}: username '{name}' was registered before and can't be re-registered")

        elif level_match:
            name = level_match.group(1)
            touched_names.add(name)
            if status == "D":
                fail(f"{path}: deleting levels is not allowed through this pipeline")

            content = read_file_at(HEAD_SHA, path)
            if content is None:
                fail(f"{path}: could not read file from PR head")
            try:
                level = json.loads(content)
            except json.JSONDecodeError:
                fail(f"{path}: not valid JSON")
                return  # unreachable, keeps type-checkers happy

            if level.get("creatorName") != name:
                fail(f"{path}: creatorName '{level.get('creatorName')}' does not match folder owner '{name}'")

            registry_content = read_file_at(BASE_SHA, f"users/{name}.pub")
            if registry_content is None:
                fail(f"{path}: no registered public key for '{name}' on the base branch -- "
                     f"register the username in its own PR first, then open this one")

            if not verify_level(level, registry_content):
                fail(f"{path}: signature does not verify against the registered key for '{name}'")

        else:
            fail(f"{path}: PRs may only touch users/<name>.pub, levels/<name>/<level>.json, or {MANIFEST_PATH} alone")

    if len(touched_names) > 1:
        fail(f"PR touches files for multiple users {sorted(touched_names)} -- keep one user per PR")

    print("all checks passed")


def main() -> None:
    files = changed_files()
    if not files:
        fail("PR contains no changes")

    if len(files) == 1 and files[0][1] == MANIFEST_PATH:
        validate_manifest_only_pr(files[0][0])
        return

    validate_ownership_pr(files)


if __name__ == "__main__":
    main()
