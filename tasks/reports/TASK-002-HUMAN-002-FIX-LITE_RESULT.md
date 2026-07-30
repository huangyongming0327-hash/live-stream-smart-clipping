# TASK-002-HUMAN-002-FIX-LITE RESULT｜最小化修复结果发布完整性

## 1. 状态

- FIX-LITE最小修复、定向测试、完整source-only回归和真实本地聚合回归已完成。
- 交付分支：`task/TASK-002-HUMAN-002-result-analysis`。
- 交付目标：现有Draft PR #4；未创建新分支或新PR。
- 本任务只修复结果发布完整性，未执行TASK-003。

## 2. 原阻断问题

原`run_analysis()`依次写入三个本地结果和两个公开结果，之后才复核完成版JSON的SHA-256。若输入在输出阶段变化，函数虽然失败，已经写入的正式结果仍会保留，并可能被后续发布流程误认为成功结果。manifest也缺少同一发布前最终复核。

## 3. 最小修复

`run_analysis()`现在执行以下固定顺序：

1. 分析开始时将完成版JSON和`review-manifest.json`各读取一次到内存，并从字节快照计算初始SHA-256；
2. 后续严格解析、manifest绑定、窗口校验、聚合统计和模型决策只使用这两份内存快照；
3. 三个本地结果和两个可选公开结果全部先写入同一个`.result-analysis-*`临时目录；
4. 临时结果全部生成后，重新计算原JSON和manifest的文件SHA-256；
5. 两个哈希均与开始时一致才使用`os.replace`将临时文件替换到正式目标；
6. 哈希不一致或渲染/生成失败时，由临时目录上下文清理全部暂存文件，原正式结果保持逐字节不变。

本修复没有引入通用事务抽象、备份目录、多层回滚或模块拆分，也没有改动统计和决策函数。

## 4. 新增定向测试

在`experiments/asr/tests/test_result_analysis.py`新增5项：

- 正常暂存与正式发布成功，五个结果均存在且无临时目录残留；
- 完成版JSON在发布前变化时抛出校验错误，五个原正式结果逐字节不变；
- manifest在发布前变化时抛出校验错误，五个原正式结果逐字节不变；
- 结果生成失败时五个原正式结果逐字节不变，且无临时目录残留；
- 暂存发布路径不改变模型胜出统计、精确质量分和生产决策。

定向测试结果：

```text
35 passed, 0 failed
```

## 5. 完整source-only测试

运行统一入口`tools/github/Invoke-SourceOnlyTests.ps1`：

```text
base-schema-media: 110 passed, 1 deselected, 0 failed
asr-experiments: 91 passed, 2 deselected, 1 existing warning, 0 failed
pip-check: No broken requirements found.
SOURCE_ONLY_RESULT.status=passed
```

三个阶段退出码均为0。既有warning为Python 3.12对`audioop`的弃用提示，与本修复无关。

## 6. 真实本地结果不变验证

使用Git忽略的本地完成版JSON和真实manifest，仅将新结果写入`runtime/`下的自动清理临时目录，并与既有本地分析JSON比较：

```text
subsets_unchanged=true
decision_unchanged=true
primary_model=paraformer
fallback_model=sensevoice
decision_confidence=high
all_outputs_exist=true
```

因此正常模型统计、Paraformer主模型、SenseVoice备用模型及高置信决策均未改变。该临时回归目录已清理，没有修改正式本地分析结果或公开报告。

## 7. 安全与范围

- 未修改或删除原始视频、完成版JSON、manifest、审核包或既有正式结果；
- 未修改`tasks/reports/TASK-002-HUMAN-002-R_AUDIT.md`；
- 未将原始JSON、用户文本、逐窗口内容、媒体、模型或`local-data/`加入Git；
- 未下载模型、未安装大型依赖、未调用云端或收费API；
- 未修改`src/liveclip`，未实现TASK-003；
- PR保持Draft，未标记Ready、未启用auto-merge、未合并。

## 8. 修改文件

- `experiments/asr/human_review/result_analysis.py`；
- `experiments/asr/tests/test_result_analysis.py`；
- `tasks/TASK-002-HUMAN-002-FIX-LITE.md`；
- `tasks/reports/TASK-002-HUMAN-002-FIX-LITE_RESULT.md`；
- `docs/CURRENT_STATUS.md`。

## 9. 后续门禁

本修复提交到现有Draft PR #4后，仍需等待最新head的三项GitHub Actions和针对FIX-LITE的独立审核。自动化不得把PR标记Ready或合并；最终操作继续由用户决定。在该门禁完成前不执行TASK-003。
