import subprocess
import sys
import tempfile
import textwrap
import unittest
import os
from pathlib import Path


PACKAGE_CONFIG = """
timezone: Asia/Shanghai

tapd:
  base_url: https://api.tapd.cn
  auth_mode: bearer
  task_done_statuses:
    - done
    - 已完成
  bug_closed_statuses:
    - resolved
    - verified
    - rejected
    - closed
    - 已关闭
  fields:
    task_owner: owner
    bug_owner: current_owner
    bug_creator: reporter
    story_pm: owner

report:
  public_base_url: https://tapd-daily.internal.example.com
  output_dir: ./reports

dingtalk:
  notifier: webhook
  webhook: ${DINGTALK_WEBHOOK}
  secret: ${DINGTALK_SECRET}
  at_mobiles: []
  is_at_all: false

projects:
  - name: Deepexi Foil
    workspace_id: "1"
    iterations:
      - name: Deepexi Foil V1.0.0
        iteration_id: "i1"
    members:
      - name: 雷艾琳
        tapd_user: leiailin
        role: 当前账号
    product_managers:
      - name: 雷艾琳
        tapd_user: leiailin

sample_data:
  tasks:
    - workspace_id: "1"
      iteration_id: i1
      owner: leiailin
      status: done
  bugs: []
  stories: []
"""


class PackageEntrypointTests(unittest.TestCase):
    def test_module_entrypoint_generates_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            config_path = workdir / "config.yaml"
            config_path.write_text(textwrap.dedent(PACKAGE_CONFIG), encoding="utf-8")
            repo_root = Path(__file__).resolve().parents[1]
            env = {
                **os.environ,
                "PYTHONPATH": str(repo_root / "src"),
            }

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tapd_auto",
                    "--config",
                    str(config_path),
                    "--date",
                    "2026-05-26",
                    "--dry-run",
                ],
                cwd=workdir,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue((workdir / "reports" / "2026-05-26" / "index.html").exists())
            self.assertTrue((workdir / "reports" / "2026-05-26" / "summary-1.png").exists())


if __name__ == "__main__":
    unittest.main()
