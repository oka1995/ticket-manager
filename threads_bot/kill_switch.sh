#!/bin/bash
# kill_switch.sh - 緊急停止スイッチ
# 実行すると data/kill_switch.flag を生成して全エージェントを停止
# 解除するには: bash kill_switch.sh --off

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KILL_FLAG="$SCRIPT_DIR/data/kill_switch.flag"

if [[ "$1" == "--off" ]]; then
    if [ -f "$KILL_FLAG" ]; then
        rm "$KILL_FLAG"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Kill switch DEACTIVATED. System resumed."
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Kill switch was not active."
    fi
else
    touch "$KILL_FLAG"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Kill switch ACTIVATED. All agents will stop."
    echo "To deactivate: bash kill_switch.sh --off"
fi
