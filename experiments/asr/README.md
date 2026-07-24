# TASK-002 ASR 实验

本目录只承载 TASK-002 的可复现实验代码，不属于正式 `src/liveclip`，不生成正式 `timeline.json`。

固定候选：

1. sherpa-onnx SenseVoice INT8（GGUF v0.1.7 无时间戳后的官方替代实现）；
2. FunASR Paraformer + FSMN-VAD + CT-Punc；
3. SYSTRAN faster-whisper small CPU int8。

所有候选由 `benchmark.py` 顺序执行。每个候选进行冷加载、30 秒预热、全样本冷运行、退出、等待 25 秒、全样本暖运行、静音探针和独立离线短探针。子进程使用 Below Normal 优先级和 4 个线程，每 0.5 秒采样 CPU、RSS 和可用内存。

运行单个候选示例：

```powershell
& .\.venv\Scripts\python.exe -m experiments.asr.benchmark --candidate sensevoice
```

基础 `.venv` 只负责无第三方依赖的编排；候选实际推理分别使用 `runtime/asr-envs/` 下的独立 Python。模型、环境、缓存、日志和结果均在 D 盘并被 Git 忽略。
