# TAPD / DingTalk Interface Rules

本文档根据 `docs/research/tapd-dingtalk-api-research.md` 沉淀为第一版实现规则。调研文档可以继续作为原始资料，本文档作为代码和配置落地时优先遵循的规则。

## 1. 总体链路

第一版链路按以下顺序执行：

1. 加载 `.env` 和配置文件。
2. 校验 `TAPD_ACCESS_TOKEN` 存在，但不得打印 token。
3. 校验钉钉发送配置；Webhook 模式下 `DINGTALK_SECRET` 非空则启用加签。
4. 对每个 `workspace_id` 拉字段信息，确认任务、缺陷、需求的状态和自定义字段。
5. live 模式对每个项目先拉 `/iterations?status=open` 发现打开迭代，再按迭代拉取 `/tasks`、`/bugs`、`/stories`。
6. 本地按项目、迭代、成员聚合缺陷统计和产品总需求。
7. 生成 PNG、HTML、Markdown、JSON；live 模式额外保存字段发现结果。
8. 通过统一通知适配器发送日报，首版使用钉钉 Webhook，长期保留应用机器人适配空间。

## 2. TAPD 通用规则

- 基础地址固定为 `https://api.tapd.cn`，可通过 `tapd.base_url` 覆盖。
- 当前鉴权模式优先使用 `Authorization: Bearer ${TAPD_ACCESS_TOKEN}`。
- TAPD 响应中 `status = 1` 视为成功，其他状态必须作为失败处理，并输出 `info`。
- TAPD 列表记录可能包在 `Task`、`Bug`、`Story`、`Iteration` 等对象键下，进入聚合前必须先展开为扁平字段。
- 列表接口统一使用 `limit=200&page=N` 翻页。
- 当某页返回数量少于 200 时停止翻页。
- 时间统计按 `Asia/Shanghai` 日期口径。
- 配置、日志、报表都不得写入 TAPD token。
- CLI 必须显式选择 `--dry-run` 或 `--live`，避免默认误请求 TAPD。

## 3. TAPD 字段发现规则

真实接口接入前，每个工作区至少拉一次字段配置：

```text
GET /tasks/get_fields_info?workspace_id={workspace_id}
GET /bugs/get_fields_info?workspace_id={workspace_id}&all_options=1
GET /stories/get_fields_info?workspace_id={workspace_id}
```

字段发现要确认：

| 对象 | 必须确认 |
| --- | --- |
| 任务 | `status` 候选值、`iteration_id`、负责人字段 |
| 缺陷 | `status` 候选值、`current_owner` 是否符合归属口径、自定义责任字段 |
| 需求 | `status` 候选值、`owner` 是否为产品经理字段、自定义 PM 字段 |

如果某个工作区字段不同，只改配置，不改聚合代码。

## 4. 字段映射规则

配置入口：

```yaml
tapd:
  fields:
    task_owner: owner
    bug_owner: current_owner
    story_pm: owner
```

第一版默认规则：

- 任务归属字段：`owner`。
- 缺陷归属字段：`current_owner`。
- 产品经理需求字段：`owner`。

缺陷统计口径：

- 未解决缺陷：`current_owner == tapd_user` 且状态不在 `bug_closed_statuses`。
- 今日新增缺陷：`current_owner == tapd_user` 且 `created` 落在当天；不因为当天内已解决或已关闭而排除。
- 当日关闭缺陷：`current_owner == tapd_user`、状态在 `bug_closed_statuses`，且 `closed`、`resolved` 或 `completed` 任一关闭时间落在当天。
- `Tora`（黄寅子）和 `nianqiongyue`（粘琼月）不进入缺陷成员表。
- `current_owner` 为空或不在配置成员中时，后续应归入“未分配/未配置人员”异常提示。

当前“当日关闭缺陷”表示最后或当前归属在此人的当日关闭缺陷，不等同于“由此人关闭的缺陷”。如果后续要统计关闭动作人，需要另行确认解决人、关闭人或自定义流程字段。

迭代展示口径：

