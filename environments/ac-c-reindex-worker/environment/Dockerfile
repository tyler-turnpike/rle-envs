FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
RUN apt-get update && apt-get install -y --no-install-recommends tmux asciinema procps jq sqlite3 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app/ /app/
RUN chmod +x /app/jobs /app/ops/supervise.py \
 && python3 -m reindex.source data/docs.db \
 && mkdir -p var \
 && python3 -m unittest tests.test_reindex.TransformTest tests.test_reindex.StoreTest
