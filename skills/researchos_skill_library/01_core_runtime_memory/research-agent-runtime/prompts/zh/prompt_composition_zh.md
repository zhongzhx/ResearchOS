# ResearchOS 中文 Prompt 组合策略

中文 prompt 由基础身份、通用可靠性策略和任务专用策略组合而成。默认组合规则如下：

## 通用组合

base_identity_zh + evidence_policy_zh + citation_policy_zh + task_specific_policy

## 任务组合

RAG：
base_identity_zh + evidence_policy_zh + citation_policy_zh + literature_rag_policy_zh

Writing：
base_identity_zh + evidence_policy_zh + citation_policy_zh + claim_policy_zh + writing_assistant_policy_zh

Experiment log：
base_identity_zh + memory_policy_zh + claim_policy_zh + experiment_log_policy_zh

Protocol：
base_identity_zh + evidence_policy_zh + protocol_extraction_policy_zh

Weekly digest：
base_identity_zh + evidence_policy_zh + citation_policy_zh + weekly_digest_policy_zh

Natural language task：
base_identity_zh + natural_language_task_policy_zh

Project retrospective：
base_identity_zh + evidence_policy_zh + memory_policy_zh + claim_policy_zh + project_retrospective_policy_zh

Peer review：
base_identity_zh + evidence_policy_zh + citation_policy_zh + claim_policy_zh + peer_review_policy_zh

Backend guardrails 可附加在需要调用 LLM 的后端任务中，用于提醒模型后端仍会执行强校验。

## Fallback

如果中文 prompt 文件缺失，系统可以回退到现有英文 ResearchOS system prompt。回退必须被记录，便于排查 prompt 版本。
