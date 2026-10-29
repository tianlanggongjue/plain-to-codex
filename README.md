# 大白话转Codex（plain-to-codex）

> 命令行工具名仍为 `codex-brief`；仓库名 plain-to-codex，中文名「大白话转Codex」。

把大白话整理成边界清晰、可以验收的 Codex 执行说明。

零第三方运行依赖，Python 3.9+，支持 Windows / Linux。`lint`、`build`、交互问答和网页均离线运行，不调用模型或付费 API。它用规则发现缺漏，再将你补充的信息整理成 Markdown；不会自动猜测业务需求。

**English:** A dependency-free, offline brief builder for nontechnical Codex CLI users. Lint Chinese or English requests, explain ambiguity in Chinese, and generate structured Markdown with editable guardrails. Sending to a local Codex CLI is optional and requires `--run`. No model name is hardcoded. MIT licensed.

## 快速使用

进入项目目录，无需安装依赖。Linux 示例：

```bash
python3 -m codex_brief lint "把那个页面优化一下，再发布。"
python3 -m codex_brief interactive --out brief.md
python3 -m codex_brief send brief.md
```

Windows 示例（需要 Python 3.9 或更高版本）：

```powershell
py -3 -m codex_brief lint "把那个页面优化一下，再发布。"
py -3 -m codex_brief interactive --out brief.md
py -3 -m codex_brief send brief.md
```

也可用 `python codex-brief.py` 替代 `python -m codex_brief`。以下命令中的 `python` 请替换为本机可用的 `python3` 或 `py -3`。

更喜欢图形界面：直接双击 **[web/index.html](web/index.html)**。粘贴需求后实时显示问题，填写五项信息，生成并复制 brief，也可下载 `.md`。单独复制这一个 HTML 到另一台电脑即可使用，无需服务器、网络或 Python。

## lint：检查歧义和缺漏

```bash
python -m codex_brief lint "整理所有文件，然后删除旧的。"
python -m codex_brief lint --file request.txt
python -m codex_brief lint --file request.txt --json --strict
python -m codex_brief lint "Optimize that thing and deploy it."
```

不带文字和 `--file` 时可读取标准输入；`--file -` 也表示标准输入。输入文件支持 UTF-8 和 UTF-8 BOM。

默认 15 条规则检查：模糊词、指代、目标、成功标准、范围白名单、禁区、输出位置、一句话多任务、危险动作确认点、真实数据、不确定事项、停止条件、验证步骤、批量样例检查点、完成标记。每条提示包含命中内容、为什么会让 Codex 误解、建议怎么补。输入中英文均可，提示为中文。

`--strict` 可用于自动检查：有任意提示返回 `1`；普通 lint 返回 `0`。参数、输入或配置错误返回 `2`；交互被取消返回 `130`。`send --run` 透传 Codex 退出码。

## build：补五项信息，生成 brief

```bash
python -m codex_brief build "根据库存表生成分类汇总" --goal "生成库存汇总报告" --scope "只读 input/，仅写 output/" --forbidden "不得修改原始数据，不要发布" --success "逐行核对总数，每项统计注明来源，缺失标未知" --output "output/report.md，中文 Markdown" --out brief.md
```

五个字段为 `--goal`（目标）、`--scope`（范围）、`--forbidden`（禁区）、`--success`（成功标准）、`--output`（**未来任务产物**的位置与格式）。`--out` 是**本次 brief 文件**的保存位置，不是任务产物的位置；省略时打印 Markdown。

也可将字段放入 JSON：

```json
{
  "goal": "生成库存汇总报告",
  "scope": "只读 input/，仅写 output/",
  "forbidden": "不得修改原始数据，不要发布",
  "success": "逐行核对总数，每项统计注明来源，缺失标未知",
  "output": "output/report.md，中文 Markdown"
}
```

保存为 `fields.json` 后：

```bash
python -m codex_brief build --file request.txt --fields fields.json --out brief.md
python -m codex_brief lint --file request.txt --fields fields.json
```

命令行单项字段优先于 JSON。留空或填写 `TBD`、`待补充` 的字段会保留为草稿；工具不会杜撰答案。生成的 brief 包含原始需求、五个字段和通用护栏。原始需求与补充字段有冲突时，要求执行者先澄清。已有输出文件默认不覆盖，明确使用 `--force` 才覆盖。

## interactive：逐项问答

```bash
python -m codex_brief interactive --out brief.md
python -m codex_brief interactive "生成库存报告" --fields fields.json
```

