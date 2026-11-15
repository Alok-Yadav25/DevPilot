# Three deliberately buggy Python fixtures

Each subdirectory is a standalone pytest project. These are DevPilot-owned synthetic cases, not third-party benchmarks or previously successful autonomous runs.

| Directory | Bug | Failing test |
| --- | --- | --- |
| `slugify/` | Underscore separator instead of hyphen | `tests/test_slugify.py::test_separator` |
| `clamp/` | Reversed bounds | `tests/test_clamp.py::test_bounds` |
| `backoff/` | First exponential delay too large | `tests/test_backoff.py::test_first_delay` |

The opt-in Docker tests execute these projects only inside the sandbox. The default controller tests use scripted outcomes and never import their source. Publish copies as your own GitHub repositories to test real Groq-driven repair through the CLI. These examples are intentionally small; they do not support any general success-rate claim.
