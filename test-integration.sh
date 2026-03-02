#!/usr/bin/env bash
# ==============================================================================
# ForgeLine Integration Test Script
# Tests the full pipeline: auth → project → index → learn → policies → analysis
# ==============================================================================

set -euo pipefail

API="http://localhost:8000/api/v1"
PASS=0
FAIL=0
TESTS=()

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log()   { echo -e "${YELLOW}[TEST]${NC} $1"; }
pass()  { echo -e "${GREEN}[PASS]${NC} $1"; PASS=$((PASS+1)); TESTS+=("PASS: $1"); }
fail()  { echo -e "${RED}[FAIL]${NC} $1${2:+ — $2}"; FAIL=$((FAIL+1)); TESTS+=("FAIL: $1${2:+ — $2}"); }

# Helper: HTTP request with optional auth
api() {
  local method="$1" path="$2"
  shift 2
  local args=(-s -w "\n%{http_code}" -X "$method" -H "Content-Type: application/json")
  if [[ -n "${TOKEN:-}" ]]; then
    args+=(-H "Authorization: Bearer $TOKEN")
  fi
  args+=("$@" "${API}${path}")
  curl "${args[@]}"
}

# Parse response — body is all lines except last, status is last line
parse_response() {
  local response="$1"
  BODY=$(echo "$response" | sed '$d')
  STATUS=$(echo "$response" | tail -n1)
}

# ==============================================================================
# 0. Health Check
# ==============================================================================
log "0. Checking if backend is running..."
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
if [[ "$HEALTH" != "200" ]]; then
  echo -e "${RED}Backend is not running at http://localhost:8000${NC}"
  echo "Start it with: cd backend && uvicorn app.main:app --reload"
  exit 1
fi
pass "Backend health check"

# ==============================================================================
# 1. Register a User
# ==============================================================================
log "1. Registering a test user..."
RAND=$RANDOM
EMAIL="test${RAND}@forgeline.dev"
parse_response "$(api POST /auth/register -d "{\"email\": \"$EMAIL\", \"password\": \"TestPass123!\", \"full_name\": \"Test User $RAND\"}")"

if [[ "$STATUS" == "201" ]]; then
  TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['token']['access_token'])" 2>/dev/null || echo "")
  if [[ -n "$TOKEN" ]]; then
    pass "User registration — got JWT token"
  else
    fail "User registration — no token in response"
  fi
else
  fail "User registration" "HTTP $STATUS"
fi

# ==============================================================================
# 2. Login
# ==============================================================================
log "2. Testing login..."
parse_response "$(api POST /auth/login -d "{\"email\": \"$EMAIL\", \"password\": \"TestPass123!\"}")"

if [[ "$STATUS" == "200" ]]; then
  LOGIN_TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['token']['access_token'])" 2>/dev/null || echo "")
  if [[ -n "$LOGIN_TOKEN" ]]; then
    TOKEN="$LOGIN_TOKEN"
    pass "Login — got JWT token"
  else
    fail "Login — no token in response"
  fi
else
  fail "Login" "HTTP $STATUS"
fi

# ==============================================================================
# 3. Get Current User
# ==============================================================================
log "3. Getting current user..."
parse_response "$(api GET /auth/me)"
if [[ "$STATUS" == "200" ]]; then
  USER_EMAIL=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['email'])" 2>/dev/null || echo "")
  if [[ "$USER_EMAIL" == "$EMAIL" ]]; then
    pass "Get current user — email matches"
  else
    fail "Get current user — email mismatch: $USER_EMAIL"
  fi
else
  fail "Get current user" "HTTP $STATUS"
fi

# ==============================================================================
# 4. Create Project
# ==============================================================================
log "4. Creating project pointing to test-project/..."
TEST_PROJECT_PATH="$(cd "$(dirname "$0")/test-project" 2>/dev/null && pwd || echo "/app/test-project")"
parse_response "$(api POST /projects/ -d "{\"name\": \"Integration Test\", \"description\": \"Test project for ForgeLine\", \"root_path\": \"$TEST_PROJECT_PATH\", \"primary_language\": \"typescript\"}")"

if [[ "$STATUS" == "201" ]]; then
  PROJECT_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
  if [[ -n "$PROJECT_ID" ]]; then
    pass "Create project — ID: $PROJECT_ID"
  else
    fail "Create project — no ID in response"
  fi
else
  fail "Create project" "HTTP $STATUS: $BODY"
fi

# ==============================================================================
# 5. List Projects
# ==============================================================================
log "5. Listing projects..."
parse_response "$(api GET /projects/)"
if [[ "$STATUS" == "200" ]]; then
  PROJECT_COUNT=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  if [[ "$PROJECT_COUNT" -ge 1 ]]; then
    pass "List projects — found $PROJECT_COUNT project(s)"
  else
    fail "List projects — empty result"
  fi
else
  fail "List projects" "HTTP $STATUS"
