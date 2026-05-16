# ResearchOS 中文记忆策略

ResearchOS 中存在多种记忆，必须保持隔离和作用域清晰。

## 记忆类型

1. system memory：系统能力、长期偏好、通用规则、可复用技能、workflow template、通用科研 agent 约束。
2. project research memory：某个项目的私有数据、实验记录、结论、失败记录、文献笔记、报告、protocol、样本和项目上下文。
3. execution memory：一次任务如何执行、输入输出、错误、复用经验、运行日志和 SkillRun 结果。
4. skill memory：可复用的任务模式、技能模板、输入输出 schema、工具需求和可靠性说明。
5. literature/reference memory：文献 metadata、chunks、摘要、引用信息、KB entry 和 citation_map。

## 隔离规则

1. 不把 project memory 写入 system memory，除非用户明确要求并确认该内容可以脱敏复用。
2. 不把私有实验数据写成通用 skill，除非用户确认已脱敏。
3. 写入 memory 前必须说明 memory scope，例如 system、project、execution、skill 或 literature。
4. 项目级私有数据只应写入对应 project_id 范围内的 project research memory。
5. skill registry 和 skill memory 可以跨项目复用，但不能包含未脱敏的项目私有实验数据。

## 信任等级

低置信度、自动抽取、模型生成或尚未人工确认的记忆必须标记为 raw_extracted。用户确认后可以变为 user_confirmed。PI 确认后可以变为 PI_confirmed。已发表或正式确认的可以是 publication_confirmed。过期、冲突或不再使用的内容应标记为 deprecated。

过期、冲突、弱证据或 deprecated 记忆不能当作事实使用。使用时必须说明其状态。

## 写入前检查

写入任何记忆前，你应确认：

1. memory_scope 是否明确。
2. project_id 是否存在且正确。
3. provenance 是否包含 source_id、source_type 或 skill_run_id。
4. trust_level 是否与证据等级匹配。
5. 是否存在冲突、缺失证据或需要人类确认的结论。
