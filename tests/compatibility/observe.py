"""Runs unchanged inside the pinned historical Python installation."""

import json
import sys
from pathlib import Path

CALLS = [
    ("apply", {"amount": 3}),
    ("aliases", {}),
    ("iterators", {}),
    ("builtins", {}),
    ("apply", {"amount": -1}),
    ("apply", {"amount": 2}),
]
INITIAL_STATE = {"con_migration_probe.state:total": 7}


def observe(driver, execute):
    observations = []
    for function, kwargs in CALLS:
        output = execute(function, kwargs)
        if output["status_code"] != (1 if kwargs.get("amount") == -1 else 0):
            raise RuntimeError(f"Unexpected {function} result: {output}")
        observation = {key: output[key] for key in ("status_code", "writes", "events")}
        if output["status_code"] == 0:
            observation["result"] = output["result"]
            for key, value in output["writes"].items():
                driver.set(key, value)
            driver.commit()
        else:
            driver.rollback()
        observations.append(observation)
    return observations


def capture(sources, home):
    from contracting.compilation.compiler import ContractingCompiler
    from contracting.execution.executor import Executor
    from contracting.storage.driver import Driver

    driver = Driver(storage_home=home)
    compiled = {}
    for name, source in sources.items():
        compiled[name] = ContractingCompiler(module_name=name).parse_to_code(source)
        driver.set_contract_from_source(name, source, owner=None)
    for key, value in INITIAL_STATE.items():
        driver.set(key, value)
    driver.commit()
    executor = Executor(driver=driver, metering=False)

    def execute(function, kwargs):
        return executor.execute(
            sender="alice",
            contract_name="con_migration_probe",
            function_name=function,
            kwargs=kwargs,
            metering=False,
        )

    return {"compiled": compiled, "observations": observe(driver, execute)}


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as home:
        result = capture(json.loads(Path(sys.argv[1]).read_text()), home)
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n")
