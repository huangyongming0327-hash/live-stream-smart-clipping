# TASK-002-HUMAN-002 RESULT｜分析人工听音结果并确定ASR生产基线

## 1. 任务状态

- 状态：本地实现、真实结果分析、专项测试和source-only回归已完成。
- 分支：`task/TASK-002-HUMAN-002-result-analysis`。
- 基线：通过`Start-CodexTask.ps1`从PR #3合并后的最新`master`提交`a5aa093b8436a6bbe37bd2fbb4ee6ac7a4d779c6`创建。
- 范围：只完成TASK-002人工结果分析与生产基线决策；未运行ASR，未执行TASK-003。

## 2. 输入保护

- 完成版JSON只读使用；开始前记录大小11,041 bytes、修改时间`2026-07-29T18:18:47.990994+00:00`和SHA-256。
- 在Git忽略目录创建一份哈希相同的只读工作副本；若已有副本哈希不同，分析流程会拒绝覆盖。
- 原文件未修改、未重命名、未移动、未覆盖。
- 分析器在读取、计算和输出写入后重复计算原文件SHA-256并要求完全一致。
- 分析后大小仍为11,041 bytes，修改时间仍为`2026-07-29T18:18:47.990994+00:00`。

## 3. 输入JSON哈希

- 分析前：`160964ef19b136947663270e6dd401ea801884518a9364c47327ce2158698aef`。
- 分析后：`160964ef19b136947663270e6dd401ea801884518a9364c47327ce2158698aef`。
- 结论：一致。

## 4. manifest强制比对

- 真实`<LOCAL_REVIEW_OUTPUT>/review-manifest.json`按原始文件字节计算SHA-256：
  `25e7d0a7c116b00b895eea0d5b67aa0ad62ff562c9d8c640685909867a9abf7b`。
- 完成版JSON的`source_manifest_sha256`规范化后为同一值。
- 结论：精确匹配，第一道强制门禁通过；未使用页面内嵌值或文件名猜测。

## 5. 20/20完成性

- `schema_version=1.0`。
- `review_type=asr_human_listening_review`。
- `completed=true`。
- `completed_window_count=20`、`total_window_count=20`、`windows`长度20。
- 20个窗口全部`reviewed=true`；窗口ID唯一，集合与真实manifest完全一致；start/end精确一致。

## 6. 严格键集合验证

- `severity`模型键集合恰好为SenseVoice、Paraformer、Faster-Whisper。
- `error_tags`模型键集合恰好为SenseVoice、Paraformer、Faster-Whisper。
- 不允许额外、缺失或重复JSON对象键；严重度只接受非布尔整数0—3；错误标签只接受十个冻结标签且不得重复。
- 实际完成版通过。专项测试分别证明两个映射中的额外模型键会被拒绝，不会静默删除或修复。

## 7. 胜出统计

| 模型 | 明确胜出 | 并列分摊 | 总胜出积分 | 占20窗口 | 占可判定窗口 |
|---|---:|---:|---:|---:|---:|
| Paraformer | 18 | 0.00 | 18.00 | 90.00% | 90.00% |
| SenseVoice | 2 | 0.00 | 2.00 | 10.00% | 10.00% |
| Faster-Whisper | 0 | 0.00 | 0.00 | 0.00% | 0.00% |

本次没有`tie`、`tie_inconsistent`或`all_unusable`。实现仍覆盖一致并列分摊、不一致并列不计分和都不可用不计胜出但保留质量统计。

## 8. severity统计

| 模型 | severity 0 | severity 1 | severity 2 | severity 3 | 平均 | 中位数 | 可用率(0—1) | 明显问题率(2—3) | 严重失败率(3) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Paraformer | 15 (75.00%) | 5 (25.00%) | 0 (0.00%) | 0 (0.00%) | 0.25 | 0.00 | 100.00% | 0.00% | 0.00% |
| SenseVoice | 5 (25.00%) | 12 (60.00%) | 3 (15.00%) | 0 (0.00%) | 0.90 | 1.00 | 85.00% | 15.00% | 0.00% |
| Faster-Whisper | 4 (20.00%) | 9 (45.00%) | 6 (30.00%) | 1 (5.00%) | 1.20 | 1.00 | 65.00% | 35.00% | 5.00% |

