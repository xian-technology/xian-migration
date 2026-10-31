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
actual application flows and authenticated exports before a cutover. The runtime's R10–R16 batch covers ordered module rebinding, finite Decimal
quantum/type behavior, Unicode numeric text, dictionary mutation, bulk Hash
operations, additional methods and starred syntax. Preserve application-level
rehearsals for these operations even with the runtime regression coverage.
The pinned runtime now implements R17: general raw Decimal powers, in-memory
non-finite values, Decimal methods and DecimalTuple behavior within explicit
resource bounds. Arithmetic uses the historical 91-digit context; exact raw
construction has separate operand limits. Ordinary power limits each operand to
1,024 coefficient digits, and integer/modular power limits exponent extent
(digits + exponent) to 512. Non-finite values remain invalid in persisted state.
A recovered-contract regression covers fractional power, quantization, tuple
fields, rejected non-finite storage, rollback and a successful follow-up call.

This bounded compatibility implementation does not approve production migration
of arbitrary Decimal-dependent applications. Review actual application inputs
against the runtime limits and preserve authenticated export rehearsals and
all acceptance decisions above. Unsupported input sizes or business-behavior
mismatches still need a reviewed override or an explicit exclusion.
