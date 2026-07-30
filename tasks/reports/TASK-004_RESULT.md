# TASK-004 RESULT｜语义分段与爆点识别

## 1. 当前状态

- 代码实现、fake HTTP client 单测、真实 timeline 离线与真实 API 贯通、中断恢复、
  最近 3 版本和前 3 候选人工抽查已完成。
- 三个 `LIVECLIP_LLM_*` 环境变量从 Windows User 作用域安全读取；API Key 未输出或
  写入文件。
- 最终 source-only 已通过；当前等待 Draft PR 三项 latest-head Actions 和独立审核。

## 2. 实现范围与 CLI

```powershell
python -m liveclip analyze `
  --timeline "<PATH>\timeline.json" `
  --output "<OPTIONAL_OUTPUT_DIR>"
```

默认输出到 timeline 同级目录。只处理单个 `timeline.json` 和单个分析任务，不读取
MP4、不重新执行 ASR、不修改 timeline。

## 3. 文本模型接口

只支持一个用户配置的 OpenAI-compatible Chat Completions HTTPS 接口：

```text
LIVECLIP_LLM_ENDPOINT
LIVECLIP_LLM_API_KEY
LIVECLIP_LLM_MODEL
```

使用 Python 标准库 HTTP，不安装厂商 SDK，不锁定厂商、不路由、不自动切换或比较
模型。超时、429 和 5xx 最多重试一次；401/403 直接失败；非法模型 JSON 或结构错误
只发起一次修复请求。

## 4. 发送和不发送的数据

发送：

- segment ID；
- 相对 `start_ms` / `end_ms`；
- 当前固定窗口内的必要字幕 `text`。

不发送：

- 视频或音频；
- timeline 文件、本地路径或视频文件名；
- API Key；
- 其他窗口全文；
- 状态、历史结果或剪辑命令。

API Key 只从环境变量读取，只进入 HTTP Authorization header，不写入请求正文、状态、
进度输出、结果、报告或 Git。

## 5. 窗口策略

- 时间顺序、非重叠；
- 单窗口最多 600,000 ms；
- 同时最多约 12,000 个字幕字符；
- 达到任一上限开始下一窗口；
- 不拆单个 segment；
- 每窗口最多 3 个候选；
- 顺序请求，不并发；
- 每窗口完成后原子保存状态；
- 不做全文第二轮模型重排，不做 embeddings。

## 6. topic、candidate 与评分

topic 包含 ID、真实连续 segment 范围、程序计算的毫秒时间、标题和摘要。

candidate 包含 ID、topic 引用、真实连续 segment 范围、程序计算的时间和时长、标题、
推荐理由、真实 quote segment 与原句、六项正向评分、风险扣分、程序总分和推荐标记。

```text
total_score =
content_value
+ problem_solving
+ emotion_or_reversal
+ information_density
+ hook_and_shareability
+ completeness
- risk_penalty
```

总分由程序限制在 0—100。60 分以下过滤，75 分及以上
`recommended=true`；候选必须为 15—180 秒。最终按总分降序、同分按开始时间排序，
重叠超过 60% 只保留高分项，全局最多 20 个。

## 7. 恢复与最近 3 版本

`.analysis_work/analysis_state.json` 绑定 timeline 文件 SHA-256、endpoint host、model、
600,000 ms 和 12,000 字符窗口参数，保存已完成窗口及其已校验结果，不保存 API Key。
中断后从下一窗口继续；绑定变化或状态损坏时拒绝复用。成功发布后清理工作状态。

新结果完整写入临时文件并校验后才发布。旧 current 进入
`analysis_history/`；最多保留 2 个历史，加 current 总共 3 个。普通发布失败会回滚并
保持旧 current 和历史字节不变。

## 8. 自动化与离线验证

- TASK-004 专项：30 passed、0 failed。
- TASK-004 + TASK-003/既有 analysis 定向回归：59 passed、0 failed。
- 真实 827.766 秒 timeline 离线 fake-client 贯通：169 segments、2 windows、
  2 requests、2 topics、0 candidates；成功发布合法 `current_analysis.json`。
