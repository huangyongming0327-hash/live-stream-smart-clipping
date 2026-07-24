# JSON 数据契约

实现位置：`src/liveclip/schemas/`。三个顶层模型都使用 Pydantic v2 严格模式，拒绝未声明字段，并支持 `model_validate_json()` 与 `model_dump_json()` 的无损往返。

## V1 共通规则

- 三个顶层模型的 `schema_version` 都只能是字符串 `"1.0"`。空值、数字版本和未知字符串版本均拒绝。
- V1 不提供迁移器。未来新增不兼容版本时，必须新增独立 Schema 或显式版本分派，旧模型不得静默接收未知版本。
- 所有时间、时长、置信度、评分和风险扣分都必须是有限数，拒绝 `NaN`、`Infinity` 和 `-Infinity`。
- 相对视频时间统一使用秒。JSON 的整数或浮点数字都是合法数值表示；数字字符串和布尔值不是时间或评分，必须拒绝。
- 所有布尔字段使用严格布尔类型，不接受 `0`、`1` 或字符串。
- ID、名称、标题和模型元数据必须非空，且不得带首尾空格；校验失败时拒绝输入，不静默修改。
- `raw_text`、`clean_text`、`transcript`、引语、推荐理由、字幕原文/修改内容和用户备注保持原样，模型构造及 JSON 往返都不裁剪首尾空格或换行。

## timeline.json

顶层字段：

- `schema_version`、`project_id`；
- `video`：视频路径、有限正时长及可选尺寸；
- `model_info`：转写模型来源和版本；
- `segments`：按开始时间升序排列的转写段。

每个 segment 包含 `id`、`start`、`end`、`speaker`、`raw_text`、`clean_text`、`risk_level`、`risk_reasons` 和允许为空的 `words`。

完整性规则：

- segment ID 唯一，`start >= 0` 且 `end > start`，segment 不得超出 `video.duration`；
- segment 按 `start` 非递减排序；V1 允许最多 `0.05` 秒的相邻识别边界重叠，超过该容差即拒绝；
- word 的有限时间范围必须位于所属 segment 内，且按开始时间非递减排序；
- `confidence` 如存在必须位于 `0—1`；
- `risk_level` 只允许 `red`、`yellow`、`none`。

## current_analysis.json

顶层字段：

- `schema_version`、`project_id`、`analysis_version`；
- `video_duration`：本次分析所对应视频的有限正时长；
- `model_usage`、`topics`、`candidates`。

每个 candidate 包含 `candidate_id`、`topic_id`、`content_type`、`grade`、`score`、`ranges`、`transcript`、`titles`、`quotes`、`recommendation_reason`、`subtitle_reliability`、`visual_dependency`、`risks` 和 `status`。

固定内部值：

- `content_type`：`viewpoint`、`story`、`emotional_resonance`、`qa`、`humor`、`product`、`transition`、`low_value`；
- `subtitle_reliability`：`high`、`medium`、`low`、`unknown`；
- `status`：`pending_review`、`submitted`、`excluded`；
- `grade`：`S`、`A`、`B`、`不推荐`；
- `visual_dependency`：严格布尔值。

中文只供未来 UI 显示映射使用，不写入上述内部分类字段。topic ID 和 candidate ID 分别唯一；candidate 的 `topic_id` 必须存在。`ranges` 的推荐范围必须包含核心范围，扩展范围必须包含推荐范围，且扩展范围不得超过 `video_duration`。

### 评分

`calculate_score()` 固定使用：

```text
base_score = sum(first_six_dimensions) / 90 * 100
final_score = max(0, min(100, base_score - risk_penalty))
```

- 六个维度各自必须为 `0—15` 的有限数，正好六项；
- `risk_penalty` 是有限非负扣分：正值降低最终分，零表示不扣分；
- 内部计算和 JSON 契约保存未舍入数值，保证精确 JSON 往返；
- UI 展示使用 `round_score_for_display()` 按十进制 `ROUND_HALF_UP` 保留 1 位小数；
- 等级始终用未舍入 `score` 判断：`S >= 85`，`75 <= A < 85`，`65 <= B < 75`，`不推荐 < 65`。

## review_current.json

顶层字段为 `schema_version`、`project_id`、`source_analysis_version` 和 `candidates`。候选 ID 必须唯一。

每个审核候选包含 `candidate_id`、`review_status`、`final_start`、`final_end`、`final_title`、`subtitle_edits`、`needs_reanalysis`、`user_notes`、`updated_at`。

- `final_start >= 0`，`final_end > final_start`，且两者必须有限；
- `review_status` 只允许 `unreviewed`、`selected`、`undecided`、`skipped`、`exported`；
- `updated_at` 必须带时区；输入可使用 UTC 或明确偏移，模型统一规范为 UTC，JSON 推荐形如 `2026-07-18T08:30:00Z`；
- 现实时间点使用带时区 datetime；视频相对时间继续使用秒数。
