# TAPD / 钉钉接口调研

日期：2026-05-26

目标链路：按配置中的多个 TAPD 项目和迭代拉取任务、缺陷、需求数据，聚合成每日复盘图和 HTML 报表，再通过钉钉群机器人发送 Markdown 消息。

## 一、结论

已确认口径：

- TAPD 当前使用个人访问令牌执行，环境变量仍用 `TAPD_ACCESS_TOKEN`。
- 缺陷归属字段暂定为 `current_owner`。
- 产品经理字段使用需求的 `owner`。
- 钉钉群自定义机器人目前还未创建。
- `public_base_url` 可以被钉钉客户端访问，手机端也可访问。

第一版建议只接 2 组接口：

1. TAPD OpenAPI 读接口：
   - `GET /iterations`
   - `GET /tasks`
   - `GET /bugs`
   - `GET /stories`
   - `GET /tasks/get_fields_info`
   - `GET /bugs/get_fields_info`
   - `GET /stories/get_fields_info`
   - 可选：`GET /tasks/count`、`GET /bugs/count`、`GET /stories/count`
2. 钉钉群机器人 Webhook：
   - `POST https://oapi.dingtalk.com/robot/send?access_token=...`
   - 消息类型用 `markdown`
   - 图片用外部可访问 PNG URL 嵌入 Markdown
   - 如果开启加签，需要追加 `timestamp` 和 `sign`

不建议第一版做 TAPD 页面自动化。钉钉侧因为自定义机器人尚未创建，建议优先评估应用机器人作为长期方案；如果只追求最快上线，可以先用群自定义机器人发送 Markdown，发送层保留适配器接口，后续切到应用机器人。

## 二、TAPD OpenAPI 通用规则

官方基础地址：`https://api.tapd.cn`

返回格式默认 JSON，主体通常是：

```json
{
  "status": 1,
  "data": {},
  "info": "success"
}
```

`status = 1` 表示成功，其他值表示失败。GET 参数放 URL 并 urlencode；POST 支持 `application/x-www-form-urlencoded` 或 `application/json`。

分页规则：列表接口默认每页 30 条，`limit` 最大 200，超过后用 `page` 翻页。

查询规则：

- 时间字段支持 `<`、`>`、`~`，例如 `created=2026-05-26 00:00:00~2026-05-26 23:59:59`。
- 枚举字段支持 `|` 表示或。
- 人员字段部分支持 `|` 表示或、`;` 表示与。
- 需求、缺陷、任务的用户相关字段支持 `USER_OR<user1|user2>`。

鉴权口径：

1. 当前项目按个人访问令牌接入，配置为 `TAPD_ACCESS_TOKEN`。
2. 实现时优先按 `Authorization: Bearer ${TAPD_ACCESS_TOKEN}` 接入，并用 `/workspaces`、`/iterations` 或一个最小 `/tasks?limit=1` 请求做启动校验。
3. 如果真实 token 不支持 Bearer，再回退官方 Basic Auth 或 OAuth/项目态 token：Basic Auth 使用 `Authorization: Basic base64(api_user:api_password)`，项目态 token 先 `POST /tokens/request_token` 换 `access_token`。

## 三、TAPD 迭代接口

用途：校验配置里的 `workspace_id`、`iteration_id`，补齐迭代名称、起止日期、状态。

```http
GET https://api.tapd.cn/iterations
```

常用参数：

| 参数 | 用途 |
| --- | --- |
| `workspace_id` | 必填，项目 ID |
| `id` | 按迭代 ID 过滤 |
| `status` | 系统状态 `open` / `done`，自定义状态可传中文 |
| `fields` | 限定返回字段 |
| `limit` / `page` | 分页 |

建议字段：

```text
id,name,workspace_id,startdate,enddate,status,created,modified,completed
```

## 四、TAPD 任务接口

用途：保留任务接口采集和字段发现能力，当前日报不展示任务数、完成数或进展。

```http
GET https://api.tapd.cn/tasks
GET https://api.tapd.cn/tasks/count
GET https://api.tapd.cn/tasks/get_fields_info
```

常用查询：

```http
GET /tasks?workspace_id={workspace_id}&iteration_id={iteration_id}&owner={tapd_user}&fields=id,name,status,owner,created,completed,iteration_id,story_id,begin,due,priority_label&limit=200&page=1
```

