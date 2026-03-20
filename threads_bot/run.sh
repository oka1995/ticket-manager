#!/bin/bash
# run.sh - 毎朝実行するメインスクリプト
# Usage: bash run.sh [--batch-size N]
# cron例: 0 7 * * * /path/to/threads_bot/run.sh >> /path/to/threads_bot/data/cron.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/data/run.log"
KILL_FLAG="$SCRIPT_DIR/data/kill_switch.flag"

BATCH_SIZE=10

while [[ $# -gt 0 ]]; do
    case $1 in
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================="
log "Threads Bot Daily Run Started"
log "========================================="

# Kill switch確認
if [ -f "$KILL_FLAG" ]; then
    log "ERROR: Kill switch is active. Stopping."
    exit 1
fi

cd "$SCRIPT_DIR"

# Python環境確認
if ! command -v python3 &> /dev/null; then
    log "ERROR: python3 not found. Please install Python 3."
    exit 1
fi

# Step 1: システム状態チェック
log "Step 1/5: Running system check (supervisor)..."
if python3 -m agents.supervisor; then
    log "System check passed."
else
    log "ERROR: System check failed."
    exit 1
fi

# Kill switch再確認
if [ -f "$KILL_FLAG" ]; then
    log "Kill switch activated. Stopping."
    exit 1
fi

# Step 2: 前日データ取得
log "Step 2/5: Fetching metrics from previous posts (fetcher)..."
if python3 -m agents.fetcher; then
    log "Metrics fetched successfully."
else
    log "WARNING: Metrics fetch failed. Continuing..."
fi

# Step 3: 分析・フィードバック生成
log "Step 3/5: Analyzing performance (analyst)..."
if python3 -m agents.analyst; then
    log "Analysis completed."
else
    log "WARNING: Analysis failed. Continuing..."
fi

# Step 4: ネタ補充
log "Step 4/5: Collecting research ideas (researcher)..."
if python3 -m agents.researcher; then
    log "Research completed."
else
    log "WARNING: Research failed. Continuing..."
fi

# Step 5: 本日分の投稿生成
log "Step 5/5: Generating posts (writer, batch_size=$BATCH_SIZE)..."
if python3 -c "from agents.writer import run; run(batch_size=$BATCH_SIZE)"; then
    log "Post generation completed."
else
    log "ERROR: Post generation failed."
    exit 1
fi

log "========================================="
log "Daily run completed successfully."
log "Check data/post_queue.json for queued posts."
log "Run poster.py via cron for scheduled posting."
log "========================================="
