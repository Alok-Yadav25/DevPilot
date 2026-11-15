> Historical checkpoint. For the current implementation and measured checks, see [README](../README.md), [quality evidence](quality/REPORT.md) and [live verification](VERIFICATION.md).

# Full build verification

Build date: November 12, 2026. Python 3.11.13; Node 22; macOS ARM64.

| Check | Result |
| --- | --- |
| Python unit/API/controller tests | 97 passed; 5 Docker checks skipped |
| Real Docker integration checks | 5 skipped: Docker is unavailable |
| Frontend interaction and sample tests | 13 passed |
| Frontend TypeScript and Vite build | Passed |
| Production npm audit | Passed: zero reported vulnerabilities |
| Mypy | Passed across application and container entrypoint |
| Alembic upgrade and schema drift check | Passed on an explicit development SQLite database |
| Real PostgreSQL execution | Not run: no PostgreSQL/Docker service available |
| Live Groq / GitHub PR | Not run: credentials unavailable; guarded publication tested with mocked REST calls |
| 25-case real evaluation | Not run; UI reports unknown success rate, not fabricated success |
| Browser visual QA / Lighthouse | Unverified: computer/browser access host unavailable |
| Local preview HTTP | Vite serves HTTP 200 at 127.0.0.1:5173 |

The generated README animation is an illustrative workflow diagram, not a recording of a live repair. Browser samples use scripted events and expected outcomes, clearly labeled in the UI, and do not count in metrics.

Real sandbox validation remains opt-in with `DEVPILOT_DOCKER_TESTS=1 uv run pytest -m docker`. It covers repairs in three fixture repositories plus actual network/UID/root-filesystem/memory/no-new-privileges and timeout checks. Enabling it without Docker/image makes the checks fail instead of silently simulating execution.

The worker's approval tests enforce an exact diff hash, a review-ready state and a one-shot decision. Dry-run approval cannot publish. Rejection prevents later approval. Publication can create only a new branch and draft PR; no merge/default-branch mutation path exists.

## Hosting policy update

The user revoked ChatGPT Sites hosting authorization. Local deployment configuration and the ChatGPT origin in the CORS example were removed. The project must never be republished on ChatGPT Sites. Removal verified on November 12, 2026: the Sites connector returned `Sites project not found` for the former DevPilot project.
