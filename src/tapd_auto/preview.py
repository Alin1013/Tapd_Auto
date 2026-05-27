"""本地预览辅助函数。"""

from __future__ import annotations


def build_local_report_url(report_date: str, port: int = 8765, host: str = "127.0.0.1") -> str:
    """生成本地静态服务下的日报访问地址。"""

    return f"http://{host}:{port}/public/reports/{report_date}/index.html"
