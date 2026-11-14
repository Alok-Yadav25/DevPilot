import hashlib
import re
from typing import Any

from app.agent.state import RunReport
from app.agent.tools.patches import protected_path
from app.errors import DevPilotError
from app.github.client import GitHubClient
from app.github.clone import validate_repo_url


def publish_reviewed_patch(
    github: GitHubClient,
    report: RunReport,
    files: dict[str, str],
    approved_hash: str,
) -> str:
    """Only called after a persisted human decision for the exact tested diff.

    Objects are uploaded through Git's REST object endpoints; the only changed ref
    is a new devpilot/fix-* branch. No default-branch update or merge endpoint exists.
    """
    digest = hashlib.sha256(report.final_diff.encode()).hexdigest()
    if not report.final_diff or digest != approved_hash:
        raise DevPilotError("The approved diff does not match the final patch.")
    paths = set(re.findall(r"^\+\+\+ b/(.+)$", report.final_diff, re.MULTILINE))
    if set(files) != paths or not paths or any(protected_path(p) for p in paths):
        raise DevPilotError("Publication snapshot does not match the reviewed production files.")
    if (
        not report.attempts
        or not report.attempts[-1].test_result
        or not report.attempts[-1].test_result.passed
    ):
        raise DevPilotError("Publication requires a passing final sandbox test report.")
    url = validate_repo_url(report.repo_url)
    repo = url.removeprefix("https://github.com/").removesuffix(".git")
    root = f"repos/{repo}"
    branch = f"devpilot/fix-{report.id}"
    info = github.request("GET", root)
    base = str(info["default_branch"])
    previous = github.request("GET", f"{root}/pulls?head={repo.split('/')[0]}:{branch}&state=all")
    for previous_pr in previous:
        if digest not in (previous_pr.get("body") or ""):
            raise DevPilotError(
                "An existing run PR does not match the approval record. Inspect it manually."
            )
        return str(previous_pr["html_url"])
    existing = github.request("GET", f"{root}/git/ref/heads/{branch}", missing_ok=True)
    if existing:
        candidate = github.request("GET", f"{root}/git/commits/{existing['object']['sha']}")
        if f"DevPilot-approved-diff: {digest}" not in candidate.get("message", "") or [
            p["sha"] for p in candidate.get("parents", [])
        ] != [report.commit_sha]:
            raise DevPilotError(
                "Existing fix branch does not match the approved patch. Inspect it manually."
            )
    else:
        # Never rebase or force-update an untested patch.
        commit = github.request("GET", f"{root}/git/commits/{report.commit_sha}")
        tree = github.request(
            "POST",
            f"{root}/git/trees",
            {
                "base_tree": commit["tree"]["sha"],
                "tree": [
                    {"path": p, "mode": "100644", "type": "blob", "content": content}
                    for p, content in sorted(files.items())
                ],
            },
        )
        new_commit = github.request(
            "POST",
            f"{root}/git/commits",
            {
                "message": (
                    f"fix: {report.issue_text.splitlines()[0][:100]}\n\n"
                    f"DevPilot-approved-diff: {digest}"
                ),
                "tree": tree["sha"],
                "parents": [report.commit_sha],
            },
        )
        # Create (never force-update) a fresh branch. A replay cannot overwrite a ref.
        github.request(
            "POST",
            f"{root}/git/refs",
            {
                "ref": f"refs/heads/{branch}",
                "sha": new_commit["sha"],
            },
        )
    test = report.attempts[-1].test_result
    body = (
        "## Problem\n"
        + report.issue_text
        + "\n\n## Change and risks\n"
        + report.review
        + "\n\n## Validation\n"
        + f"- Tested commit: `{report.commit_sha}`\n"
        + f"- Patch attempts: {len(report.attempts)}\n"
        + f"- Final pytest exit code: {test.exit_code}\n"
        + f"- Tests recorded: {len(test.outcomes)}\n"
        + f"- Human-approved diff SHA-256: `{approved_hash}`\n"
        + "\nRepository test files were not changed. Passing tests do not prove correctness. "
        "This draft requires human review and is never merged by DevPilot."
    )
    pr: dict[str, Any] = github.request(
        "POST",
        f"{root}/pulls",
        {
            "title": f"fix: {report.issue_text.splitlines()[0][:100]}",
            "head": branch,
            "base": base,
            "body": body,
            "draft": True,
        },
    )
    return str(pr["html_url"])
