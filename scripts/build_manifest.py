#!/usr/bin/env python3
"""Rebuilds meta/manifest.json from every levels/<name>/<level>.json in the
working tree. Run after checkout on `main` (not a PR branch) -- this is the
trusted listing, so it re-verifies each level's signature itself rather than
trusting a 'verified' flag anyone could have put in the file.

Keeps the manifest small on purpose: no levelData/levelImage, so the client
can load this one file to show the browse/list screen instead of fetching
every level's full JSON (see the NOTE in LevelServer.gd's loadAllLevels).
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import verify_level


def main() -> None:
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

        entries.append({
            "path": path,
            "levelName": level.get("levelName"),
            "creatorName": level.get("creatorName"),
            "description": level.get("description"),
            "gameVersion": level.get("gameVersion"),
            "levelVersion": level.get("levelVersion"),
            "verified": verified,
        })

    os.makedirs("meta", exist_ok=True)
    with open("meta/manifest.json", "w", encoding="utf-8") as f:
        json.dump({"levels": entries}, f, indent=2)
        f.write("\n")

    print(f"wrote {len(entries)} entries to meta/manifest.json")


if __name__ == "__main__":
    main()
