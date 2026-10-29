# 扩展规则

默认数据源为 `codex_brief/defaults.json`。自定义配置用 `--config` 传入 JSON 对象，顶层仅支持 `rules`、`guardrails`、`template`。

每条启用规则包含 `id`、`kind`、`severity`、`title`、`why`、`suggestion`。严重度为 `info`、`warning` 或 `error`；所有提示仍需人工判断。`enabled: false` 禁用规则。同一自定义文件不得重复 `id`。

| 类型 | 必需正则字段 | 行为 |
| --- | --- | --- |
| `match` | `pattern` | 出现匹配内容时提示 |
| `missing` | `pattern` | 未出现必要信息时提示；可绑定 `field` |
| `multiple` | `pattern`、`connector` | 原始需求同一句出现多个动作和连接词时提示 |
| `danger` | `pattern`、`negative`、`confirm`、`bypass`、`global_confirm` | 检查动作、禁止措辞、确认点与跳过确认 |

`when` 可选，只在全文符合该条件时应用规则。`field` 只接受 `goal`、`scope`、`forbidden`、`success`、`output`。明确填写有效字段可满足对应的 missing 规则；明确填写待补充占位符会继续提示。原始需求中的空标题和占位符不会充当有效证据。

危险动作规则按句子及分句检查确认范围。例如“不要删除，发布页面”仍报告发布风险；“删除后确认”和“不用确认直接删除”仍报告风险。否定可以跨“删除或发布”这类动作列表延续。复杂自然语言仍可能误判，通用护栏是文本约束，不能代替实际权限控制。

规则匹配不调用网络或模型。正则以忽略大小写方式运行；避免依赖 Python 专属语法，也避免复杂嵌套回溯。默认网页使用同一份 JSON 数据，经 `scripts/build_web.py` 内嵌，但规则引擎分别由 Python 和 JavaScript 实现；`tests/test_web.py` 在 Node 可用时比较两端的实际结果。

修改 `template` 时必须保留全部八个占位符；不允许属性访问、格式化转换或未知字段。`guardrails` 为字符串数组，传入即整体替换，因此应保留任务需要的约束。为避免原始输入伪装成模板标题，原话和五项字段均以 Markdown 引用块插入。

新增规则后，增加包含正例、反例与中英文边界的测试，再运行单元测试及网页生成检查。
