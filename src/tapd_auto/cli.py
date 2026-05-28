"""命令行入口。"""

from __future__ import annotations

import argparse
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .config import load_config
from .dingtalk import send_dingtalk_report
from .report import build_report
from .render import public_report_asset_url, public_report_url, render_dingtalk_markdown, write_field_info, write_page_screenshot, write_report
from .tapd import collect_live_data, create_tapd_client


def load_sample_data(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    sample_data = config.get("sample_data")
    if sample_data is None:
        return {"tasks": [], "bugs": [], "stories": []}
    return {
        "tasks": list(sample_data.get("tasks", [])),
        "bugs": list(sample_data.get("bugs", [])),
        "stories": list(sample_data.get("stories", [])),
    }


def today_in_timezone(timezone: str) -> str:
    return datetime.now(ZoneInfo(timezone)).strftime("%Y-%m-%d")


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 TAPD 每日复盘报表")
    parser.add_argument("--config", default="configs/config.example.yaml", help="配置文件路径")
    parser.add_argument("--date", default=None, help="报表日期，格式 YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="使用配置里的 sample_data 生成本地报表")
    parser.add_argument("--live", action="store_true", help="使用 TAPD OpenAPI 拉取真实数据")
    parser.add_argument("--send-dingtalk", action="store_true", help="生成报表后发送钉钉 Markdown 消息")
    parser.add_argument("--skip-field-info", action="store_true", help="live 模式下不写入字段发现结果")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    report_date = args.date or today_in_timezone(config["timezone"])

    if args.dry_run and args.live:
        raise SystemExit("请只选择 --dry-run 或 --live 其中一种模式。")
    if not args.dry_run and not args.live:
        raise SystemExit("请显式选择 --dry-run 或 --live，避免误请求 TAPD。")

    field_info: dict[str, Any] | None = None
    if args.live:
        client = create_tapd_client(config)
        raw_data, field_info = collect_live_data(config, client)
    else:
        raw_data = load_sample_data(config)

    report = build_report(config, raw_data, report_date=report_date)
    output_dir = write_report(report, config["report"]["output_dir"], config["report"]["public_base_url"])
    report_url = public_report_url(config, report)

    if field_info is not None and not args.skip_field_info:
        field_info_path = write_field_info(field_info, output_dir)
        print(f"TAPD 字段发现结果：{field_info_path}")
    if args.send_dingtalk:
        screenshot_path = write_page_screenshot(output_dir / "index.html", output_dir)
        image_url = public_report_asset_url(config["report"]["public_base_url"], report["date"], screenshot_path.name)
        markdown = render_dingtalk_markdown(report, report_url, image_urls=[image_url])
        send_dingtalk_report(config, report, report_url, markdown)
        print("已发送钉钉 Markdown 日报。")

    print(f"已生成 TAPD 每日复盘：{output_dir / 'index.html'}")
    print(f"钉钉 Markdown 摘要：{output_dir / 'summary.md'}")
    return 0
