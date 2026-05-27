"""TAPD 自动日报工具。"""

from .cli import load_sample_data, run_cli, today_in_timezone
from .config import load_config, load_config_from_text, load_dotenv, resolve_env, validate_config
from .dingtalk import build_dingtalk_markdown_payload, build_dingtalk_signed_url, send_dingtalk_report
from .report import build_report, normalize_record
from .render import public_report_url, render_html, render_markdown, write_field_info, write_report, write_summary_png
from .tapd import TapdClient, collect_live_data, create_tapd_client, extract_tapd_data, join_fields, unwrap_tapd_data
from .preview import build_local_report_url

__all__ = [
    "TapdClient",
    "build_dingtalk_markdown_payload",
    "build_dingtalk_signed_url",
    "build_report",
    "build_local_report_url",
    "collect_live_data",
    "create_tapd_client",
    "extract_tapd_data",
    "join_fields",
    "load_config",
    "load_config_from_text",
    "load_dotenv",
    "load_sample_data",
    "normalize_record",
    "public_report_url",
    "render_html",
    "render_markdown",
    "resolve_env",
    "run_cli",
    "send_dingtalk_report",
    "today_in_timezone",
    "unwrap_tapd_data",
    "validate_config",
    "write_field_info",
    "write_report",
    "write_summary_png",
]
