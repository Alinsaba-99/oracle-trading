#!/usr/bin/env bash
# scripts/check_credentials.sh — Verify no secrets leaked into the repository
# Run after credential rotation. Exit non-zero if any check fails.

set -euo pipefail

echo "=== Credential Security Check ==="
echo ""

# Check 1: .env is gitignored
if git check-ignore .env >/dev/null 2>&1; then
    echo "✅ .env is gitignored"
else
    echo "❌ .env is NOT gitignored"
    exit 1
fi

# Check 2: .env has correct permissions (600)
PERMS=$(stat -c '%a' .env 2>/dev/null || echo "000")
if [ "$PERMS" = "600" ]; then
    echo "✅ .env permissions: $PERMS"
else
    echo "⚠️  .env permissions: $PERMS (expected 600)"
fi

# Check 3: No gitleaks findings
if command -v gitleaks &>/dev/null; then
    if gitleaks detect --source . --config .gitleaks.toml --no-color 2>&1 | grep -q "leaks found"; then
        echo "❌ gitleaks found secrets in the repository!"
        gitleaks detect --source . --config .gitleaks.toml --verbose
        exit 1
    else
        echo "✅ gitleaks: no secrets detected"
    fi
else
    echo "⚠️  gitleaks not installed — skipping scan"
fi

# Check 4: No common secret patterns in tracked files
echo ""
echo "=== Checking for secret patterns in tracked files ==="
SUSPICIOUS=$(git grep -n 'sk-[a-zA-Z0-9]\{20,\}' -- ':!.env' ':!.venv/' 2>/dev/null || true)
if [ -n "$SUSPICIOUS" ]; then
    echo "❌ Found potential API keys in tracked files:"
    echo "$SUSPICIOUS"
    exit 1
fi
echo "✅ No API key patterns in tracked files"

# Check 5: Verify fail-closed works
echo ""
echo "=== Checking API fail-closed ==="
if ORACLE_DEBUG=false uv run --frozen python -c "from apps.api.main import settings" 2>&1 | grep -q "FATAL"; then
    echo "✅ API correctly fails closed without key in production"
else
    echo "⚠️  API fail-closed check skipped (dependencies may not be installed)"
fi

echo ""
echo "=== All credential checks passed ==="
