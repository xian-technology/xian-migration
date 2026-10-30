import hashlib
import json
import subprocess
import sys

import pytest
from test_legacy_genesis import CONTRACTS_DIR, _legacy_export_data


def command(tmp_path, *, checksum=None, output_name="genesis.json"):
    export = tmp_path / "export.json"
    export.write_text(json.dumps(_legacy_export_data()))
    digest = checksum or hashlib.sha256(export.read_bytes()).hexdigest()
    return [
        sys.executable,
        "-m",
        "xian_migration.cli",
        "--export",
        str(export),
        "--export-sha256",
        digest,
        "--chain-id",
        "xian-migration-local",
        "--genesis-time",
        "2026-11-01T00:00:00Z",
        "--network",
        "local",
        "--contracts-dir",
        str(CONTRACTS_DIR),
        "--runtime-features",
        '{"zk": false}',
        "--output",
        str(tmp_path / output_name),
    ]


def test_cli_builds_verified_reproducible_genesis(tmp_path):
    args = command(tmp_path)
    result = subprocess.run(
        args + ["--sources-dir", str(tmp_path / "sources")], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    genesis = json.loads((tmp_path / "genesis.json").read_text())
    report = json.loads((tmp_path / "genesis.report.json").read_text())
    assert report["verification"]["app_hash"] == genesis["app_hash"]
    assert report["verification"]["nonces_verified"] == 2
    assert (tmp_path / "sources" / "con_tok.py").is_file()
    second = subprocess.run(
        command(tmp_path, output_name="again.json"), capture_output=True, text=True
    )
    assert second.returncode == 0, second.stderr
    assert (tmp_path / "again.json").read_bytes() == (tmp_path / "genesis.json").read_bytes()


def test_cli_checksum_failure_writes_no_genesis(tmp_path):
    result = subprocess.run(command(tmp_path, checksum="00" * 32), capture_output=True, text=True)
    assert result.returncode == 1
    assert "sha256 mismatch" in result.stderr
    assert not (tmp_path / "genesis.json").exists()
    assert not (tmp_path / "genesis.report.json").exists()


def test_cli_explicit_overrides_and_validator_are_reported(tmp_path):
    from xian_migration.cli import main

    override = tmp_path / "override.py"
    override.write_text(
        "data = Hash()\n@export\ndef check(locker_id: str):\n    return data[locker_id]\n"
    )
    args = command(tmp_path)[3:] + [
        "--validator",
        "A" * 64 + ":12",
        "--source-override",
        f"con_lock={override}",
        "--report",
        str(tmp_path / "review.json"),
        "--no-compat-rewrites",
        "--no-collision-renames",
        "--keep-masternode-holdings",
    ]
    assert main(args) == 0
    report = json.loads((tmp_path / "review.json").read_text())
    assert report["contracts"]["con_lock"]["source"] == "override"
    assert report["target"]["validators"] == [{"public_key": "a" * 64, "power": 12, "name": ""}]
    assert not report["system_contracts"]["masternodes"].get("holdings_refunded_to_depositors")


@pytest.mark.parametrize(
    "extra",
    [
        ["--source-override", "invalid"],
        ["--source-override", "con_lock=/nonexistent/source.py"],
        ["--runtime-features", "invalid-json"],
    ],
)
def test_cli_bad_operator_inputs_fail_without_writing(tmp_path, extra, capsys):
    from xian_migration.cli import main

    assert main(command(tmp_path)[3:] + extra) == 1
    assert "legacy migration failed:" in capsys.readouterr().err
    assert not (tmp_path / "genesis.json").exists()


@pytest.mark.parametrize(
    "flag",
    [
        "--export",
        "--chain-id",
        "--genesis-time",
        "--network",
        "--contracts-dir",
        "--runtime-features",
        "--output",
    ],
)
def test_cli_requires_explicit_target_inputs(tmp_path, flag):
    args = command(tmp_path)
    offset = args.index(flag)
    del args[offset : offset + 2]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 2
    assert flag in result.stderr
    assert not (tmp_path / "genesis.json").exists()


@pytest.mark.parametrize("value", ["con_lock=", "=unused"])
def test_cli_rejects_incomplete_source_override(tmp_path, capsys, value):
    from xian_migration.cli import main

    assert main(command(tmp_path)[3:] + ["--source-override", value]) == 1
    assert "expected NAME=PATH" in capsys.readouterr().err
    assert not (tmp_path / "genesis.json").exists()