- 中断恢复：自动测试确认首窗口落盘后从窗口 2 继续，已完成窗口不重跑，成功后
  `.analysis_work` 不存在。
- 最近 3 版本：自动测试连续发布 5 次后保持 current + 2 history。
- 完整 source-only：
  - base-schema-media：158 passed、1 deselected、0 failed；
  - asr-experiments：91 passed、2 deselected、1 个既有 deprecation warning、0 failed；
  - `pip check`：`No broken requirements found.`；
  - 三阶段退出码均为 0，`SOURCE_ONLY_RESULT.status=passed`。
- 本地 Actions 等价门禁：
  - `repository-safety` PublishCandidates：167 files、0 issues；
  - `lightweight-tests`：上述统一 source-only 全部通过；
  - `task-report-gate`：`tasks/reports/TASK-004_RESULT.md` 已新增并通过存在性检查。
- GitHub latest-head 三项 Actions 由 Draft PR 执行；提交前不伪造其状态，最终状态以
  PR handoff 为准。

离线 fake-client 贯通只验证程序与真实 timeline 的窗口、范围、状态和发布，不冒充
真实 API 或真实候选质量验证。

## 9. 真实 API 与人工抽查

- 是否完成：是。
- 模型：`qwen-flash`。
- 输入：827.766 秒、169 segments 的真实 timeline。
- 完成态窗口数：2。
- 完成态请求数：2。
- 完成态总耗时：16.282 秒。
- topics：11。
- candidates：6。
- recommended：6。
- 分数范围：89—94；前三分数为 94、92、91。
- 输出校验：timeline SHA 匹配；schema、连续 segment 范围、程序时间、duration、
  quote、总分、排序和推荐标记全部通过；成功后 `.analysis_work` 已清理。
- 验证会话在完成态运行前另有一次错误凭据 401 和一次本地工具超时终止；两次均没有
  完成窗口、状态或正式输出，不计入上述完成态 2 次请求和 16.282 秒。

前 3 高分候选人工抽查只记录聚合判断：

- 3/3 quote 均逐字来自候选范围内真实 segment。
- 第 1 项标题、理由和时间范围与字幕基本一致，具有剪辑价值；营销价格主张仍需合规
  复核，不应把模型 0 风险扣分当作发布许可。
- 第 2 项存在标题外推、quote 代表性弱和结尾不完整，不宜直接采用。
- 第 3 项主题与推荐理由基本一致，核心叙事可理解，但结尾略有截断；涉及家庭健康和
  隐私，模型风险扣分偏低，必须人工复核。
- 综合结论：候选生成真实可用，但模型推荐不能替代人工审核；前三项中 1 项基本可用、
  1 项需调整后再评估、1 项不宜直接采用。

真实字幕、候选标题、推荐理由和完整分析结果未写入本公开报告，也不会上传 Git。

## 10. 隐私边界

- 真实视频和音频不读取、不发送；
- 只发送当前窗口必要字幕文本；
- API Key 不写文件、日志或 Git；
- 真实 timeline、current/history/state 和 `local-data/` 均被 Git 忽略；
- 公开报告只记录聚合数据。

## 11. 修改文件

- 实现：`src/liveclip/analysis/`、`src/liveclip/cli.py`；
- 测试：`tests/test_semantic_analysis.py`；
- 安全：`.gitignore`；
- 文档：README、CURRENT_STATUS、DECISIONS、TASK 和本 RESULT。

## 12. 已知限制与未实现范围

- 第一版不跨窗口合并 topic；
- 模型对营销合规、隐私风险、标题外推、quote 代表性和片段结尾完整性的判断仍不稳定，
  所有候选必须人工审核；
- 不提供多模型、模型路由、流式输出、后台队列或批量 timeline；
- 未实现 GUI、视频预览、剪辑导出、字幕烧录、发布文案、Agent、插件、数据库、
  embeddings、RAG 或 TASK-005。

## 13. 下一步

只继续 Draft PR 三项 Actions 和独立审核交接。继续禁止 TASK-005。
