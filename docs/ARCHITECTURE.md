# Architecture

`xian_migration.source` recovers authored Python from the legacy transformed
source and applies explicitly reported compatibility rewrites.
`xian_migration.genesis` parses exports, orchestrates target bundle deployment,
layers legacy state and nonces, and verifies the rendered genesis.
`xian_migration.cli` owns arguments, file input/output and operator reporting.

The dependency direction is migration → ABCI/compiler/runtime. ABCI owns
generic bundle deployment, genesis finalization, state replay and state-root
calculation. Contracting owns compilation, VM execution and storage. Configs
owns target network contract bundles. None of these packages imports migration.

Runtime dependencies use immutable Git revisions in package metadata and the uv lockfile. Inherited uv development-source
overrides are disabled so dependencies cannot resolve to implicit sibling paths.
Configuration inputs are external and must be recorded for each rehearsal.
The CLI runs offline against temporary storage; it never modifies a node home.

Changes to recovered source do not prove equivalent business logic. Reviewed
overrides and unresolved compatibility decisions remain operator inputs.