常用参数：

| 参数 | 用途 |
| --- | --- |
| `workspace_id` | 必填，项目 ID |
| `iteration_id` | 迭代 ID |
| `owner` | 任务当前处理人，对应配置里的 `tapd_user` |
| `status` | 任务状态 |
| `created` / `modified` / `completed` | 时间筛选 |
| `fields` | 限定字段，减少响应体 |
| `limit` / `page` | 分页 |

任务默认状态：

| 值 | 含义 |
| --- | --- |
| `open` | 未开始 |
| `progressing` | 进行中 |
| `done` | 已完成 |

实现口径：

- 第一版完成状态默认用 `done`。
- 如果项目自定义了任务状态，用 `/tasks/get_fields_info?workspace_id=...` 拉候选值，再在配置中维护 `task_done_statuses`。
- 为了画图，建议拉列表并本地聚合；只有做快速校验或优化时再用 `/tasks/count`。

## 五、TAPD 缺陷接口

用途：统计每个人未解决、今日新增、当日关闭缺陷数。

```http
GET https://api.tapd.cn/bugs
GET https://api.tapd.cn/bugs/count
GET https://api.tapd.cn/bugs/get_fields_info
```

常用查询：

```http
GET /bugs?workspace_id={workspace_id}&iteration_id={iteration_id}&current_owner={tapd_user}&fields=id,title,status,current_owner,reporter,created,resolved,closed,iteration_id,priority_label,severity&limit=200&page=1
```

今日新增可以额外加：

```http
created=2026-05-26 00:00:00~2026-05-26 23:59:59
```

当日关闭按 `closed`、`resolved` 或 `completed` 落在当天统计：

```http
closed=2026-05-26 00:00:00~2026-05-26 23:59:59
```

常用参数：

| 参数 | 用途 |
| --- | --- |
| `workspace_id` | 必填，项目 ID |
| `iteration_id` | 迭代 ID |
| `current_owner` | 当前处理人 |
| `participator` | 参与人，可用于兜底统计 |
| `reporter` | 创建人 |
| `status` / `v_status` | 状态；`v_status` 支持中文状态 |
| `created` / `closed` / `resolved` / `modified` | 时间字段 |
| `fields` | 限定字段 |
| `limit` / `page` | 分页 |

实现口径：

- 第一版缺陷归属字段固定用 `current_owner`，含义是缺陷当前处理人，也就是“现在这条缺陷在谁手上”。
- `current_owner == tapd_user` 用于人员维度聚合，适合日报里展示每个人当前缺陷压力、待处理缺陷和负责推进的缺陷。
- 未解决缺陷：`current_owner == tapd_user` 且 `status not in bug_closed_statuses`。
- 今日新增缺陷：`current_owner == tapd_user` 且 `created` 落在当天；即使当天已经解决或关闭，也仍计入今日新增。
- 当日关闭缺陷：`current_owner == tapd_user`、`status in bug_closed_statuses`，且 `closed`、`resolved` 或 `completed` 任一字段落在当天。这个指标表示“当前/最后归属在此人的当日关闭缺陷”，不等同于“由此人关闭的缺陷”。
- 单个缺陷如果 `current_owner` 支持多人或返回多人字符串，需要按 TAPD 实际返回格式拆分后归属到多个人；否则只归属给单人。
- `current_owner` 为空或不在配置成员表里时，不丢弃数据，归入“未分配/未配置人员”汇总，并在日报异常提示里列出数量。
- 如果测试团队实际要按开发人员、测试人员、参与人或自定义字段看责任，需要通过 `/bugs/get_fields_info?workspace_id=...&all_options=1` 确认字段名，再把 `fields.bug_owner` 从 `current_owner` 改成对应字段。
- 缺陷状态是项目级动态字段，必须用 `/bugs/get_fields_info?workspace_id=...&all_options=1` 拉状态候选值。
- 第一版关闭类状态建议默认配置为：`已解决`、`已关闭`、`无需解决`，但最终以实际工作区状态为准。
- 未解决 = 当前状态不在关闭状态映射中的缺陷。
- 今日新增和当日关闭时间范围 = `Asia/Shanghai` 当天 00:00:00 到 23:59:59。

### 缺陷归属字段选择说明

