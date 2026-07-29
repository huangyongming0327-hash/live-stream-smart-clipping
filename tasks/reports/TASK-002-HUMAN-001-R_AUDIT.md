# TASK-002-HUMAN-001-R AUDIT｜本地人工听音审核包独立审核

- 审核结论：通过
- 总分：92/100
- 阻断问题：无
- 审核对象：PR #3
- PR URL：`https://github.com/huangyongming0327-hash/live-stream-smart-clipping/pull/3`
- 被审核 head：`86dc2bccda88a7066d08ec3848605c610f1683c1`
- 分支：`task/TASK-002-HUMAN-001-review-package`
- 审核日期：2026-07-30（Asia/Shanghai）

## 1. 结论

PR #3 完成了本任务要求的 20 窗口离线人工听音审核包。20 个窗口、时间、标签、分歧分和三模型共 60 段候选文本与原 CSV 逐字符一致；20 个 WAV 的格式、帧数、时间、相对路径及 SHA-256 全部与 manifest 一致。Edge 通过 `file://` 实际打开页面，窗口 1、10、20 实际播放成功；localStorage、刷新恢复、完成门禁、双确认清空、完成版/草稿版 JSON/CSV 导入导出均完成真实验证。

未发现一票否决项。存在两个非阻断校验缺口和一个 CSV 公式解释风险，均应进入后续 backlog；其中 Python 结果校验器未绑定真实 manifest 哈希，后续人工结果分析必须显式补做真实 manifest 比对。

最终建议：**通过，可以由用户手动将 PR #3 标记 Ready 并决定合并**。

## 2. 100 分制评分

| 维度 | 得分 | 满分 | 说明 |
|---|---:|---:|---|
| 需求实现程度 | 24 | 25 | 主要功能和本地交付完整；Chrome 未安装，实际浏览器证据来自任务允许的 Edge |
| 正确性与稳定性 | 17 | 20 | 核心数据、音频、页面和导出正确；扣分项为 Python manifest 绑定缺失及 JS/Python 额外键规则不一致 |
| 测试与验证质量 | 13 | 15 | 21 项专项、source-only、Actions、真实文件和真实 Edge 均验证；自动化测试未覆盖完整浏览器交互和负面导入矩阵 |
| 代码简洁与可维护性 | 14 | 15 | parser、WAV、schema、builder、模板职责清晰；双端校验规则已有轻微漂移 |
| 性能与资源影响 | 10 | 10 | 标准库裁切、20 个短 WAV、无模型/云端/大型依赖，重跑可复用 |
| 安全与任务边界 | 9 | 10 | 完全离线、local-data 被忽略、无上传；CSV 公式前缀未中和 |
| 文档与可追溯性 | 5 | 5 | 任务、指南、决策、RESULT、manifest 和哈希证据完整 |
| 总分 | **92** | **100** | **通过** |

## 3. 阻断问题

未发现阻断问题。

以下一票否决项均未触发：

- 页面可通过 Edge `file://` 直接打开；
- 本地相对 WAV 可实际播放；
- 20 窗口和三模型文本与源 CSV 一致；
- 保存及刷新恢复有效；
- 完成门禁未被绕过；
- 页面拒绝错误 manifest；
- 真实音频、local-data 和用户结果未进入 Git；
- 源 CSV/WAV 哈希未变化；
- 本地与 Actions 测试均为真实 0 failed；
- 页面没有上传或网络请求逻辑。

## 4. 重要问题

### I-1｜Python 校验器未把导出结果绑定到真实 manifest

`validate_review_export()` 只要求 `source_manifest_sha256` 为字符串，不接收或比较预期 manifest SHA。程序化变异测试确认：将该字段替换为另一个 64 字符字符串后，Python 校验仍接受。

当前页面的 JavaScript `validateImport()` 会与页面内嵌的真实 `source_manifest_sha256` 做严格相等比较，因此本地页面导入门禁不受影响，也不构成本次一票否决。

后续人工结果分析必须显式读取真实 `review-manifest.json`、计算 SHA-256，并在进入统计或模型结论前与导出 JSON 的 `source_manifest_sha256` 比对；不能只调用当前 Python 校验器。

### I-2｜JavaScript 与 Python 对额外模型键的规则不一致

