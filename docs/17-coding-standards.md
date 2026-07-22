# CampusHub — Coding Standards

**Document Phase:** 17 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Flutter/Dart Standards

- Follow the official [Effective Dart](https://dart.dev/effective-dart) guidelines as the baseline; project-specific additions below take precedence where they conflict.
- Clean Architecture layering enforced per feature (`data/domain/presentation`, Phase 16 §2) — presentation never imports data-layer classes directly, only domain entities/use cases.
- State management: one consistent approach across the app (chosen at implementation kickoff, e.g., Riverpod) — no mixing of multiple state-management paradigms within the same feature.
- Widgets are kept small and composable; any widget build method exceeding ~150 lines should be decomposed.
- All async operations use `async`/`await`, never raw `.then()` chains, for readability and consistent error propagation.
- Null-safety is strict; `!` (force-unwrap) is avoided except where nullability has just been explicitly checked in the same scope.

## 2. Python Standards

- Follow **PEP 8**, enforced automatically via `ruff` (lint) and `black` (format) — no manual style debates, tooling is authoritative.
- Type hints are mandatory on all function signatures; FastAPI route handlers and Pydantic models are the primary API contract and must be fully typed.
- Business logic lives in `service.py`; `router.py` contains only request/response wiring and dependency injection — no business logic in route handlers.
- Repository layer (`repository.py`) is the only place raw SQLAlchemy queries appear; services never construct queries directly (Repository Pattern, per project philosophy).
- Async-first: all I/O-bound FastAPI routes and database calls use `async`/`await` with an async SQLAlchemy session.

## 3. Naming Conventions

| Context | Convention | Example |
|---|---|---|
| Dart classes/enums | UpperCamelCase | `ResourceRepository` |
| Dart files | snake_case | `resource_repository.dart` |
| Dart variables/functions | lowerCamelCase | `fetchResources()` |
| Python classes | UpperCamelCase | `ResourceService` |
| Python files/functions/variables | snake_case | `resource_service.py`, `fetch_resources()` |
| Database tables/columns | snake_case, plural table names | `resource_versions` |
| REST endpoints | kebab-case path segments, plural nouns | `/course-enrollments` |
| Environment variables | SCREAMING_SNAKE_CASE | `DATABASE_URL` |
| Git branches | `type/short-slug` | `feat/offline-sync-queue` |

## 4. Documentation Standards

- Every backend module (`modules/<name>/`) has a short `README.md` describing its responsibility, key entities, and its position in the module dependency graph (referencing Phase 4).
- Public API routes are documented via FastAPI's `summary`/`description` (feeds the OpenAPI spec, Phase 6 §8) rather than separate hand-written API docs, keeping docs and code inseparable.
- Client feature modules document non-obvious architectural decisions (e.g., why a particular sync strategy was chosen for that feature) in a short `NOTES.md` only when the reasoning isn't evident from the code itself.

## 5. Commenting Standards

- Default to **no comments** — code should be self-explanatory through naming and structure.
- A comment is added only when it explains **why**, not **what**: a non-obvious constraint, a workaround for a specific bug/platform quirk, or an invariant that isn't visible from the code alone.
- No commented-out code committed to `main` — deleted code is retrieved from git history, not preserved as comments.
- No docstring boilerplate that merely restates the function name/signature; docstrings are reserved for public APIs where behavior/edge cases genuinely need explanation (e.g., conflict-resolution logic in the sync engine).

## 6. Commit Message Standards

Conventional Commits format:

```
<type>(<scope>): <short summary>

[optional body — the "why", not the "what"]
```

| Type | Use |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code change with no behavior change |
| `test` | Test-only change |
| `docs` | Documentation-only change |
| `chore` | Tooling, dependencies, CI config |
| `perf` | Performance improvement |

Example: `feat(sync): add version-based conflict detection to submission sync`

## 7. Linting Rules

- **Dart:** `flutter_lints` (or stricter `very_good_analysis`-style ruleset) enabled in `analysis_options.yaml`; CI fails the build on any lint error (warnings tracked but non-blocking initially, promoted to blocking as the codebase matures).
- **Python:** `ruff` configured with an opinionated rule set (pyflakes, pycodestyle, bugbear, import-sorting); CI fails on any violation.
- No inline lint-suppression (`# noqa`, `// ignore:`) without a comment explaining why the suppression is justified.

## 8. Formatting Rules

- **Dart:** `dart format` (default 80-column line length) run as a pre-commit hook and CI check — no manual formatting debates.
- **Python:** `black` (default line length) + `ruff format` for import ordering, run as a pre-commit hook and CI check.
- Pre-commit hooks configured in the repo (`.pre-commit-config.yaml` or equivalent Husky-style setup for a mixed Dart/Python repo) so formatting issues are caught before commit, not just in CI.

---

*Next document: Phase 18 — Future Expansion.*
