# Agent Memory Lifecycle

## Goal

Keep long-running agent work usable after many tasks. The memory folder stores task records and artifact references. Context shards store compact summaries that can be loaded into a future conversation.

## Storage Contract

Each task should produce:

- Task record Markdown.
- Task record JSON.
- Artifact links with absolute paths and hashes when possible.
- Optional KB event or skill folder link.
- Updated context shard after compaction.

## Folder Roles

- `tasks/`: append-only task records grouped by date.
- `contexts/`: compact context shards designed for future prompt loading.
- `artifacts/`: optional copied artifacts or artifact manifests.
- `knowledge_bases/`: pointers or copied project KB roots.
- `skills/`: pointers to skill folders or generated skill packages.
- `archive/`: compressed or old snapshots.

## Compaction Levels

1. Task record: detailed but still human-readable.
2. Context shard: compressed, file/path-centric summary.
3. Archive: optional long-term storage.

## Sharding

Never keep expanding one context file forever. If `context_0001.md` exceeds the configured byte limit, write `context_0002.md`. Continue this pattern.

If a single task summary cannot fit in one shard, split it into parts:

- `Task X part 1`
- `Task X part 2`

## Source Priority

When resuming:

1. Load latest context shard.
2. Load the relevant project KB.
3. Load specific task records or artifacts only when needed.

## Sensitive Data

Do not include passwords, API keys, tokens, patient identifiers, raw private datasets, or full copyrighted articles in context shards.
