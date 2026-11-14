"""Local recovery tests: scripted model/test outcomes, real temporary Git checkouts."""

import json
import shutil
from datetime import UTC, datetime, timedelta

import pytest
from app.agent.graph import Agent
from app.config import Settings
from app.db.models import Base, RunRow
from app.db.session import make_engine, make_sessions
from app.service import RunService
from conftest import CASES, ScriptedLLM, ScriptedSandbox, seed_repo
from git import Repo


class PowerLoss(BaseException):
    pass


@pytest.mark.parametrize(
    "node",
    [
        "clone",
        "baseline",
        "locate",
        "diagnose",
        "patch",
        "validate_patch",
        "test",
        "review",
        "recover",
    ],
)
def test_resume_after_each_completed_node(tmp_path, node):
    origin = seed_repo(tmp_path / "origin")
    with Repo(origin) as repo:
        sha = repo.head.commit.hexsha

    class PinnedCloner:
        timeout = 90

        def clone(self, url, destination):
            shutil.copytree(origin, destination)
            return sha

        def clone_pinned(self, url, destination, pinned):
            assert pinned == sha
            return self.clone(url, destination)

    case = CASES[0]
    saved = {}

    def checkpoint(name, state, report):
        if name == node:
            saved.update(
                json.loads(
                    json.dumps(
                        {
                            "node": name,
                            "state": {
                                k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
                                for k, v in state.items()
                                if k != "workdir"
                            },
                            "report": report.model_dump(mode="json"),
                        }
                    )
                )
            )
            raise PowerLoss()

    settings = Settings(_env_file=None, work_root=tmp_path / "work")
    retry = node == "recover"
    wrong = json.loads(case.proposal())
    wrong["changes"][0]["replace"] = 'return ".".join'
    sandbox = ScriptedSandbox(
        [case.baseline(), case.baseline(), *([case.baseline()] if retry else []), case.success()]
    )
    llm = ScriptedLLM(([json.dumps(wrong)] if retry else []) + [case.proposal()])
    agent = Agent(settings, llm, sandbox, cloner=PinnedCloner(), on_checkpoint=checkpoint)
    with pytest.raises(PowerLoss):
        agent.run("https://github.com/fixtures/slugify", case.issue)
    restored = Agent(settings, llm, sandbox, cloner=PinnedCloner())
    report = restored.run("https://github.com/fixtures/slugify", case.issue, resume=saved)
    assert report.status == "ready_for_review", report.reason
    assert report.commit_sha == sha and report.attempts[-1].test_result.passed
    assert len(report.attempts) == (2 if retry else 1) and list(settings.work_root.iterdir()) == []


def test_database_leases_expire_and_terminal_runs_are_not_claimed(tmp_path):
    settings = Settings(
        _env_file=None, runner_mode="replay", database_url=f"sqlite:///{tmp_path}/db"
    )
    engine = make_engine(settings)
    Base.metadata.create_all(engine)
    sessions = make_sessions(engine)
    a, b = RunService(settings, sessions), RunService(settings, sessions)
    with sessions.begin() as db:
        db.add(
            RunRow(
                id="job",
                repo_url="https://github.com/owner/repo",
                issue_text="fix bug",
                status="queued",
            )
        )
    assert a.claim("job") and not b.claim("job")
    with sessions.begin() as db:
        db.get(RunRow, "job").lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert b.claim("job")
    with sessions.begin() as db:
        db.get(RunRow, "job").status = "completed"
        db.get(RunRow, "job").lease_expires_at = None
    assert not a.claim("job")
    a.shutdown()
    b.shutdown()
    engine.dispose()