## 9. 错误标签统计

| 错误类型 | SenseVoice | Paraformer | Faster-Whisper |
|---|---:|---:|---:|
| 漏字/漏词 | 3 | 3 | 4 |
| 多字/幻觉 | 8 | 0 | 2 |
| 错字/替换 | 3 | 1 | 7 |
| 人名/品牌/专名 | 0 | 0 | 4 |
| 英文 | 2 | 0 | 1 |
| 数字 | 0 | 0 | 0 |
| 标点/可读性 | 1 | 1 | 15 |
| 非中文异常字符 | 2 | 0 | 0 |
| 切点/分段 | 0 | 0 | 2 |
| 其他 | 0 | 0 | 0 |

## 10. 难辨认子集

- `audio_hard_to_hear`数量：0；清晰音频子集仍为20窗口。
- 因此排除难辨认窗口后的胜出、severity、错误标签、得分和排序与全量结果完全一致。
- `all_unusable=0`、`tie=0`、`tie_inconsistent=0`。
- 实际听写填写数0、备注填写数0；只统计是否填写，不读取到公开报告。

## 11. 聚合质量公式

- `winner_score = 胜出积分 / 窗口数 × 100`。
- `severity_quality_score = mean((3 - severity) / 3) × 100`。
- `reliability_score = (1 - severity_3_count / 窗口数) × 100`。
- `aggregate_quality_score = 0.45 × winner_score + 0.35 × severity_quality_score + 0.20 × reliability_score`。
- 公开显示使用`ROUND_HALF_UP`保留2位小数；本地分析JSON保留未舍入浮点值和精确分数。

| 模型 | winner_score | severity_quality_score | reliability_score | aggregate_quality_score |
|---|---:|---:|---:|---:|
| Paraformer | 90.00 | 91.67 | 100.00 | 92.58 |
| SenseVoice | 10.00 | 70.00 | 100.00 | 49.00 |
| Faster-Whisper | 0.00 | 60.00 | 95.00 | 40.00 |

## 12. 三模型排名

全量窗口与清晰音频子集均为：

1. Paraformer；
2. SenseVoice；
3. Faster-Whisper。

排序严格使用聚合质量分降序、平均severity升序、severity 3数量升序、胜出积分降序。

## 13. 主模型

`primary_model=paraformer`。Paraformer在20窗口中胜出18次，聚合质量分92.58，平均severity 0.25，无severity 2或3；相对第二名领先43.58分。

## 14. 备用模型

`fallback_model=sensevoice`。SenseVoice聚合质量排名第二，且既有技术报告显示其热RTF 0.02449、峰值RSS 490.44 MiB，适合作为资源受限场景的备用路线。

## 15. 决策状态和置信度

- `decision_status=confirmed_mvp_baseline`。
- `decision_confidence=high`。
- 第一名领先第二名43.58分，不少于8分；平均severity不更差，severity 3数量不更多，胜出积分不更低；清晰音频子集保持同一第一名。
- 不建议补充10—20个窗口作为当前决策的强制前置，但样本分布变化时仍需重新评估。

## 16. 技术性能次级依据

- SenseVoice：既有热RTF 0.02449、峰值RSS 490.44 MiB，资源最低。
- Paraformer：既有热RTF 0.04827、峰值RSS 5.979 GiB，中文标点与热词路径完整但资源成本高。
- Faster-Whisper：既有热RTF 0.22376、峰值RSS 655.27 MiB，唯一提供完整词级时间戳。
- 人工质量是主证据；本任务只引用`docs/ASR_MODEL_COMPARISON_REPORT.md`和`tasks/reports/TASK-002_RESULT.md`，没有重跑模型或编造数据。

