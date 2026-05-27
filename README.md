# TAPD 自动日报

这个项目用于生成 TAPD 每日复盘报表。第一版先把本地链路打通：读取配置、聚合任务/缺陷/需求数据、生成 HTML 交互报表、Markdown 摘要和 JSON 数据文件。后续补齐项目、迭代、成员、钉钉机器人和 TAPD 实际字段后，再切到真实接口同步。

## 当前文件

- `tapd_daily.py`：日报生成主程序。
- `config.example.yaml`：示例配置，不包含真实 token。
- `.env`：本地敏感配置，只保存在本机，不提交到 Git。
- `test_tapd_daily.py`：单元测试。
- `implementation-plan.md`：实施计划。
- `interface-rules.md`：TAPD 和钉钉接口落地规则。
- `TAPD每日复盘链路设计.md`：链路设计说明。

## 本地配置

`.env` 已预留这些字段：

```bash
TAPD_ACCESS_TOKEN=你的 TAPD 个人访问令牌
DINGTALK_WEBHOOK=
DINGTALK_SECRET=
```

注意：不要把 `.env` 提交到 Git。当前 `.gitignore` 已经忽略 `.env` 和生成的 `public/reports/`。

## 运行依赖

```bash
python3 -m pip install -r requirements.txt
```

如果本机已经安装了 `PyYAML` 和 `requests`，可以直接运行。

## 本地验证

先使用示例数据生成报表：

```bash
python3 tapd_daily.py --config config.example.yaml --date 2026-05-26 --dry-run
```

生成文件位置：

```text
public/reports/2026-05-26/index.html
public/reports/2026-05-26/summary.md
public/reports/2026-05-26/report.json
```

测试命令：

```bash
python3 -m unittest test_tapd_daily.py -v
```

## 后续需要补充的信息

- TAPD 真实项目 `workspace_id`。
- 每个项目的迭代 `iteration_id`。
- 成员姓名、TAPD 用户标识、角色、详情链接。
- 产品经理姓名和 TAPD 用户标识。
- 钉钉机器人 webhook 和加签 secret。
- TAPD 任务、缺陷、需求接口返回字段与当前工作区字段映射。

## 接口规则

- TAPD 默认使用 `Authorization: Bearer ${TAPD_ACCESS_TOKEN}`。
- TAPD 返回 `status = 1` 才算成功，否则使用 `info` 作为错误原因。
- TAPD 列表统一使用 `limit=200&page=N` 翻页。
- 任务归属字段默认 `owner`。
- 缺陷归属字段默认 `current_owner`。
- 需求产品经理字段默认 `owner`。
- 钉钉首版使用群自定义机器人 Webhook，开启加签时按 `timestamp + "\n" + secret` 生成 `sign`。
- 详细规则见 `interface-rules.md`。

## 当前链路

1. 从 `.env` 读取 token 和钉钉敏感配置。
2. 从 `config.example.yaml` 读取项目、迭代、成员、状态映射和示例数据。
3. 按项目和迭代过滤任务、缺陷、需求。
4. 按人员计算任务完成率、已关闭缺陷、未解决缺陷、当天新增缺陷。
5. 按产品经理展示需求排期。
6. 输出 HTML、Markdown 和 JSON。

真实 TAPD 接口接入后，`sample_data` 会被 API 返回数据替换，后面的聚合和展示链路保持不变。
