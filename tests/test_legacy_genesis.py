import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from legacy_fixtures import LEGACY_TOKEN
from xian_runtime_types.encoding import decode, encode

from xian_migration.genesis import (
    LegacyMigrationError,
    LegacyMigrationOptions,
    build_legacy_migration_genesis,
    load_legacy_export,
    parse_legacy_export,
    verify_migration_genesis,
)

CONTRACTS_DIR = Path(
    os.environ.get(
        "XIAN_MIGRATION_CONTRACTS_DIR",
        Path(__file__).resolve().parents[2] / "xian-configs" / "contracts",
    )
)
NODE = "a" * 64
HOLDER = "b" * 64
SPENDER_OWNER = "c" * 64

LEGACY_FSTRING = """\
__data = Hash(contract='con_lock', name='data')


@__export('con_lock')
def check(locker_id: str):
    assert locker_id == 'x', f"bad contract {__data[locker_id, 'contract']}."
"""


def _legacy_export_data():
    def entry(key, value):
        return {"key": key, "value": value}

    return {
        "hash": "ab" * 64,
        "number": 1000,
        "origin": {"sender": "", "signature": ""},
        "genesis": [
            entry("currency.__code__", "legacy currency code"),
            entry("currency.__developer__", "sys"),
            entry("currency.__submitted__", {"__time__": [2024, 9, 17, 9, 13, 0, 0]}),
            entry(
                f"currency.balances:{HOLDER}",
                {"__fixed__": "165805.201447835145634816366439603423"},
            ),
            entry("currency.balances:dao", {"__fixed__": "47481674.3934038559855599195"}),
            entry("currency.balances:masternodes", 200000),
            entry(f"currency.balances:{NODE}", 5),
            entry(f"currency.balances:{SPENDER_OWNER}:con_tok", {"__fixed__": "12.5"}),
            entry("currency.metadata:token_name", "XIAN"),
            entry("currency.streams:s1:status", "active"),
            entry("currency.streams:s1:sender", "dao_funding_stream"),
            entry("currency.streams:s1:receiver", "dao"),
            entry("currency.streams:s1:rate", {"__fixed__": "0.1"}),
            entry("foundation.__code__", "legacy foundation code"),
            entry("foundation.owner", HOLDER),
            entry("masternodes.__code__", "legacy masternodes code"),
            entry("masternodes.nodes", [NODE]),
            entry(f"masternodes.holdings:{NODE}", 100000),
            entry(f"masternodes.holdings:{HOLDER}", 100000),
            entry("stamp_cost.__code__", "legacy stamp code"),
            entry("stamp_cost.S:value", 100),
            entry("con_tok.__code__", LEGACY_TOKEN),
            entry("con_tok.__developer__", HOLDER),
            entry("con_tok.__submitted__", {"__time__": [2025, 1, 2, 3, 4, 0, 0]}),
            entry(f"con_tok.balances:{HOLDER}", 7),
            entry("con_tok.owner", HOLDER),
            entry("con_tok.weights", [-1.25, 0.5]),
            entry("con_lock.__code__", LEGACY_FSTRING),
            entry("con_lock.__developer__", HOLDER),
            entry("con_lock.data:l1:contract", "con_tok"),
        ],
        "nonces": [
            {"key": HOLDER, "value": 18},
            {"key": NODE, "value": 0},
        ],
    }


def _options(**overrides):
    values = {
        "chain_id": "xian-migrated-test",
        "genesis_time": "2026-11-01T00:00:00Z",
        "network": "local",
        "contracts_dir": CONTRACTS_DIR,
    }
    values.update(overrides)
    return LegacyMigrationOptions(**values)


class LegacyGenesisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.export = parse_legacy_export(decode(encode(_legacy_export_data())), sha256="test")
        cls.result = build_legacy_migration_genesis(cls.export, _options())
        cls.state = {
            entry["key"]: entry["value"] for entry in cls.result.genesis["abci_genesis"]["genesis"]
        }

    def test_genesis_verifies_by_replay(self):
        verification = verify_migration_genesis(
            self.result.genesis, self.export, self.result.report
        )
        self.assertEqual(verification["app_hash"], self.result.genesis["app_hash"])
        self.assertEqual(verification["nonces_verified"], 2)

    def test_build_is_reproducible(self):
        again = build_legacy_migration_genesis(self.export, _options())
        self.assertEqual(encode(again.genesis), encode(self.result.genesis))

    def test_heights_continue_from_legacy_chain(self):
        self.assertEqual(self.result.genesis["initial_height"], "1001")
        self.assertEqual(self.result.genesis["abci_genesis"]["number"], "1000")
        self.assertEqual(self.result.genesis["chain_id"], "xian-migrated-test")

    def test_nonces_are_carried_with_runtime_key_format(self):
        self.assertEqual(self.state[f"__n.{HOLDER}:"], 18)
        self.assertEqual(self.state[f"__n.{NODE}:"], 0)

    def test_legacy_ledger_replaces_bundle_allocation_exactly(self):
        balances = {
            key.split(":", 1)[1]: value
            for key, value in self.state.items()
            if key.startswith("currency.balances:")
        }
        self.assertEqual(
            str(balances[HOLDER]),
            str(decode('{"__fixed__":"265805.201447835145634816366439603423"}')),
        )
        self.assertEqual(int(balances["masternodes"]), 0)
        self.assertEqual(int(balances[NODE]), 100005)
        self.assertNotIn(f"{SPENDER_OWNER}:con_tok", balances)
        self.assertEqual(str(self.state[f"currency.approvals:{SPENDER_OWNER}:con_tok"]), "12.5")
        self.assertEqual(
            str(self.state["currency.metadata:total_supply"]),
            "47847484.594851691131194735866439603423",
        )

    def test_streams_are_preserved_and_flagged(self):
        self.assertEqual(self.state["currency.streams:s1:sender"], "dao_funding_stream")
        self.assertTrue(any("streams" in w for w in self.result.report["warnings"]))

    def test_user_contract_recompiled_with_metadata_and_state(self):
        self.assertIn("con_tok.__xian_ir_v1__", self.state)
        self.assertIn("@export", self.state["con_tok.__source__"])
        self.assertEqual(self.state["con_tok.__developer__"], HOLDER)
        self.assertEqual(self.state[f"con_tok.balances:{HOLDER}"], 7)
        self.assertEqual(self.state["con_tok.weights"], [-1.25, 0.5])

    def test_compat_rewrite_is_applied_and_reported(self):
        entry = self.result.report["contracts"]["con_lock"]
        self.assertEqual(entry["compat_rewrites"], {"fstring_string_literals": 1})
        self.assertIn("con_lock.__xian_ir_v1__", self.state)

    def test_retired_system_contracts_are_not_deployed(self):
        self.assertNotIn("masternodes.__source__", self.state)
        self.assertNotIn("stamp_cost.__source__", self.state)
        retired = self.result.report["system_contracts"]["masternodes"]
        self.assertEqual(
            retired["holdings_refunded_to_depositors"],
            {HOLDER: "100000", NODE: "100000"},
        )

    def test_validators_and_foundation_owner_come_from_legacy_state(self):
        self.assertEqual(self.state["foundation.owner"], HOLDER)
        self.assertEqual(len(self.result.genesis["validators"]), 1)
        self.assertEqual(self.result.report["target"]["validators"][0]["public_key"], NODE)

    def test_uncompilable_contract_stops_the_build(self):
        data = _legacy_export_data()
        data["genesis"].append({"key": "con_bad.__code__", "value": "while True:\n    pass\n"})
        export = parse_legacy_export(decode(encode(data)))
        with self.assertRaisesRegex(LegacyMigrationError, "con_bad"):
            build_legacy_migration_genesis(export, _options())
        skipped = build_legacy_migration_genesis(
            export, _options(skip_contracts=frozenset({"con_bad"}))
        )
        self.assertEqual(skipped.report["summary"]["user_contracts_skipped"], ["con_bad"])

    def test_disabling_compat_rewrites_fails_loudly(self):
        with self.assertRaisesRegex(LegacyMigrationError, "con_lock"):
            build_legacy_migration_genesis(self.export, _options(compat_rewrites=frozenset()))

    def test_source_override_replaces_recovered_source(self):
        override = "data = Hash()\n\n@export\ndef check(locker_id: str):\n    return data[locker_id, 'contract']\n"
        result = build_legacy_migration_genesis(
            self.export, _options(source_overrides={"con_lock": override})
        )
        self.assertEqual(result.report["contracts"]["con_lock"]["source"], "override")

    def test_export_checksum_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exported_state.json"
            raw = json.dumps(_legacy_export_data()).encode()
            path.write_bytes(raw)
            self.assertEqual(
                load_legacy_export(path, expected_sha256=hashlib.sha256(raw).hexdigest()).sha256,
                hashlib.sha256(raw).hexdigest(),
            )
            with self.assertRaisesRegex(LegacyMigrationError, "sha256 mismatch"):
                load_legacy_export(path, expected_sha256="00" * 32)

    def test_malformed_exports_are_rejected(self):
        data = _legacy_export_data()
        data["nonces"].append({"key": "not-a-key", "value": 1})
        with self.assertRaisesRegex(LegacyMigrationError, "nonce sender"):
            parse_legacy_export(data)
        data = _legacy_export_data()
        data["genesis"].append(copy.deepcopy(data["genesis"][0]))
        with self.assertRaisesRegex(LegacyMigrationError, "duplicate key"):
            parse_legacy_export(data)
        data = _legacy_export_data()
        data["genesis"].append({"key": "con_orphan.balances:x", "value": 1})
        with self.assertRaisesRegex(LegacyMigrationError, "no __code__"):
            parse_legacy_export(data)


