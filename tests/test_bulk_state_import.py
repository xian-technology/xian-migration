"""Offline imports preserve large detached state without execution metering."""

from contracting.storage.driver import Driver
from xian.constants import Constants
from xian_runtime_types.time import Datetime

from xian_migration.genesis import (
    DELIMITER,
    INDEX_SEPARATOR,
    LegacyExport,
    LegacyMigrationOptions,
    _Builder,
    _ReplayNonces,
)


def builder(driver, tmp_path):
    export = LegacyExport("", 0, {}, {}, "", 0)
    options = LegacyMigrationOptions(
        chain_id="migration-bulk-test",
        genesis_time="2026-11-01T00:00:00Z",
        network="local",
        contracts_dir=tmp_path,
    )
    return _Builder(export, options, driver, Datetime(2026, 11, 1))


def test_large_imports_and_nonces_persist_without_transaction_write_limits(tmp_path):
    storage = tmp_path / "storage"
    entries = {f"con_bulk.state:{index}": "x" * 40_000 for index in range(8)}
    entries["con_bulk.large"] = "y" * 140_000
    sender = "a" * 64
    nonce_key = f"{Constants.NONCE_FILENAME}{INDEX_SEPARATOR}{sender}{DELIMITER}"
    with Driver(storage_home=storage) as driver:
        importer = builder(driver, tmp_path)
        for key, value in entries.items():
            importer.set(key, value)
        _ReplayNonces(driver).set_nonce(sender, 18)
        driver.commit()
    with Driver(storage_home=storage) as reopened:
        assert {key: reopened.get(key) for key in entries} == entries
        assert reopened.get(nonce_key) == 18


def test_imported_mutable_state_is_detached_from_export_inputs(tmp_path):
    source = {"nested": [{"items": [1, 2]}]}
    with Driver(storage_home=tmp_path / "storage") as driver:
        importer = builder(driver, tmp_path)
        importer.set("con_bulk.value", source)
        source["nested"][0]["items"].append(3)
        assert driver.get("con_bulk.value") == {"nested": [{"items": [1, 2]}]}
        driver.commit()
    with Driver(storage_home=tmp_path / "storage") as reopened:
        assert reopened.get("con_bulk.value") == {"nested": [{"items": [1, 2]}]}
