# ResearchOS 中文实验日志策略

实验日志是观察记录，不等于统计结果，不等于机制结论，也不等于最终项目结论。

## 字段提取

从实验日志提取字段时必须保守。优先使用明确字段标签：

- Date
- Experiment
- Operator
- Objective
- Sample
- Conditions
- Observations
- Abnormal
- Failure reason
- Decision
- Next step

缺失字段进入 missing_fields。含义不清、跨字段、无法判断归属的内容进入 ambiguous_fields。不要让 Date 吞掉整篇日志，不要让 Experiment 吞掉 Operator、Objective 或 Sample。

## 异常和失败记录

异常事件应进入 abnormal_events 或 failure_log。失败原因如果只是猜测，应标记为 suspected 或 draft，不要写成确定原因。

## 下一步建议

下一步建议应偏向：

1. 补充阴性、阳性、vehicle、blank 或 batch controls。
2. 重复实验。
3. 补全样本信息、批次、浓度、溶剂和处理时间。
4. 保存原始文件和仪器导出。
5. 明确是否需要重新做 protocol 或试剂准备记录。

## 禁止过度解释

不允许把“细胞看起来状态差”写成“药物有毒性结论”。可以写“观察到细胞状态变差，需用活性/毒性 assay 和重复实验确认”。

实验日志产生的 claim 默认只能是 draft 或 weak，并且需要人类确认。
