# Repository Guidelines

This repository owns offline legacy-chain migration: source recovery, state
conversion, genesis verification, reports, and the `xian-legacy-genesis` CLI.
Read README.md, docs/ARCHITECTURE.md and docs/BACKLOG.md before changing it.

- Follow sibling `xian-meta` conventions and change workflow; use UB-mode.
- Keep dependency direction one-way: migration imports the node/compiler APIs;
  node runtime repositories must never depend on this package.
- Never copy compiler, genesis hashing, or node execution implementations here.
- Pin runtime sources in pyproject.toml and uv.lock; pin configuration fixtures
  in runtime-manifest.json. Update pins only with compatibility validation.
- Require explicit target network/bundle inputs. Do not add public RPC defaults.
- Never commit real exports, private keys, or generated chain state.
- Preserve storage identity. Unsafe recovery must require a reviewed override.
- Streams and allowance-reader compatibility remain explicit policy decisions.
- Do not start a network for unit/CLI tests; use temporary storage directories.

## Validation

Run `uv sync --locked --group dev`, then `./scripts/validate.sh`. This runs
lint, format checks, all migration tests, CLI help, and a package build.
Tests use the pinned sibling xian-configs fixture; see README.md for setup.
Behavior changes require meaningful regressions, coverage and focused mutation
checks. Keep evidence in ignored `.artifacts/`; do not commit generated graphs.

## Documentation

Keep docs/MIGRATION.md aligned with CLI/API behavior and docs/BACKLOG.md explicit
about unresolved compatibility. Check public xian-docs-web operator guidance
when changing the migration workflow.