fi

# ==============================================================================
# 6. List Builtin Policy Templates
# ==============================================================================
log "6. Listing builtin policy templates..."
parse_response "$(api GET /policies/builtin)"
if [[ "$STATUS" == "200" ]]; then
  TEMPLATE_COUNT=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  if [[ "$TEMPLATE_COUNT" -ge 1 ]]; then
    pass "Builtin templates — found $TEMPLATE_COUNT template(s)"
  else
    fail "Builtin templates — no templates found (seed may not have run)"
  fi
else
  fail "Builtin templates" "HTTP $STATUS"
fi

# ==============================================================================
# 7. Activate All Builtin Policies
# ==============================================================================
log "7. Activating builtin policies..."
ACTIVATED=0
TEMPLATE_IDS=$(echo "$BODY" | python3 -c "
import sys, json
templates = json.load(sys.stdin)
for t in templates:
    print(t['id'], t['name'], t['category'], t['default_severity'])
" 2>/dev/null || echo "")

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  TMPL_ID=$(echo "$line" | awk '{print $1}')
  TMPL_NAME=$(echo "$line" | awk '{$1=""; print $0}' | sed 's/^ //')

  parse_response "$(api POST "/projects/${PROJECT_ID}/policies" -d "{
    \"policy_template_id\": \"$TMPL_ID\",
    \"name\": \"$TMPL_NAME\",
    \"category\": \"security\",
    \"severity_default\": \"warning\"
  }")"

  if [[ "$STATUS" == "201" ]]; then
    ACTIVATED=$((ACTIVATED+1))
  fi
done <<< "$TEMPLATE_IDS"

if [[ "$ACTIVATED" -ge 1 ]]; then
  pass "Activated $ACTIVATED builtin policies"
else
  fail "Activate builtin policies — none activated"
fi

# ==============================================================================
# 8. List Project Policies
# ==============================================================================
log "8. Listing project policies..."
parse_response "$(api GET "/projects/${PROJECT_ID}/policies")"
if [[ "$STATUS" == "200" ]]; then
  POLICY_COUNT=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  pass "List policies — $POLICY_COUNT policies active"
else
  fail "List policies" "HTTP $STATUS"
fi

# ==============================================================================
# 9. Trigger Full Index
# ==============================================================================
log "9. Triggering full index..."
parse_response "$(api POST "/projects/${PROJECT_ID}/index")"
if [[ "$STATUS" == "202" ]]; then
  JOB_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
  pass "Full index triggered — job ID: $JOB_ID"
else
  # 400 is ok if no root_path, 409 if already running
  fail "Full index trigger" "HTTP $STATUS: $BODY"
fi

# ==============================================================================
# 10. Check Index Status
# ==============================================================================
log "10. Checking index status..."
sleep 2
parse_response "$(api GET "/projects/${PROJECT_ID}/index/status")"
if [[ "$STATUS" == "200" ]]; then
  JOB_STATUS=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "")
  pass "Index status — $JOB_STATUS"
else
  fail "Index status" "HTTP $STATUS"
fi

# ==============================================================================
# 11. Trigger Convention Learning
# ==============================================================================
log "11. Triggering convention learning..."
parse_response "$(api POST "/projects/${PROJECT_ID}/learn")"
if [[ "$STATUS" == "202" ]]; then
  pass "Convention learning triggered"
else
  fail "Convention learning" "HTTP $STATUS"
fi

# ==============================================================================
# 12. Query Patterns
# ==============================================================================
log "12. Querying patterns..."
sleep 2
parse_response "$(api GET "/projects/${PROJECT_ID}/patterns")"
if [[ "$STATUS" == "200" ]]; then
  PATTERN_COUNT=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null || echo "0")
  pass "Patterns query — $PATTERN_COUNT patterns"
else
  fail "Patterns query" "HTTP $STATUS"
fi

# ==============================================================================
# 13. Query Conventions
# ==============================================================================
log "13. Querying conventions..."
parse_response "$(api GET "/projects/${PROJECT_ID}/conventions")"
if [[ "$STATUS" == "200" ]]; then
  CONV_COUNT=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null || echo "0")
  pass "Conventions query — $CONV_COUNT conventions"
else
  fail "Conventions query" "HTTP $STATUS"
fi

# ==============================================================================
# 14. Query Architecture
# ==============================================================================
log "14. Querying architecture..."
parse_response "$(api GET "/projects/${PROJECT_ID}/architecture")"
if [[ "$STATUS" == "200" ]]; then
  pass "Architecture query"
else
  fail "Architecture query" "HTTP $STATUS"
fi

# ==============================================================================
# 15. Create Custom Policy
# ==============================================================================
log "15. Creating custom policy..."
parse_response "$(api POST "/projects/${PROJECT_ID}/policies" -d '{
  "name": "Custom No Console Log",
  "description": "Forbid console.log in production code",
  "category": "security",
  "severity_default": "warning",
  "is_active": true,
  "configuration": {"pattern": "console\\.log", "message": "Remove console.log before committing"}
}')"
if [[ "$STATUS" == "201" ]]; then
  CUSTOM_POLICY_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
  pass "Custom policy created — ID: $CUSTOM_POLICY_ID"
