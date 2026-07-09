#!/bin/bash
# Triton 算子合规性检查 - 快捷启动脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 默认参数
CONFIG="${SCRIPT_DIR}/config.yaml"
VERBOSE=""
EXTRA_ARGS=""

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -c CONFIG    Config file path (default: config.yaml)"
    echo "  -o OP...     Only check specific operator(s)"
    echo "  --vendor V   Only check specific vendor(s)"
    echo "  --limit N    Limit number of operators"
    echo "  -v           Verbose/debug logging"
    echo "  -h           Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                              # Check all operators"
    echo "  $0 -o add abs                   # Check only add and abs"
    echo "  $0 --vendor metax               # Check only metax vendor"
    echo "  $0 --limit 5 -v                 # Check first 5 operators with debug"
    echo "  $0 -o add --vendor nvidia -v    # Check nvidia/add with debug"
}

# Parse args and forward to Python
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        *) EXTRA_ARGS="$EXTRA_ARGS $1" ;;
    esac
    shift
done

cd "$SCRIPT_DIR"
python3 checker.py $EXTRA_ARGS
