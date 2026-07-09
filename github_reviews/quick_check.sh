#!/bin/bash
# 快速查看最近几天未回复的 review/comment。
# 用法:
#   ./quick_check.sh        # 最近 7 天未回复
#   ./quick_check.sh 3      # 最近 3 天未回复
#   ./quick_check.sh --date today

set -euo pipefail

# GitHub API 不走代理，直连避免 proxy 连接被拒
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -eq 0 ]]; then
  exec "$SCRIPT_DIR/fetch_reviews.sh" --days 7 --unreplied
elif [[ "$1" =~ ^[0-9]+$ ]]; then
  DAYS="$1"
  shift
  exec "$SCRIPT_DIR/fetch_reviews.sh" --days "$DAYS" --unreplied "$@"
else
  exec "$SCRIPT_DIR/fetch_reviews.sh" "$@"
fi