| 字段 | 适合回答的问题 | 优点 | 风险 |
| --- | --- | --- | --- |
| `current_owner` | 现在谁要处理这些缺陷 | 最适合日报压力和待办视角；随流程流转自动变化 | 当日关闭数代表最后/当前归属，不一定代表关闭动作人 |
| `reporter` | 谁提了这些缺陷 | 适合测试产出、缺陷发现量 | 不代表谁负责解决 |
| `participator` | 谁参与过这些缺陷 | 适合追踪协作范围 | 容易多人重复计数 |
| 开发/测试/自定义字段 | 组织内部定义的责任人 | 可贴合团队真实责任口径 | 需要先用字段发现接口确认字段名和候选值 |

当前日报图建议把 `current_owner` 作为唯一归属字段，避免一个缺陷在多人之间重复计算。若后续需要更细，可以拆成两个维度：

- 处理压力：按 `current_owner` 统计未解决、今日新增。
- 质量归因：按开发人员、自定义责任人或需求归属统计缺陷分布。

## 六、TAPD 需求接口

用途：展示产品经理负责或创建的需求排期和内容。

```http
GET https://api.tapd.cn/stories
GET https://api.tapd.cn/stories/count
GET https://api.tapd.cn/stories/get_fields_info
```

常用查询：

```http
GET /stories?workspace_id={workspace_id}&iteration_id={iteration_id}&owner={tapd_user}&fields=id,name,status,owner,creator,developer,begin,due,created,completed,iteration_id,priority_label&limit=200&page=1
```

常用参数：

| 参数 | 用途 |
| --- | --- |
| `workspace_id` | 必填，项目 ID |
| `iteration_id` | 迭代 ID，支持不等于或枚举查询 |
| `owner` | 处理人 / 负责人 |
| `creator` | 创建人，支持多人员查询 |
| `developer` | 开发人员 |
| `begin` / `due` | 预计开始 / 预计结束 |
| `created` / `modified` / `completed` | 时间字段 |
| `status` / `v_status` | 状态；`v_status` 支持中文状态 |
| `fields` | 限定字段 |
| `include_sub_iteration` | 是否包含子迭代 |
| `include_leaf_stories` | 是否包含子需求 |
| `limit` / `page` | 分页 |

实现口径：

- 产品经理归属字段使用 `owner`。
- 如果后续发现你们工作区的“产品经理”是自定义字段，需要先调 `/stories/get_fields_info?workspace_id=...` 找到 `custom_field_*`，再写到配置里，例如 `pm_field: custom_field_12`。
- 展示字段建议最少包含：标题、产品经理、开始时间、结束时间、状态、TAPD 链接。
- 需求排序：`begin ASC`，再 `due ASC`；如果接口排序不稳定，拉回本地排序。

## 七、TAPD 字段发现和配置落地

不同 TAPD 项目的状态、迭代、模块、自定义字段都可能不同。实现前建议每个 `workspace_id` 启动时拉一次字段配置并缓存到本次运行内。

必拉：

```http
GET /tasks/get_fields_info?workspace_id={workspace_id}
GET /bugs/get_fields_info?workspace_id={workspace_id}&all_options=1
GET /stories/get_fields_info?workspace_id={workspace_id}
```

要从字段配置里确认：

| 对象 | 要确认的字段 |
| --- | --- |
| 任务 | `status` 候选值、`iteration_id` 候选值、自定义字段 |
| 缺陷 | `status` 候选值、`iteration_id` 候选值、`current_owner` 是否符合口径、自定义字段 |
| 需求 | `status` 候选值、`iteration_id` 候选值、产品经理字段是否为 `owner` 或 `custom_field_*` |

建议在 `projects.yaml` 增加可覆盖配置：

```yaml
tapd:
  base_url: https://api.tapd.cn
  auth_mode: bearer # bearer | basic
  task_done_statuses: ["done", "已完成", "已关闭"]
  bug_closed_statuses: ["已解决", "已关闭", "无需解决"]
  fields:
    bug_owner: current_owner
    story_pm: owner
```

## 八、钉钉群机器人 Webhook

用途：发送日报摘要、PNG 图片 URL、HTML 报表链接。

```http
POST https://oapi.dingtalk.com/robot/send?access_token={ACCESS_TOKEN}
Content-Type: application/json;charset=utf-8
```

Markdown payload：

