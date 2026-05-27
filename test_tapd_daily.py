import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import tapd_daily as td


CONFIG_TEXT = """
timezone: Asia/Shanghai

tapd:
  base_url: https://api.tapd.cn
  auth_mode: bearer
  task_done_statuses:
    - done
    - 已完成
    - 已关闭
  bug_closed_statuses:
    - 已解决
    - 已关闭
    - 无需解决
  fields:
    task_owner: owner
    bug_owner: current_owner
    story_pm: owner

report:
  public_base_url: https://tapd-daily.internal.example.com
  output_dir: ./public/reports

dingtalk:
  webhook: ${DINGTALK_WEBHOOK}
  secret: ${DINGTALK_SECRET}

projects:
  - name: 示例项目
    workspace_id: "33002756"
    iterations:
      - name: 2026-05 Sprint
        iteration_id: "sprint-1"
    members:
      - name: 张三
        tapd_user: zhangsan
        role: dev
        tapd_report_url: https://tapd.cn/member/zhangsan
      - name: 李四
        tapd_user: lisi
        role: test
    product_managers:
      - name: 产品A
        tapd_user: product_a
"""


RAW_DATA = {
    "tasks": [
        {
            "workspace_id": "33002756",
            "iteration_id": "sprint-1",
            "owner": "zhangsan",
            "status": "已完成",
            "title": "完成日报页面",
        },
        {
            "workspace_id": "33002756",
            "iteration_id": "sprint-1",
            "owner": "zhangsan",
            "status": "开发中",
            "title": "接入 TAPD API",
        },
        {
            "workspace_id": "33002756",
            "iteration_id": "sprint-1",
            "owner": "lisi",
            "status": "已关闭",
            "title": "验证日报输出",
        },
    ],
    "bugs": [
        {
            "workspace_id": "33002756",
            "iteration_id": "sprint-1",
            "current_owner": "zhangsan",
            "status": "已关闭",
            "created": "2026-05-26 10:30:00",
        },
        {
            "workspace_id": "33002756",
            "iteration_id": "sprint-1",
            "current_owner": "zhangsan",
            "status": "处理中",
            "created": "2026-05-26 11:30:00",
        },
        {
            "workspace_id": "33002756",
            "iteration_id": "sprint-1",
            "current_owner": "lisi",
            "status": "处理中",
            "created": "2026-05-25 18:30:00",
        },
    ],
    "stories": [
        {
            "workspace_id": "33002756",
            "iteration_id": "sprint-1",
            "owner": "product_a",
            "title": "配置化日报范围",
            "status": "规划中",
            "start": "2026-05-25",
            "end": "2026-05-29",
            "url": "https://tapd.cn/story/1",
        }
    ],
}


