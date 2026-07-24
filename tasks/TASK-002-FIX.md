# TASK-002-FIX｜Paraformer 时间戳回退修复

- 状态：本地实现与验证完成，等待 TASK-002-FIX-R 独立定向只读复核
- 日期：2026-07-23（Asia/Shanghai）
- Git 基线：`master` / `59c1d895a92d9b8319e04dd1d7fa933ef894c1a7` / `baseline-task-001`
- 范围：只修复 Paraformer 缺失或异常时间戳时伪造整段音频范围的问题；不执行 TASK-003

## 修复契约

- 只有 FunASR 提供且通过格式、有限性、正序、单调和音频边界校验的时间范围可以进入 segment。
- 无时间文本保留在 raw JSON；统一结果用结构化 warning/error 记录数量、raw 索引、sentence 索引（如适用）和原因。
- 全部无可用时间轴时标记 `timeline_status=unavailable`，保留 raw/unified/TXT/metrics，候选失败且不生成正常 SRT。
- 部分缺失时标记 `timeline_status=partial`，只保留有真实时间证据的 segment，不静默丢弃异常条目。
- 不按完整音频、字符长度、平均分配、相邻结果或其他无模型证据的信息猜测时间戳。

## 验证摘要

- ASR 实验测试：31 passed；覆盖字段缺失、`None`、空列表、格式错误、非有限值、逆序、非单调、越界、部分缺失、顶层失败语义和既有 399 段回归。
- 既有 Paraformer cold/warm raw 重建结果均为 399 段；unified、SRT、TXT 与原文件逐字节一致，语音覆盖率仍为 696.75 秒。
- 基础项目：148 passed；媒体验证：18 passed；基础及三个 ASR 环境 `pip check` 全通过；三个 ASR freeze 与 lock 的 5/86/27 行逐行一致。
- Paraformer 30 秒离线探针：18 个真实有效 segment；20 秒静音探针：0 segment；两次 socket guard 均通过。
- 原 MP4、统一 WAV、五个主权重、既有 warm unified 和人工审核包哈希均未变化。

## 边界确认

- 未修改 SenseVoice 或 Faster-Whisper 适配器，未修改正式 `src/liveclip`。
- 未下载或更新模型，未安装或更新依赖，未运行三套完整全长实验。
- 未上传视频、音频、字幕或结果，未调用云端 ASR、收费 API 或 OpenAI API。
- 未安装 CUDA/NVIDIA，未修改系统 PATH 或永久环境变量。
- 未生成正式 `timeline.json`，未执行 TASK-003，未创建 Git commit、remote 或 push。
- 人工准确率审核仍未完成，不宣布准确率冠军或最终生产模型。

详细证据见 `tasks/reports/TASK-002-FIX_RESULT.md`。下一步仅建议执行一次 TASK-002-FIX-R 定向只读复核。
