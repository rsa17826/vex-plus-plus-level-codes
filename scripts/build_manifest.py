#!/usr/bin/env python3
"""Rebuilds meta/manifest.json from every levels/<name>/<level>.json in the
working tree. Run after checkout -- this is the trusted listing, so it
re-verifies each level's signature itself rather than trusting a 'verified'
flag anyone could have put in the file.

Keeps the manifest small on purpose: no levelData/levelImage, so the client
can load this one file to show the browse/list screen instead of fetching
every level's full JSON (see the NOTE in LevelServer.gd's loadAllLevels).

build_manifest_text() is also imported by validate_pr.py, which uses it to
check that a manifest-only PR's proposed meta/manifest.json is EXACTLY what
regenerating it would produce -- not just well-formed, but the real thing.
"""
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import verify_level


def commit_timestamp(path: str) -> str:
    """ISO 8601 commit date of the most recent commit touching this path, per
    the repo's own git history -- not anything the uploader supplies, so it
    can't be gamed to rank a level artificially high. Needs real history in
    the checkout (fetch-depth: 0); returns "" if none is found, which sorts
    last rather than crashing the whole build."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", path],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return out
    except subprocess.CalledProcessError:
        return ""


def build_manifest_entries() -> list[dict]:
    entries = []
    for path in sorted(glob.glob("levels/*/*.json")):
        with open(path, encoding="utf-8") as f:
            try:
                level = json.loads(f.read())
            except json.JSONDecodeError:
                print(f"skipping {path}: not valid JSON", file=sys.stderr)
                continue

        name = path.split("/")[1]
        pub_path = f"users/{name}.pub"
        registry_key = None
        if os.path.exists(pub_path):
            with open(pub_path, encoding="utf-8") as f:
                registry_key = f.read().strip()

        verified = bool(registry_key) and verify_level(level, registry_key)

        # History dir now holds only strictly-superseded versions -- each
        # overwrite archives whatever WAS in latest before replacing it
        # (see uploadLevel in LevelServer.gd), so the current version is
        # never in there. Total history files == how many older versions
        # exist besides this one.
        history_glob = path[: -len(".json")] + "/*.json"
        old_version_count = len(glob.glob(history_glob))

        entries.append({
            "path": path,
            "levelName": level.get("levelName"),
            "creatorName": level.get("creatorName"),
            "description": level.get("description"),
            "gameVersion": level.get("gameVersion"),
            "levelVersion": level.get("levelVersion"),
            "verified": verified,
            "uploadedAt": commit_timestamp(path),
            "oldVersionCount": old_version_count,
        })

    # Newest first. "" (no history found) sorts smallest, so with reverse=True
    # those entries fall to the bottom instead of crashing or landing on top.
    entries.sort(key=lambda e: e["uploadedAt"], reverse=True)
    return entries


def build_manifest_text() -> str:
    """The exact bytes build_manifest.py would write to meta/manifest.json,
    as a string, for byte-for-byte comparison elsewhere."""
    return json.dumps({"levels": build_manifest_entries()}, indent=2) + "\n"


def main() -> None:
    os.makedirs("meta", exist_ok=True)
    text = build_manifest_text()
    with open("meta/manifest.json", "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {text.count('\"path\":')} entries to meta/manifest.json")


if __name__ == "__main__":
    main()