```json
{
  "msgtype": "markdown",
  "markdown": {
    "title": "TAPD 每日复盘 2026-05-26",
    "text": "### TAPD 每日复盘 2026-05-26\n\n今日统计：3 个项目 / 5 个迭代 / 18 人\n\n![日报图](https://tapd-daily.internal.example.com/reports/2026-05-26/summary-1.png)\n\n[查看交互报表](https://tapd-daily.internal.example.com/reports/2026-05-26/index.html)"
  },
  "at": {
    "atMobiles": [],
    "isAtAll": false
  }
}
```

加签算法：

```text
timestamp = 当前毫秒时间戳
string_to_sign = timestamp + "\n" + secret
sign = urlencode(base64(hmac_sha256(secret, string_to_sign)))
send_url = webhook + "&timestamp=" + timestamp + "&sign=" + sign
```

Node.js 示例：

```js
import crypto from "node:crypto";

function signDingTalk(timestamp, secret) {
  const stringToSign = `${timestamp}\n${secret}`;
  return encodeURIComponent(
    crypto.createHmac("sha256", secret).update(stringToSign).digest("base64")
  );
}
```

注意点：

- `DINGTALK_WEBHOOK` 和 `DINGTALK_SECRET` 都只能放 `.env`。
- 发送 PNG 图片时，Markdown 里的图片 URL 必须能被钉钉客户端访问；当前已确认 `public_base_url` 在钉钉客户端和手机端都可访问。
- 自定义群机器人只适合“往群里发消息”，不支持单聊，也不支持接收消息。
- 钉钉开发者百科提示群自定义机器人“即将下线，已创建的机器人不受影响”。如果这是新建长期系统，建议预留切换到“应用机器人”的发送适配层。
- 自定义机器人 API 能力受限，不能直接调用钉钉 OpenAPI 上传图片；如果要上传图片并用 `MediaID`，需要用应用机器人。
- 常见限流口径：每个机器人每分钟最多 20 条消息。日报图片分页时要合并发送，避免循环刷屏。

## 九、钉钉应用机器人长期方案

因为钉钉群自定义机器人当前还没创建，如果这是一个长期运行的内部日报系统，更推荐把发送层设计成可切换：

```text
Notifier
  DingTalkWebhookNotifier  # 快速上线，发 markdown webhook
  DingTalkAppBotNotifier   # 长期方案，走钉钉应用机器人 OpenAPI
```

长期推荐应用机器人的原因：

- 能使用钉钉 OpenAPI，能力范围比 Webhook 更完整。
- 可以上传图片并用媒体资源发送，避免仅依赖外链 Markdown 图片。
- 可以扩展互动卡片、按钮、回调、接收用户消息等能力。
- 更适合企业内部长期维护、权限治理和审计。
- 群自定义机器人更偏轻量通知，平台文档已有生命周期风险提示。

应用机器人的代价：

- 需要在钉钉开放平台创建企业内部应用。
- 需要企业管理员授权、配置应用凭证、机器人能力和可见范围。
- 发送群消息前通常需要处理 `appKey/appSecret`、`access_token`、会话或群机器人安装关系。
- 首版开发复杂度高于 Webhook。

建议决策：

- 如果你要 1-2 天内先跑通日报链路：先创建群自定义机器人，代码里实现 `DingTalkWebhookNotifier`。
- 如果这是要长期沉淀的团队工具：现在就按应用机器人方向申请应用，同时 Webhook 只作为过渡适配器。
- 无论选哪种，业务层只调用统一的 `sendDailyReport(summary, imageUrls, reportUrl)`，不要把 Webhook URL 拼接散落在业务代码里。

## 十、第一版调用流程

1. 加载 `.env` 和 `projects.yaml`。
2. 校验 `TAPD_ACCESS_TOKEN`。
3. 按钉钉发送方案校验 `DINGTALK_WEBHOOK` 或应用机器人配置；Webhook 如有 `DINGTALK_SECRET` 则启用加签。
4. 对每个 `workspace_id` 拉字段配置：
   - `/tasks/get_fields_info`
   - `/bugs/get_fields_info?all_options=1`
   - `/stories/get_fields_info`
5. 对每个项目拉 `/iterations?status=open` 发现打开迭代，再逐个迭代拉：
   - `/tasks` 拉任务列表
   - `/bugs` 拉缺陷列表
   - `/stories` 拉需求列表
