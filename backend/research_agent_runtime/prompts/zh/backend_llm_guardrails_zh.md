# ResearchOS 中文后端 LLM 强约束说明

Prompt 不是安全边界。即使模型违反 prompt，后端也必须执行以下强约束。

1. confirmed claim 必须降级为 draft，除非请求来自 human confirm endpoint。
2. mock reference 不能进入 real evidence pool。
3. project memory 不能进入 system memory，除非用户明确要求并确认脱敏。
4. unsupported statement 不能进入正文 claim。
5. citation_map 必须由系统生成，模型不能自行生成或重排。
6. 缺失 source_id 的 evidence 不得计入 evidence_count。
7. 所有 memory 写入必须有 scope。
8. 所有 report 必须有 limitations。
9. 项目级私有数据不能写入全局 reusable skill。
10. 原始数据不得被自动删除、覆盖或静默替换。
11. workflow step 必须保留 logs。
12. conflict 必须保留，不得自动消除。

模型应遵守这些规则；后端应独立校验这些规则。Prompt 只能降低错误概率，不能替代 schema validation、status downgrade、scope check、evidence counting、citation map generation 和 human confirmation endpoint。
