# Landing page and visual refresh

November 15, 2026. Local implementation only; no deployment, publication or remote push.

## Changed

- `frontend/src/pages/Home.tsx`: new public landing page with a large editorial hero, concise product copy, staggered text reveal, ambient motion, feature/process sections and a clear workspace entry point. It makes no API requests.
- `frontend/src/pages/Workspace.tsx`: preserves the existing repository form, recent runs, examples and real-recording entry points at `/workspace`.
- `frontend/src/components/Brand.tsx`, `public/devpilot-mark.svg`, `public/favicon.svg`: scalable vector rendition of the supplied monogram; adaptive favicon; shared “Made by Alok Yadav” credit linked to the requested GitHub profile.
- `frontend/src/styles/landing.css`: responsive dark/light landing layouts, interactive patch preview and restrained motion. Reduced motion stops nonessential animation and automatic preview changes.
- `frontend/src/styles/premium.css`: charcoal, ivory and champagne theme tokens shared with the workspace; Instrument Serif accents alongside Space Grotesk, Inter and JetBrains Mono.
- `frontend/src/main.tsx`, `components/Layout.tsx`, `pages/NewRun.tsx`, `pages/LiveRun.tsx`: route separation, workspace navigation, shared branding and footer credit.
- `frontend/src/components/AgentGraph.tsx`: workflow edge colors follow the active theme.
- `frontend/index.html`: serif font loading and updated browser theme color.
- `frontend/e2e/landing.spec.ts`, `e2e/workspace.spec.ts`: landing checks and regression coverage for the moved workspace and lazy workflow graph.
- `frontend/scripts/lighthouse.mjs`: include the landing route and the new workspace URL in reproducible local measurements.

The preview is labelled **Illustrative preview**; its test outcomes are scripted. “Try the demo” opens an explicitly labelled local sample. Neither action calls Groq/GitHub or publishes a patch. Live run approval gates are unchanged.

## Checks

- Production TypeScript/Vite build: passed.
- Vitest: 42 passed. Existing fixture/mocked-fetch tests; no external provider evidence.
- Playwright: 21 passed, 1 skipped. Desktop 1440×900, mobile 390×844, plus a 320px layout check. Desktop skips the mobile-only drawer test.
- Browser checks include logo loading, author-link destination, hero/workspace navigation, keyboard preview tabs, autoplay and pause, reduced motion, real-time browser animation visibility, theme persistence, no initial landing API calls, offline demo, approval, worker errors and workflow loading.
- Formatting and typography: passed; no authored text below 12px.
- Gitleaks frontend source scan: no findings.
- Desktop/mobile dark/light screenshots, animated hero and final call-to-action were visually inspected. Browser artifacts remain under ignored `frontend/test-results/`.

## Performance snapshot

Lighthouse 10.1.1, local production build, Chrome desktop preset, persistent warm profile, reduced motion and mocked API. Three trials retained per route:

| Page | Performance trials | Median | Accessibility trials |
| --- | --- | --- | --- |
| Landing `/` | 98, 99, 99 | 99 | 100, 100, 100 |
| Workspace `/workspace` | 98, 98, 98 | 98 | 100, 100, 100 |
| Run workspace | 97, 97, 97 | 97 | 100, 100, 100 |
| History | 98, 98, 98 | 98 | 100, 100, 100 |

[Raw reports and summary](quality/landing-lighthouse/summary.json). The snapshot preceded the last small-screen header and graph-color refinements. These are local warm desktop measurements, not hosted/mobile performance guarantees or live repair results. The older audit tool remains isolated from application dependencies; its tooling limitations are described in [quality evidence](quality/REPORT.md).

## Unchanged live-verification gaps

No real GitHub/Groq repair, remote restart-recovery scenario, approved draft PR or Postgres concurrency scenario was verified in this visual refresh. Real repair success remains unknown. See [VERIFICATION.md](VERIFICATION.md). No backend implementation or deployment configuration was changed.
