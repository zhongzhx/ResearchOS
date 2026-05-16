# ResearchOS 中文 Claim 策略

ResearchOS 中的 claim 是科研陈述，不是自动事实。模型生成的 claim 默认只能是 draft、weak 或 unsupported。

## Claim 状态规则

1. confirmed claim 只能由人类通过确认入口产生。
2. 如果 LLM 输出 confirmed，后端也必须降级为 draft，除非请求来自 human confirm endpoint。
3. evidence_count=0 的 claim 必须是 unsupported 或 weak，不能是 confirmed。
4. 实验日志只能生成 draft 或 weak claim，不能直接生成机制结论或统计结论。
5. writing assistant 不能把 unsupported statement 写进正文当事实。
6. conflict 或 contradictory evidence 必须保留，不要自动消除、覆盖或隐藏。

## Evidence linkage

每个 claim 应尽量链接 evidence，包括 reference、reference_chunk、source_file、experiment_log、protocol、report、rag_query、project_memory 或 skill_run。缺少 source_id 的 evidence 不得计入 evidence_count。

## 科学语气

草稿 claim 应使用保守语言，例如“可能提示”“需要进一步验证”“当前记录显示”“本地 KB 中有限证据支持”。不要使用“证明”“明确表明”“显著提高”“机制已经确定”等强语气，除非有统计结果和可靠证据支持。

## 不支持陈述

unsupported statement 必须单独列出，不能混入已确认结论。可以作为下一步检索、实验设计或人工复核的对象。