class ExplicitBundleTests(unittest.TestCase):
    def test_network_and_contract_directory_are_required(self):
        base = {"chain_id": "migration-test", "genesis_time": "2026-11-01T00:00:00Z"}
        with self.assertRaisesRegex(TypeError, "network.*contracts_dir"):
            LegacyMigrationOptions(**base)
        with self.assertRaisesRegex(TypeError, "contracts_dir"):
            LegacyMigrationOptions(**base, network="local")
        with self.assertRaisesRegex(TypeError, "network"):
            LegacyMigrationOptions(**base, contracts_dir=CONTRACTS_DIR)

    def test_missing_explicit_bundle_does_not_fall_back_to_sibling(self):
        export = parse_legacy_export(decode(encode(_legacy_export_data())))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                build_legacy_migration_genesis(export, _options(contracts_dir=Path(directory)))

    def test_none_contract_directory_does_not_select_default(self):
        export = parse_legacy_export(decode(encode(_legacy_export_data())))
        with self.assertRaises(TypeError):
            build_legacy_migration_genesis(export, _options(contracts_dir=None))

    def test_relative_explicit_path_is_not_rewritten_on_options(self):
        export = parse_legacy_export(decode(encode(_legacy_export_data())))
        options = _options(contracts_dir=Path(os.path.relpath(CONTRACTS_DIR)))
        original = options.contracts_dir
        result = build_legacy_migration_genesis(export, options)
        self.assertEqual(options.contracts_dir, original)
        self.assertEqual(result.report["target"]["network_bundle"], "local")


class LegacyExportBoundaryTests(unittest.TestCase):
    def test_invalid_shapes_and_missing_code_are_rejected(self):
        for data in [None, [], {}, {"genesis": {}}, {"genesis": []}]:
            with self.subTest(data=data), self.assertRaises(LegacyMigrationError):
                parse_legacy_export(data)
        for key in ["currency", "currency.", "__n.sender:"]:
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(LegacyMigrationError, "unexpected key"),
            ):
                parse_legacy_export({"genesis": [{"key": key, "value": 1}]})

    def test_nonce_validation_and_legacy_delimiter(self):
        data = _legacy_export_data()
        data["nonces"] = [{"key": HOLDER + ":", "value": 3}]
        self.assertEqual(parse_legacy_export(data).nonces, {HOLDER: 3})
        for nonce in [-1, True, 1.5, "1"]:
            data["nonces"] = [{"key": HOLDER, "value": nonce}]
            with (
                self.subTest(nonce=nonce),
                self.assertRaisesRegex(LegacyMigrationError, "invalid nonce"),
            ):
                parse_legacy_export(data)
        data["nonces"] = [{"key": HOLDER, "value": 1}, {"key": HOLDER + ":", "value": 1}]
        with self.assertRaisesRegex(LegacyMigrationError, "duplicate nonce"):
            parse_legacy_export(data)


class MigrationVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = _legacy_export_data()
        data["genesis"].append({"key": "currency.balances:empty_account", "value": 0})
        cls.export = parse_legacy_export(decode(encode(data)))
        cls.result = build_legacy_migration_genesis(cls.export, _options())

    def changed_genesis(self, key, value=None, *, remove=False):
        from xian.state_root import compute_exported_state_root

        genesis = copy.deepcopy(self.result.genesis)
        entries = genesis["abci_genesis"]["genesis"]
        if remove:
            entries[:] = [entry for entry in entries if entry["key"] != key]
        else:
            next(entry for entry in entries if entry["key"] == key)["value"] = value
        # A valid app hash is necessary but does not prove migration fidelity.
        root = compute_exported_state_root(genesis["abci_genesis"]).hex()
        genesis["abci_genesis"]["hash"] = root
        genesis["app_hash"] = root
        return genesis

    def test_changed_user_state_is_rejected_even_with_consistent_hash(self):
        genesis = self.changed_genesis(f"con_tok.balances:{HOLDER}", 99)
        with self.assertRaisesRegex(LegacyMigrationError, "value con_tok.balances"):
            verify_migration_genesis(genesis, self.export, self.result.report)

    def test_missing_native_artifact_is_rejected_even_when_source_exists(self):
        genesis = self.changed_genesis("con_tok.__xian_ir_v1__", remove=True)
        with self.assertRaisesRegex(LegacyMigrationError, "has no xian_vm_v1 artifacts"):
            verify_migration_genesis(genesis, self.export, self.result.report)

    def test_absent_zero_balance_is_equivalent_to_legacy_zero(self):
        genesis = self.changed_genesis("currency.balances:empty_account", remove=True)
        verification = verify_migration_genesis(genesis, self.export, self.result.report)
        self.assertEqual(verification["app_hash"], genesis["app_hash"])

    def test_initial_height_must_be_positive_and_one_is_valid(self):
        for height in (0, -1):
            with (
                self.subTest(height=height),
                self.assertRaisesRegex(LegacyMigrationError, "at least 1"),
            ):
                build_legacy_migration_genesis(self.export, _options(initial_height=height))
        result = build_legacy_migration_genesis(self.export, _options(initial_height=1))
        self.assertEqual(result.genesis["initial_height"], "1")
        self.assertEqual(result.genesis["abci_genesis"]["number"], "0")


if __name__ == "__main__":
    unittest.main()
