# search-reindex

Builds the search index (`var/index/shard-*.jsonl`) from the document store
(`data/docs.db`).

| path | what |
|------|------|
| `reindex/worker.py` | the reindex job: reads docs in id order, transforms, writes shards, checkpoints |
| `reindex/transform.py` | doc -> index row (row format documented there) |
| `reindex/store.py` | shard writer / reader |
| `reindex/checkpoint.py` | progress checkpoint (`var/checkpoint.json`) |
| `reindex/source.py` | source corpus access (+ fixture generator) |
| `ops/supervise.py` | job runner used for every batch job here: budget, SIGTERM/SIGKILL, run log |
| `ops/limits.json` | per-job budgets and cooldowns |
| `jobs` | entry points: `./jobs reindex`, `./jobs status`, `./jobs history`, `./jobs test`, `./jobs clean` |

A full reindex of the current corpus is several budgets long; the job is designed
to be run repeatedly and pick up where the previous run stopped.
