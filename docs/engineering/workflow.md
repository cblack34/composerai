# Workflow

## Delivery

- Direct PRs to `main`. A human merges.
- Agents never merge to `main`.
- Conventional Commits PR titles.

## Refactor-before-handoff

Before a PR is ready:

1. Review changed files against `code-quality.md`.
2. Apply justified, behavior-preserving refactors.
3. Re-run verification.
4. Record a short receipt in the PR.

## Stop conditions

Stop and ask if a change would alter a non-negotiable, expand past the seed, or require a new external dependency not already agreed.