先显示检查结果，再依次询问目标、范围、禁区、成功标准、输出。回车保留已填内容，未填项标为待补充。问题和提示写入标准错误，Markdown 写入标准输出，因此可直接重定向保存。

## send：默认仅预览

```bash
python -m codex_brief send brief.md
python -m codex_brief send brief.md --cwd . --sandbox workspace-write --model MODEL_ID
```

`MODEL_ID` 是占位符，请替换为自己可用的模型标识；省略 `--model` 时使用本机 Codex 配置。默认沙箱是 `read-only`，可选 `workspace-write` 或 `danger-full-access`。`--cwd` 指定工作目录，`--codex` 指定 Codex 可执行文件。

检查 brief 和预览命令后，显式执行：

```bash
python -m codex_brief send brief.md --cwd . --sandbox workspace-write --run
```

只有 `--run` 会启动 Codex。此时 Codex 可能联网并按本机配置产生费用。工具以参数数组启动进程，brief 通过 UTF-8 标准输入传递，不拼进 shell 命令。预览末尾的 `-` 表示从标准输入读取；复制预览行本身不会自动带上 brief。

未安装 Codex 仍可预览；实际运行时会给出缺失提示。非 Git 工作目录可显式加 `--skip-git-repo-check`。Windows 预览采用 PowerShell 引号；实际启动使用参数数组。若安装方式只暴露 `.cmd` / `.bat` 启动器，请用 `--codex` 指向安装包内的原生 `codex.exe`。

参数与本机 `codex exec --help` 核对。跨版本使用时，也请核对自己安装的 CLI 帮助。

## 修改规则与模板

默认规则、五项提示和 Markdown 模板在 [codex_brief/defaults.json](codex_brief/defaults.json)。规则支持中英文正则，规则类型包括 `match`、`missing`、`multiple`、`danger`。

```bash
python -m codex_brief lint "制作报告" --config examples/custom-config.json
python -m codex_brief build "制作报告" --config examples/custom-config.json
```

`--config` 按规则 `id` 合并，可以增加规则、修改提示或设置 `"enabled": false`。`guardrails` 数组和 `template` 字符串若提供，会整体替换默认值。模板必须保留所有简单占位符：`{request}`、`{goal}`、`{scope}`、`{forbidden}`、`{success}`、`{output}`、`{guardrails}`、`{status}`。JSON 中正则反斜线要写为 `\\`；配置来自可信的本地文件。

网页使用内嵌的默认配置，不会自动读取命令行的 `--config`。修改默认规则、页面模板或 JS 引擎后重新生成：

```bash
python scripts/build_web.py
python scripts/build_web.py --check
```

自定义 Python 正则不一定适用于浏览器。修改共享默认规则时，请使用两者支持的语法并运行对齐测试。更多扩展约定见 [docs/rules.md](docs/rules.md)。

## 示例与验证

- [最小示例（无真实身份）](examples/minimal/README.md)
- [完整的 5 组示例：原话 → 检查结果 → brief](examples/README.md)
- [提炼出的写指令规律](docs/principles.md)
- [实际运行的 lint 演示](docs/qa/lint-demo.md)
- [完成摘要与测试输出](DONE.md)

```bash
python -m unittest discover -s tests -v
python scripts/demo.py
python scripts/build_web.py --check
```

测试只使用标准库；已安装 Node 时额外验证 Python / JavaScript 的 lint 与 brief 一致性，否则明确跳过该项。可选浏览器检查使用本机已安装的 Chromium 类浏览器，不安装依赖：

```bash
python scripts/browser_smoke.py --browser CHROMIUM_EXECUTABLE
```

`CHROMIUM_EXECUTABLE` 是浏览器可执行文件占位符。该检查从 `file://` 加载临时页面，检查实时提示、生成、剪贴板调用及失败回退、输入变化后重新生成和不同窗口宽度。剪贴板系统权限因浏览器而异，页面会在自动复制失败时选中文本供手动复制。

## 能力边界

这是规则检查器，不能理解所有上下文，也不能保证 Codex 绝不越界。否定句、复杂确认语句、同义词和跨句指代可能误报或漏报；提示为零不等于可以安全执行。填写了范围和验收字段，也仍需检查它们是否足够具体。原话中保留的模糊词仍可能提示，即使补充字段已经解释其含义。

网页不上传、不持久保存输入，没有外部脚本、字体、遥测或模型请求。CLI 只写你指定的文件；`send --run` 按明确指令把 brief 交给本机 Codex。本项目只保留从既有 brief 提炼的通用规则，示例使用通用场景，不含私人来源内容。

## 许可证

[MIT](LICENSE)
