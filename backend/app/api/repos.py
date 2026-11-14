import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.deps import require_access
from app.errors import DevPilotError
from app.github.client import GitHubClient
from app.policy import RunPolicy

router = APIRouter(dependencies=[Depends(require_access)])


class RepoInput(BaseModel):
    repo_url: str


@router.post("/api/repos/validate")
def validate(body: RepoInput, request: Request) -> dict:
    try:
        return {
            "repo_url": RunPolicy(request.app.state.settings).readiness(body.repo_url),
            "supported": "Python 3.11 / pytest",
        }
    except DevPilotError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/api/repos/issue")
def issue(url: str, request: Request) -> dict:
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+)/issues/(\d+)", url)
    if not match:
        raise HTTPException(422, "Use a GitHub issue URL: https://github.com/owner/repo/issues/123")
    client = GitHubClient("")
    try:
        owner, repo, number = match.groups()
        result = client.request("GET", f"repos/{owner}/{repo}/issues/{number}")
        return {"title": result["title"], "body": result.get("body", "")[:16000]}
    except DevPilotError as exc:
        raise HTTPException(502, str(exc)) from exc
    finally:
        client.close()
