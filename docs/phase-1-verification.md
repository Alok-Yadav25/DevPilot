> Historical checkpoint. For the current implementation and measured checks, see [README](../README.md), [quality evidence](quality/REPORT.md) and [live verification](VERIFICATION.md).

# Phase 1 verification

Build date: **November 12, 2026**. Runtime: **Python 3.11.13**, macOS ARM64.

The workspace initially had no application files, Docker installation or Groq credentials. Python 3.11 and the locked development environment were installed locally. No GitHub credentials were present; no repository was pushed or modified remotely.

| Check | Result | Meaning |
| --- | --- | --- |
| Unit/controller tests | **80 passed; 5 Docker tests skipped** | Includes three fixture Git repositories; model and sandbox outcomes are scripted |
| Application coverage | **89% on the preceding 79-test run** | Unit/controller coverage; does not establish real sandbox behavior |
| Ruff lint/format | **Passed** | Static code quality |
| Mypy | **Passed, 18 source files** | Application and container entrypoint types |
| Docker baseline → repair, 3 repos | **Not run** | Docker engine unavailable; opt-in integration tests included |
| Real Docker isolation and timeout | **Not run** | Container options tested using SDK mocks; actual kernel behavior unverified here |
| Live Groq repair | **Not run** | `GROQ_API_KEY` absent |
| Groq model documentation | Checked | `openai/gpt-oss-120b` listed in the official supported-model page; authenticated availability checked at runtime |
| PR/merge behavior | Absent by design | Phase 1 contains no external write operation |
| Real repair success rate | **Unknown (0 live runs)** | No denominator or inferred success percentage |

## Reproduce locally

```sh
uv sync --locked --extra dev
uv run pytest -q --junitxml=.devpilot/verification/unit-results.xml
uv run ruff check .
uv run ruff format --check .
uv run mypy backend/app sandbox-image/runner.py

docker build -t devpilot-sandbox:py311 sandbox-image
DEVPILOT_DOCKER_TESTS=1 uv run pytest -q -m docker \
  --junitxml=.devpilot/verification/docker-results.xml
```

The Docker integration suite is intentionally skipped unless explicitly enabled. If enabled with Docker/image missing, it fails instead of silently skipping. Its three repository fixtures use the real graph, patch validator and Docker runner with scripted proposals. This verifies test execution and orchestration, not model performance.

## Three live-model cases to run after setup

Publish each `examples/<name>/` directory as a separate repository you control. The test harness's `github.com/fixtures/...` URLs are test identities, not real example URLs.

| Example | Bug | Exact baseline failing ID | Expected fix |
| --- | --- | --- | --- |
| `slugify` | Words separated with `_` | `tests/test_slugify.py::test_separator` | Hyphen separator |
| `clamp` | `min`/`max` bounds reversed | `tests/test_clamp.py::test_bounds` | Clamp to lower/upper correctly |
| `backoff` | First exponent off by one | `tests/test_backoff.py::test_first_delay` | Delay starts at 1 |

For each real URL, use `devpilot run URL --issue 'BUG' --expected-failure 'ID'`. Keep the commit SHA, model ID, baseline outcomes, attempts, final diff, review and duration from `report.json`. Review the patch and independently assess correctness; do not count an orchestration unit test, cached response or scripted candidate as an autonomous repair success.

Phase 1 implementation is available for review. Real sandbox and live-model acceptance remain pending those prerequisites; later phases have not started.
