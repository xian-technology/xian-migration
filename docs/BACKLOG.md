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
