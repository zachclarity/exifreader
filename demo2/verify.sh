#!/bin/bash
# ── OCR Extract Health Check ──
set -e
EP="http://localhost:4566"
BE="http://localhost:5000"
FN="ocr-extract"
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1
G='\033[0;32m'; R='\033[0;31m'; N='\033[0m'
ok(){ echo -e "  ${G}✓${N} $1"; }
fail(){ echo -e "  ${R}✗${N} $1"; }

echo ""
echo "═══ OCR Extract Health Check ═══"

echo ""; echo "1. LocalStack"
curl -sf "$EP/_localstack/health" > /dev/null 2>&1 && ok "Reachable" || { fail "Not reachable"; exit 1; }

echo ""; echo "2. Lambda Function"
STATE=$(aws --endpoint-url=$EP lambda get-function --function-name $FN \
    --query 'Configuration.State' --output text 2>/dev/null || echo "NOT_FOUND")
[ "$STATE" = "Active" ] && ok "State: Active" || fail "State: $STATE"

echo ""; echo "3. Lambda Layers"
aws --endpoint-url=$EP lambda list-layers \
    --query 'Layers[].{Name:LayerName}' --output table 2>/dev/null || fail "No layers"

echo ""; echo "4. Function Config"
aws --endpoint-url=$EP lambda get-function --function-name $FN \
    --query 'Configuration.{State:State,Runtime:Runtime,Timeout:Timeout,Layers:Layers[].Arn}' \
    --output table 2>/dev/null || fail "Can't get config"

echo ""; echo "5. Backend"
HEALTH=$(curl -sf "$BE/api/health" 2>/dev/null)
[ -n "$HEALTH" ] && ok "Reachable — $HEALTH" || fail "Not reachable"

echo ""; echo "6. Frontend"
curl -sf "http://localhost:8080" > /dev/null 2>&1 && ok "Reachable" || fail "Not reachable"

echo ""; echo "═══════════════════════════════"
