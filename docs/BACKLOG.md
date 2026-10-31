# Migration decisions

Before any real cutover:

- Decide how active legacy streams and their backing balances will be migrated;
  the target currency contract lacks the legacy stream operations.
- Review contracts reading allowances through `currency.balances`; migrated
  allowances live in `currency.approvals`.
- Review source overrides and skipped contracts, including affected callers.
- Select consensus keys, target bundle, runtime features and a pinned release.
- Rehearse against an authenticated complete export, independently reproduce
  the genesis, and test representative migrated applications end to end.

The synthetic regression suite is not a production migration acceptance gate.
See [the migration guide](MIGRATION.md) for exact current transformations.

The pinned historical execution corpus now verifies recovered source, constructor
state preservation, imports, aliasing, lazy iteration, builtins, writes/events,
rollback and subsequent calls through migrated native artifacts. Expand it with
actual application flows and authenticated exports before a cutover. In particular,
review duplicate module bindings, decimal quantum/type behavior, Unicode numeric
parsing and same-size dictionary key replacement during iteration; the synthetic
corpus does not settle these remaining runtime compatibility gaps.
