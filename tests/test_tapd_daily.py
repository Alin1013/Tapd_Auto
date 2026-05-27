import tempfile
import textwrap
import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import tapd_auto as td


CONFIG_TEXT = """
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
    - 已解决
    - 已验证
    - 已关闭
    - 无需解决
  fields:
    task_owner: owner
    bug_owner: current_owner
    story_pm: owner
  status_labels:
    stories:
      status_17: 已提测
      status_21: 发布

report:
  public_base_url: https://tapd-daily.internal.example.com
  output_dir: ./public/reports

dingtalk:
  webhook: ${DINGTALK_WEBHOOK}
  secret: ${DINGTALK_SECRET}
  at_mobiles:
    - "13800138000"
  is_at_all: false

projects:
  - name: Deepexi Foil
    workspace_id: "33002756"
    iterations:
      - name: Deepexi Foil V1.0.0
        iteration_id: "1133002756001001828"
    members:
      - name: 雷艾琳
        tapd_user: leiailin
        role: 当前账号
        tapd_report_url: https://www.tapd.cn/33002756/prong/stories/stories_list
    product_managers:
      - name: 雷艾琳
        tapd_user: leiailin
"""


RAW_DATA = {
    "tasks": [
        {
            "workspace_id": "33002756",
            "iteration_id": "1133002756001001828",
            "owner": "leiailin",
            "status": "done",
            "title": "本地链路验证任务",
        },
        {
            "workspace_id": "33002756",
            "iteration_id": "1133002756001001828",
            "owner": "leiailin",
            "status": "progressing",
            "title": "TAPD 配置同步检查",
        },
    ],
    "bugs": [
        {
            "workspace_id": "33002756",
            "iteration_id": "1133002756001001828",
            "current_owner": "leiailin;",
            "status": "closed",
            "created": "2026-05-26 10:30:00",
            "closed": "2026-05-26 16:30:00",
        },
        {
            "workspace_id": "33002756",
            "iteration_id": "1133002756001001828",
            "current_owner": "leiailin;",
            "status": "in_progress",
            "created": "2026-05-26 11:30:00",
        },
    ],
    "stories": [
        {
            "workspace_id": "33002756",
            "iteration_id": "1133002756001001828",
            "owner": "leiailin",
            "title": "真实配置同步范围",
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
        self.assertEqual(config["projects"][0]["name"], "Deepexi Foil")
        self.assertEqual(config["projects"][0]["iterations"][0]["iteration_id"], "1133002756001001828")
        self.assertEqual(config["projects"][0]["members"][0]["tapd_user"], "leiailin")

    def test_build_report_aggregates_tasks_bugs_and_stories_by_member(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})
        report = td.build_report(config, RAW_DATA, report_date="2026-05-26")
        iteration = report["projects"][0]["iterations"][0]
        leiailin = iteration["members"][0]

        self.assertEqual(leiailin["task_total"], 2)
        self.assertEqual(leiailin["task_done"], 1)
        self.assertEqual(leiailin["task_completion_rate"], 50)
        self.assertEqual(leiailin["bugs_closed"], 1)
        self.assertEqual(leiailin["bugs_open"], 1)
        self.assertEqual(leiailin["bugs_new"], 2)
        self.assertEqual(iteration["requirements"][0]["title"], "真实配置同步范围")

    def test_build_report_accepts_tapd_wrapped_api_records(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})
        wrapped_data = {
            "tasks": [
                {
                    "Task": {
                        "workspace_id": "33002756",
                        "iteration_id": "1133002756001001828",
                        "owner": "leiailin",
                        "status": "done",
                    }
                }
            ],
            "bugs": [
                {
                    "Bug": {
                        "workspace_id": "33002756",
                        "iteration_id": "1133002756001001828",
                        "current_owner": "leiailin;",
                        "status": "closed",
                        "created": "2026-05-26 10:30:00",
                        "closed": "2026-05-26 16:30:00",
                    }
                }
            ],
            "stories": [
                {
                    "Story": {
                        "workspace_id": "33002756",
                        "iteration_id": "1133002756001001828",
                        "owner": "leiailin",
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
        leiailin = iteration["members"][0]

        self.assertEqual(leiailin["task_total"], 1)
        self.assertEqual(leiailin["task_done"], 1)
        self.assertEqual(leiailin["bugs_closed"], 1)
        self.assertEqual(iteration["requirements"][0]["title"], "包装数据也能展示")

    def test_build_report_uses_configured_story_status_labels(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})
        raw_data = {
            "tasks": [],
            "bugs": [],
            "stories": [
                {
                    "workspace_id": "33002756",
                    "iteration_id": "1133002756001001828",
                    "owner": "leiailin",
                    "name": "状态映射验证",
                    "status": "status_17",
                }
            ],
        }

        report = td.build_report(config, raw_data, report_date="2026-05-26")

        self.assertEqual(report["projects"][0]["iterations"][0]["requirements"][0]["status"], "已提测")

    def test_build_report_keeps_member_bug_visibility_rule(self):
        config_text = CONFIG_TEXT.replace(
            "tapd_user: leiailin\n        role: 当前账号",
            "tapd_user: leiailin\n        role: 当前账号\n        hide_bug_metrics: true",
        )
        config = td.load_config_from_text(config_text, env={})
        report = td.build_report(config, RAW_DATA, report_date="2026-05-26")

        leiailin = report["projects"][0]["iterations"][0]["members"][0]

        self.assertTrue(leiailin.get("hide_bug_metrics"))

    def test_build_report_uses_today_window_for_bug_metrics(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})
        raw_data = {
            "tasks": [],
            "bugs": [
                {
                    "workspace_id": "33002756",
                    "iteration_id": "1133002756001001828",
                    "current_owner": "leiailin",
                    "status": "in_progress",
                    "created": "2026-05-20 09:00:00",
                },
                {
                    "workspace_id": "33002756",
                    "iteration_id": "1133002756001001828",
                    "current_owner": "leiailin",
                    "status": "closed",
                    "created": "2026-05-26 09:30:00",
                    "closed": "2026-05-27 10:00:00",
                },
                {
                    "workspace_id": "33002756",
                    "iteration_id": "1133002756001001828",
                    "current_owner": "leiailin",
                    "status": "closed",
                    "created": "2026-05-25 09:30:00",
                    "closed": "2026-05-26 18:30:00",
                },
                {
                    "workspace_id": "33002756",
                    "iteration_id": "1133002756001001828",
                    "current_owner": "leiailin",
                    "status": "closed",
                    "created": "2026-05-25 09:30:00",
                    "closed": "2026-05-25 18:30:00",
                },
            ],
            "stories": [],
        }

        report = td.build_report(config, raw_data, report_date="2026-05-26")
        leiailin = report["projects"][0]["iterations"][0]["members"][0]

        self.assertEqual(leiailin["bugs_open"], 1)
        self.assertEqual(leiailin["bugs_new"], 1)
        self.assertEqual(leiailin["bugs_closed"], 1)
        self.assertEqual(report["summary"]["bugs_open"], 1)
        self.assertEqual(report["summary"]["bugs_new"], 1)
        self.assertEqual(report["summary"]["bugs_closed"], 1)

    def test_build_report_excludes_hidden_bug_members_from_defect_summary(self):
        config_text = CONFIG_TEXT.replace(
            "      - name: 雷艾琳\n        tapd_user: leiailin\n        role: 当前账号",
            "      - name: 雷艾琳\n        tapd_user: leiailin\n        role: 当前账号\n"
            "      - name: 黄寅子\n        tapd_user: Tora\n        role: 团队成员\n        hide_bug_metrics: true",
        )
        config = td.load_config_from_text(config_text, env={})
        raw_data = {
            "tasks": [],
            "bugs": [
                {
                    "workspace_id": "33002756",
                    "iteration_id": "1133002756001001828",
                    "current_owner": "leiailin",
                    "status": "in_progress",
                    "created": "2026-05-26 09:00:00",
                },
                {
                    "workspace_id": "33002756",
                    "iteration_id": "1133002756001001828",
                    "current_owner": "Tora",
                    "status": "in_progress",
                    "created": "2026-05-26 10:00:00",
                },
            ],
            "stories": [],
        }

        report = td.build_report(config, raw_data, report_date="2026-05-26")

        self.assertEqual(report["summary"]["bugs_open"], 1)
        self.assertEqual(report["summary"]["bugs_new"], 1)
        self.assertEqual(report["projects"][0]["iterations"][0]["summary"]["bugs_open"], 1)
        self.assertEqual(report["projects"][0]["iterations"][0]["summary"]["bugs_new"], 1)

    def test_render_markdown_contains_clear_daily_summary(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})
        report = td.build_report(config, RAW_DATA, report_date="2026-05-26")
        markdown = td.render_markdown(report, "https://tapd-daily.internal.example.com/reports/2026-05-26/index.html")

        self.assertIn("### TAPD 每日复盘 2026-05-26", markdown)
        self.assertIn("今日统计：1 个项目 / 1 个迭代 / 1 人", markdown)
        self.assertNotIn("任务整体完成率", markdown)
        self.assertIn("今日缺陷：未解决 1，今日新增 2，当日关闭 1", markdown)

    def test_render_html_contains_team_defect_table(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})
        report = td.build_report(config, RAW_DATA, report_date="2026-05-26")
        html = td.render_html(report)

        self.assertIn("今日缺陷", html)
        self.assertIn('class="member-table"', html)
        self.assertIn("<th>成员</th>", html)
        self.assertIn("<th>今日缺陷</th>", html)
        self.assertNotIn("<th>任务</th>", html)
        self.assertNotIn("<th>完成率</th>", html)
        self.assertNotIn("任务总数", html)
        self.assertNotIn("任务完成率", html)
        self.assertIn("雷艾琳", html)
        self.assertIn("真实配置同步范围", html)
        self.assertNotIn("workspace_id:", html)
        self.assertNotIn("iteration_id:", html)

    def test_render_html_hides_bug_metrics_for_configured_members(self):
        report = {
            "date": "2026-05-26",
            "timezone": "Asia/Shanghai",
            "summary": {
                "project_count": 1,
                "iteration_count": 1,
                "member_count": 3,
                "task_total": 99,
                "task_done": 42,
                "task_completion_rate": 42,
                "bugs_closed": 9,
                "bugs_open": 6,
                "bugs_new": 3,
            },
            "projects": [
                {
                    "name": "Deepexi Foil",
                    "workspace_id": "33002756",
                    "iterations": [
                        {
                            "name": "Deepexi Foil V1.0.0",
                            "iteration_id": "1133002756001001828",
                            "requirements": [],
                            "members": [
                                {
                                    "name": "雷艾琳",
                                    "tapd_user": "leiailin",
                                    "role": "当前账号",
                                    "tapd_report_url": "",
                                    "task_total": 8,
                                    "task_done": 4,
                                    "task_completion_rate": 50,
                                    "bugs_closed": 3,
                                    "bugs_open": 1,
                                    "bugs_new": 2,
                                },
                                {
                                    "name": "黄寅子",
                                    "tapd_user": "Tora",
                                    "role": "团队成员",
                                    "tapd_report_url": "",
                                    "hide_bug_metrics": True,
                                    "task_total": 7,
                                    "task_done": 1,
                                    "task_completion_rate": 14,
                                    "bugs_closed": 44,
                                    "bugs_open": 22,
                                    "bugs_new": 11,
                                },
                                {
                                    "name": "粘琼月",
                                    "tapd_user": "nianqiongyue",
                                    "role": "团队成员",
                                    "tapd_report_url": "",
                                    "hide_bug_metrics": True,
                                    "task_total": 6,
                                    "task_done": 2,
                                    "task_completion_rate": 33,
                                    "bugs_closed": 55,
                                    "bugs_open": 33,
                                    "bugs_new": 12,
                                },
                            ],
                        }
                    ],
                }
            ],
        }

        html = td.render_html(report)

        self.assertIn("雷艾琳", html)
        self.assertIn("未解 1", html)
        self.assertIn("新增 2", html)
        self.assertIn("当日关闭 3", html)
        self.assertNotIn("缺陷不展示", html)
        self.assertNotIn("未解 22", html)
        self.assertNotIn("未解 33", html)
        self.assertNotIn("8/8", html)
        self.assertNotIn("任务 4/8", html)

    def test_render_html_adds_requirement_tabs_for_tora_and_nianqiongyue(self):
        report = {
            "date": "2026-05-26",
            "timezone": "Asia/Shanghai",
            "summary": {
                "project_count": 1,
                "iteration_count": 1,
                "member_count": 3,
                "task_total": 0,
                "task_done": 0,
                "task_completion_rate": 0,
                "bugs_closed": 0,
                "bugs_open": 1,
                "bugs_new": 1,
            },
            "projects": [
                {
                    "name": "Deepexi Foil",
                    "workspace_id": "33002756",
                    "iterations": [
                        {
                            "name": "Deepexi Foil V1.0.0",
                            "iteration_id": "1133002756001001828",
                            "summary": {"member_count": 1, "bugs_open": 1, "bugs_new": 1, "bugs_closed": 0},
                            "requirements": [
                                {
                                    "title": "Tora 需求内容",
                                    "product_manager": "黄寅子",
                                    "product_manager_user": "Tora",
                                    "status": "已提测",
                                    "start": "2026-05-25",
                                    "end": "2026-05-29",
                                    "url": "",
                                },
                                {
                                    "title": "粘琼月需求内容",
                                    "product_manager": "粘琼月",
                                    "product_manager_user": "nianqiongyue",
                                    "status": "开发实现",
                                    "start": "2026-05-26",
                                    "end": "2026-05-30",
                                    "url": "",
                                },
                                {
                                    "title": "其他需求内容",
                                    "product_manager": "雷艾琳",
                                    "product_manager_user": "leiailin",
                                    "status": "规划中",
                                    "start": "2026-05-26",
                                    "end": "2026-05-30",
                                    "url": "",
                                },
                            ],
                            "members": [
                                {
                                    "name": "雷艾琳",
                                    "tapd_user": "leiailin",
                                    "role": "当前账号",
                                    "tapd_report_url": "",
                                    "task_total": 0,
                                    "task_done": 0,
                                    "task_completion_rate": 0,
                                    "bugs_closed": 0,
                                    "bugs_open": 1,
                                    "bugs_new": 1,
                                },
                                {
                                    "name": "黄寅子",
                                    "tapd_user": "Tora",
                                    "role": "团队成员",
                                    "tapd_report_url": "",
                                    "hide_bug_metrics": True,
                                    "task_total": 0,
                                    "task_done": 0,
                                    "task_completion_rate": 0,
                                    "bugs_closed": 0,
                                    "bugs_open": 22,
                                    "bugs_new": 11,
                                },
                                {
                                    "name": "粘琼月",
                                    "tapd_user": "nianqiongyue",
                                    "role": "团队成员",
                                    "tapd_report_url": "",
                                    "hide_bug_metrics": True,
                                    "task_total": 0,
                                    "task_done": 0,
                                    "task_completion_rate": 0,
                                    "bugs_closed": 0,
                                    "bugs_open": 33,
                                    "bugs_new": 12,
                                },
                            ],
                        }
                    ],
                }
            ],
        }

        html = td.render_html(report)

        self.assertIn("今日缺陷", html)
        self.assertIn("Tora 需求", html)
        self.assertIn("粘琼月需求", html)
        self.assertIn("Tora 需求内容", html)
        self.assertIn("粘琼月需求内容", html)
        self.assertNotIn("未解 22", html)
        self.assertNotIn("未解 33", html)

    def test_render_html_handles_empty_requirement_dates(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})
        raw_data = {
            "tasks": [],
            "bugs": [],
            "stories": [
                {
                    "workspace_id": "33002756",
                    "iteration_id": "1133002756001001828",
                    "owner": "leiailin",
                    "name": "空日期需求",
                    "status": "status_17",
                    "begin": None,
                    "due": None,
                }
            ],
        }
        report = td.build_report(config, raw_data, report_date="2026-05-26")

        html = td.render_html(report)

        self.assertIn("空日期需求", html)
        self.assertIn("已提测", html)

    def test_write_report_outputs_html_markdown_and_json(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})
        report = td.build_report(config, RAW_DATA, report_date="2026-05-26")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = td.write_report(report, Path(temp_dir), config["report"]["public_base_url"])

            self.assertEqual(output_dir.name, "2026-05-26")
            self.assertTrue((output_dir / "index.html").exists())
            self.assertTrue((output_dir / "summary.md").exists())
            self.assertTrue((output_dir / "summary-1.png").exists())
            self.assertTrue((output_dir / "report.json").exists())
            self.assertTrue((output_dir / "summary-1.png").read_bytes().startswith(b"\x89PNG"))
            self.assertIn("![日报图]", (output_dir / "summary.md").read_text(encoding="utf-8"))

    def test_tapd_client_validates_api_status_and_reads_paginated_lists(self):
        first_page_items = [{"id": item_id} for item_id in range(200)]
        first_response = Mock()
        first_response.json.return_value = {"status": 1, "data": first_page_items, "info": "success"}
        first_response.raise_for_status.return_value = None
        second_response = Mock()
        second_response.json.return_value = {"status": 1, "data": [], "info": "success"}
        second_response.raise_for_status.return_value = None

        with patch("tapd_auto.tapd.requests.get", side_effect=[first_response, second_response]) as request_get:
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

        with patch("tapd_auto.tapd.requests.get", return_value=failed_response):
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

    def test_create_tapd_client_requires_access_token_for_live_mode(self):
        config = td.load_config_from_text(CONFIG_TEXT, env={})

        with self.assertRaisesRegex(RuntimeError, "TAPD_ACCESS_TOKEN"):
            td.create_tapd_client(config, env={"TAPD_ACCESS_TOKEN": ""})

    def test_collect_live_data_fetches_fields_iterations_and_lists(self):
        class FakeTapdClient:
            def __init__(self):
                self.json_calls = []
                self.paginated_calls = []

            def get_json(self, path, params=None):
                self.json_calls.append((path, params or {}))
                return {"status": 1, "data": {"path": path, "workspace_id": (params or {}).get("workspace_id")}}

            def get_paginated(self, path, params=None):
                self.paginated_calls.append((path, params or {}))
                if path == "tasks":
                    return [{"workspace_id": "33002756", "iteration_id": "1133002756001001828", "owner": "leiailin", "status": "done"}]
                if path == "bugs":
                    return [{"workspace_id": "33002756", "iteration_id": "1133002756001001828", "current_owner": "leiailin;", "status": "closed"}]
                if path == "stories":
                    return [{"workspace_id": "33002756", "iteration_id": "1133002756001001828", "owner": "leiailin", "name": "真实需求"}]
                return []

        config = td.load_config_from_text(CONFIG_TEXT, env={})
        raw_data, field_info = td.collect_live_data(config, FakeTapdClient())

        self.assertEqual(len(raw_data["tasks"]), 1)
        self.assertEqual(len(raw_data["bugs"]), 1)
        self.assertEqual(len(raw_data["stories"]), 1)
        self.assertIn("33002756", field_info["workspaces"])
        self.assertEqual(field_info["workspaces"]["33002756"]["tasks"]["path"], "tasks/get_fields_info")
        self.assertEqual(field_info["workspaces"]["33002756"]["bugs"]["path"], "bugs/get_fields_info")
        self.assertEqual(field_info["workspaces"]["33002756"]["stories"]["path"], "stories/get_fields_info")
        self.assertEqual(field_info["workspaces"]["33002756"]["iterations"][0]["path"], "iterations")

    def test_send_dingtalk_report_posts_signed_markdown_payload(self):
        config = td.load_config_from_text(
            CONFIG_TEXT,
            env={
                "DINGTALK_WEBHOOK": "https://oapi.dingtalk.com/robot/send?access_token=abc",
                "DINGTALK_SECRET": "SECsecret",
            },
        )
        report = td.build_report(config, RAW_DATA, report_date="2026-05-26")
        response = Mock()
        response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        response.raise_for_status.return_value = None

        with patch("tapd_auto.dingtalk.time.time", return_value=1760000000), patch("tapd_auto.dingtalk.requests.post", return_value=response) as request_post:
            td.send_dingtalk_report(config, report, "https://tapd-daily.internal.example.com/reports/2026-05-26/index.html")

        request_post.assert_called_once()
        post_url = request_post.call_args.args[0]
        payload = request_post.call_args.kwargs["json"]
        self.assertIn("timestamp=1760000000000", post_url)
        self.assertIn("sign=", post_url)
        self.assertEqual(payload["msgtype"], "markdown")
        self.assertEqual(payload["markdown"]["title"], "TAPD 每日复盘 2026-05-26")
        self.assertEqual(payload["at"]["atMobiles"], ["13800138000"])


if __name__ == "__main__":
    unittest.main()