class TapdDailyTests(unittest.TestCase):
    def write_config(self, directory: Path) -> Path:
        config_path = directory / "config.yaml"
        config_path.write_text(textwrap.dedent(CONFIG_TEXT), encoding="utf-8")
        return config_path

    def test_load_config_resolves_env_and_keeps_project_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = td.load_config(
                self.write_config(Path(temp_dir)),
                env={
                    "DINGTALK_WEBHOOK": "https://oapi.dingtalk.com/robot/send",
                    "DINGTALK_SECRET": "SECxxxx",
                },
            )

        self.assertEqual(config["timezone"], "Asia/Shanghai")
        self.assertEqual(config["tapd"]["auth_mode"], "bearer")
        self.assertEqual(config["tapd"]["fields"]["bug_owner"], "current_owner")
        self.assertEqual(config["dingtalk"]["secret"], "SECxxxx")
        self.assertEqual(config["projects"][0]["name"], "示例项目")
        self.assertEqual(config["projects"][0]["iterations"][0]["iteration_id"], "sprint-1")
        self.assertEqual(config["projects"][0]["members"][0]["tapd_user"], "zhangsan")

    def test_build_report_aggregates_tasks_bugs_and_stories_by_member(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})
        report = td.build_report(config, RAW_DATA, report_date="2026-05-26")
        iteration = report["projects"][0]["iterations"][0]
        zhangsan = iteration["members"][0]
        lisi = iteration["members"][1]

        self.assertEqual(zhangsan["task_total"], 2)
        self.assertEqual(zhangsan["task_done"], 1)
        self.assertEqual(zhangsan["task_completion_rate"], 50)
        self.assertEqual(zhangsan["bugs_closed"], 1)
        self.assertEqual(zhangsan["bugs_open"], 1)
        self.assertEqual(zhangsan["bugs_new"], 2)
        self.assertEqual(lisi["task_completion_rate"], 100)
        self.assertEqual(iteration["requirements"][0]["title"], "配置化日报范围")

    def test_build_report_accepts_tapd_wrapped_api_records(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})
        wrapped_data = {
            "tasks": [
                {
                    "Task": {
                        "workspace_id": "33002756",
                        "iteration_id": "sprint-1",
                        "owner": "zhangsan",
                        "status": "done",
                    }
                }
            ],
            "bugs": [
                {
                    "Bug": {
                        "workspace_id": "33002756",
                        "iteration_id": "sprint-1",
                        "current_owner": "zhangsan",
                        "status": "已关闭",
                        "created": "2026-05-26 10:30:00",
                    }
                }
            ],
            "stories": [
                {
                    "Story": {
                        "workspace_id": "33002756",
                        "iteration_id": "sprint-1",
                        "owner": "product_a",
                        "name": "包装数据也能展示",
                        "status": "规划中",
                        "begin": "2026-05-26",
                        "due": "2026-05-27",
                    }
                }
            ],
        }

        report = td.build_report(config, wrapped_data, report_date="2026-05-26")
        iteration = report["projects"][0]["iterations"][0]
        zhangsan = iteration["members"][0]

        self.assertEqual(zhangsan["task_total"], 1)
        self.assertEqual(zhangsan["task_done"], 1)
        self.assertEqual(zhangsan["bugs_closed"], 1)
        self.assertEqual(iteration["requirements"][0]["title"], "包装数据也能展示")

    def test_render_markdown_contains_clear_daily_summary(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})
        report = td.build_report(config, RAW_DATA, report_date="2026-05-26")
        markdown = td.render_markdown(report, "https://tapd-daily.internal.example.com/reports/2026-05-26/index.html")

        self.assertIn("### TAPD 每日复盘 2026-05-26", markdown)
        self.assertIn("今日统计：1 个项目 / 1 个迭代 / 2 人", markdown)
        self.assertIn("任务整体完成率：67%", markdown)
        self.assertIn("缺陷：未解决 2，今日新增 2，今日关闭 1", markdown)

    def test_write_report_outputs_html_markdown_and_json(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})
        report = td.build_report(config, RAW_DATA, report_date="2026-05-26")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = td.write_report(report, Path(temp_dir), config["report"]["public_base_url"])

            self.assertEqual(output_dir.name, "2026-05-26")
            self.assertTrue((output_dir / "index.html").exists())
            self.assertTrue((output_dir / "summary.md").exists())
            self.assertTrue((output_dir / "report.json").exists())

    def test_tapd_client_validates_api_status_and_reads_paginated_lists(self):
        first_page_items = [{"id": item_id} for item_id in range(200)]
        first_response = Mock()
        first_response.json.return_value = {"status": 1, "data": first_page_items, "info": "success"}
        first_response.raise_for_status.return_value = None
        second_response = Mock()
        second_response.json.return_value = {"status": 1, "data": [], "info": "success"}
        second_response.raise_for_status.return_value = None

        with patch("tapd_daily.requests.get", side_effect=[first_response, second_response]) as request_get:
            client = td.TapdClient("https://api.tapd.cn", "token-value")
            items = client.get_paginated("tasks", {"workspace_id": "33002756"})

        self.assertEqual(len(items), 200)
        self.assertEqual(items[0], {"id": 0})
        self.assertEqual(items[-1], {"id": 199})
        self.assertEqual(request_get.call_count, 2)
        self.assertEqual(request_get.call_args_list[0].kwargs["params"]["limit"], 200)
        self.assertEqual(request_get.call_args_list[0].kwargs["params"]["page"], 1)
        self.assertEqual(request_get.call_args_list[0].kwargs["headers"]["Authorization"], "Bearer token-value")

    def test_tapd_client_raises_when_api_status_is_not_success(self):
        failed_response = Mock()
        failed_response.json.return_value = {"status": 0, "data": {}, "info": "token invalid"}
        failed_response.raise_for_status.return_value = None

        with patch("tapd_daily.requests.get", return_value=failed_response):
            client = td.TapdClient("https://api.tapd.cn", "token-value")
            with self.assertRaisesRegex(RuntimeError, "token invalid"):
                client.get_json("tasks", {"limit": 1})

    def test_dingtalk_signature_and_markdown_payload_follow_webhook_rules(self):
        signed_url = td.build_dingtalk_signed_url(
            "https://oapi.dingtalk.com/robot/send?access_token=abc",
            "SECsecret",
            timestamp=1760000000000,
        )
        payload = td.build_dingtalk_markdown_payload(
            title="TAPD 每日复盘 2026-05-26",
            markdown="### TAPD 每日复盘 2026-05-26",
            at_mobiles=["13800138000"],
            is_at_all=False,
        )

        self.assertIn("timestamp=1760000000000", signed_url)
        self.assertIn("sign=", signed_url)
        self.assertEqual(payload["msgtype"], "markdown")
        self.assertEqual(payload["markdown"]["title"], "TAPD 每日复盘 2026-05-26")
        self.assertEqual(payload["at"]["atMobiles"], ["13800138000"])


if __name__ == "__main__":
    unittest.main()
