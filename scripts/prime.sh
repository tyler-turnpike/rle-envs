#!/bin/bash
# Prime the local build cache for an environment's Dockerfile. Only needed for
# layers that download packages. The container proxy rejects plain HTTP, so apt
# goes through a local HTTP->HTTPS shim on 127.0.0.1:3128. Proxy build args are
# not part of the cache key, so Harbor's own unchanged build reuses these layers.
set -eu
id=$1
pgrep -f "aptshim" >/dev/null || (cd /tmp && nohup python3 "$(dirname "$0")/aptshim.py" >/dev/null 2>&1 &)
sleep 1
docker build --network host --build-arg http_proxy=http://127.0.0.1:3128 -t "prime-$id" "$(cd "$(dirname "$0")/.." && pwd)/environments/$id/environment"
