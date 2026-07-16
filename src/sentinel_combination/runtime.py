from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence

from .components import COMPONENTS, PROJECT_ROOT, ComponentPin, component_python_paths


def _clean_remainder(args: Sequence[str]) -> list[str]:
    values = list(args)
    if values and values[0] == "--":
        values.pop(0)
    return values


def component_env(component: ComponentPin) -> dict[str, str]:
    env = os.environ.copy()
    paths = component_python_paths([component])
    existing = env.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["SENTINEL_COMBINATION_COMPONENT"] = component.key
    env["SENTINEL_COMBINATION_PIN"] = component.commit
    return env


def require_component(key: str) -> ComponentPin:
    component = COMPONENTS[key]
    if not component.initialized:
        raise RuntimeError(
            f"{component.display_name} is not initialized at {component.path}. "
            "Run: git submodule update --init --recursive"
        )
    return component


def run_chain(*, host: str, port: int, reload: bool = False, extra_args: Sequence[str] = ()) -> int:
    component = require_component("chain")
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "sentinel_chain.app:create_app_from_env",
        "--factory",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        command.append("--reload")
    command.extend(_clean_remainder(extra_args))
    return subprocess.run(command, cwd=component.path, env=component_env(component), check=False).returncode


def run_iron(args: Sequence[str]) -> int:
    component = require_component("iron")
    forwarded = _clean_remainder(args)
    code = (
        "import sys; "
        "from sentinel_iron.cli import main; "
        "sys.argv = ['sentinel-iron', *sys.argv[1:]]; "
        "raise SystemExit(main())"
    )
    command = [sys.executable, "-c", code, *forwarded]
    return subprocess.run(command, cwd=component.path, env=component_env(component), check=False).returncode


def verify_import(component: ComponentPin) -> tuple[bool, str]:
    if not component.initialized:
        return False, "submodule_not_initialized"
    code = f"import {component.package_name}; print({component.package_name}.__name__)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=component.path,
        env=component_env(component),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True, result.stdout.strip() or "import_ok"
    return False, result.stderr.strip() or "import_failed"


def run_tests(keys: Iterable[str] = ("combination", "chain", "iron")) -> int:
    for key in keys:
        if key == "combination":
            command = [sys.executable, "-m", "pytest", str(PROJECT_ROOT / "tests")]
            result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        else:
            component = require_component(key)
            command = [sys.executable, "-m", "pytest", str(component.path / "tests")]
            result = subprocess.run(command, cwd=component.path, env=component_env(component), check=False)
        if result.returncode != 0:
            return result.returncode
    return 0
