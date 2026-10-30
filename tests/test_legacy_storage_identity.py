"""Migration must retain storage identity, including native foreign readers."""

import copy

import pytest
import xian_vm_core
from contracting.storage.driver import Driver
from test_legacy_genesis import _legacy_export_data, _options
from xian_runtime_types.encoding import decode, encode
from xian_runtime_types.time import Datetime

from xian.legacy_genesis import (
    LegacyMigrationError,
    _ReplayClient,
    _ReplayNonces,
    build_legacy_migration_genesis,
    parse_legacy_export,
    verify_migration_genesis,
)
from xian.utils.block import apply_state_changes_from_block

COLLIDING_EXPORT = """
__burn = Hash(default_value=False, contract='con_collision', name='burn')
@__export('con_collision')
def burn(token_id: str):
    __burn[token_id] = True
@__export('con_collision')
def read(token_id: str):
    return __burn[token_id]
"""
SCOPED_HANDLE = """
__ledger = Hash(default_value=0, contract='con_collision', name='ledger')
@__export('con_collision')
def snapshot(ledger: str):
    __ledger = ForeignHash(foreign_contract=ledger, foreign_name='balances',
                          contract='con_collision', name='ledger')
    return __ledger['alice']
@__export('con_collision')
def read(token_id: str):
    return __ledger[token_id]
"""
LOCAL_STORAGE = """
@__export('con_collision')
def read(ledger: str):
    __ledger = Hash(default_value=0, contract='con_collision', name='ledger')
    return __ledger[ledger]
"""


@pytest.fixture(
    params=[
        (COLLIDING_EXPORT, "burn", True),
        (SCOPED_HANDLE, "ledger", 7),
        (LOCAL_STORAGE, "ledger", 7),
    ]
)
def legacy_collision(request):
    code, variable, value = request.param
    data = _legacy_export_data()
    reader = (
        "__seen = ForeignHash(foreign_contract='con_collision', "
        f"foreign_name='{variable}', contract='con_reader', name='seen')\n"
        "@__export('con_reader')\n"
        "def read(token_id: str):\n    return __seen[token_id]\n"
    )
    data["genesis"].extend(
        [
            {"key": "con_collision.__code__", "value": code},
            {"key": f"con_collision.{variable}:alice", "value": value},
            {"key": "con_reader.__code__", "value": reader},
        ]
    )
    export = parse_legacy_export(decode(encode(data)))
    # A reviewed override deliberately removes the conflicting legacy API;
    # it keeps the original storage binding and the reader's existing API.
    override = (
        f"{variable} = Hash()\n@export\ndef read(token_id: str):\n    return {variable}[token_id]\n"
    )
    return export, override, variable, value


def test_build_rejects_unsafe_storage_collision(legacy_collision):
    export, _, _, _ = legacy_collision
    with pytest.raises(LegacyMigrationError, match="storage identity.*source override"):
        build_legacy_migration_genesis(export, _options())


def test_explicit_override_keeps_native_owner_and_foreign_reads(legacy_collision, tmp_path):
    export, override, variable, value = legacy_collision
    result = build_legacy_migration_genesis(
        export, _options(source_overrides={"con_collision": override})
    )
    verify_migration_genesis(result.genesis, export, result.report)
    assert result.report["contracts"]["con_collision"]["source"] == "override"
    with Driver(storage_home=tmp_path) as driver:
        block = decode(encode(result.genesis))["abci_genesis"]
        apply_state_changes_from_block(_ReplayClient(driver), _ReplayNonces(driver), block)
        driver.flush_cache()
        assert driver.get(f"con_collision.{variable}:alice") == value
        for name in ("con_collision", "con_reader"):
            output = xian_vm_core.execute_contract(
                driver=driver,
                contract_name=name,
                function_name="read",
                kwargs={"token_id": "alice"},
                context={"signer": "alice", "caller": "alice", "this": name},
                meter=True,
                chi_budget_raw=12_000_000,
            )
            assert output.status_code == 0, output.result
            assert output.result == value


def test_verifier_refuses_to_certify_unsafe_automatic_recovery(legacy_collision):
    export, override, _, _ = legacy_collision
    result = build_legacy_migration_genesis(
        export, _options(source_overrides={"con_collision": override})
    )
    report = copy.deepcopy(result.report)
    report["contracts"]["con_collision"]["source"] = "recovered"
    # A correct root and unchanged raw values cannot establish that automatic
    # recovery preserved binding semantics. Require an explicit override.
    with pytest.raises(LegacyMigrationError, match="storage identity.*source override"):
        verify_migration_genesis(result.genesis, export, report)


def test_verifier_rejects_old_storage_remapping_reports(legacy_collision):
    export, override, variable, _ = legacy_collision
    result = build_legacy_migration_genesis(
        export, _options(source_overrides={"con_collision": override})
    )
    result.report["contracts"]["con_collision"]["storage_renames"] = {variable: f"{variable}_store"}
    with pytest.raises(LegacyMigrationError, match="storage identity changed; rebuild"):
        verify_migration_genesis(result.genesis, export, result.report)


def test_migration_uses_full_utc_instant_for_missing_and_system_timestamps():
    export = parse_legacy_export(decode(encode(_legacy_export_data())))
    export.contracts["con_lock"].submitted = None
    # The fixture already omits submitted for con_lock, so entry_count is unchanged.
    result = build_legacy_migration_genesis(
        export, _options(genesis_time="2026-01-02T05:04:05.123456+02:00")
    )
    state = {entry["key"]: entry["value"] for entry in result.genesis["abci_genesis"]["genesis"]}
    expected = Datetime(2026, 1, 2, 3, 4, 5, 123456)
    assert state["submission.__submitted__"] == expected
    assert state["currency.__submitted__"] == expected
    assert state["con_lock.__submitted__"] == expected
    assert result.genesis["genesis_time"] == "2026-01-02T03:04:05.123456Z"
    assert result.report["target"]["genesis_time"] == result.genesis["genesis_time"]
