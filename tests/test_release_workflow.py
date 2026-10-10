from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "release.yml"


def test_release_workflow_exists_and_valid_yaml():
    assert WORKFLOW_FILE.exists(), ".github/workflows/release.yml must exist"
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert isinstance(data, dict), "Workflow file must be valid YAML mapping"
    assert "name" in data, "Workflow must have a name"


def test_release_workflow_triggers():
    assert WORKFLOW_FILE.exists()
    with WORKFLOW_FILE.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    triggers = data.get(True) or data.get("on")  # yaml parses 'on' as boolean True in 1.1 or string 'on'
    assert triggers is not None, "Workflow must define triggers ('on')"

    # Check push tags
    assert "push" in triggers, "Workflow must trigger on push"
    push_triggers = triggers["push"]
    assert "tags" in push_triggers, "Push trigger must filter for tags"
    assert any("v*" in tag for tag in push_triggers["tags"]), "Tags filter must include 'v*'"

    # Check workflow_dispatch
    assert "workflow_dispatch" in triggers, "Workflow must support manual workflow_dispatch"


def test_release_workflow_permissions():
    assert WORKFLOW_FILE.exists()
    with WORKFLOW_FILE.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Check permissions at top-level or in jobs
    top_permissions = data.get("permissions", {})
    release_job = data.get("jobs", {}).get("release", {})
    job_permissions = release_job.get("permissions", {})

    permissions = {**top_permissions, **job_permissions}
    assert permissions.get("contents") == "write", "Workflow requires write permissions for contents (releases)"
    assert permissions.get("packages") == "write", "Workflow requires write permissions for packages (ghcr.io)"


def test_release_workflow_steps():
    assert WORKFLOW_FILE.exists()
    with WORKFLOW_FILE.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    jobs = data.get("jobs", {})
    assert len(jobs) > 0, "Workflow must define jobs"

    # Find the job that builds and pushes the image
    job_key = "release" if "release" in jobs else list(jobs.keys())[0]
    steps = jobs[job_key].get("steps", [])

    step_uses = [s.get("uses", "") for s in steps]
    step_names = [s.get("name", "").lower() for s in steps]

    # Checkout
    assert any("checkout" in u for u in step_uses), "Must use checkout action"

    # Buildx
    assert any("setup-buildx-action" in u for u in step_uses), "Must use setup-buildx-action"

    # GHCR Login
    assert any("login-action" in u for u in step_uses), "Must use docker login-action"

    # Build and Push
    build_push_step = next((s for s in steps if "build-push-action" in s.get("uses", "")), None)
    assert build_push_step is not None, "Must use docker/build-push-action"

    with_params = build_push_step.get("with", {})
    platforms = with_params.get("platforms", "")
    assert "linux/amd64" in platforms, "Must target linux/amd64 platform"

    build_args = with_params.get("build-args", "")
    assert "APP_VERSION" in build_args, "Must pass APP_VERSION build-arg"
    assert "BUILD_COMMIT" in build_args, "Must pass BUILD_COMMIT build-arg"

    # GitHub Release creation
    has_release_action = any("action-gh-release" in u for u in step_uses)
    has_gh_cli_release = any("release" in name and ("gh release" in s.get("run", "")) for s, name in zip(steps, step_names))
    assert has_release_action or has_gh_cli_release, "Must include step to create GitHub Release"
