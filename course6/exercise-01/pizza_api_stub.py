"""A local stand-in for the university Pizza API -- so the exercise runs offline.

    python pizza_api_stub.py                 # serves on http://127.0.0.1:8000
    python pizza_api_stub.py --port 8080

Then point the bot at it:

    PIZZA_API_BASE=http://127.0.0.1:8000 python run_dialog.py     (macOS/Linux)
    $env:PIZZA_API_BASE="http://127.0.0.1:8000"; python run_dialog.py   (Windows)

It mirrors the university service endpoint for endpoint, payload for payload
(source: WSE-research/langgraph-examples, common/main.py):

    GET  /                   -> a plain HTML page listing the endpoints (the real
                                service shows its Swagger UI here; the stub has no
                                internet, so it shows a static page instead)
    GET  /pizza              -> [{"id": 1, "name": "Margherita", "available": true}, ...]
    POST /address/validate   -> 200 {"message": "Address is valid", "address": {...}}
                                400 {"detail": "We don't deliver to ..."}
    POST /order              -> 200 {"order_id": "...", "status": "received"}
                                409 {"detail": "... is sold out right now ..."} -- two
                                pizzas per minute, unless X-Accept-Everything: true
    GET  /order/<order_id>   -> 200 {"order_id", "status", "pizza_id", "address"}

Same menu, same ids, same delivery area, same error shapes -- so a run against
the stub and a run against https://wse-research.org/pizza-api behave alike.

Standard library only -- nothing to install. Orders live in memory and are gone
when you stop the server; that is fine, the order id is all the process needs.

Why a stub is not cheating: the component `pizzabot/pizza_api.py` owns the
contract, and a contract can be satisfied by more than one implementation. That
is the same idea that lets an LLM replace a rule in Iteration 2.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import secrets
import time
import unicodedata
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

MENU = [
    {"id": 1, "name": "Margherita"},
    {"id": 2, "name": "Pepperoni"},
    {"id": 3, "name": "Hawaiian"},
    {"id": 4, "name": "Quattro Formaggi"},
    {"id": 5, "name": "Funghi"},
    {"id": 6, "name": "Salami"},
    {"id": 7, "name": "Prosciutto"},
    {"id": 8, "name": "Diavola"},
    {"id": 9, "name": "Vegetariana"},
    {"id": 10, "name": "Calzone"},
]

ORDERS: dict[str, dict] = {}


# Availability, as in the service since version 1.3.0: every minute two pizzas
# are sold out -- "available": false in GET /pizza, the same two for every
# request in that minute, drawn at random for the next -- and POST /order refuses
# them with 409 unless the request carries X-Accept-Everything: true (test
# drivers only). Same draw as `unavailable_ids()` in common/main.py: a pure
# function of a seed and the minute. PIZZA_AVAILABILITY_SEED makes it
# reproducible; without it the seed is random per start of the stub.
UNAVAILABLE_PER_MINUTE = 2
AVAILABILITY_SEED = os.environ.get("PIZZA_AVAILABILITY_SEED") or secrets.token_hex(16)


def current_minute() -> int:
    return int(time.time() // 60)


def unavailable_ids(minute: int) -> set[int]:
    rng = random.Random(f"{AVAILABILITY_SEED}:{minute}")
    return set(rng.sample([pizza["id"] for pizza in MENU], UNAVAILABLE_PER_MINUTE))


def minute_iso(minute: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(minute * 60))

# The delivery area of the real service: the HTWK cities plus the Saint-Étienne
# region. Compared without accents and without case, so "saint-etienne" and
# "Saint-Étienne" are the same place -- exactly as the university service does it.
VALID_CITIES = [
    "Leipzig", "Halle", "Dresden",
    "Saint-Étienne", "Saint-Priest-en-Jarez", "Lyon",
]


def normalize_city(city: str) -> str:
    """Fold a city name for comparison: no accents, no case, no stray spaces."""
    stripped = unicodedata.normalize("NFKD", city or "")
    stripped = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return " ".join(stripped.replace("-", " ").split()).casefold()


VALID_CITIES_NORMALIZED = {normalize_city(city) for city in VALID_CITIES}


# The page served at the stub's own URL. The university service answers there
# with its Swagger UI (https://wse-research.org/pizza-api); the stub cannot -- a
# Swagger UI needs to be fetched from a CDN, and the stub exists for the moment
# when there is no network. So it serves the same information as plain HTML,
# with no external asset at all.
INDEX_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pizza API (local stub)</title>
<style>
 :root {{ color-scheme: light dark;
        --bg: #fff; --fg: #111; --box: #f4f4f6; --note: #fff8e1; --rule: #e6b800; }}
 @media (prefers-color-scheme: dark) {{
   :root {{ --bg: #16161a; --fg: #e8e8ea; --box: #24242b; --note: #2c2618; --rule: #a88a1c; }}
 }}
 body {{ font: 15px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 46rem;
        padding: 0 1rem; background: var(--bg); color: var(--fg); }}
 h1 {{ font-size: 1.4rem; }} h2 {{ font-size: 1.05rem; margin-top: 2rem; }}
 code, pre {{ background: var(--box); color: var(--fg); border-radius: 4px; }}
 code {{ padding: .1rem .3rem; }} pre {{ padding: .6rem .8rem; overflow-x: auto; }}
 .note {{ background: var(--note); border-left: 3px solid var(--rule); padding: .6rem .8rem; }}
 table {{ border-collapse: collapse; }} td, th {{ text-align: left; padding: .2rem .8rem .2rem 0; }}
</style></head><body>
<h1>Pizza API <small>(local stub)</small></h1>
<p class="note">This is the offline stand-in that ships with Exercise 1. It answers exactly like the
university service at <a href="https://wse-research.org/pizza-api">https://wse-research.org/pizza-api</a>
&mdash; same endpoints, same menu and ids, same delivery area, same error messages &mdash; but it runs on your
machine and keeps its orders in memory. The real service shows its interactive Swagger UI at its own URL;
this page is the static equivalent, so that it also works with no network at all.
It is served by <code>pizza_api_stub.py</code> in your terminal &mdash; closing that terminal stops it.</p>

<h2>Endpoints</h2>
<table>
<tr><th><code>GET&nbsp;/pizza</code></th><td>the menu: <code>[{{"id": 1, "name": "Margherita", "available": true}}, ...]</code> &mdash; two pizzas per minute are <code>false</code></td></tr>
<tr><th><code>POST&nbsp;/address/validate</code></th><td>body <code>{{"city", "street", "house_number"}}</code> &rarr; <code>200</code> or <code>400</code> with a <code>detail</code> message</td></tr>
<tr><th><code>POST&nbsp;/order</code></th><td>body <code>{{"pizza_id", "city", "street", "house_number"}}</code> &rarr; <code>{{"order_id", "status": "received"}}</code></td></tr>
<tr><th><code>GET&nbsp;/order/&lt;order_id&gt;</code></th><td>the stored order</td></tr>
</table>

<h2>Menu</h2>
<p>{menu}</p>

<h2>Delivery area</h2>
<p>{cities} &mdash; compared without accents and without case, so <code>saint-etienne</code> and
<code>Saint-&Eacute;tienne</code> are the same place. Anything else is answered with
<code>400 &quot;We don&#39;t deliver to ...&quot;</code>.</p>

<h2>Try it &mdash; macOS, Linux (bash, zsh)</h2>
<pre>curl {base}/pizza
ORDER=$(curl -s -X POST -H 'Content-Type: application/json' \\
     -d '{{"pizza_id": 1, "street": "Rue Michelet", "house_number": "5", "city": "Saint-\u00c9tienne"}}' \\
     {base}/order)
echo "$ORDER"
curl {base}/order/$(echo "$ORDER" | sed 's/.*"order_id":"\\([^"]*\\)".*/\\1/')</pre>

<h2>Try it &mdash; Windows PowerShell</h2>
<pre>Invoke-RestMethod {base}/pizza
$o = Invoke-RestMethod -Method Post -Uri {base}/order -ContentType 'application/json' `
     -Body '{{"pizza_id":1,"street":"Rue Michelet","house_number":"5","city":"Saint-\u00c9tienne"}}'
$o
Invoke-RestMethod {base}/order/$($o.order_id)</pre>

<p>The second call is the round trip the exercise sheet asks you to try: place an order,
then read it back with the id you were given.</p>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "PizzaApiStub/1.0"

    def _send(self, status: int, body: dict | list, headers: dict | None = None) -> None:
        # Same wire format as the FastAPI service: compact, real UTF-8, so even
        # a raw `curl` against the stub and against the university service look
        # alike (no \u00c9 escapes here, real accents there).
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return {}

    def _send_html(self, status: int, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802  (name required by http.server)
        if self.path.rstrip("/") in ("", "/docs"):
            self._send_html(200, INDEX_HTML)
        elif self.path.rstrip("/") == "/pizza":
            minute = current_minute()
            sold_out = unavailable_ids(minute)
            self._send(200, [{**pizza, "available": pizza["id"] not in sold_out} for pizza in MENU],
                       {"X-Availability-Minute": minute_iso(minute),
                        "X-Availability-Valid-Until": minute_iso(minute + 1),
                        "Cache-Control": "no-store"})
        elif self.path.startswith("/order/"):
            order_id = self.path.split("/order/", 1)[1]
            if order_id in ORDERS:
                self._send(200, ORDERS[order_id])
            else:
                self._send(404, {"detail": "Order not found"})
        else:
            self._send(404, {"detail": f"no such endpoint: GET {self.path}"})

    def do_POST(self) -> None:  # noqa: N802
        body = self._read_json()

        if self.path.rstrip("/") == "/address/validate":
            city = str(body.get("city", ""))
            street = str(body.get("street", ""))
            house_number = str(body.get("house_number", ""))
            if normalize_city(city) not in VALID_CITIES_NORMALIZED:
                self._send(400, {"detail": f"We don't deliver to {city}. "
                                           f"Available cities: {', '.join(VALID_CITIES)}"})
            elif len(street) < 2:
                self._send(400, {"detail": "Invalid street name"})
            elif not house_number:
                self._send(400, {"detail": "House number is required"})
            else:
                self._send(200, {"message": "Address is valid",
                                 "address": {"city": city, "street": street,
                                             "house_number": house_number}})

        elif self.path.rstrip("/") == "/order":
            pizza = next((p for p in MENU if p["id"] == body.get("pizza_id")), None)
            if pizza is None:
                self._send(404, {"detail": "Pizza not found"})
                return
            minute = current_minute()
            if (pizza["id"] in unavailable_ids(minute)
                    and (self.headers.get("X-Accept-Everything") or "").strip().lower() != "true"):
                self._send(409, {"detail": f"{pizza['name']} (id {pizza['id']}) is sold out right now, "
                                           f"until {minute_iso(minute + 1)}. GET /pizza lists what is available."})
                return
            city = str(body.get("city", ""))
            if normalize_city(city) not in VALID_CITIES_NORMALIZED:
                self._send(400, {"detail": f"We don't deliver to {city}. "
                                           f"Available cities: {', '.join(VALID_CITIES)}"})
                return
            if not all(body.get(field) for field in ("street", "house_number", "city")):
                self._send(400, {"detail": "street, house_number and city are required"})
                return
            order_id = str(uuid.uuid4())
            ORDERS[order_id] = {
                "order_id": order_id,
                "status": "received",
                "pizza_id": pizza["id"],
                "address": {"city": city, "street": body["street"],
                            "house_number": body["house_number"]},
            }
            self._send(200, {"order_id": order_id, "status": "received"})

        else:
            self._send(404, {"detail": f"no such endpoint: POST {self.path}"})

    def log_message(self, fmt: str, *args) -> None:
        # One readable line per request -- students should see the traffic their
        # process causes.
        print(f"    [pizza-api] {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    global INDEX_HTML
    INDEX_HTML = INDEX_HTML.format(
        menu=", ".join(f"<code>{p['id']}</code> {p['name']}" for p in MENU),
        cities=", ".join(VALID_CITIES),
        base=f"http://{args.host}:{args.port}",
    )

    base = f"http://{args.host}:{args.port}"
    print(f"Pizza API stub is running on {base}")
    print()
    print("  NOW, IN YOUR OTHER TERMINAL, RUN ONE OF THESE:")
    print(f"      export PIZZA_API_BASE={base}      macOS, Linux")
    print(f'      $env:PIZZA_API_BASE="{base}"      PowerShell')
    print(f"      set PIZZA_API_BASE={base}         cmd.exe")
    print()
    print("  Leave THIS window open -- closing it stops the stub.")
    print("  Stop it yourself with Ctrl+C.")
    print(f"  {len(MENU)} pizzas, {len(VALID_CITIES)} delivery cities: open {base}")
    print()
    print("  Every request your bot makes is logged below, one line each:")
    try:
        HTTPServer((args.host, args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nstub stopped")


if __name__ == "__main__":
    main()
