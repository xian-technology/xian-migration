"""Compare migrated artifact execution with an independent pre-VM capture."""

import hashlib
import json
from pathlib import Path

import xian_vm_core
from compatibility.observe import INITIAL_STATE, observe
from contracting.storage.driver import Driver
from test_legacy_genesis import _legacy_export_data, _options
from xian_runtime_types.encoding import decode, encode

from xian_migration.genesis import build_legacy_migration_genesis, parse_legacy_export

FIXTURES = Path(__file__).absolute().parent / "compatibility"
BASELINE = json.loads((FIXTURES / "legacy_execution.json").read_text())


def test_execution_baseline_provenance():
    assert BASELINE["revision"] == "3b82001f2d587bbfb51f3d9235a2a8dcd0078a9a"
    assert BASELINE["python"] == "3.12.10"
    for filename, digest in BASELINE["inputs"].items():
        assert hashlib.sha256((FIXTURES / filename).read_bytes()).hexdigest() == digest
    assert [item["status_code"] for item in BASELINE["observations"]] == [0, 0, 0, 0, 1, 0]


def test_recovered_migrated_artifacts_preserve_calls_state_and_events(tmp_path):
    export = _legacy_export_data()
    for name, compiled in BASELINE["compiled"].items():
        export["genesis"].extend(
            [
                {"key": f"{name}.__code__", "value": compiled},
                {"key": f"{name}.__developer__", "value": "alice"},
                {"key": f"{name}.__owner__", "value": None},
            ]
        )
    export["genesis"].extend({"key": key, "value": value} for key, value in INITIAL_STATE.items())
    migrated = build_legacy_migration_genesis(
        parse_legacy_export(decode(encode(export))), _options()
    )
    driver = Driver(storage_home=tmp_path)
    for item in decode(encode(migrated.genesis))["abci_genesis"]["genesis"]:
        driver.set(item["key"], item["value"])
    driver.commit()
    # Constructors must not overwrite migrated state while executing the new IR.
    assert driver.get("con_migration_probe.state:total") == 7

    def execute(function, kwargs):
        result = xian_vm_core.execute_contract(
            driver=driver,
            contract_name="con_migration_probe",
            function_name=function,
            kwargs=kwargs,
            context={"signer": "alice", "caller": "alice"},
            meter=False,
        )
        return {key: getattr(result, key) for key in ("status_code", "result", "writes", "events")}

    actual = observe(driver, execute)
    assert actual == BASELINE["observations"]
    assert driver.get("con_migration_probe.state:total") == 12
    assert driver.get("con_migration_probe.state:calls") == 3


def test_explicit_null_metadata_is_counted_as_an_export_entry():
    data = _legacy_export_data()
    data["genesis"].append({"key": "con_tok.__owner__", "value": None})
    migrated = build_legacy_migration_genesis(parse_legacy_export(decode(encode(data))), _options())
    assert migrated.report["contracts"]["con_tok"]["status"] == "migrated"