- live 模式默认遍历项目下所有打开迭代，不要求团队成员都在同一个迭代内。
- 同一迭代内的团队成员缺陷汇总在同一张迭代卡片内展示。
- 迭代必须有当日动作才进入日报：至少有今日新增缺陷、当日关闭缺陷，或当天创建/修改/完成/排期覆盖当天的产品需求。
- 仅有历史未解决缺陷或历史产品需求的迭代不进入当日日报。
- 项目下没有任何当日活跃迭代时，整个项目不进入当日日报。
- 已展示迭代中的“产品总需求”保留当前迭代内所有未发布需求，不再按当天动作二次裁剪。
- 页面使用纵向滚动承载多迭代卡片，不再使用迭代内标签页切换。

## 5. 状态映射规则

配置入口：

```yaml
tapd:
  task_done_statuses:
    - done
    - 已完成
    - 已关闭
  bug_closed_statuses:
    - 已解决
    - 已关闭
    - 无需解决
```

规则：

- 每个项目真实状态以字段发现接口为准。
- 任务数据用于保留接口链路，不在日报页面、Markdown 通知或 PNG 摘要中展示任务数、完成率、进展。
- 未解决缺陷 = 当前状态不在关闭状态映射中的缺陷。
- 团队成员默认展示未解决、今日新增、当日关闭缺陷；配置 `hide_bug_metrics: true` 的成员不展示缺陷数字。
- HTML 页面需要按成员展示 TAPD 缺陷状态柱状图，不同状态使用不同颜色；没有缺陷状态数据时仍展示成员和 0 指标。
- 配置了显式迭代范围时，该范围内成员即使当天工作量为 0 也展示，避免当前关注迭代页面为空。
- “产品总需求”排除状态为 `发布`、`已发布` 或原始状态 `status_21` 的需求。
- 状态映射不确定时，先展示原始状态候选，不擅自归类。

## 6. 钉钉 Webhook 规则

首版通知使用群自定义机器人 Webhook：

```text
POST https://oapi.dingtalk.com/robot/send?access_token=...
Content-Type: application/json;charset=utf-8
```

发送 payload：

```json
{
  "msgtype": "markdown",
  "markdown": {
    "title": "TAPD 每日复盘 2026-05-26",
    "text": "### TAPD 每日复盘 2026-05-26"
  },
  "at": {
    "atMobiles": [],
    "isAtAll": false
  }
}
```

加签规则：

```text
timestamp = 当前毫秒时间戳
string_to_sign = timestamp + "\n" + secret
sign = urlencode(base64(hmac_sha256(secret, string_to_sign)))
send_url = webhook + "&timestamp=" + timestamp + "&sign=" + sign
```

约束：

- `DINGTALK_WEBHOOK` 和 `DINGTALK_SECRET` 只放 `.env`。
- 钉钉 Markdown 开头嵌入页面截图 `page-screenshot.png`，后续复盘解析保持 Markdown 文字。
- 页面截图 URL 和 HTML 报表 URL 必须能被钉钉客户端访问，便于群内成员查看首图和详情。
- 自定义机器人限流要按每分钟 20 条消息控制，日报应合并为单条消息发送。
- 发送层必须保留统一入口，后续可以替换为应用机器人。

## 7. 长期通知适配规则

发送层按统一接口设计：

```text
Notifier
  DingTalkWebhookNotifier
  DingTalkAppBotNotifier
```

业务层只关心：

```text
send_daily_report(summary, image_urls, report_url)
```

长期如果切到应用机器人，可以支持上传图片、互动卡片、按钮和回调；不要把 Webhook 拼接逻辑散落在业务层。

## 8. 待确认清单

- 各项目真实 `workspace_id`。
- dry-run 示例或指定迭代运行时需要补充真实 `iteration_id`；live 模式默认自动发现打开迭代。
- 各项目任务完成状态枚举。
- 各项目缺陷关闭状态枚举。
- TAPD 个人访问令牌是否稳定支持 Bearer。
- 钉钉最终使用群 Webhook 过渡，还是直接申请企业内部应用机器人。
