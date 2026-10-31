# Tests

Synthetic legacy exports exercise source recovery and native genesis replay.
CLI tests call the package command with temporary files. Never add live exports
or private keys. Run the suite using the root validation script.

`test_execution_compatibility.py` compares actual migrated native execution with
an independent pre-VM capture in `compatibility/legacy_execution.json`. The
capture script binds source and observer hashes and requires successful oracle
calls before writing evidence. An intentional failure tests rollback and a
subsequent call. It also covers explicit null metadata entry accounting.

`test_decimal_execution.py` migrates a synthetic legacy compiler-shaped contract
and checks raw fractional power, Decimal methods/tuple fields, finite-only
storage rollback and a successful follow-up call. Its recorded power value
comes from Python 3.12.10/libmpdec 4.0.0. This is a focused runtime-pin regression,
not an additional authenticated historical contract capture or a production
migration acceptance gate.
