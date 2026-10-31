"""Capture pre-migration execution with the independently pinned old runtime."""

import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).absolute().parents[1]
FIXTURES = ROOT / "tests" / "compatibility"
REVISION = "3b82001f2d587bbfb51f3d9235a2a8dcd0078a9a"


def capture(directory):
    archive = subprocess.check_output(
        ["git", "archive", REVISION], cwd=ROOT.parent / "xian-contracting"
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as files:
        files.extractall(directory, filter="data")
    subprocess.run(
        ["uv", "sync", "--frozen", "--python", "3.12.10", "--no-editable"],
        cwd=directory,
        check=True,
    )
    python = directory / ".venv/bin/python"
    origin = subprocess.check_output(
        [str(python), "-c", "import contracting; print(contracting.__file__)"],
        cwd=directory,
        text=True,
    ).strip()
    if not Path(origin).is_relative_to(directory):
        raise RuntimeError(f"Oracle imported an unintended installation: {origin}")
    output = directory / "observations.json"
    subprocess.run(
        [
            str(python),
            str(FIXTURES / "observe.py"),
            str(FIXTURES / "contracts.json"),
            str(output),
        ],
        cwd=directory,
        check=True,
        timeout=120,
    )
    baseline = json.loads(output.read_text())
    baseline.update(
        revision=REVISION,
        python="3.12.10",
        dependency_lock_sha256=hashlib.sha256((directory / "uv.lock").read_bytes()).hexdigest(),
    )
    baseline["inputs"] = {
        name: hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
        for name in ("observe.py", "contracts.json")
    }
    return baseline


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="xian-migration-oracle-") as temporary:
        result = capture(Path(temporary))
    (FIXTURES / "legacy_execution.json").write_text(json.dumps(result, indent=2) + "\n")
