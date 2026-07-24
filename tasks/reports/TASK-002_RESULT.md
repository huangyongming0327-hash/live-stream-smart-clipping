# TASK-002 完成报告｜本地字幕识别模型对比验证

## 一、任务结果

- 状态：**已完成**（仅完成 TASK-002；未执行 TASK-003）
- 完成日期：2026-07-20（Asia/Shanghai）
- 基线：`master` / `59c1d895a92d9b8319e04dd1d7fa933ef894c1a7` / `baseline-task-001`
- 输入：`项目\ASR基准\input\benchmark.mp4`
- 原始 SHA-256：`DA2CD4041C7FB59A1DFC08C80B0358C28DBBDC59608A469EB1A0A8AC63694BFF`（任务前后相同）
- 参考字幕：不存在，因此未计算 CER/WER、未生成准确率排名

三候选全部完成同一 827.690688 秒 PCM s16le / 16 kHz / 单声道 WAV 的冷跑与热跑，并完成 20 秒静音和断网守卫短探针。每个成功运行均生成 raw JSON、统一 JSON、SRT、TXT、metrics 和资源采样。

| 候选 | 冷 RTF | 热 RTF | 热峰值 RSS | 时间戳 | 静音 | 离线 |
|---|---:|---:|---:|---|---|---|
| SenseVoiceSmall / sherpa-onnx INT8 | 0.02409 | 0.02449 | 490.44 MiB | VAD 段级，172 段 | 无幻觉 | 通过 |
| Paraformer + FSMN-VAD + CT-Punc | 0.04782 | 0.04827 | 5.979 GiB | 句级，399 段 | 无幻觉 | 通过 |
| Faster-Whisper small CPU int8 | 0.22759 | 0.22376 | 655.27 MiB | 297 段、3,033 词级时间戳 | 无幻觉 | 通过 |

> 准确率排名待人工审核，当前只比较技术性能、输出完整性和候选分歧。

## 二、交付物

- 详细报告：`docs\ASR_MODEL_COMPARISON_REPORT.md`
- 依赖与存储计划：`docs\ASR_DEPENDENCY_PLAN.md`
- 任务记录：`tasks\TASK-002.md`
- 本完成报告：`tasks\reports\TASK-002_RESULT.md`
- 人工审核：`项目\ASR基准\output\人工审核对比.md`、`人工审核对比.csv`
- 实验代码、测试与锁文件：`experiments\asr\`

人工审核包恰好包含 20 个并排窗口，实际覆盖开头/中间/结尾、长句/短句、英文词、低音量、噪声、笑声/掌声人工检查和三候选高分歧位置。

## 三、暂定结论

- 低资源默认候选：SenseVoiceSmall。吞吐和资源明显最好，但只有 VAD 段级时间戳。
- 中文生产准确率挑战者：Paraformer。中文标点和热词路径完整，但约 6 GiB 峰值内存，需要人审证明准确率收益。
- 词级时间戳/多语言备用：Faster-Whisper。时间戳最细，推理最慢且本样本输出无标点。
- 不给最终生产模型与准确率总排名；20 窗口人工审核完成前，文本准确率保持“待审核”。

## 四、测试与验收

- 实验测试：12 passed。
- 基础项目回归：148 passed、0 failed、0 skipped（25.92 秒）；基础 `.venv` `pip check` 通过。
- 媒体验证：能力检查与端到端流程通过；同步/集成 18 passed；`TRIM_VALID=True`、`BURN_VALID=True`。
- 三个独立 ASR 环境：`pip check` 全通过；`pip freeze --all` 与锁文件逐行一致。
- CUDA 核验：无 CUDA/NVIDIA 包；FunASR 使用 `torch 2.11.0+cpu`，`torch.version.cuda=None`、`cuda_available=False`；CTranslate2 CUDA 设备数为 0。
- 三候选冷/热输出各自完全一致；静音均为 0 segment；离线 socket 守卫均通过。

## 五、异常与处理

- SenseVoice 的 NumPy 未声明依赖和 VAD 对象生命周期问题在冒烟阶段暴露并修复；最终全长结果通过。
- FunASR 1.3.22 导入需要 torchaudio；由于无匹配的 Windows `torchaudio 2.13.0`，独立环境改用官方 CPU 配对 `torch/torchaudio 2.11.0+cpu`，并重新完成无 CUDA 核验。
- ModelScope 标点权重下载曾由底层进程持锁；安全检查阻止删除非空 partial，最终下载完整且无 `.incomplete`。
- Python 3.12 对 `audioop` 发出未来移除警告；不影响本轮结果，后续升级 Python 前需替换 RMS 实现。
- CAM++ 未下载：没有足够证据确认样本明显含两个以上真实说话人，按可选探针规则跳过。

## 六、安全边界

- 视频、音频、字幕和结果未上传；未调用云端 ASR、收费 API 或 OpenAI API；未写 API Key。
- 所有环境、模型、缓存、临时文件、日志和结果都位于 D 盘。
- 基础 `.venv` 清单与任务前一致，未污染。
- 未安装 CUDA、GPU PyTorch、NVIDIA 包或 CUDA toolkit。
- 原样本未修改或删除；模型、环境、缓存、样本和结果均被 Git 忽略。
- 未生成正式 `timeline.json`，未修改 `src/liveclip`，未执行 TASK-003。
- 未创建 Git remote、commit 或 push；HEAD 仍为原基线。

## 七、修改范围与回滚

修改/新增范围为 `.gitignore`、`experiments\asr\`、TASK-002 文档、`docs\CURRENT_STATUS.md` 和 `docs\DECISIONS.md`；运行产物位于被忽略的 D 盘目录。未修改正式媒体代码。

若以后明确要求回滚，只删除详细报告“回滚方法”列出的 TASK-002 新增目录与文档；绝不删除 `项目\ASR基准\input\benchmark.mp4`、基础 `.venv`、项目 FFmpeg、`src/liveclip` 或 TASK-001 产物。

## 八、未完成项与下一步

唯一影响选型的未完成项是人工准确率审核：审核现有 20 个窗口，必要时形成参考 SRT/TXT，然后再计算 CER/WER、漏句与重复。TASK-002 在此停止；不自动开始 TASK-003，不创建 Git 提交。
