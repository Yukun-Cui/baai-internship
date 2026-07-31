#!/usr/bin/env bash
# ============================================================
# claude-trace: 带轨迹收集的 Claude Code 启动器
# 用法: claude-trace [profile] [claude 参数...]
#   - claude-trace           使用默认 settings.json
#   - claude-trace zy         使用 settings.zy.json  (等价于 cc zy)
#   - claude-trace zy --resume 后面的参数透传给 claude
#
# 特点:
#   - 与 ~/.bashrc 里的 cc 函数一致: 第一个参数是 profile,
#     对应 ~/.claude/settings.<profile>.json, 并注入
#     IS_SANDBOX=1 与 --dangerously-skip-permissions
#   - 代理变量只对 claude 进程生效，不影响其他工具
#   - 自动检测并拉起 mitmdump（如果没在跑）
#   - 任意终端都能直接用
# ============================================================

PROXY_PORT=8181
TRACE_DIR="$HOME/baai-internship/claude_trace"
SESSIONS_DIR="${TRACE_DIR}/sessions"
ADDON_SCRIPT="${TRACE_DIR}/trajectory_writer_cc.py"
CERT_FILE="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
ALLOW_HOSTS='zyapi\.xmsxb\.com'

# ---------- 解析 profile 参数（与 cc 函数一致）----------
# 第一个参数作为 profile: cc zy -> settings.zy.json
# 无参数时使用默认 settings.json
PROFILE=""
if [ -n "$1" ]; then
    PROFILE="$1."
fi
SETTINGS_FILE="$HOME/.claude/settings.${PROFILE}json"
CLAUDE_ARGS=("${@:2}")

if [ ! -f "$SETTINGS_FILE" ]; then
    echo "❌ 找不到配置文件: $SETTINGS_FILE"
    echo "   可用的 profile:"
    for f in "$HOME"/.claude/settings.*.json; do
        [ -e "$f" ] || continue
        name="${f##*/settings.}"
        echo "     ${name%.json}"
    done
    exit 1
fi

# ---------- 确保 sessions 目录存在 ----------
mkdir -p "$SESSIONS_DIR"

# ---------- 引用计数文件 ----------
REFCOUNT_FILE="${TRACE_DIR}/.mitm_refcount"

# ---------- 启动 mitmdump ----------
STARTED_MITM=false
if ! pgrep -f "mitmdump.*trajectory_writer_cc" >/dev/null 2>&1; then
    echo "🔄 启动 mitmdump..."
    export MITMPROXY_OUTDIR="$SESSIONS_DIR"
    mitmdump -s "$ADDON_SCRIPT" -p "$PROXY_PORT" --allow-hosts "$ALLOW_HOSTS" \
        > "$TRACE_DIR/mitmdump.log" 2>&1 &
    MITM_PID=$!
    sleep 1
    if kill -0 "$MITM_PID" 2>/dev/null; then
        echo "✅ mitmdump 已启动 (PID: $MITM_PID)"
        STARTED_MITM=true
        echo 0 > "$REFCOUNT_FILE"
    else
        echo "❌ mitmdump 启动失败，查看日志: $TRACE_DIR/mitmdump.log"
        exit 1
    fi
else
    MITM_PID=$(pgrep -f "mitmdump.*trajectory_writer_cc" | head -1)
fi

# 增加引用计数
COUNT=$(cat "$REFCOUNT_FILE" 2>/dev/null || echo 0)
echo $((COUNT + 1)) > "$REFCOUNT_FILE"

# ---------- 退出时清理 ----------
cleanup() {
    # 减少引用计数
    COUNT=$(cat "$REFCOUNT_FILE" 2>/dev/null || echo 1)
    echo $((COUNT - 1)) > "$REFCOUNT_FILE"

    # 最后一个退出时杀掉 mitmdump
    if [[ $((COUNT - 1)) -le 0 ]] && kill -0 "$MITM_PID" 2>/dev/null; then
        kill "$MITM_PID" 2>/dev/null
        wait "$MITM_PID" 2>/dev/null
        rm -f "$REFCOUNT_FILE"
        echo "🛑 mitmdump 已停止"
    fi
}
trap cleanup EXIT

# ---------- 仅对 claude 注入代理变量 ----------
# 与 cc 函数保持一致: IS_SANDBOX=1 + --settings + --dangerously-skip-permissions
IS_SANDBOX=1 \
HTTPS_PROXY="http://127.0.0.1:${PROXY_PORT}" \
HTTP_PROXY="http://127.0.0.1:${PROXY_PORT}" \
NODE_EXTRA_CA_CERTS="$CERT_FILE" \
claude --settings "$SETTINGS_FILE" --dangerously-skip-permissions "${CLAUDE_ARGS[@]}"
