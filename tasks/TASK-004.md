# TASK-004｜语义分段与爆点识别

## 目标

实现单个已完成 `timeline.json` 的最小语义分析闭环：

```text
timeline.json
→ 话题分段
→ 爆点候选
→ 程序评分
→ 标题和推荐理由
→ current_analysis.json
```

## 范围

- 单 timeline、单分析任务；
- 一个用户配置的 OpenAI-compatible Chat Completions HTTPS 接口；
- 只发送 segment ID、相对时间和必要字幕文本；
- 最多 10 分钟且约 12,000 字符的固定顺序窗口；
- 每窗口最多 3 个候选，全局最多 20 个；
- topic/candidate 只引用真实连续 segment；
- 程序计算时间、quote、总分、推荐标记、过滤与重叠去重；
- 每窗口原子保存状态，中断后从下一窗口继续；
- 当前结果加历史总共只保留最近 3 个完整版本。

## 验收

- fake HTTP client 单元测试覆盖输入、窗口、模型 JSON、评分、范围、恢复和发布；
- 使用一份 Git 忽略的真实 timeline 完成真实 API 分析；
- 人工抽查分数最高的前 3 个候选；
- 中断恢复和最近 3 版本保留通过；
- 完整 source-only 回归和 `pip check` 通过；
- Draft PR 的 `repository-safety`、`lightweight-tests`、`task-report-gate` 通过；
- 真实 timeline、analysis、state、字幕、API Key 和本地路径不进入 Git。

## 不做

GUI、视频预览、剪辑导出、字幕烧录、多片段拼接、竖屏转换、封面与发布文案、
多模型投票、Agent、插件系统、数据库、工作流引擎、embeddings、RAG 和 TASK-005。
