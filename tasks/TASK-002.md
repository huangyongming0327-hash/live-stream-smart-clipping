# TASK-002｜本地字幕识别模型对比验证

- 状态：已完成
- 开始日期：2026-07-20（Asia/Shanghai）
- 完成日期：2026-07-20（Asia/Shanghai）
- 基线：`59c1d895a92d9b8319e04dd1d7fa933ef894c1a7` / `master` / `baseline-task-001`
- 输入：`项目\ASR基准\input\benchmark.mp4`
- 范围：只比较三条本地 CPU ASR 路线，不开发 UI、不生成正式 `timeline.json`、不执行 TASK-003。

## 固定安全边界

- 所有环境、模型、缓存、临时文件、日志和结果只放 D 盘；
- 不上传用户视频、音频或字幕；
- 不调用云端 ASR、收费 API 或 OpenAI API；
- 不污染基础 `.venv`，不安装 CUDA 或 GPU 版 PyTorch；
- 不修改系统 PATH、电源计划或永久环境变量；
- 不创建 Git commit、remote 或 push。

## 路线说明

官方 FunASR llama.cpp `runtime-llamacpp-v0.1.7` 的 SenseVoice README 将 timestamps 列在 Roadmap，故该路线不能满足最低时间轴要求。按原指令允许的替代条件，SenseVoice 候选使用官方 sherpa-onnx INT8 Windows CPU 实现。

最终结果以 `tasks/reports/TASK-002_RESULT.md` 与 `docs/ASR_MODEL_COMPARISON_REPORT.md` 为准。

## 完成摘要

- SenseVoiceSmall/sherpa-onnx INT8、Paraformer/FSMN-VAD/CT-Punc、Faster-Whisper small CPU int8 均完成冷/热全样本、20 秒静音和离线短探针。
- 三候选冷/热输出各自完全一致，静音均无幻觉，离线 socket 守卫均通过。
- 无参考字幕，未计算 CER/WER；已生成恰好 20 个固定窗口的人工审核 Markdown/CSV。
- 实验测试 12 passed；基础回归 148 passed；媒体验证 18 passed；所有环境 `pip check` 通过。
- 暂定低资源候选为 SenseVoiceSmall；最终准确率和生产选型待人工审核，不给准确率总排名。
- 未执行 TASK-003，未创建 Git commit、remote 或 push。
