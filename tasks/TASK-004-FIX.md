# TASK-004-FIX：爆点候选容错与分析稳定性

## 背景

真实端到端验收中，同一个视频的 ASR 首次完成、第二次正确复用，但爆点分析分别在唯一一次
repair 后因 candidate 时长不符合 15—180 秒、candidate 未完整属于一个 topic 而失败。问题
集中在 TASK-004 文本模型 candidate 输出稳定性。

## 目标

保持首次模型输出的现有严格校验和最多一次 repair。repair 后：

1. JSON、顶层结构、topics 或 candidates 容器无效时继续失败，不强行修复。
2. topics 完全有效、candidates 是合法数组且不超过每窗 3 个时，对 candidates 逐项执行原有
   严格规则；只丢弃不合格项并保留合格项，窗口继续成功。
3. repair 后所有 candidate 均不合格时，以 `candidates=[]` 完成并保存当前窗口，不再请求模型。

## 必须保持的规则

- candidate 时长必须为 15—180 秒。
- candidate 必须完整属于一个 topic。
- `quote_segment_id` 必须在 candidate 内。
- 所有 segment ID 必须真实且范围连续。
- score 与 risk 必须在原有范围。
- 没有合格候选时允许空 candidates。
- 每窗口最多 3 个 candidate。
- 最终 `current_analysis.json` 必须通过严格 `validate_analysis`。
- 每个窗口最多 2 次 API 请求：首次请求加唯一一次 repair。

## 禁止范围

- 不自动延长或缩短 candidate，不改 topic，不猜 segment ID，不强塞 candidate 到 topic。
- 不增加第 3、4 次模型请求，不更换模型。
- 不修改 ASR、字幕烧录或 Windows 启动器。
- 不实现批量、多片段拼接、自动发布或 TASK-008。
- 不删除或覆盖原始视频，不提交真实字幕正文、候选标题、本地路径、API Key 或其他秘密。

## 验收

- 1 个合法 candidate、1 个时长错误、1 个跨 topic 时只保留合法项。
- quote 越界、score 越界、candidate 字段错误时只丢对应项。
- 全部 candidate 无效时窗口成功且 `candidates=[]`。
- repair 后 JSON 损坏、topics 重叠、topic 引用不存在 segment 或 candidates 不是数组时仍失败。
- 自动测试证明每窗最多 2 次请求且不会发生第 3 次请求。
- candidate 过滤后的窗口可以原子保存 state，再运行从下一窗口恢复。
- 最近 3 个 analysis 版本规则保持不变。
- 完整 source-only 回归 0 failed，`pip check` 通过。
- 优先复用 Git 忽略的真实 timeline 做一次真实 API 验证，不重跑 ASR、不扫描整个用户磁盘、
  不要求重新上传视频。

## 交付

- 分支：`task/TASK-004-FIX-candidate-tolerance`
- 结果报告：`tasks/reports/TASK-004-FIX_RESULT.md`
- 创建 Draft PR；不 Ready、不 merge、不 auto-merge、不 force push。
- 最后运行 `tools/github/Get-PRHandoff.ps1`，输出完整 `PR_HANDOFF` 后停止。
