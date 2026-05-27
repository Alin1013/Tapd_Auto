# TAPD 账号同步记录

最近同步时间：2026-05-27 15:22:39 CST

## 当前账号

| 字段 | 值 |
| --- | --- |
| TAPD 用户 ID | `2001353378` |
| TAPD 用户 nick | `leiailin` |
| 工作区显示名 | 雷艾琳 |
| 当前配置角色 | 当前账号 |

## 当前项目

| 字段 | 值 |
| --- | --- |
| 项目名称 | Deepexi Foil |
| workspace_id | `33002756` |
| 项目状态 | normal |
| 项目分类 | project |

## 当前配置迭代

| 字段 | 值 |
| --- | --- |
| 迭代名称 | Deepexi Foil V1.0.0 |
| iteration_id | `1133002756001001828` |
| 开始日期 | 2026-05-01 |
| 结束日期 | 2026-05-31 |
| 状态 | open |

## 团队成员映射

| 截图姓名 | TAPD 显示名 | TAPD user |
| --- | --- | --- |
| 买年顺 | 买年顺 | `mainianshun` |
| 董超 | 董超 | `dongchao` |
| 杨耀发 | 杨耀发 | `endeavor` |
| 雷艾琳 | 雷艾琳 | `leiailin` |
| 肖文杨 | 肖文扬 | `xiaowenyang` |
| 邹步青 | 邹步青 | `zoubuqing` |
| 孙默 | 孙默 | `sunmo` |
| 符叶茜 | 符叶茜 | `fuyexi` |
| 粘琼月 | 粘琼月 | `nianqiongyue` |
| 郝文林 | 郝文林 | `haowenlin` |
| 黄寅子 | 黄寅子 | `Tora` |
| 唐浩宇 | 唐浩宇 | `tanghaoyu` |

## 当前迭代接口分布

| 对象 | 接口 | 归属字段 | 当前迭代数量 | 团队内命中 |
| --- | --- | --- | --- | --- |
| 任务 | `GET /tasks` | `owner` | 3 | 暂无截图名单内任务归属 |
| 缺陷 | `GET /bugs` | `current_owner` | 138 | 肖文扬 60、雷艾琳 32、唐浩宇 13、符叶茜 12、黄寅子 2 |
| 需求 | `GET /stories` | `owner` | 17 | 黄寅子 4、邹步青 3、董超 2、郝文林 2、孙默 1 |

## 同步规则

- `configs/config.yaml` 是本地真实运行配置，已被 `.gitignore` 忽略，不提交。
- `configs/config.example.yaml` 保留真实项目、真实团队成员和脱敏 dry-run 数据。
- TAPD token 只放 `.env` 的 `TAPD_ACCESS_TOKEN`，不得写入文档、配置示例、测试或报表源码。
- 需求 owner 先按同一团队名单筛选，后续可单独拆产品经理配置。
- 钉钉 webhook 和手机号后续再补充。
- 当前项目任务状态：`open` 未开始、`progressing` 进行中、`done` 已完成。
- 当前项目缺陷关闭类状态：`resolved` 已解决、`verified` 已验证、`rejected` 无需解决、`closed` 已关闭。
- 当前项目需求状态已写入 `tapd.status_labels.stories`，页面会把 `status_17` 等编码转换成中文；完整字段见 live 运行生成的 `field-info.json`。
