from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = PROJECT_ROOT / "combination.lock.json"


@dataclass(frozen=True)
class ComponentPin:
    key: str
    display_name: str
    repository: str
    commit: str
    relative_path: str
    package_name: str

    @property
    def path(self) -> Path:
        return PROJECT_ROOT / self.relative_path

    @property
    def src_path(self) -> Path:
        return self.path / "src"

    @property
    def initialized(self) -> bool:
        return (self.path / "pyproject.toml").is_file() and self.src_path.is_dir()

    def current_head(self) -> str | None:
        if not self.initialized:
            return None
        try:
            result = subprocess.run(
                ["git", "-C", str(self.path), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        head = result.stdout.strip()
        return head or None

    def status(self) -> dict[str, object]:
        head = self.current_head()
        return {
            **asdict(self),
            "path": str(self.path),
            "initialized": self.initialized,
            "current_head": head,
            "pin_matches": head == self.commit if head else False,
        }


COMPONENTS: dict[str, ComponentPin] = {
    "chain": ComponentPin(
        key="chain",
        display_name="Sentinel Chain",
        repository="https://github.com/Tetradim/Sentinel-Chain.git",
        commit="6b8af3675cc4ecf6cea879f740d614764805756c",
        relative_path="components/sentinel-chain",
        package_name="sentinel_chain",
    ),
    "iron": ComponentPin(
        key="iron",
        display_name="Sentinel Iron",
        repository="https://github.com/Tetradim/Sentinel-Iron.git",
        commit="f26c1c2010f1c2e94a13147f58d6dd99c6c9bb21",
        relative_path="components/sentinel-iron",
        package_name="sentinel_iron",
    ),
}


def load_lock() -> dict[str, object]:
    with LOCK_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def component_python_paths(components: Iterable[ComponentPin] | None = None) -> list[str]:
    selected = list(components or COMPONENTS.values())
    return [str(component.src_path) for component in selected if component.initialized]


def doctor_report() -> dict[str, object]:
    statuses = {key: component.status() for key, component in COMPONENTS.items()}
    return {
        "project_root": str(PROJECT_ROOT),
        "lock_path": str(LOCK_PATH),
        "lock_present": LOCK_PATH.is_file(),
        "components": statuses,
        "healthy": all(status["initialized"] and status["pin_matches"] for status in statuses.values()),
    }
