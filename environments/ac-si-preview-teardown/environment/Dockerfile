FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
RUN apt-get update && apt-get install -y --no-install-recommends tmux asciinema procps jq sqlite3 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app/ /app/
COPY account/state.json /var/tmp/mockcloud/state.json
RUN install -m 0755 /app/tools/cloudctl.py /usr/local/bin/cloudctl \
 && touch /var/tmp/mockcloud/calls.log \
 && chmod -R a+rwX /var/tmp/mockcloud /app \
 && chmod +x /app/teardown.sh /app/tests/test_teardown.sh