Python 要求 `severity` 和 `error_tags` 的键集合恰好等于三模型；页面 JavaScript 只逐项检查三个预期模型，因此会接受例如 `severity.ExtraModel` 的额外键。该数据随后可被页面再次导出，但会被 Python 拒绝。

这不会绕过候选、严重度、完成状态或 manifest 的核心门禁，但会造成页面与后续 Python 工具的互操作性漂移。建议后续统一为“恰好三个模型键”并补回归测试。

## 5. 一般问题与建议

### G-1｜CSV 未中和公式前缀

实际完成版 CSV 使用 `=FORMULA_TEST` 备注验证。CSV 保留该文本；表格引擎导入后把它解释为公式并显示 `#NAME?`。同类风险还包括以 `+`、`-`、`@` 开头的自填文本。

当前数据完全由用户本地自填且不会自动外发，按任务规则记为建议、不单独阻断。后续若 CSV 会被他人打开或进入共享流程，建议在导出时对危险前缀加单引号或采用明确的文本格式策略。

### G-2｜浏览器交互缺少自动化回归

当前 21 项专项测试覆盖生成、结构、WAV、部分 schema 和离线静态检查，但没有自动执行 localStorage、刷新、导入下载、双确认清空和全部负面导入用例。本次通过真实 Edge 人工操作和对生成页面原始 JavaScript 函数的程序化变异测试补足证据。建议后续增加轻量浏览器回归，但不需要为当前技术验证阶段引入大型框架。

## 6. 开始前状态与 PR

- 公开工作副本：`<PUBLIC_WORKTREE>`；
- 当前分支：`task/TASK-002-HUMAN-001-review-package`；
- 本地 HEAD：`86dc2bccda88a7066d08ec3848605c610f1683c1`；
- PR #3 head：`86dc2bccda88a7066d08ec3848605c610f1683c1`；
- 本地分支相对 upstream：`+0/-0`；
- 开始时工作区和暂存区为空；
- origin fetch/push 均为 canonical repository；
- PR 状态：Open、Draft、未合并、auto-merge 关闭；
- PR 变更 15 个文件，未修改 `src/liveclip`，未包含 TASK-003。

原私有仓库开始与结束状态一致：

- HEAD：`24b2496a23aa5fcf26f334fc18e5757c31bbba1f`；
- index SHA-256：`7865DC6450B5221A43EE60AB6BD62AEA9AD0AA67418B0F9EC2A6C9920648CD6C`；
- 仅保留审核前已存在的未跟踪文件 `tasks/reports/TASK-GIT-002-R_AUDIT.md`；
- tracked/index 未发生变化。

## 7. 源输入与 20 窗口真实性

源 CSV：

- SHA-256（审核前后）：`3A31CEA90B97BBF7DFF032627E0B344A26EF09490964D3E37F7CE78ECED7421B`；
- UTF-8 BOM；
- 8 列标题与既有格式完全一致；
- 20 行、20 个唯一窗口 ID；
- 20 组开始/结束时间、类型、分歧分全部与 `review-data.json` 一致；
- SenseVoice、Paraformer、Faster-Whisper 共 60 个文本字段逐字符比较，0 mismatch。

源 WAV：

- SHA-256（审核前后）：`9625C4ED1A2A501DE580BB7713ABEC3F964B93EFFFE6AF3735F719964B4E0CEA`；
- PCM/NONE、16 kHz、单声道、16-bit；
- 13,243,051 帧，827.6906875 秒；
- CSV 最后端点 827.691 秒高出 0.0003125 秒，位于允许的 0.0005 秒三位小数舍入范围；
- 实际帧严格钳制到源 WAV 末帧。

## 8. WAV、manifest 与重复生成

- `clips/` 恰好包含 `window-001.wav` 至 `window-020.wav`；
- 20/20 均可由 Python `wave` 读取；
- 20/20 均为 PCM/NONE、16 kHz、单声道、16-bit；
- 20/20 文件 SHA-256 与 manifest 一致；
- manifest 的窗口 ID、原时间、实际时间、时长、相对路径全部正确；
- padding 为前后各 0.8 秒，窗口 1 首端和窗口 5 末端正确钳制；
- 最短片段 20.7996875 秒，最长 21.600125 秒；
- manifest SHA-256：`25E7D0A7C116B00B895EEA0D5B67AA0AD62FF562C9D8C640685909867A9ABF7B`；
- `review-data.json` 和 HTML 内嵌数据均引用该 manifest；
- HTML 的 20 个相对音频引用全部存在。

