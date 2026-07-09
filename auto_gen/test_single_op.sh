#!/bin/bash
# 测试单个算子的脚本

# 使用方法: ./test_single_op.sh operator_name
# 例如: ./test_single_op.sh relu

if [ -z "$1" ]; then
    echo "用法: $0 <operator_name>"
    echo "例如: $0 relu"
    exit 1
fi

OPERATOR=$1

# 创建临时算子列表
echo "$OPERATOR" > ops_list_test.txt

echo "=========================================="
echo "测试算子: $OPERATOR"
echo "=========================================="
echo ""

# 运行 orchestrator（ops_list 为位置参数）
python3 orchestrator.py ops_list_test.txt

echo ""
echo "=========================================="
echo "测试完成！"
echo "=========================================="
echo ""
echo "结果保存在带时间戳的目录下（取最新一次）："
LATEST_LOGS=$(ls -dt results/logs_* 2>/dev/null | head -1)
LATEST_SUMMARY=$(ls -t results/summary_*.json 2>/dev/null | head -1)
echo "  日志目录: ${LATEST_LOGS:-results/logs_<timestamp>}"
echo "  摘要: ${LATEST_SUMMARY:-results/summary_<timestamp>.json}"
echo ""
echo "快速查看命令："
echo "  tail -100 ${LATEST_LOGS:-results/logs_<timestamp>}/${OPERATOR}.log"
echo "  tail -20 ${LATEST_LOGS:-results/logs_<timestamp>}/${OPERATOR}.jsonl"
echo "  cat ${LATEST_LOGS:-results/logs_<timestamp>}/${OPERATOR}.timeline.txt"