else
  fail "Custom policy creation" "HTTP $STATUS"
fi

# ==============================================================================
# 16. Get Policy Detail
# ==============================================================================
log "16. Getting policy detail..."
if [[ -n "${CUSTOM_POLICY_ID:-}" ]]; then
  parse_response "$(api GET "/projects/${PROJECT_ID}/policies/${CUSTOM_POLICY_ID}")"
  if [[ "$STATUS" == "200" ]]; then
    pass "Policy detail retrieved"
  else
    fail "Policy detail" "HTTP $STATUS"
  fi
else
  fail "Policy detail" "No policy ID"
fi

# ==============================================================================
# 17. Update Policy
# ==============================================================================
log "17. Updating policy..."
if [[ -n "${CUSTOM_POLICY_ID:-}" ]]; then
  parse_response "$(api PUT "/projects/${PROJECT_ID}/policies/${CUSTOM_POLICY_ID}" -d '{"severity_default": "error"}')"
  if [[ "$STATUS" == "200" ]]; then
    pass "Policy updated"
  else
    fail "Policy update" "HTTP $STATUS"
  fi
else
  fail "Policy update" "No policy ID"
fi

# ==============================================================================
# 18. Get Project Detail
# ==============================================================================
log "18. Getting project detail..."
parse_response "$(api GET "/projects/${PROJECT_ID}")"
if [[ "$STATUS" == "200" ]]; then
  pass "Project detail retrieved"
else
  fail "Project detail" "HTTP $STATUS"
fi

# ==============================================================================
# 19. Knowledge Stats
# ==============================================================================
log "19. Querying knowledge stats..."
parse_response "$(api GET "/projects/${PROJECT_ID}/knowledge/stats")"
if [[ "$STATUS" == "200" ]]; then
  pass "Knowledge stats retrieved"
else
  fail "Knowledge stats" "HTTP $STATUS"
fi

# ==============================================================================
# 20. Error Handling Tests
# ==============================================================================
log "20. Testing error handling..."

# 20a. Invalid login
parse_response "$(api POST /auth/login -d '{"email": "nobody@x.com", "password": "wrong"}')"
if [[ "$STATUS" == "401" ]]; then
  pass "Invalid login returns 401"
else
  fail "Invalid login" "Expected 401, got $STATUS"
fi

# 20b. Missing auth header
OLD_TOKEN="$TOKEN"
TOKEN=""
parse_response "$(api GET /projects/)"
if [[ "$STATUS" == "401" || "$STATUS" == "403" ]]; then
  pass "Missing auth returns 401/403"
else
  fail "Missing auth" "Expected 401/403, got $STATUS"
fi
TOKEN="$OLD_TOKEN"

# 20c. Non-existent project
FAKE_ID="00000000-0000-0000-0000-000000000000"
parse_response "$(api GET "/projects/${FAKE_ID}")"
if [[ "$STATUS" == "404" ]]; then
  pass "Non-existent project returns 404"
else
  fail "Non-existent project" "Expected 404, got $STATUS"
fi

# 20d. Non-existent policy
parse_response "$(api GET "/projects/${PROJECT_ID}/policies/${FAKE_ID}")"
if [[ "$STATUS" == "404" ]]; then
  pass "Non-existent policy returns 404"
else
  fail "Non-existent policy" "Expected 404, got $STATUS"
fi

# ==============================================================================
# 21. Cleanup — Delete Policy
# ==============================================================================
log "21. Cleaning up — deleting custom policy..."
if [[ -n "${CUSTOM_POLICY_ID:-}" ]]; then
  parse_response "$(api DELETE "/projects/${PROJECT_ID}/policies/${CUSTOM_POLICY_ID}")"
  if [[ "$STATUS" == "204" ]]; then
    pass "Custom policy deleted"
  else
    fail "Custom policy delete" "HTTP $STATUS"
  fi
fi

# ==============================================================================
# Summary
# ==============================================================================
echo ""
echo "============================================="
echo -e " ${GREEN}PASSED: $PASS${NC}  ${RED}FAILED: $FAIL${NC}  TOTAL: $((PASS+FAIL))"
echo "============================================="
echo ""

for t in "${TESTS[@]}"; do
  if [[ "$t" == PASS:* ]]; then
    echo -e "  ${GREEN}$t${NC}"
  else
    echo -e "  ${RED}$t${NC}"
  fi
done

echo ""
if [[ "$FAIL" -gt 0 ]]; then
  echo -e "${RED}Some tests failed!${NC}"
  exit 1
else
  echo -e "${GREEN}All tests passed!${NC}"
  exit 0
fi