使用真实源输入在 D 盘临时目录连续生成两次：

- 第一次生成 20 个片段；
- 第二次复用 20/20；
- 两次共 25 个稳定文件哈希一致；
- 临时重建结果与现有本地审核包完全一致；
- 源 CSV/WAV 哈希不变；
- 临时目录已删除。

## 9. 页面离线、安全与直接打开

静态检查：

- 无 CDN、HTTP/HTTPS、`fetch`、XHR、WebSocket、`sendBeacon` 或上传；
- 无外部 script/stylesheet；
- CSP 为 `default-src 'none'`，脚本和样式仅允许内联，媒体仅允许 self/data/blob；
- 候选文本使用 `textContent`；
- HTML 嵌入 JSON 对 `&`、`<`、`>` 做安全转义；
- 未发现真实绝对路径、凭据或机器身份；
- 生成的 `review.html` 与“公开模板 + review-data 渲染结果”全文一致。

直接打开证据：

- 本机未安装 Google Chrome，默认浏览器为 Microsoft Edge；
- 用户在 Edge 通过 `file://` 直接打开 `<LOCAL_REVIEW_OUTPUT>/review.html`；
- Edge 标题为“ASR 本地人工听音审核”；
- 用户确认 20 个窗口和三模型文本正常渲染；
- 用户实际播放窗口 1、10、20，均有声音且进度条移动；
- 未使用本地 HTTP 服务器替代结论。

由于 Windows 浏览器自动化无法可靠读取当前 `file://` URL，交互证据由用户按最小步骤实际操作并回报；数据文件和导出内容由本审核程序独立复核。未伪称自动浏览器验证，也未取得控制台自动检查证据；页面实际使用未出现阻断性提示。

## 10. localStorage、表单门禁与导航

Edge 实际验证：

- 窗口 1 填写候选和三项严重度后可标记完成；
- 刷新后显示本地进度恢复，字段保留且进度为 1/20；
- 清空最佳候选或严重度会自动取消完成；
- 缺少候选或任一严重度时勾选完成被拒绝；
- 清空全部结果连续出现两次确认；
- 两次确认后恢复 0/20；
- 最终再次导入 0/20 草稿，页面保持 0/20。

代码与状态机检查同时确认：

- 严重度只接受整数 0—3；
- `tie` 和 `none` 是合法候选；
- 错误标签、实际听写、备注、难辨认均进入 state/localStorage/导出；
- “仅显示未完成”、上一个/下一个和进度使用同一 state 计算；
- 完成状态不能在缺少必填项时保留。

## 11. JSON 导入导出

真实 Edge 完成版流程：

1. 导入同 manifest 的 20/20 完成版 JSON；
2. 页面显示 20/20；
3. 实际下载 `asr-human-review-completed.json` 和 `.csv`；
4. 导出的 JSON 与导入 JSON 逐字段完全一致。

真实 Edge 草稿版流程：

1. 双确认清空到 0/20；
2. 实际下载 `asr-human-review-draft.json` 和 `.csv`；
3. 草稿 JSON 为 `completed=false`、`completed_window_count=0`、20 个窗口均 `reviewed=false`；
4. 将实际导出的草稿 JSON 重新导入 Edge，提示成功且仍为 0/20。

直接从生成页面提取原始 `validateImport()` 后执行变异矩阵，以下全部被拒绝：

- 错 manifest；
- 未知窗口；
- 重复窗口；
- 缺失窗口；
- 非法候选；
- severity 浮点、字符串、越界值；
- 非法标签、重复标签；
- 时间不一致；
- 完成计数不一致；
- completed 标志不一致；
- 已完成但缺少必填项。

草稿和完成版正例均被接受。Python 侧除 I-1 所述 manifest 绑定问题外，会拒绝未知/重复窗口、时间不一致、非法严重度/标签、统计不一致和完成缺必填项。

## 12. CSV 导出

实际下载文件验证：

- 完成版和草稿版文件名正确；
- UTF-8 BOM；
- CRLF；
- 20 个数据行、14 列；
- 中文错误标签正确；
- severity、error tags、reviewed、draft/completed 状态正确；
- 逗号、双引号和多行 reference 文本可完整往返；
- 使用表格运行时按 21 行 × 14 列成功导入完成版和草稿版。

