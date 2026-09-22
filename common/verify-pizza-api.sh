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
assert set(d["paths"]) == {"/pizza", "/city", "/address/validate", "/order", "/order/{order_id}"}, sorted(d["paths"])
' 2>/dev/null; then
  ok "openapi.json lists the five endpoints"
else
  bad "openapi.json is not the schema of this version"
fi

# 3 -- the menu: ids 1-10 are stable, 11-20 were appended on 2026-09-18,
#      21-22 (the declared vegetarian and vegan pizza) on 2026-09-20
menu=$(body "$BASE/pizza")
if printf '%s' "$menu" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert [p["id"] for p in d] == list(range(1, 23)), [p["id"] for p in d]
assert [p["name"] for p in d[:4]] == ["Margherita", "Pepperoni", "Hawaiian", "Quattro Formaggi"], d[:4]
assert d[9]["name"] == "Calzone", d[9]
assert d[19]["name"] == "Boscaiola", d[19]
assert [p["name"] for p in d[20:]] == ["Ortolana", "Verdure"], d[20:]
' 2>/dev/null; then
  ok "the menu has twenty-two pizzas, ids 1-22, the first ten unchanged"
else
  bad "the menu is not the extended one: $(printf '%s' "$menu" | head -c 120)"
fi

# 3a -- availability: every minute two pizzas are sold out ("available": false),
#       the same two for every request in that minute. Two requests are compared
#       only when both headers name the same minute; one that straddles a minute
#       boundary is simply asked again.
snapshot() {
  curl -sS -m 20 -D - "$BASE/pizza" | tr -d '\r' | python3 -c '
import json, sys
head, _, body = sys.stdin.read().partition("\n\n")
minute = [l.split(":", 1)[1].strip() for l in head.splitlines() if l.lower().startswith("x-availability-minute:")]
off = sorted(p["name"] for p in json.loads(body) if p.get("available") is False)
print(minute[0] if minute else "-", ",".join(off))
' 2>/dev/null
}
for attempt in 1 2 3; do
  first=$(snapshot); second=$(snapshot)
  [ "${first%% *}" = "${second%% *}" ] && break
done
off_count=$(printf '%s' "${first#* }" | tr ',' '\n' | grep -c .)
if [ "${first%% *}" != "-" ] && [ -n "$first" ] && [ "$off_count" = "2" ]; then
  ok "two pizzas are unavailable in minute ${first%% *}: ${first#* }"
else
  bad "GET /pizza should mark exactly two pizzas \"available\": false and send X-Availability-Minute, got '${first:-nothing}'"
fi
if [ -n "$first" ] && [ "$first" = "$second" ]; then
  ok "two requests in the same minute see the same two pizzas"
else
  bad "two requests in the same minute disagree: '$first' vs '$second'"
fi

# 3b -- the delivery area is browsable: every commune of France, plus three German cities
cities=$(body "$BASE/city?q=saint-eti&limit=5")
if printf '%s' "$cities" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d, "no city matched saint-eti"
assert d[0]["name"] == "Saint-\u00c9tienne", d[0]
assert d[0]["country"] == "FR" and d[0]["population"] > 100000, d[0]
assert len(d) <= 5, len(d)
' 2>/dev/null; then
  ok "GET /city?q=saint-eti finds Saint-Etienne"
else
  bad "GET /city does not answer with the delivery area: $(printf '%s' "$cities" | head -c 160)"
fi

total=$(curl -sS -m 20 -D - -o /dev/null "$BASE/city?limit=1" | tr -d '\r' | awk 'tolower($1) == "x-total-count:" {print $2}')
if [ -n "$total" ] && [ "$total" -gt 30000 ]; then
  ok "the delivery area has $total cities (X-Total-Count)"
else
  bad "X-Total-Count should report more than 30000 cities, got '${total:-none}' (old version deployed?)"
fi

if body "$BASE/city?limit=3" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert len(d) == 3, len(d)
assert [c["name"] for c in d][0] == "Paris", d
' 2>/dev/null; then
  ok "GET /city returns the largest cities first"
else
  bad "GET /city?limit=3 did not answer with the three largest cities"
fi

# 4 -- the delivery area, including the spellings students actually type
validate() {
  code -X POST "$BASE/address/validate" -H 'Content-Type: application/json' \
       -d "{\"street\":\"Rue Michelet\",\"house_number\":\"5\",\"city\":\"$1\"}"
}
for city in "Saint-Étienne" "saint etienne" "SAINT-ETIENNE" "Saint-Priest-en-Jarez" "Lyon" "Leipzig" "Paris" "Roanne"; do
  c=$(validate "$city")
  if [ "$c" = "200" ]; then ok "delivers to $city"; else bad "should deliver to $city, got HTTP $c"; fi
done
# Since 2026-09-18 the area is all of France, so the refusal case has to be a
# city outside it. Barcelona is not a commune and not one of the three German
# cities -- and the exercises use it as their "nothing recognised" example.
c=$(validate "Barcelona")
if [ "$c" = "400" ]; then ok "refuses Barcelona with HTTP 400"; else bad "Barcelona should be refused with 400, got HTTP $c"; fi

# 5 -- a real order, and reading it back. Pizza 9 may be sold out in this very
#      minute, so this driver sends X-Accept-Everything: true -- the header a test
#      driver uses to make its result independent of the minute it runs in.
order=$(body -X POST "$BASE/order" -H 'Content-Type: application/json' -H 'X-Accept-Everything: true' \
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

# 5b -- a pizza sold out in this minute: 409 without the header, 200 with it.
#       The check is trusted only if the minute did not change around the order.
sold_out_id() {
  curl -sS -m 20 -D - "$BASE/pizza" | tr -d '\r' | python3 -c '
import json, sys
head, _, body = sys.stdin.read().partition("\n\n")
minute = [l.split(":", 1)[1].strip() for l in head.splitlines() if l.lower().startswith("x-availability-minute:")]
off = [p["id"] for p in json.loads(body) if p.get("available") is False]
print(minute[0] if minute else "-", off[0] if off else "-")
' 2>/dev/null
}
order_code() {
  code -X POST "$BASE/order" -H 'Content-Type: application/json' "$@"
}
for attempt in 1 2 3; do
  before=$(sold_out_id); id=${before#* }
  refused=$(order_code -d "{\"pizza_id\":$id,\"street\":\"Rue Michelet\",\"house_number\":\"5\",\"city\":\"Lyon\"}")
  accepted=$(order_code -H 'X-Accept-Everything: true' -d "{\"pizza_id\":$id,\"street\":\"Rue Michelet\",\"house_number\":\"5\",\"city\":\"Lyon\"}")
  after=$(sold_out_id)
  [ "${before%% *}" = "${after%% *}" ] && break
done
if [ "$refused" = "409" ]; then ok "an order for sold-out pizza $id answers 409"; else bad "an order for sold-out pizza '$id' should answer 409, got HTTP $refused"; fi
if [ "$accepted" = "200" ]; then ok "with X-Accept-Everything: true the same order is accepted"; else bad "with X-Accept-Everything: true the order should be accepted, got HTTP $accepted"; fi

c=$(code "$BASE/order/does-not-exist")
if [ "$c" = "404" ]; then ok "an unknown order id answers 404"; else bad "unknown order id should answer 404, got HTTP $c"; fi

printf '\n%d checks: %d passed, %d failed.\n' "$((PASS + FAIL))" "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
printf 'The deployed version is current.\n'