6. 本地按项目、迭代、人员聚合今日缺陷，并将 Tora 与粘琼月负责的需求合并为“产品总需求”。
7. 生成 HTML 和 PNG。
8. 用钉钉发送适配器发送 Markdown 消息；Webhook 过渡版走群自定义机器人，长期版走应用机器人。

## 十一、接口到日报字段映射

| 日报字段 | 来源接口 | TAPD 字段 |
| --- | --- | --- |
| 项目 ID | 配置 | `workspace_id` |
| 迭代名称 | `/iterations` | `name` |
| 迭代起止 | `/iterations` | `startdate` / `enddate` |
| 成员 | 配置 | `tapd_user` |
| 任务总数 | `/tasks` | 保留采集能力，当前日报不展示 |
| 完成任务数 | `/tasks` | 保留采集能力，当前日报不展示 |
| 缺陷总数 | `/bugs` | 按 `current_owner` 聚合 |
| 缺陷当日关闭 | `/bugs` | `status in bug_closed_statuses` 且 `closed/resolved/completed` 当天 |
| 缺陷未解决 | `/bugs` | `status not in bug_closed_statuses` |
| 今日新增缺陷 | `/bugs` | `created` 当天 |
| 需求标题 | `/stories` | `name` |
| 产品经理 | `/stories` | `owner` |
| 需求开始 | `/stories` | `begin` |
| 需求结束 | `/stories` | `due` |
| 需求状态 | `/stories` | `status` / `v_status` |

## 十二、仍需确认的点

1. 各项目“完成任务”和“关闭缺陷”的中文状态枚举。
2. TAPD 个人访问令牌的实际请求头格式是否为 Bearer。
3. 钉钉最终选择 Webhook 过渡，还是直接上应用机器人。
4. 如果直接上应用机器人，需要确认企业内部应用创建权限和机器人可见范围。

## 十三、参考文档

- TAPD 使用必读：https://open.tapd.cn/document/api-doc/API%E6%96%87%E6%A1%A3/%E4%BD%BF%E7%94%A8%E5%BF%85%E8%AF%BB.html
- TAPD API 配置指引：https://open.tapd.cn/document/api-doc/API%E6%96%87%E6%A1%A3/API%E9%85%8D%E7%BD%AE%E6%8C%87%E5%BC%95.html
- TAPD 项目态授权：https://open.tapd.cn/document/api-doc/API%E6%96%87%E6%A1%A3/%E6%8E%88%E6%9D%83%E5%87%AD%E8%AF%81/%E9%A1%B9%E7%9B%AE%E6%80%81.html
- TAPD 获取迭代：https://open.tapd.cn/document/api-doc/API%E6%96%87%E6%A1%A3/api_reference/iteration/get_iterations.html
- TAPD 获取任务：https://open.tapd.cn/document/api-doc/API%E6%96%87%E6%A1%A3/api_reference/task/get_tasks.html
- TAPD 获取缺陷：https://open.tapd.cn/document/api-doc/API%E6%96%87%E6%A1%A3/api_reference/bug/get_bugs.html
- TAPD 获取需求：https://open.tapd.cn/document/api-doc/API%E6%96%87%E6%A1%A3/api_reference/story/get_stories.html
- TAPD 任务数量：https://open.tapd.cn/document/api-doc/API%E6%96%87%E6%A1%A3/api_reference/task/get_tasks_count.html
- TAPD 缺陷数量：https://open.tapd.cn/document/api-doc/API%E6%96%87%E6%A1%A3/api_reference/bug/get_bugs_count.html
- TAPD 需求数量：https://open.tapd.cn/document/api-doc/API%E6%96%87%E6%A1%A3/api_reference/story/get_stories_count.html
- 钉钉自定义机器人发送群消息：https://open.dingtalk.com/document/development/custom-robots-send-group-messages
- 钉钉开发者百科：群自定义机器人：https://opensource.dingtalk.com/developerpedia/docs/learn/bot/webhook/overview/
- 钉钉开发者百科：机器人发送消息方式：https://open-dingtalk.github.io/developerpedia/docs/learn/bot/appbot/reply/
- 钉钉开发者百科：应用机器人与群自定义机器人对比：https://opensource.dingtalk.com/developerpedia/docs/learn/bot/overview/
