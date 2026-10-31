# Tests

Synthetic legacy exports exercise source recovery and native genesis replay.
CLI tests call the package command with temporary files. Never add live exports
or private keys. Run the suite using the root validation script.

`test_execution_compatibility.py` compares actual migrated native execution with
an independent pre-VM capture in `compatibility/legacy_execution.json`. The
capture script binds source and observer hashes and requires successful oracle
calls before writing evidence. An intentional failure tests rollback and a
subsequent call. It also covers explicit null metadata entry accounting.
