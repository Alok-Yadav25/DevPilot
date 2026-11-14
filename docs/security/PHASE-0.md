# Phase 0 security report — November 14, 2026

**Status: code safeguards implemented; manual credential revocation/rotation remains unconfirmed. Do not advance to Phase 1 yet.**

## Manual credential action

Treat the previously exposed Groq key as compromised. The owner must revoke/delete it in [the Groq console](https://console.groq.com/keys), create a replacement, and save the new value only in the ignored local `.env` or the eventual provider's secret manager. Do not paste either key into chat, tracked files, issue text or logs. Removing a key from `.env.example` does not revoke it. No rotation or revocation was performed or tested against Groq in this phase; no authenticated provider request was made.

## Local scanner results

The official gitleaks **v8.30.1** Darwin ARM64 archive was downloaded and its SHA-256 compared with the official published checksum. The local executable and redacted reports are under ignored `.devpilot/security/`.

| Local scope | Measured result | Limit |
| --- | --- | --- |
| Root Git history, `--log-opts=--all` | 0 findings; initially 0 commits | The root repository had no committed baseline at the start of the phase |
| Nested `frontend/.git` history, `--log-opts=--all` | 0 findings; 1 commit scanned | All available local refs; no remote refs fetched or history rewritten |
| Git-visible working source snapshot | 0 findings across 131 files at scan time | Includes untracked source and nested frontend files; excludes Git-ignored environments, generated output and dependencies |
| Environment example | Provider/access-token settings empty; no real token detected | Local `.env` is intentionally not printed or committed |
| Ignore rules | `.env`, `.env.recovered`, and `frontend/.env.local` ignored | Confirmed with `git check-ignore --no-index` |

The first history scan failed because the PATH selected an incompatible x86 Git binary; it was rerun successfully with `/usr/bin/git`. Only completed scans count above. No positive credential finding was discovered in the scanned histories, so no history rewriting was done. These results cannot prove a previously shared key is revoked or that secrets never existed in unfetched/unreachable remote history.

Reproduce locally with the official gitleaks binary:

```sh
gitleaks git --log-opts="--all" --config=.gitleaks.toml --redact=100 --no-banner .
gitleaks git --log-opts="--all" --config=.gitleaks.toml --redact=100 --no-banner frontend
```

Use only redacted reports. Do not upload local environments or scanner snapshots. An actual leak must be revoked even if removed from current source. Do not mask a genuine finding with a broad scanner allowlist.

## Changed files

| File | Reason |
| --- | --- |
| `.gitleaks.toml` | Extend built-in detection, explicitly detect Groq keys; one exact existing numeric dummy exception, no blanket test/doc exclusions |
| `.github/workflows/secret-scan.yml` | Pinned, checksum-checked gitleaks; full fetched history and checkout checks, read-only permissions, redacted output; no deployment |
| `backend/app/logging.py` | Redact fully formatted log output, including arguments, custom formatter fields and exception traces |
| `backend/app/security.py` | Cover quoted Authorization fields and authenticated database URLs |
| `backend/app/main.py` | Install redacting log formatters and sanitize validation/HTTP errors; generic unexpected-error response |
| `backend/app/config.py` | Include the database URL among configured secret values |
| `backend/tests/test_logging_security.py` | Fake-token log/traceback, URL, API-error and env-example regressions |
| `pyproject.toml` | Register `live` and exclude live tests from the default run |
| `.gitignore` | Existing environment/dependency/report exclusions retained in the local security commit |
| `docs/security/PHASE-0.md` | Evidence, manual gap and token-read inventory |

## Tests and evidence

The full default Python test run completed locally: **114 passed; 5 Docker integration checks skipped**. These are local/unit/controller or mocked HTTP checks, not live Groq/GitHub/Postgres evidence. A focused run covered 21 logging/security/API tests. Ruff passes; mypy checks the application. The secret-scanning workflow is authored locally and has not run on GitHub. No CI run URL is claimed.

New tests:

- `test_logger_redacts_arguments_json_and_exception_tracebacks`: fake credentials through a real local logging handler, including `%s` args, JSON and traceback output.
- `test_database_and_authenticated_clone_urls_are_redacted`: database and Git credential URL cleanup.
- `test_api_redacts_validation_http_and_unhandled_errors`: in-process ASGI responses, not a hosted API.
- `test_env_examples_have_no_provider_credentials`: tracked examples must not contain populated provider/access-token settings.

Live tests must use `@pytest.mark.live`; default pytest uses `-m 'not live'`. Explicit execution uses `pytest -m live` and must never silently substitute mocks.

## Every application credential-read location

This inventory distinguishes loading values from using them. Names refer to current source, including legacy paths that later phases must migrate.

| Location | What it reads / why |
| --- | --- |
| `backend/app/config.py` — `Settings` | Pydantic loads `.env`/process environment: `GROQ_API_KEY`, legacy `GITHUB_TOKEN`, `SANDBOX_GITHUB_TOKEN`, `TARGET_GITHUB_TOKEN`, `API_ACCESS_TOKEN`, and credential-bearing `DATABASE_URL`; `secrets()` supplies redaction values |
| `backend/app/cli.py` | Reads the sandbox token and Groq key from Settings for Actions dispatch and LLM requests; passes the complete configured secret set to redaction |
| `backend/app/agent/llm.py` — `GroqClient.__init__` | Receives the Groq key and builds only the Groq Authorization header |
| `backend/app/agent/graph.py` — `Agent.__init__` | Legacy direct-agent path reads `GITHUB_TOKEN` for clone access; revised public CLI supplies an unauthenticated cloner instead; token-policy consolidation remains Phase 3 |
| `backend/app/github/clone.py` — `git_env` | Receives a clone token and encodes an ephemeral HTTP Basic header; never writes it to the URL/config; inherited process environment is restricted to PATH/HOME/SYSTEMROOT |
| `backend/app/sandbox/github_actions.py` — constructor | Receives only the sandbox token and builds the GitHub API header; artifact redirects use a separate unauthenticated client |
| `backend/app/github/client.py` — constructor | Receives a GitHub token for its REST Authorization header |
| `backend/app/service.py` — execute/decide/publish | Reads Groq for model calls; legacy `GITHUB_TOKEN` for the old approval/publication path; pending token separation is not claimed fixed |
| `backend/app/api/repos.py` — issue | Reads legacy `GITHUB_TOKEN` for optional issue retrieval |
| `backend/app/api/runs.py` — create | Reads only whether the Groq key is configured before starting a run |
| `backend/app/api/health.py` | Reads only whether Groq, API-access and legacy GitHub tokens are configured; does not return their values |
| `backend/app/deps.py` — require_access | Reads configured `API_ACCESS_TOKEN` and the incoming HTTP bearer credentials; compares with `hmac.compare_digest` |
| `backend/app/db/session.py` | Reads the secret database connection URL when constructing SQLAlchemy's engine |
| `backend/app/db/migrations/env.py` | Reads the database connection URL for migrations |
| `scripts/evaluate.py` | Reads the Groq key for the existing evaluation command and the secret collection for redaction |
| `frontend/src/lib/store.ts` | Reads/writes the worker access token in browser session storage (`getToken`/`setToken`); no Groq/GitHub credential storage |
| `frontend/src/lib/api.ts` | Reads the worker session token and sends the API Authorization header |
| `frontend/src/pages/LiveRun.tsx` | Reads the worker session token for authenticated SSE fetches |
| `frontend/src/components/ConnectionDialog.tsx` | Reads the worker token to populate the connection form; accepts only the worker credential for backend access |

`TARGET_GITHUB_TOKEN` is declared and redacted but is not yet used by the legacy publication service. That gap is explicitly assigned to later phases, not hidden by this report. Workflow target/ref/allowlist environment reads are not credential reads. Neither sandbox entrypoint is given Groq, sandbox PAT, target PAT or worker access token.

## Remaining risks and next step

- Manual key rotation/revocation is still unconfirmed. Phase 0 is not fully complete until the owner confirms it.
- Redaction is a defense, not proof that every unknown secret format is covered. The installed formatter protects configured handlers; custom handlers added later must also use it.
- Full remote history, deployed logs, CI execution and live providers were not inspected.
- The root repository initially had no commits, while the frontend has separate local Git history. The Phase 0 commit is deliberately limited to security-related paths; existing unrelated untracked application files are not silently staged.
- No deployment, remote push or history rewrite is authorized or performed here. The ChatGPT hosting ban remains in effect.

Next: after confirming old-key revocation and replacement, review Phase 0 before any selected-runner/API migration.
