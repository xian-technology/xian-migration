"""Execute a recovered Decimal contract against the pinned migration runtime."""

import xian_vm_core
from contracting.storage.driver import Driver
from test_legacy_genesis import _legacy_export_data, _options
from xian_runtime_types.encoding import decode, encode

from xian_migration.genesis import build_legacy_migration_genesis, parse_legacy_export

CONTRACT = "con_decimal_migration"
# Same transformed source shape as the legacy compiler: explicit storage identity,
# privatized storage binding, constructor alias and contract-bound export decorator.
LEGACY_DECIMAL_CONTRACT = """\
__state = Hash(default_value=0, contract='con_decimal_migration', name='state')


def ____():
    __state['calls'] = 999


@__export('con_decimal_migration')
def quote(amount: int, fail: bool = False):
    __state['calls'] += amount
    raw = round(decimal('2'), 0) ** round(decimal('0.3'), 1)
    rounded = raw.quantize(round(decimal('0.0001'), 4))
    parts = rounded.as_tuple()
    if fail:
        __state['invalid'] = round(decimal('0'), 0) ** -1
    return {
        'power': str(raw),
        'rounded': str(rounded),
        'tuple': [parts.sign, list(parts.digits), parts.exponent],
        'calls': __state['calls'],
    }
"""
# Captured independently with Python 3.12.10/libmpdec 4.0.0 at precision 91,
# ROUND_DOWN, Emin=-100, Emax=100; also covered by the runtime oracle corpus.
EXPECTED_POWER = (
    "1.231144413344916284499393069167743109876137761100817794337065538246100719719358458404022749"
)


def _migrated_decimal_driver(home):
    export = _legacy_export_data()
    export["genesis"].extend(
        [
            {"key": f"{CONTRACT}.__code__", "value": LEGACY_DECIMAL_CONTRACT},
            {"key": f"{CONTRACT}.__developer__", "value": "alice"},
            {"key": f"{CONTRACT}.__owner__", "value": None},
            {"key": f"{CONTRACT}.state:calls", "value": 7},
        ]
    )
    migrated = build_legacy_migration_genesis(
        parse_legacy_export(decode(encode(export))), _options()
    )
    assert migrated.report["contracts"][CONTRACT]["source"] == "recovered"
    driver = Driver(storage_home=home)
    for item in decode(encode(migrated.genesis))["abci_genesis"]["genesis"]:
        driver.set(item["key"], item["value"])
    driver.commit()
    return driver


def _quote(driver, amount, *, fail=False):
    return xian_vm_core.execute_contract(
        driver=driver,
        contract_name=CONTRACT,
        function_name="quote",
        kwargs={"amount": amount, "fail": fail},
        context={"signer": "alice", "caller": "alice"},
        meter=False,
    )


def _commit(driver, result):
    for key, value in result.writes.items():
        driver.set(key, value)
    driver.commit()


def test_migrated_decimal_power_methods_tuple_and_storage_rollback(tmp_path):
    with _migrated_decimal_driver(tmp_path) as driver:
        # Recompilation must not replace exported state with the constructor's 999.
        assert driver.get(f"{CONTRACT}.state:calls") == 7
        first = _quote(driver, 2)
        assert first.status_code == 0, first.result
        assert first.result == {
            "power": EXPECTED_POWER,
            "rounded": "1.2311",
            "tuple": [0, [1, 2, 3, 1, 1], -4],
            "calls": 9,
        }
        _commit(driver, first)

        rejected = _quote(driver, 100, fail=True)
        assert rejected.status_code == 1
        assert "non-finite" in str(rejected.result)
        assert rejected.writes == {}
        driver.rollback()
        assert driver.get(f"{CONTRACT}.state:calls") == 9
        assert driver.get(f"{CONTRACT}.state:invalid") is None

        followup = _quote(driver, 1)
        assert followup.status_code == 0, followup.result
        assert followup.result == {**first.result, "calls": 10}
        _commit(driver, followup)
        assert driver.get(f"{CONTRACT}.state:calls") == 10
