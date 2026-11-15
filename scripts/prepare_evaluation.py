"""Materialize 25 deliberately buggy Git repos locally. Never execute or publish them."""

import argparse
import json
from pathlib import Path

from app.evaluation import catalog, materialize
from git import Repo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".devpilot/evaluation-repos"))
    args = parser.parse_args()
    entries = []
    for case in catalog():
        root = args.output / case["id"]
        materialize(case, root)
        with Repo(root) as repo:
            sha = repo.head.commit.hexsha
        entries.append({"case_id": case["id"], "repo_url": "", "expected_commit_sha": sha})
    (args.output / "manifest.json").write_text(json.dumps(entries, indent=2) + "\n")
    print(
        f"Prepared {len(entries)} local repos. Publish to your own allowlisted repos, "
        "then fill manifest.json. Nothing was uploaded."
    )


if __name__ == "__main__":
    main()
