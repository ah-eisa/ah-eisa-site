#!/usr/bin/env bash
# ==============================================================================
# Hardened Automatic Insights Publishing Pipeline
# ah-eisa.com ? Ahmed Eisa Investment Portfolio Management
# ==============================================================================

LOG_FILE="/var/log/insights_sync.log"
LOCK_FILE="/tmp/insights_sync.lock"
WEB_ROOT="/var/www/ah-eisa.com"
BACKUP_DIR="${WEB_ROOT}/.deploy_backup"
COMMIT_RECORD="${WEB_ROOT}/.last_successful_commit"

# 1. Prevent overlapping cron runs using file locking
exec 200>"${LOCK_FILE}"
if ! flock -n 200; then
    # Another instance is already running; exit silently
    exit 0
fi

cd "${WEB_ROOT}" || exit 1
git config --global --add safe.directory "${WEB_ROOT}"

# 2. Check for new commits on GitHub
if ! git fetch origin main -q 2>> "${LOG_FILE}"; then
    echo "$(date): git fetch failed (network or remote issue). Will retry next minute." >> "${LOG_FILE}"
    exit 1
fi

REMOTE_COMMIT=$(git rev-parse origin/main 2>/dev/null)
LAST_SUCCESS=$(cat "${COMMIT_RECORD}" 2>/dev/null || echo "")

# If repository is already up to date with last verified build, nothing to do
if [ -n "$REMOTE_COMMIT" ] && [ "$REMOTE_COMMIT" = "$LAST_SUCCESS" ]; then
    exit 0
fi

echo "$(date): New commit detected ($REMOTE_COMMIT). Initiating hardened deployment..." >> "${LOG_FILE}"

# 3. Create a snapshot buffer for atomic rollback
mkdir -p "${BACKUP_DIR}"
rm -rf "${BACKUP_DIR:?}"/*
if [ -d "insights" ]; then cp -r insights "${BACKUP_DIR}/" 2>/dev/null || true; fi
if [ -d "content" ]; then cp -r content "${BACKUP_DIR}/" 2>/dev/null || true; fi
if [ -f "insights.html" ]; then cp insights.html "${BACKUP_DIR}/" 2>/dev/null || true; fi
if [ -f "blog.html" ]; then cp blog.html "${BACKUP_DIR}/" 2>/dev/null || true; fi
if [ -f "index.html" ]; then cp index.html "${BACKUP_DIR}/" 2>/dev/null || true; fi

# Rollback helper function
rollback() {
    echo "$(date): Deployment failed! Rolling back to previous working snapshot..." >> "${LOG_FILE}"
    if [ -d "${BACKUP_DIR}" ]; then
        cp -r "${BACKUP_DIR}"/* "${WEB_ROOT}/" 2>/dev/null || true
        chown -R www-data:www-data "${WEB_ROOT}"
        echo "$(date): Rollback completed successfully. Live site remains operational." >> "${LOG_FILE}"
    else
        echo "$(date): Warning: No snapshot directory available to restore." >> "${LOG_FILE}"
    fi
    # Intentionally do NOT update .last_successful_commit so it retries automatically next run
    exit 1
}

# 4. Pull latest code from origin/main
if ! git reset --hard origin/main >> "${LOG_FILE}" 2>&1; then
    echo "$(date): git reset failed." >> "${LOG_FILE}"
    rollback
fi

# 5. Build static articles and manifest
if ! python3 build_insights.py >> "${LOG_FILE}" 2>&1; then
    echo "$(date): python3 build_insights.py failed." >> "${LOG_FILE}"
    rollback
fi

# 6. Post-deployment Health Check
HEALTH_OK=true

# Check 1: insights.html exists and is larger than 2KB
if [ ! -f "insights.html" ] || [ "$(wc -c < "insights.html")" -lt 2000 ]; then
    echo "$(date): Health Check Failed: insights.html is missing or smaller than 2KB." >> "${LOG_FILE}"
    HEALTH_OK=false
fi

# Check 2: index.html exists and is larger than 2KB
if [ ! -f "index.html" ] || [ "$(wc -c < "index.html")" -lt 2000 ]; then
    echo "$(date): Health Check Failed: index.html is missing or corrupted." >> "${LOG_FILE}"
    HEALTH_OK=false
fi

# Check 3: content/insights.json exists, is valid JSON, and has at least 1 article
if [ ! -f "content/insights.json" ] || ! python3 -c "import json; data=json.load(open('content/insights.json')); assert isinstance(data, list) and len(data) > 0" 2>> "${LOG_FILE}"; then
    echo "$(date): Health Check Failed: content/insights.json is missing, empty, or invalid JSON." >> "${LOG_FILE}"
    HEALTH_OK=false
fi

# Check 4: generated article files exist under insights/
ARTICLE_COUNT=$(find insights/ -name "*.html" | wc -l)
if [ "$ARTICLE_COUNT" -lt 1 ]; then
    echo "$(date): Health Check Failed: No HTML articles found in insights/ directory." >> "${LOG_FILE}"
    HEALTH_OK=false
fi

# Check 5: Ensure root-relative paths are maintained
if grep -q 'href="../style.css"' insights.html 2>/dev/null; then
    echo "$(date): Health Check Failed: insights.html contains legacy relative CSS paths." >> "${LOG_FILE}"
    HEALTH_OK=false
fi

# If any health check failed, trigger rollback
if [ "$HEALTH_OK" = false ]; then
    rollback
fi

# 7. Deployment Validated: Record successful commit and set permissions
echo "$REMOTE_COMMIT" > "${COMMIT_RECORD}"
chown -R www-data:www-data "${WEB_ROOT}"
# Clean up temporary backup to save disk space
rm -rf "${BACKUP_DIR:?}"/*

echo "$(date): Commit ${REMOTE_COMMIT} passed all health checks and is successfully live!" >> "${LOG_FILE}"
exit 0
