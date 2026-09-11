#!/usr/bin/env bash
# Verify a deployment of the Pizza API (main.py).
#
# Usage:
#   bash verify-pizza-api.sh                              # the live service
#   bash verify-pizza-api.sh http://127.0.0.1:8000        # a container you just built
#
# Run it after every deployment: the API is the shared dependency of the
# "Question Answering & Chatbots" exercises, and a course starts on time or not
# at all. Exit code 0 means the deployed version is the current one.
set -uo pipefail

BASE="${1:-https://wse-research.org/pizza-api}"
PASS=0
FAIL=0

ok()   { printf '[ok  ] %s\n' "$1"; PASS=$((PASS + 1)); }
bad()  { printf '[FAIL] %s\n' "$1"; FAIL=$((FAIL + 1)); }
body() { curl -sS -m 20 "$@"; }
code() { curl -sS -m 20 -o /dev/null -w '%{http_code}' "$@"; }

printf 'Pizza API at %s\n\n' "$BASE"

# 1 -- the base URL answers with its own documentation
root_code=$(code -L "$BASE/")
if [ "$root_code" = "200" ] && body -L "$BASE/" | grep -qi 'swagger'; then
  ok "the base URL serves the Swagger UI"
else
  bad "the base URL should serve the Swagger UI, got HTTP $root_code (old version deployed?)"
fi

# 2 -- the schema
if body "$BASE/openapi.json" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["info"]["title"] == "Pizza API", d["info"]["title"]
assert set(d["paths"]) == {"/pizza", "/address/validate", "/order", "/order/{order_id}"}, sorted(d["paths"])
' 2>/dev/null; then
  ok "openapi.json lists the four endpoints"
else
  bad "openapi.json is not the schema of this version"
fi

# 3 -- the menu: ids 1-4 are stable, 5-10 were appended
menu=$(body "$BASE/pizza")
if printf '%s' "$menu" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert [p["id"] for p in d] == list(range(1, 11)), [p["id"] for p in d]
assert [p["name"] for p in d[:4]] == ["Margherita", "Pepperoni", "Hawaiian", "Quattro Formaggi"], d[:4]
' 2>/dev/null; then
  ok "the menu has ten pizzas, ids 1-10, the first four unchanged"
else
  bad "the menu is not the extended one: $(printf '%s' "$menu" | head -c 120)"
fi

# 4 -- the delivery area, including the spellings students actually type
validate() {
  code -X POST "$BASE/address/validate" -H 'Content-Type: application/json' \
       -d "{\"street\":\"Rue Michelet\",\"house_number\":\"5\",\"city\":\"$1\"}"
}
for city in "Saint-Étienne" "saint etienne" "SAINT-ETIENNE" "Saint-Priest-en-Jarez" "Lyon" "Leipzig"; do
  c=$(validate "$city")
  if [ "$c" = "200" ]; then ok "delivers to $city"; else bad "should deliver to $city, got HTTP $c"; fi
done
c=$(validate "Paris")
if [ "$c" = "400" ]; then ok "refuses Paris with HTTP 400"; else bad "Paris should be refused with 400, got HTTP $c"; fi

# 5 -- a real order, and reading it back
order=$(body -X POST "$BASE/order" -H 'Content-Type: application/json' \
        -d '{"pizza_id":9,"street":"Rue Michelet","house_number":"5","city":"Saint-Étienne"}')
order_id=$(printf '%s' "$order" | python3 -c 'import json,sys; print(json.load(sys.stdin)["order_id"])' 2>/dev/null)
if [ -n "$order_id" ]; then
  ok "POST /order accepted a Saint-Étienne order -- $order_id"
  if body "$BASE/order/$order_id" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["pizza_id"] == 9, d
assert d["address"]["city"] == "Saint-Étienne", d
' 2>/dev/null; then
    ok "GET /order/{id} returns that order"
  else
    bad "GET /order/$order_id did not return the order"
  fi
else
  bad "POST /order failed: $(printf '%s' "$order" | head -c 160)"
  bad "GET /order/{id} could not be checked -- no order was created"
fi

c=$(code "$BASE/order/does-not-exist")
if [ "$c" = "404" ]; then ok "an unknown order id answers 404"; else bad "unknown order id should answer 404, got HTTP $c"; fi

printf '\n%d checks: %d passed, %d failed.\n' "$((PASS + FAIL))" "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
printf 'The deployed version is current.\n'