## 17. 样本限制

- 仅20个定向窗口，且来自单次直播录制，不能外推为行业基准。
- 没有完整人工参考字幕，不计算或声称CER/WER。
- 人工严重度和最佳候选具有主观性；当前没有难辨认窗口，因此敏感性子集不能展示排除样本后的变化。
- 模型、预处理、切段、硬件、语种、噪声、专名或领域分布实质变化时应重新评估。

## 18. 本地完整输出

只保存在Git忽略的`<LOCAL_REVIEW_OUTPUT>/analysis/`：

- `asr-human-review-analysis.json`；
- `asr-human-review-analysis.md`；
- `asr-production-baseline.json`。

完整JSON包含未舍入数值、精确分数、两套口径、排名、决策和输入完整性摘要，不复制实际听写、备注或候选文本。

## 19. 公开输出

- `docs/ASR_HUMAN_REVIEW_RESULT.md`；
- `docs/ASR_PRODUCTION_BASELINE.md`；
- 本任务与RESULT、状态和决策文档。

公开内容只保留输入哈希、聚合统计、决策和样本限制。

## 20. 测试

- 新增专项：30 passed、0 failed；覆盖正常20窗口、manifest匹配/阻断、完成性、窗口集合、两个额外模型键、非法严重度/标签、胜出/并列/都不可用、难辨认子集、公式、排序、三档置信度、脱敏、确定性和输入哈希。
- source-only基础：110 passed、1 deselected、0 failed，exit 0。
- source-only ASR实验：86 passed、2 deselected、1条既有`audioop`弃用warning、0 failed，exit 0。
- `pip check`：`No broken requirements found.`，exit 0。
- 最终`SOURCE_ONLY_RESULT.status=passed`。

未运行模型、真实媒体集成或FFmpeg集成。

## 21. 安全边界

- 原始人工JSON、用户备注、实际听写、逐窗口候选文本和`local-data/`未进入Git。
- `review-manifest.json`、`review-data.json`和原完成版JSON未修改。
- 未运行任何ASR模型，未调用云端/收费API，未下载模型或安装大型依赖。
- 未修改`src/liveclip`，未执行TASK-003。
- 未force push、未启用auto-merge、未合并PR。
- 公开变更未写入真实本机路径、用户名、邮箱、IP或凭据。

## 22. 修改文件

- 分析实现：`experiments/asr/human_review/result_analysis.py`、`analyze_results.py`。
- 测试：`experiments/asr/tests/test_result_analysis.py`。
- 公开结果：`docs/ASR_HUMAN_REVIEW_RESULT.md`、`docs/ASR_PRODUCTION_BASELINE.md`。
- 状态与决策：`docs/CURRENT_STATUS.md`、`docs/DECISIONS.md`。
- 任务与报告：`tasks/TASK-002-HUMAN-002.md`、本RESULT。
- 本地忽略输出：`<LOCAL_REVIEW_OUTPUT>/imports/`和`analysis/`。

## 23. 未完成项

- Draft PR尚待创建及三项Actions完成。
- 尚未执行独立审核；没有本任务AUDIT报告或审核分数。
- TASK-002在独立审核和用户手动合并前尚不能正式关闭。
- TASK-003尚未开始。

## 24. 下一步

下一步只建议对本Draft PR执行独立审核，重点复核真实manifest SHA绑定、严格键集合、并列规则、两套口径、精确公式、脱敏边界和Paraformer/SenseVoice角色。独立审核前继续禁止TASK-003。

## 25. 回滚方法

- PR合并前：关闭Draft PR，并仅删除精确任务分支；不触碰原始人工JSON、审核包、媒体或私有归档。
- PR合并后：通过新的修复/回滚PR执行`git revert`，不重写公开历史。
- 本地`analysis/`可由同一只读输入确定性重建；只有用户明确要求时才处理本地副本，绝不删除或覆盖原完成版JSON。
