#!/bin/bash
cd /var/www/ah-eisa.com || exit 1
git config --global --add safe.directory /var/www/ah-eisa.com
git fetch origin main -q
LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse origin/main 2>/dev/null)

if [ "$LOCAL" != "$REMOTE" ] && [ -n "$REMOTE" ]; then
    echo "$(date): New article or commit detected! Pulling and compiling..." >> /var/log/insights_sync.log
    git reset --hard origin/main >> /var/log/insights_sync.log 2>&1
    python3 build_insights.py >> /var/log/insights_sync.log 2>&1
    chown -R www-data:www-data /var/www/ah-eisa.com
    echo "$(date): Build completed successfully!" >> /var/log/insights_sync.log
fi
