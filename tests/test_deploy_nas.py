import os
import stat
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_SCRIPT = REPO_ROOT / "scripts" / "deploy_nas.sh"


def test_deploy_script_exists_and_executable():
    assert DEPLOY_SCRIPT.exists(), "scripts/deploy_nas.sh must exist"
    file_stat = os.stat(DEPLOY_SCRIPT)
    assert bool(file_stat.st_mode & stat.S_IXUSR), "scripts/deploy_nas.sh must be executable"


def test_deploy_script_help():
    res = subprocess.run(
        [str(DEPLOY_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert res.returncode == 0
    assert "Usage" in res.stdout or "Verwendung" in res.stdout
    assert "deploy_nas.sh" in res.stdout


def test_deploy_script_dry_run():
    res = subprocess.run(
        [str(DEPLOY_SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert res.returncode == 0
    assert "[DRY-RUN]" in res.stdout
    assert "docker compose pull" in res.stdout
    assert "docker compose up" in res.stdout
    assert "http://localhost:9015/health" in res.stdout


def test_deploy_script_successful_execution_with_mock_ssh():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_ssh = tmp_path / "ssh"
        log_file = tmp_path / "ssh.log"

        # Mock ssh script that logs arguments and returns success with mock health output
        mock_ssh.write_text(
            f"""#!/usr/bin/env bash
echo "$@" >> "{log_file}"
# Simulate docker compose ps and curl responses if asked
if [[ "$*" == *"curl"* ]]; then
    echo '{{"status":"ok","version":"0.2.0","app_name":"data-recorder"}}'
    exit 0
fi
if [[ "$*" == *"docker compose ps"* ]]; then
    echo 'data-recording Up (healthy)'
    exit 0
fi
exit 0
""",
            encoding="utf-8",
        )
        mock_ssh.chmod(0o755)

        env = os.environ.copy()
        env["PATH"] = f"{tmpdir}:{env['PATH']}"
        env["NAS_HOST"] = "test-nas"
        env["SERVICE_NAME"] = "data-recording"

        res = subprocess.run(
            [str(DEPLOY_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=env,
        )

        assert res.returncode == 0, f"Script failed with output: {res.stderr}\n{res.stdout}"
        assert "Deployment erfolgreich" in res.stdout or "erfolgreich abgeschlossen" in res.stdout
        assert "0.2.0" in res.stdout

        ssh_log = log_file.read_text(encoding="utf-8")
        assert "test-nas" in ssh_log
        assert "docker compose pull data-recording" in ssh_log
        assert "docker compose up -d --no-deps data-recording" in ssh_log


def test_deploy_script_ssh_failure():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_ssh = tmp_path / "ssh"

        mock_ssh.write_text(
            """#!/usr/bin/env bash
echo "ssh: connect to host test-nas port 22: Connection refused" >&2
exit 255
""",
            encoding="utf-8",
        )
        mock_ssh.chmod(0o755)

        env = os.environ.copy()
        env["PATH"] = f"{tmpdir}:{env['PATH']}"
        env["NAS_HOST"] = "test-nas"

        res = subprocess.run(
            [str(DEPLOY_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=env,
        )

        assert res.returncode != 0
        assert "Connection refused" in res.stderr or "Fehler" in res.stdout or "Fehler" in res.stderr


def test_deploy_script_healthcheck_failure():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_ssh = tmp_path / "ssh"

        # Mock ssh that succeeds for docker compose but fails curl healthcheck
        mock_ssh.write_text(
            """#!/usr/bin/env bash
if [[ "$*" == *"curl"* ]]; then
    echo "curl: (7) Failed to connect to localhost port 9015" >&2
    exit 2
fi
exit 0
""",
            encoding="utf-8",
        )
        mock_ssh.chmod(0o755)

        env = os.environ.copy()
        env["PATH"] = f"{tmpdir}:{env['PATH']}"
        env["NAS_HOST"] = "test-nas"
        env["MAX_RETRIES"] = "2"
        env["RETRY_INTERVAL"] = "0"

        res = subprocess.run(
            [str(DEPLOY_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=env,
        )

        assert res.returncode == 2 or res.returncode != 0
        assert "Healthcheck" in res.stderr or "Healthcheck" in res.stdout
        assert "fehlgeschlagen" in res.stderr or "fehlgeschlagen" in res.stdout


def test_deploy_script_idempotency_multiple_runs():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_ssh = tmp_path / "ssh"

        mock_ssh.write_text(
            """#!/usr/bin/env bash
if [[ "$*" == *"curl"* ]]; then
    echo '{"status":"ok","version":"0.2.0","app_name":"data-recorder"}'
    exit 0
fi
if [[ "$*" == *"docker compose ps"* ]]; then
    echo 'data-recording Up (healthy)'
    exit 0
fi
exit 0
""",
            encoding="utf-8",
        )
        mock_ssh.chmod(0o755)

        env = os.environ.copy()
        env["PATH"] = f"{tmpdir}:{env['PATH']}"
        env["NAS_HOST"] = "test-nas"

        # Run 1
        res1 = subprocess.run(
            [str(DEPLOY_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=env,
        )
        assert res1.returncode == 0

        # Run 2 (idempotent, must succeed identically without errors)
        res2 = subprocess.run(
            [str(DEPLOY_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=env,
        )
        assert res2.returncode == 0
        assert "Deployment erfolgreich" in res2.stdout

