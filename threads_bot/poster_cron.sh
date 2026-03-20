#!/bin/bash
# poster_cron.sh - 投稿実行用cronスクリプト
# cronに登録して各タイムスロットに実行する
#
# cron設定例（crontab -e で追加）:
# 0  8  * * * /path/to/threads_bot/poster_cron.sh
# 0 10  * * * /path/to/threads_bot/poster_cron.sh
# 0 12  * * * /path/to/threads_bot/poster_cron.sh
# 0 14  * * * /path/to/threads_bot/poster_cron.sh
# 30 16 * * * /path/to/threads_bot/poster_cron.sh
# 0 19  * * * /path/to/threads_bot/poster_cron.sh
# 30 20 * * * /path/to/threads_bot/poster_cron.sh
# 0 22  * * * /path/to/threads_bot/poster_cron.sh
# 30 23 * * * /path/to/threads_bot/poster_cron.sh
# 0  1  * * * /path/to/threads_bot/poster_cron.sh
#
# フェッチ用cron:
# 0  2  * * * cd /path/to/threads_bot && python3 -m agents.fetcher >> data/cron.log 2>&1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/data/cron.log"
KILL_FLAG="$SCRIPT_DIR/data/kill_switch.flag"

if [ -f "$KILL_FLAG" ]; then
    exit 0
fi

cd "$SCRIPT_DIR"
python3 -m agents.poster >> "$LOG_FILE" 2>&1
