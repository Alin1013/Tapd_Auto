# Production Runbook

本文档用于把 TAPD 自动日报部署成稳定的生产工具。

## 1. 目录约定

推荐部署目录：

```text
/opt/tapd-auto/
```

目录中的敏感文件：

```text
.env
configs/config.yaml
```

这两个文件只保存在服务器本地，不提交到 Git。

## 2. 首次部署

```bash
git clone git@github.com:Alin1013/Tapd_Auto.git /opt/tapd-auto
cd /opt/tapd-auto
python3 -m pip install -r requirements.txt
cp .env.example .env
cp configs/config.example.yaml configs/config.yaml
mkdir -p logs
```

然后补齐：

- `.env` 中的 `TAPD_ACCESS_TOKEN`
- `.env` 中的 `DINGTALK_WEBHOOK` 和 `DINGTALK_SECRET`
- `configs/config.yaml` 中的真实项目、迭代、成员、产品经理和状态映射

## 3. 手动验证

只生成报表，不发送钉钉：

```bash
python3 tapd_daily.py --config configs/config.yaml --live
```

确认输出：

```text
public/reports/YYYY-MM-DD/index.html
public/reports/YYYY-MM-DD/summary-1.png
public/reports/YYYY-MM-DD/summary.md
public/reports/YYYY-MM-DD/report.json
public/reports/YYYY-MM-DD/field-info.json
```

确认 `summary-1.png` 和 `index.html` 可以通过 `report.public_base_url` 被钉钉客户端访问。传入 `--send-dingtalk` 时会额外生成 `page-screenshot.png` 并作为钉钉推送首图。

本地预览：

```bash
bash scripts/preview.sh
```

默认地址：

```text
http://127.0.0.1:8765/public/reports/YYYY-MM-DD/index.html
```

## 4. 发送钉钉

确认报表 URL 外部可访问后再执行：

```bash
python3 tapd_daily.py --config configs/config.yaml --live --send-dingtalk
```

发送失败时优先检查：

- `.env` 中的 `DINGTALK_WEBHOOK`
- `.env` 中的 `DINGTALK_SECRET`
- 钉钉机器人关键词或加签设置
- `report.public_base_url` 是否能在手机端访问
- 服务器是否安装 Chrome/Chromium；页面实时截图依赖无头浏览器，必要时设置 `TAPD_AUTO_BROWSER_PATH`

## 5. 定时任务

推荐每天 17:00 发送：

```bash
crontab -e
```

写入：

```text
0 17 * * * cd /opt/tapd-auto && /bin/bash scripts/run_daily.sh >> logs/tapd-daily.log 2>&1
```

## 6. 回滚

如果新版本异常：

```bash
cd /opt/tapd-auto
git log --oneline -5
git revert <异常提交>
python3 -m unittest discover -s tests -v
```

确认测试通过后再恢复 cron。

## 7. 升级前检查

每次改接口字段、状态映射、项目或迭代后，先跑：

```bash
python3 -m unittest discover -s tests -v
python3 tapd_daily.py --config configs/config.yaml --live
```

查看 `field-info.json`，确认 TAPD 字段和状态枚举没有偏差。
