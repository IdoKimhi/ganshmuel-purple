#!/usr/bin/env bash

set -e

BASE_URL="http://localhost:8088"
PASS=0
FAIL=0

cleanup() {
  echo
  echo "🧹 Cleaning up containers and volumes..."
  docker compose down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

run_test() {
  local name="$1"
  local expected="$2"
  shift 2

  local -a cmd=("$@")

  echo
  echo "▶ Running test: $name"

  response=$(mktemp)
  http_code=$(curl -s -o "$response" -w "%{http_code}" "${cmd[@]}" || echo "000")
  http_code="${http_code: -3}"
  body=$(cat "$response")
  rm -f "$response"

  # strictly compare
  if [[ "$http_code" == "$expected" ]]; then
    echo "✅ [PASS] $name (HTTP $http_code)"
    PASS=$((PASS + 1))
  else
    echo "❌ [FAIL] $name (expected $expected, got $http_code)"
    echo "   Body:"
    echo "   $body"
    FAIL=$((FAIL + 1))
  fi
}

wait_for_db() {
  echo
  echo "⏳ Waiting for Billing DB (via /provider)..."
  for i in {1..20}; do
    code=$(curl -s -o /dev/null -w "%{http_code}" \
      -X POST "$BASE_URL/provider" \
      -H "Content-Type: application/json" \
      -d '{"name": "__db_healthcheck__"}' || echo "000")
    code="${code: -3}"

    # 201 = created (first time), 409 = already exists (subsequent runs)
    if [[ "$code" == "201" || "$code" == "409" ]]; then
      echo "✅ DB is ready (HTTP $code)"
      return 0
    fi

    echo "Attempt $i: $code"
    sleep 2
  done

  echo "❌ DB did not become ready in time"
  return 1
}

echo "🚀 Starting docker compose..."
docker compose up -d

echo
echo "⏳ Waiting for Billing /health..."
for i in {1..20}; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health" || echo "000")
  if [[ "$code" == "200" ]]; then
    echo "✅ Billing is healthy"
    break
  fi
  echo "Attempt $i: $code"
  sleep 2
done

#################################
# 1. Health
#################################
run_test "Health check" 200 GET "$BASE_URL/health"

# Extra: wait for DB to be ready (after app health is OK)
wait_for_db

#################################
# 2. Create Provider
#################################
echo
echo "▶ Create provider"
CREATE=$(curl -s -X POST "$BASE_URL/provider" \
  -H "Content-Type: application/json" \
  -d '{"name": "Gan Shmuel"}' -w " STATUS:%{http_code}")

STATUS=${CREATE##*STATUS:}
BODY=${CREATE% STATUS:*}

if [[ "$STATUS" == "201" ]]; then
  echo "✅ [PASS] Create provider"
  PASS=$((PASS + 1))
else
  echo "❌ [FAIL] Create provider ($STATUS)"
  FAIL=$((FAIL + 1))
fi

# Extract ID cleanly
PROVIDER_ID=$(echo "$BODY" | jq -r '.id')

echo "Provider ID = $PROVIDER_ID"

#################################
# 3. Duplicate Provider
#################################
run_test "Duplicate provider" 409 \
  -X POST "$BASE_URL/provider" \
  -H "Content-Type: application/json" \
  -d '{"name": "Gan Shmuel"}'

#################################
# 4. Update Provider
#################################
run_test "Update provider" 200 \
  -X PUT "$BASE_URL/provider/$PROVIDER_ID" \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name"}'

#################################
# 5. Update Provider (not found)
#################################
run_test "Update provider (not found)" 404 \
  -X PUT "$BASE_URL/provider/999999" \
  -H "Content-Type: application/json" \
  -d '{"name": "X"}'

#################################
# 6. Import rates
#################################
run_test "Import rates" 201 \
  -X POST "$BASE_URL/rates?file=rates.xlsx"

#################################
# 7. Download rates
#################################
run_test "Download rates" 200 \
  -X GET "$BASE_URL/rates"

#################################
# 8. Create truck
#################################
run_test "Create truck" 201 \
  -X POST "$BASE_URL/truck" \
  -H "Content-Type: application/json" \
  -d "{\"id\": \"T-12345\", \"provider\": $PROVIDER_ID}"

#################################
# 9. Duplicate truck
#################################
run_test "Duplicate truck" 409 \
  -X POST "$BASE_URL/truck" \
  -H "Content-Type: application/json" \
  -d "{\"id\": \"T-12345\", \"provider\": $PROVIDER_ID}"

#################################
# 10. Update truck
#################################
run_test "Update truck" 200 \
  -X PUT "$BASE_URL/truck/T-12345" \
  -H "Content-Type: application/json" \
  -d "{\"provider\": $PROVIDER_ID}"

#################################
# 11. Update truck (provider not found)
#################################
run_test "Update truck (provider not found)" 404 \
  -X PUT "$BASE_URL/truck/T-12345" \
  -H "Content-Type: application/json" \
  -d '{"provider": 999999}'

#################################
# Summary
#################################
echo
echo "📊 SUMMARY"
echo "Passed: $PASS"
echo "Failed: $FAIL"
