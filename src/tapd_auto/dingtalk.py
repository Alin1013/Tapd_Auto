"""钉钉通知发送。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any
from urllib.parse import quote_plus

import requests


def build_dingtalk_signed_url(webhook: str, secret: str, timestamp: int | None = None) -> str:
    """按钉钉群自定义机器人规则生成加签 URL。"""

    if not secret:
        return webhook
    timestamp = timestamp or int(time.time() * 1000)
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    sign = quote_plus(base64.b64encode(digest).decode("utf-8"))
    separator = "&" if "?" in webhook else "?"
    return f"{webhook}{separator}timestamp={timestamp}&sign={sign}"


def build_dingtalk_markdown_payload(
    title: str,
    markdown: str,
    at_mobiles: list[str] | None = None,
    is_at_all: bool = False,
) -> dict[str, Any]:
    return {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": markdown,
        },
        "at": {
            "atMobiles": at_mobiles or [],
            "isAtAll": is_at_all,
        },
    }


def send_dingtalk_report(config: dict[str, Any], report: dict[str, Any], report_url: str, markdown: str | None = None) -> None:
    """发送钉钉 Markdown 日报。"""

    dingtalk = config.get("dingtalk", {})
    webhook = dingtalk.get("webhook", "").strip()
    if not webhook:
        raise RuntimeError("缺少 DINGTALK_WEBHOOK，无法发送钉钉日报。")
    if markdown is None:
        from .render import render_markdown

        image_url = f"{report_url.rsplit('/', 1)[0]}/summary-1.png"
        markdown = render_markdown(report, report_url, image_urls=[image_url])

    payload = build_dingtalk_markdown_payload(
        title=f"TAPD 每日复盘 {report['date']}",
        markdown=markdown,
        at_mobiles=dingtalk.get("at_mobiles", []),
        is_at_all=bool(dingtalk.get("is_at_all", False)),
    )
    send_url = build_dingtalk_signed_url(webhook, dingtalk.get("secret", ""))
    response = requests.post(
        send_url,
        json=payload,
        headers={"Content-Type": "application/json;charset=utf-8"},
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    if isinstance(result, dict) and result.get("errcode") not in (None, 0):
        raise RuntimeError(f"钉钉发送失败：{result.get('errmsg', '未知错误')}")