公式前缀风险见 G-1。当前没有自动外发路径，因此不阻断。

## 13. 测试与 GitHub Actions

专项测试：

```text
21 passed in 0.97s
```

source-only 本地真实结果：

```text
base-schema-media: 110 passed, 1 deselected, 0 failed, exit 0
asr-experiments: 56 passed, 2 deselected, 1 warning, 0 failed, exit 0
pip check: No broken requirements found, exit 0
SOURCE_ONLY_RESULT.status: passed
```

warning 为既有 Python `audioop` 弃用提示，不是失败。

PR #3 被审核 head `86dc2bcc...` 的 Actions run `30146101383`：

- `repository-safety`：SUCCESS；
- `lightweight-tests`：SUCCESS；
- `task-report-gate`：SUCCESS；
- required jobs 均实际执行，未跳过。

已完整读取 `lightweight-tests` 日志。日志实际显示：

- 基础 `110 passed, 1 deselected`；
- ASR `56 passed, 2 deselected, 1 warning`；
- `pip check` 通过；
- 三阶段退出码为 0；
- `SOURCE_ONLY_RESULT.status=passed`；
- 未发现真实 pytest FAILED/ERROR。

审核报告上传后产生的新 head Actions 由最终 handoff 再次等待和复核，不以本段旧 head 结果替代。

## 14. 代码简洁性与可维护性

- `input_parser.py`：严格解析 CSV，不修复输入；
- `wav_clipper.py`：WAV 检查、帧边界、原子发布与复用；
- `review_schema.py`：审核状态构建和 Python 校验；
- `build_review_package.py`：编排生成、manifest、模板 CSV、HTML；
- `templates/review.html`：单文件离线 UI 与浏览器本地逻辑。

职责分离清楚，未修改正式 `src/liveclip`，无大型依赖、模型、网络服务或不必要抽象。文件写入采用同目录临时文件加原子替换，WAV 重跑按哈希复用。主要维护风险是 Python/JavaScript 双份规则已出现 I-1/I-2 所述漂移。

## 15. Git、隐私与任务边界

`git check-ignore -v` 确认以下全部命中 `.gitignore` 的 `local-data/`：

- `review.html`；
- `review-data.json`；
- `clips/window-001.wav`；
- `exports/`。

检查结果：

- tracked tree 不含 `local-data/**`；
- tracked tree 不含 WAV；
- PR 15 个文件不含真实 review-data、真实音频或用户结果；
- PR 不含模型、运行字幕、虚拟环境、runtime、cache、log；
- PR diff 未发现本机绝对路径、用户名、真实邮箱、私网 IP、token、API key 或私钥；
- tracked tree 仓库安全扫描：137 个文件、0 issue；
- 未修改 `src/liveclip`；
- 未执行 TASK-003；
- 未调用 ASR、云端或收费 API；
- 未创建新 PR、未推 master、未 force push、未 Ready、未 merge、未启用 auto-merge。

## 16. 本地数据最终状态

- 本地审核包核心文件哈希与审核开始时一致；
- `review.html` SHA-256：`0047091A3FC2C6126E4CB3B0C6CB11058E3A132F7BD3AEB92BA9EBF75AB7BDAB`；
- manifest SHA-256：`25E7D0A7C116B00B895EEA0D5B67AA0AD62FF562C9D8C640685909867A9ABF7B`；
- 窗口 1/10/20 WAV 哈希与开始时一致；
- 页面最终人工进度：0/20；
- 审核期间未修改或删除审核包；
- 浏览器下载目录保留本次用户实际导出的完成版和草稿版测试文件；它们位于 Git 仓库外；
- 本审核创建的临时导入样本和临时重建目录已删除；
- 源 CSV、源 WAV、原私有 tracked/index 均未变化。

## 17. 最终建议

审核结论：通过。

总分：92/100。

无阻断问题，不需要 `TASK-002-HUMAN-001-FIX`。I-1、I-2 和 G-1 建议进入 backlog；在后续人工结果分析任务开始前，必须落实“真实 manifest SHA 显式比对”这一操作门禁。

可以由用户手动将 PR #3 标记 Ready 并决定是否合并。本审核不代替用户的 Ready 或合并决定。
