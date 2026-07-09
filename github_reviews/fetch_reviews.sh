#!/bin/bash
set -euo pipefail

# GitHub API 不走代理，直连避免 proxy 连接被拒
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/fetch_reviews.py" "$@"
