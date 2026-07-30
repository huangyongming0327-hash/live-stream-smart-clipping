# ASR MVP 生产基线决策

## 决策

- `primary_model`: `paraformer`（Paraformer）
- `fallback_model`: `sensevoice`（SenseVoice）
- `decision_confidence`: `high`（高）
- `decision_status`: `confirmed_mvp_baseline`
- 第一名相对第二名聚合分领先：43.58 分。

人工质量是主证据。质量排序依次使用聚合质量分降序、平均严重度升序、severity 3 数量升序、胜出积分降序。排除难辨认音频后的第一名保持一致。

## 三模型排序

| 排名 | 全部窗口 | 聚合分 | 清晰音频子集 | 聚合分 |
|---:|---|---:|---|---:|
| 1 | Paraformer | 92.58 | Paraformer | 92.58 |
| 2 | SenseVoice | 49.00 | SenseVoice | 49.00 |
| 3 | Faster-Whisper | 40.00 | Faster-Whisper | 40.00 |

## 技术性能次级证据

- 既有 TASK-002 报告显示，SenseVoice 热 RTF 0.02449、峰值 RSS 490.44 MiB，资源成本最低。
- Paraformer 热 RTF 0.04827、峰值 RSS 5.979 GiB，中文标点与热词路径较完整但资源成本高。
- Faster-Whisper 热 RTF 0.22376、峰值 RSS 655.27 MiB，是唯一提供完整词级时间戳的候选。
- 本任务没有重新运行任何 ASR 模型；以上仅引用既有技术报告。

## 决策理由

Paraformer 的全量窗口聚合质量分排名第一，领先 SenseVoice 43.58 分；置信度同时依据平均严重度、severity 3 数量、胜出积分以及清晰音频子集是否保持同一第一名确定。

## 已知限制

- 20窗口来自单个样本，人工评分存在主观性。
- 没有完整人工参考字幕，本分数不是 CER、WER 或通用准确率。
- 生产硬件、语种、噪声和专名分布变化时需要重新评估。
- 若后续模型、预处理、切段规则或领域分布发生实质变化，应重新执行定向人工听音评估。

## 后续门禁

TASK-003 仍未开始。只有本任务通过独立审核、Draft PR 三项检查通过，并由用户手动决定合并后，才可另行启动 TASK-003。
