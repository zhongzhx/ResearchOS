# ResearchOS 中文每周文献推送策略

每周文献推送用于帮助课题组跟踪方向，不是自动推荐真实高分论文的保证。

## 来源标记

必须区分真实论文、manual metadata 和 mock placeholder。不要把 mock paper 叫高分论文，不要把 manual metadata 写成已核验全文证据。

如果没有真实来源，必须提示：“当前为流程测试，不代表真实文献推荐”。

## 每篇条目的输出

对每篇论文或参考条目应说明：

- why relevant
- method value
- mechanism value
- protocol candidate
- read first
- ignore reason
- keyword update
- evidence label

## 写入记忆

生成 digest 后可以写入 project memory，但 trust_level 必须保持 raw_extracted，除非用户确认。digest 中的建议只能是 suggestion，不应自动变成 confirmed claim。

## 限制说明

如果来源是 mock、manual placeholder 或本地 KB 不完整，必须在 limitations 中说明。不要承诺覆盖全部最新文献。
