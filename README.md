# xian-migration

Offline tooling for converting an exported legacy Xian chain into a genesis
for the current VM. It recovers contract source, recompiles contracts, carries
state and nonces, and verifies the resulting genesis by replaying its state.
Nodes do not install or depend on this tool.

## Quick Start

Use Python 3.14, uv, and a Rust toolchain to build the pinned native compiler
and VM dependencies. From this repository:

```bash
uv sync --locked --group dev
uv run --locked xian-legacy-genesis --help
```

The runtime source revisions are pinned in `pyproject.toml` and `uv.lock`.
The configuration fixture revision is recorded in `runtime-manifest.json`.
For tests, place that revision of `xian-configs` alongside this repository,
or set `XIAN_MIGRATION_CONTRACTS_DIR` to its `contracts` directory. Do not
reset an existing sibling checkout to prepare a rehearsal; use an isolated
clone when it differs from the recorded revision.

An explicit local rehearsal command is:

```bash
uv run --locked xian-legacy-genesis \
  --export /path/to/exported_state.json \
  --export-sha256 <expected-sha256> \
  --chain-id xian-migration-local \
  --genesis-time 2026-11-01T00:00:00Z \
  --network local \
  --contracts-dir ../xian-configs/contracts \
  --runtime-features '{"zk": false}' \
  --output /path/to/rehearsal/genesis.json
```

Review the accompanying report and recovered sources before accepting a
migration. Passing validation does not resolve the frozen-stream and
allowance-reader compatibility decisions described in the migration guide.

## Scope

- Legacy-specific transforms live here; generic genesis and state primitives
  are imported from `xian-abci`, with compilation supplied by `xian-contracting`.
- Storage-binding collisions require reviewed source overrides or explicit
  skips. The tool does not automatically move user storage keys.
- Target bundle and network are explicit inputs. No node or Docker service is
  needed to build and verify an offline genesis.
- After a migration, retain the exact tool revision, lockfile, input hashes,
  report and operator decisions for audit and reproducibility. The repository
  can then be archived independently of the node runtime.

## Validation

```bash
./scripts/validate.sh
uv run --locked pytest --cov=xian_migration --cov-report=term-missing
```

Tests use synthetic state exports and temporary storage. They cover source
recovery, balances, nonces, timestamps, reproducibility, storage identity, and
the installed command-line workflow.

## Related Docs

- [AGENTS.md](AGENTS.md) — contributor workflow
- [Migration guide](docs/MIGRATION.md) — transformations and compatibility
- [Architecture](docs/ARCHITECTURE.md) — ownership and dependencies
- [Backlog](docs/BACKLOG.md) — unresolved migration decisions
- [Source provenance](PROVENANCE.md) — original implementation and repairs
- [Workspace conventions](https://github.com/xian-technology/xian-meta)
