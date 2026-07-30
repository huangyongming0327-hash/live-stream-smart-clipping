# TASK-002-HUMAN-002｜分析人工听音结果并确定ASR生产基线

## 目标

对用户完成的20窗口人工听音JSON执行真实manifest绑定、严格结构校验、确定性聚合与MVP模型决策；生成本地完整结果和可公开提交的脱敏报告。

## 强制门禁

- 从PR #3已合并的最新`master`创建`task/TASK-002-HUMAN-002-result-analysis`；
- 原始JSON只读，记录分析前后大小、修改时间与SHA-256；
- `source_manifest_sha256`必须与真实`review-manifest.json`精确匹配；
- 必须为`completed=true`、20/20，窗口集合和时间与manifest一致；
- `severity`和`error_tags`必须恰好包含SenseVoice、Paraformer、Faster-Whisper，拒绝额外模型键；
- 不上传原始JSON、实际听写、用户备注、逐窗口候选文本、音频或`local-data/`。

## 分析范围

- 胜出次数、并列分摊、胜出积分与比例；
- severity 0/1/2/3数量与比例、均值、中位数、可用率、明显问题率和严重失败率；
- 十类错误标签；
- 全部窗口及排除难辨认窗口两套口径；
- 确定性聚合质量分、三模型排序、主模型、备用模型、决策状态与置信度。

## 公开交付

- `experiments/asr/human_review/result_analysis.py`
- `experiments/asr/human_review/analyze_results.py`
- `experiments/asr/tests/test_result_analysis.py`
- `docs/ASR_HUMAN_REVIEW_RESULT.md`
- `docs/ASR_PRODUCTION_BASELINE.md`
- `docs/CURRENT_STATUS.md`
- `docs/DECISIONS.md`
- `tasks/reports/TASK-002-HUMAN-002_RESULT.md`

## 本地交付

以下文件只保存在Git忽略的`<LOCAL_REVIEW_OUTPUT>/analysis/`：

- `asr-human-review-analysis.json`
- `asr-human-review-analysis.md`
- `asr-production-baseline.json`

## 边界

- 不运行ASR模型，不读取或处理真实媒体；
- 不调用云端或收费API，不安装大型依赖；
- 不修改`src/liveclip`，不执行TASK-003；
- 不自动标记Ready，不启用auto-merge，不合并PR。

## 完成条件

严格门禁、双口径统计、脱敏输出、专项测试、source-only回归和原输入哈希保护全部通过；使用项目发布器创建Draft PR并等待三项Actions。之后停止，等待独立审核。
