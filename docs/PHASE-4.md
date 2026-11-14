# Phase 4 — cold starts and connection state

Changed: frontend `lib/client.ts` centralizes timeouts, classified errors, bounded wake polling/backoff and run idempotency keys. The lightweight health query avoids runner/database work. Layout displays waking/reconnecting/offline states. Live events reconnect using Last-Event-ID with polling retained. Status badges distinguish queued, runner wait, testing, throttling and approval. Connection setup reflects the selected runner instead of assuming a local container host. API run creation recognizes a repeated idempotency key; duplicate identical decisions are safe to repeat.

Tests added: six frontend client checks, including fake-timer 60-second wake-up, finite 90-second failure and preserved idempotency key; in-process lightweight health and duplicate-create tests. Frontend: 19 tests passed and production build passed. Focused API: 16 passed. Ruff/mypy pass.

Verified live: none. A real sleeping Render deployment and proxy/SSE disconnect were not exercised. Cold-start timing is simulated, not hosted evidence. Current [Render free-service documentation](https://render.com/docs/free) was consulted November 14, 2026: services can sleep after 15 minutes idle, take about a minute to wake, and restart. No completion ETA is shown.

Risks: a persistently incorrect API/CORS address also looks like a network failure and eventually gets an actionable connection error. Wake probes are shared per base URL; cancelling one caller does not cancel another caller's probe. No deployment performed. Manual key revocation remains unconfirmed.
