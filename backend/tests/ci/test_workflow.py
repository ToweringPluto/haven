"""P0-09: the GitHub Actions workflow runs the same gates as the local loop."""

import re
from typing import Any

import yaml

from haven.config import REPO_ROOT

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PINNED_TAG = re.compile(r"^[\w.-]+/[\w.-]+@v\d+\.\d+\.\d+$")


def _workflow() -> dict[Any, Any]:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _steps() -> list[dict[str, Any]]:
    return [step for job in _workflow()["jobs"].values() for step in job["steps"]]


def test_triggers_on_push_and_pull_request() -> None:
    wf = _workflow()
    # PyYAML (YAML 1.1) reads the bare key `on` as the boolean True.
    triggers = wf.get("on", wf.get(True))
    assert isinstance(triggers, dict)
    assert {"push", "pull_request"} <= set(triggers)


def test_runs_on_ubuntu_latest() -> None:
    for job in _workflow()["jobs"].values():
        assert job["runs-on"] == "ubuntu-latest"


def test_actions_are_pinned_to_full_version_tags() -> None:
    uses = [step["uses"] for step in _steps() if "uses" in step]
    assert uses, "workflow uses no actions"
    for ref in uses:
        assert PINNED_TAG.match(ref), f"{ref} is not pinned to a vX.Y.Z tag"
    assert any(ref.startswith("astral-sh/setup-uv@") for ref in uses)


def test_runs_lint_test_and_contract_check() -> None:
    runs = [step["run"] for step in _steps() if "run" in step]
    for task in ("lint", "test", "contract-check"):
        assert f"uv run --directory backend poe {task}" in runs, f"poe {task} missing"
