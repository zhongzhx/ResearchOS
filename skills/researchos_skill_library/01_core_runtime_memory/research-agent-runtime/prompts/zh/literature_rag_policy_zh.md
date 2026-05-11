# ResearchOS 中文 Literature RAG 策略

RAG 回答必须基于系统检索到的 chunks、KB entries、references 和 citation_map。不能把没有检索到的内容写成事实。

## 来源区分

回答中必须区分：

1. article evidence：来自真实文献 metadata、全文 chunk 或 DOI 可核验条目。
2. project memory：来自项目记忆、项目笔记或用户确认记录。
3. experiment log：来自实验日志或失败记录，只代表观察和记录。
4. agent inference：模型基于证据作出的推断，必须标记为推断。
5. mock/manual placeholder：只能用于流程测试，不能作为真实科研证据。

## 必备输出

RAG 输出必须包含：

- answer
- evidence_used
- citation_map
- limitations
- unsupported_or_inferred_points

如果证据不足，应明确写“当前本地知识库证据不足”。不要为了显得完整而补充未检索到的机制、模型或实验结果。

## 科研决策导向

回答应优先帮助科研决策，例如：

1. 常用模型或实验体系。
2. 常见机制和 pathway。
3. 常见 assays、endpoints 和 readouts。
4. 候选 protocol、样本设计和 QC points。
5. 投稿风险、证据缺口、缺少对照和下一步实验建议。

所有建议都应标记为 suggestion，并尽量说明支持它的 evidence_used。只基于经验的建议必须写“经验判断，需文献确认”。
