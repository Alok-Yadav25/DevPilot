"""Explicitly opt in: this test contacts the configured real API and providers."""

import os
import sys
from pathlib import Path

import pytest


@pytest.mark.live
def test_real_api_pipeline_dry_run():
    if os.environ.get("DEVPILOT_RUN_LIVE") != "1":
        pytest.skip("Set DEVPILOT_RUN_LIVE=1 and the LIVE_* variables to contact real services.")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from verify_live import verify

    evidence = verify(
        os.environ["LIVE_API_URL"], os.environ["LIVE_REPO"], os.environ["LIVE_ISSUE"], "approve_dry"
    )
    assert evidence["run"]["status"] == "completed", evidence["run"].get("reason")
    assert evidence["run"]["attempts"][-1]["test_result"]["exit_code"] == 0
    assert not evidence["run"].get("pr_url")
