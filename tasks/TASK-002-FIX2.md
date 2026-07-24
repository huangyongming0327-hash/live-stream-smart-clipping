# TASK-002-FIX2｜Paraformer 非单调时间轴修复

- 状态：本地实现与验证完成，等待 TASK-002-FIX2-R 独立定向复核与质量评分
- 日期：2026-07-23（Asia/Shanghai）
- Git 基线：`master` / `59c1d895a92d9b8319e04dd1d7fa933ef894c1a7` / `baseline-task-001`
- 范围：只修复 Paraformer `sentence_info` 条目之间和多个 raw item 之间的非单调来源顺序、结构化排除及测试覆盖；不执行 TASK-003

## 修复契约

- 模型来源顺序必须在 Paraformer 适配器层校验，公共排序不作为异常修复手段。
- 当前条目同时满足单项时间有效性以及 `start`、`end` 均不早于上一个已接受有效段时，才可进入统一时间轴。
- 非单调条目使用既有 `PARAFORMER_TIMESTAMP_INVALID` / `timestamp_non_monotonic` 体系结构化排除，并保留 raw/sentence 索引、当前与前序时间及 raw 可追溯标记。
- 异常条目排除后，后续条目继续与上一个已接受有效段比较；正常时间戳不重排、不重分配、不猜测。
- 部分有效时保留真实段并标记 `partial`；全部无可用时间时标记 `unavailable`、保留失败产物并抑制正常 SRT；正常空结果不误报。

## 固定边界

- 不修改 SenseVoice、Faster-Whisper、正式 `src/liveclip`、既有 399 段结果或人工审核包。
- 不下载/更新模型，不安装/更新依赖，不运行三套完整全长实验，不上传数据，不调用云端 ASR 或收费 API。
- 不生成正式 `timeline.json`，不执行 TASK-003，不创建 Git commit、tag、remote 或 push。

完成证据见 `tasks/reports/TASK-002-FIX2_RESULT.md`；下一步仅建议 TASK-002-FIX2-R 独立定向复核。

## 验证摘要

- ASR 实验测试 37 passed；新增六类来源顺序/失败/空结果行为测试，既有异常回归继续通过。
- cold/warm 正式 raw 重建仍为 399 段、4,288 字符、696.75 秒覆盖，unified/SRT/TXT 逐字节一致；原结果目录未改写。
- 30 秒本地离线探针为 18 段，20 秒静音为 0 段；两次 socket guard 均通过。
- 基础回归 148 passed；媒体验证 18 passed；基础及三个 ASR 环境 `pip check` 通过，三个 freeze 与 lock 逐行一致。
- 人工审核包和受保护媒体/模型哈希不变；人工准确率仍待审核，不宣布最终生产模型。
