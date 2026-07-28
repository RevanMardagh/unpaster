"""Guards on the GitHub Actions workflows.

A ${{ }} expression inside a run: script is substituted textually before the
shell sees it, so any context value an attacker can influence becomes shell
input. Git allows ; & | $ ( ) in a ref name, which made
`--tag ${{ github.ref_name }}` a command injection in a job holding a
contents: write token. Values belong in env: instead, where the runner sets
them at execution time.
"""

from pathlib import Path

import pytest
import yaml

WORKFLOW_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"
WORKFLOWS = sorted(WORKFLOW_DIR.glob("*.yml"))


def _steps(workflow: dict):
    for job_name, job in workflow["jobs"].items():
        for step in job["steps"]:
            yield job_name, step


def test_the_workflows_are_where_the_tests_look():
    assert [path.name for path in WORKFLOWS] == ["release.yml", "tests.yml"]


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_run_script_interpolates_an_expression(path):
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    for job_name, step in _steps(workflow):
        script = step.get("run", "")
        assert "${{" not in script, (
            f"{path.name} job {job_name} step {step.get('name', step.get('uses'))!r} "
            "interpolates an expression into a shell script; pass it through env: instead"
        )


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_write_permission_is_only_granted_where_it_is_needed(path):
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    permissions = workflow.get("permissions", {})
    if path.name == "release.yml":
        assert permissions == {"contents": "write"}
    else:
        assert permissions == {}, "only the release workflow may write to the repository"


def test_the_release_job_checks_the_tag_before_publishing():
    workflow = yaml.safe_load((WORKFLOW_DIR / "release.yml").read_text(encoding="utf-8"))
    names = [step.get("name") or step.get("uses") for _job, step in _steps(workflow)]
    assert names.index("Check the tag matches the recorded version") < names.index(
        "Publish the release")
