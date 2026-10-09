"""Exercise bin/bg-job with an isolated state directory and real jobs."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid

BG_JOB = Path(__file__).resolve().parent.parent.parent / "bin" / "bg-job"


class BgJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bg-job-test-")
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, BG_JOB_DIR=str(self.root / "jobs"), BG_JOB_TEST_FLAG="kept")
        self.names = []

    def tearDown(self):
        if shutil.which("systemctl"):
            for name in self.names:
                subprocess.run(["systemctl", "--user", "stop", f"bgjob-{name}"], capture_output=True)
        self.temp.cleanup()

    def name(self):
        # Unique, because systemd units outlive a failed test run.
        self.names.append(f"t{uuid.uuid4().hex[:8]}")
        return self.names[-1]

    def bg(self, *args, cwd=None):
        return subprocess.run([str(BG_JOB), *args], cwd=cwd or self.root, env=self.env,
                              capture_output=True, text=True, timeout=60)

    def test_wait_reports_log_environment_directory_and_exit_code(self):
        name = self.name()
        work = self.root / "work"
        work.mkdir()
        started = self.bg("start", name, "--", "sh", "-c",
                          'echo "flag=$BG_JOB_TEST_FLAG"; pwd -P; exit 7', cwd=work)
        self.assertEqual(started.returncode, 0, started.stderr)
        waited = self.bg("wait", name)
        self.assertEqual(waited.returncode, 7)
        self.assertIn("flag=kept", waited.stdout)
        self.assertIn(str(work.resolve()), waited.stdout)
        self.assertIn(f"{name} exited 7", waited.stdout)
        self.assertIn("exited 7", self.bg("status", name).stdout)

    def test_running_job_is_reported_and_not_restarted(self):
        name = self.name()
        self.assertEqual(self.bg("start", name, "--", "sleep", "3").returncode, 0)
        time.sleep(0.5)
        self.assertIn("running", self.bg("status", name).stdout)
        again = self.bg("start", name, "--", "true")
        self.assertEqual(again.returncode, 2)
        self.assertIn("already running", again.stderr)
        self.assertEqual(self.bg("wait", name).returncode, 0)

    def test_job_survives_its_starting_session(self):
        name = self.name()
        marker = self.root / "survived"
        # The starting shell exits at once, as an agent session would.
        launcher = subprocess.run(
            ["sh", "-c", f'"{BG_JOB}" start {name} -- sh -c "sleep 1; touch {marker}"'],
            env=self.env, cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertEqual(launcher.returncode, 0, launcher.stderr)
        self.assertEqual(self.bg("wait", name).returncode, 0)
        self.assertTrue(marker.exists())

    def test_missing_command_and_bad_names_are_rejected(self):
        self.assertEqual(self.bg("start", "ok-name").returncode, 2)
        self.assertEqual(self.bg("start", "bad/name", "--", "true").returncode, 2)
        self.assertEqual(self.bg("wait", "never-started").returncode, 2)


if __name__ == "__main__":
    unittest.main()
