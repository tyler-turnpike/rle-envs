**SEARCH-412 — reindex never converges; make it resumable**

The search reindex in `/app` (`./jobs reindex`, which runs `reindex/worker.py` under
`ops/supervise.py`) stopped working once the corpus grew. A full pass is now longer
than one supervised run, and the job is supposed to pick up where the previous run
stopped. It doesn't: after a few runs `var/index/` is missing documents, has
duplicate rows, and progress jumps around between runs.

What we need:

- Repeated `./jobs reindex` invocations converge to a complete, duplicate-free index:
  exactly one row per live document in `data/docs.db`, same row format as today.
- A stop at any point — including the stop the supervisor sends when a run reaches
  its budget — loses no committed work: everything the checkpoint says is done is in
  the index, and the next run carries on from there.
- Index row contents must not change (the search service verifies `checksum` and
  `minhash`).
- `./jobs test` passes.

Once it's fixed, please leave a complete index in `/app/var/index/` — the search
cutover loads it first thing tomorrow morning.

`./jobs status` shows progress and `./jobs history` lists recent runs.
