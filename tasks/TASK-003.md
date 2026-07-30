# TASK-003｜MP4 生成本地字幕时间轴

## 目标

实现第一条真正可用的单视频本地生产流程：

```text
单个 MP4 → 分块提取音频 → 本地 ASR
         → timeline.json + subtitles.srt + transcript.txt + task_state.json
```

默认模型为 Paraformer；SenseVoice 仅作为用户手动选择的低资源模式。

## 范围

- 单 MP4、单任务、最长 3 小时；
- 路径支持中文、空格和括号；
- 默认 60 秒顺序分块，模型只加载一次；
- 每块完成后保存状态，中断后从最近完成块继续；
- 源 SHA-256、模型身份、引擎和分块参数绑定恢复状态；
- 从既有项目 FFmpeg 提取 PCM16、16 kHz、单声道 WAV；
- 全部处理、源复核和 timeline 校验通过后才发布三项正式输出；
- 模型加载与推理保持离线，电池供电时不自动暂停。

## 验收

- fake adapter 单元测试覆盖输入、timeline、SRT/TXT、模型选择、状态、恢复和失败发布；
- Paraformer 与 SenseVoice 真实短 MP4 完整流程通过；
- 真实多分块异常终止与恢复通过，完成块不重复；
- 至少一次较长真实视频分块验证；
- `Invoke-SourceOnlyTests.ps1` 全部 0 failed，`pip check` 通过；
- Draft PR 的 `repository-safety`、`lightweight-tests`、`task-report-gate` 通过；
- 真实媒体、音频、字幕、状态、模型和 `local-data/` 不进入 Git。

## 不做

GUI、批量导入、多任务队列、托盘或 Windows 服务、模型下载/更新/自动切换、
复杂调度、说话人分离、翻译、语义分段、爆点识别、候选审核、视频导出和 TASK-004。
