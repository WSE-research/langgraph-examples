"""A local stand-in for the university Pizza API -- so the exercise runs offline.

    python pizza_api_stub.py                 # serves on http://127.0.0.1:8000
    python pizza_api_stub.py --port 8080

Then point the bot at it:

    PIZZA_API_BASE=http://127.0.0.1:8000 python run_dialog.py     (macOS/Linux)
    $env:PIZZA_API_BASE="http://127.0.0.1:8000"; python run_dialog.py   (Windows)

It mirrors version v2 of the university service -- the version this exercise
uses, https://wse-research.org/pizza-api/v2 -- endpoint for endpoint, payload for
payload (source: WSE-research/langgraph-examples, common/main.py):

    GET  /                   -> a plain HTML page listing the endpoints (the real
                                service shows its Swagger UI here; the stub has no
                                internet, so it shows a static page instead)
    GET  /pizza              -> [{"id": 1, "name": "Margherita"}, ...]   (22 pizzas)
    POST /address/validate   -> 200 {"message": "Address is valid", "address": {...}}
                                400 {"detail": "We don't deliver to ..."}
                                422 a missing field, as the service's FastAPI says it
    POST /order              -> 200 {"order_id": "...", "status": "received"}
    GET  /order/<order_id>   -> 200 {"order_id", "status", "pizza_id", "address"}

Same menu, same ids, same delivery area, same error messages -- so a run against
the stub and a run against https://wse-research.org/pizza-api/v2 behave alike.
The delivery area is the data file the service uses, `data/cities.tsv.gz`:
every commune of France, every town and village of Greece, plus Leipzig, Halle
and Dresden, compared without accents and case, a Greek place also under its
other spellings; without the file the stub falls back to the nine cities of the
course examples and says so. The one thing of v2 the stub does not serve is
GET /city -- this exercise never calls it; it arrives with Exercise 3. Every
pizza can always be ordered, in v2 as here: pizzas that sell out arrive with
version v5 of the service.

Standard library only -- nothing to install. Orders live in memory and are gone
when you stop the server; that is fine, the order id is all the process needs.

Why a stub is not cheating: the component `pizzabot/pizza_api.py` owns the
contract, and a contract can be satisfied by more than one implementation. That
is the same idea that lets an LLM replace a rule in Iteration 2.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import unicodedata
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

from pizzabot import log          # the log layer: no script here calls print()

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
    # Ids 11-20 were appended to the service on 2026-09-18, so they are here
    # too: the stub mirrors the menu, and a student who compares GET /pizza
    # against both must see the same list. Nothing in this iteration uses them.
    {"id": 11, "name": "Capricciosa"},
    {"id": 12, "name": "Marinara"},
    {"id": 13, "name": "Siciliana"},
    {"id": 14, "name": "Tonno"},
    {"id": 15, "name": "Frutti di Mare"},
    {"id": 16, "name": "Quattro Stagioni"},
    {"id": 17, "name": "Bufala"},
    {"id": 18, "name": "Tartufo"},
    {"id": 19, "name": "Rucola"},
    {"id": 20, "name": "Boscaiola"},
    # Ids 21-22 followed on 2026-09-20: a declared vegetarian and a declared
    # vegan pizza, added for the Iteration 4 knowledge graph.
    {"id": 21, "name": "Ortolana"},
    {"id": 22, "name": "Verdure"},
]

ORDERS: dict[str, dict] = {}


# The delivery area: the cities of the course examples -- the HTWK cities, the
# Saint-Étienne region and the Athens region. Compared without accents and
# without case, so "saint-etienne" and "Saint-Étienne" are the same place, and a
# Greek city is also known by its other spellings ("Athina", "Αθήνα") -- exactly
# as the university service does it.
# NOTE: version v2 of the university service delivers to EVERY commune of France
# and every town and village of Greece, plus the three German cities, and lists
# them at GET /city. This stub keeps the nine cities the examples use -- they
# all deliver there too -- so a run against the stub and a run against the
# service agree on every case in this exercise. The one case where they differ
# is a city that is not in this list: the service accepts Paris or Patras, the
# stub refuses them. Iteration 3 ships the full area as a data file.
VALID_CITIES = [
    "Leipzig", "Halle", "Dresden",
    "Saint-Étienne", "Saint-Priest-en-Jarez", "Lyon",
    "Athens", "Piraeus", "Agia Paraskevi",
]

# The other spellings the service accepts for the three Greek cities -- copied
# from its data file (GeoNames), so that stub and service agree on every one.
OTHER_SPELLINGS = {
    'Athens': [
        'Afina', 'Afini', 'Afiny', 'An Aithin', 'Ateena', 'Atehny', 'Aten', 'Atena',
        'Atenai', 'Atenas', 'Atene', 'Atenes', 'Ateni', 'Ateno', 'Atenoj', 'Ateny', 'Athen',
        'Athena', 'Athenae', 'Athenai', 'Athene', 'Athenes', 'Atheny', 'Athina', 'Athinai',
        'Athinia', 'Atina', 'Aþena', 'Kota Athena', 'Lungsod ng Athina', 'Αθήνα', 'Αθήναι'
    ],
    'Piraeus': [
        'El Pireo', 'El Pireu', 'Il Pireo', 'Le Piree', 'Lo Pireu', 'O Pireo', 'Peiraeus',
        'Peiraia', 'Peiraias', 'Peiraiefs', 'Peiraieus', 'Peiraievs', 'Piraievs', 'Piraus',
        'Pire', 'Pireas', 'Pireefs', 'Pirehj', 'Pirej', 'Pireja', 'Pirejas', 'Pireo',
        'Pireu', 'Pireus', 'Pireusz', 'Piræus', 'Πειραιάς', 'Πειραιεύς'
    ],
    'Agia Paraskevi': [
        'Agia Paraskeue', 'Ayia Paraskevi', 'Αγία Παρασκευή'
    ],
}


def normalize_city(city: str) -> str:
    """Fold a city name for comparison: no accents, no case, no stray spaces."""
    stripped = unicodedata.normalize("NFKD", city or "")
    stripped = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return " ".join(stripped.replace("-", " ").split()).casefold()


VALID_CITIES_NORMALIZED = {normalize_city(city) for city in VALID_CITIES}
VALID_CITIES_NORMALIZED |= {normalize_city(spelling)
                            for spellings in OTHER_SPELLINGS.values() for spelling in spellings}

# The delivery area of v2 itself: the data file the service reads (name, country,
# population, other spellings separated by "|"). VALID_CITIES above are the nine
# of the course examples -- the page below names them, and they are the fallback
# when the file is missing.
CITY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cities.tsv.gz")
AREA = "every commune of France, every town and village of Greece, plus Leipzig, Halle and Dresden"


def load_area() -> tuple[set[str], int]:
    """The folded names and spellings of the delivery area, and how many places it has."""
    if not os.path.exists(CITY_FILE):
        log.warn(f"{CITY_FILE} not found -- serving the nine cities of the course examples")
        return VALID_CITIES_NORMALIZED, len(VALID_CITIES)
    accepted, places = set(), 0
    with gzip.open(CITY_FILE, "rt", encoding="utf-8") as handle:
        for line in handle:
            name, _country, _population, *rest = line.rstrip("\n").split("\t")
            places += 1
            accepted.add(normalize_city(name))
            accepted.update(normalize_city(s) for s in (rest[0].split("|") if rest and rest[0] else []))
    return accepted, places


ACCEPTED, PLACES = load_area()


def refusal(city: str) -> str:
    """The 400 message of v2, word for word."""
    if PLACES == len(VALID_CITIES):                       # the fallback without the data file
        return f"We don't deliver to {city}. Available cities: {', '.join(VALID_CITIES)}"
    return (f"We don't deliver to {city}. We deliver to {PLACES} places -- {AREA}. "
            f"Look yours up with GET /city?q={city[:40]}")


def missing_fields(body: dict, fields: tuple[str, ...]) -> list[dict]:
    """The 422 detail FastAPI gives for missing fields, in the order of the service's model."""
    return [{"type": "missing", "loc": ["body", field], "msg": "Field required", "input": body}
            for field in fields if field not in body]


def address_error(city: str, street: str, house_number: str) -> str | None:
    """The three checks of POST /address/validate, in the service's order."""
    if normalize_city(city) not in ACCEPTED:
        return refusal(city)
    if len(street) < 2:
        return "Invalid street name"
    if not house_number:
        return "House number is required"
    return None


# The page served at the stub's own URL. The university service answers there
# with its Swagger UI (https://wse-research.org/pizza-api/v2); the stub cannot -- a
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
<p class="note">This is the offline stand-in that ships with Exercise 2. It answers like version v2 of the
university service at <a href="https://wse-research.org/pizza-api/v2">https://wse-research.org/pizza-api/v2</a>
&mdash; same endpoints, same menu and ids, same delivery area, same error messages &mdash; but it runs on your
machine and keeps its orders in memory. The real service shows its interactive Swagger UI at its own URL;
this page is the static equivalent, so that it also works with no network at all.
It is served by <code>pizza_api_stub.py</code> in your terminal &mdash; closing that terminal stops it.</p>

<h2>Endpoints</h2>
<table>
<tr><th><code>GET&nbsp;/pizza</code></th><td>the menu: <code>[{{"id": 1, "name": "Margherita"}}, ...]</code> &mdash; every pizza can always be ordered</td></tr>
<tr><th><code>POST&nbsp;/address/validate</code></th><td>body <code>{{"city", "street", "house_number"}}</code> &rarr; <code>200</code> or <code>400</code> with a <code>detail</code> message</td></tr>
<tr><th><code>POST&nbsp;/order</code></th><td>body <code>{{"pizza_id", "city", "street", "house_number"}}</code> &rarr; <code>{{"order_id", "status": "received"}}</code></td></tr>
<tr><th><code>GET&nbsp;/order/&lt;order_id&gt;</code></th><td>the stored order</td></tr>
</table>

<h2>Menu</h2>
<p>{menu}</p>

<h2>Delivery area</h2>
<p>{area} &mdash; {cities} among them &mdash; compared without accents and without case, so <code>athens</code> and
<code>ATHENS</code> are the same place, and so are <code>Athina</code> and <code>Αθήνα</code>. Anything else is answered with
<code>400 &quot;We don&#39;t deliver to ...&quot;</code>.</p>

<h2>Try it &mdash; macOS, Linux (bash, zsh)</h2>
<pre>curl {base}/pizza
ORDER=$(curl -s -X POST -H 'Content-Type: application/json' \\
     -d '{{"pizza_id": 1, "street": "Ermou", "house_number": "5", "city": "Athens"}}' \\
     {base}/order)
echo "$ORDER"
curl {base}/order/$(echo "$ORDER" | sed 's/.*"order_id":"\\([^"]*\\)".*/\\1/')</pre>

<h2>Try it &mdash; Windows PowerShell</h2>
<pre>Invoke-RestMethod {base}/pizza
$o = Invoke-RestMethod -Method Post -Uri {base}/order -ContentType 'application/json' `
     -Body '{{"pizza_id":1,"street":"Ermou","house_number":"5","city":"Athens"}}'
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

    def _read_json(self) -> dict | None:
        """The request body, or None when it is not a JSON object (the service: 422)."""
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return None
        return body if isinstance(body, dict) else None

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
            self._send(200, MENU)
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
        if body is None and self.path.rstrip("/") in ("/address/validate", "/order"):
            self._send(422, {"detail": [{"type": "json_invalid", "loc": ["body", 0],
                                         "msg": "JSON decode error", "input": {},
                                         "ctx": {"error": "Expecting value"}}]})
            return

        if self.path.rstrip("/") == "/address/validate":
            missing = missing_fields(body, ("city", "street", "house_number"))
            if missing:
                self._send(422, {"detail": missing})
                return
            city = str(body.get("city", ""))
            street = str(body.get("street", ""))
            house_number = str(body.get("house_number", ""))
            error = address_error(city, street, house_number)
            if error:
                self._send(400, {"detail": error})
            else:
                self._send(200, {"message": "Address is valid",
                                 "address": {"city": city, "street": street,
                                             "house_number": house_number}})

        elif self.path.rstrip("/") == "/order":
            missing = missing_fields(body, ("pizza_id", "city", "street", "house_number"))
            if missing:
                self._send(422, {"detail": missing})
                return
            pizza = next((p for p in MENU if p["id"] == body.get("pizza_id")), None)
            if pizza is None:
                self._send(404, {"detail": "Pizza not found"})
                return
            city = str(body.get("city", ""))
            error = address_error(city, str(body.get("street", "")), str(body.get("house_number", "")))
            if error:
                self._send(400, {"detail": error})
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
        # process causes. It goes through the log layer like everything else,
        # with the `detail` role: it is the stub's diagnostics, not its answer.
        log.detail(f"[pizza-api] {fmt % args}", indent="    ")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    global INDEX_HTML
    INDEX_HTML = INDEX_HTML.format(
        menu=", ".join(f"<code>{p['id']}</code> {p['name']}" for p in MENU),
        cities=", ".join(VALID_CITIES),
        area=(f"{PLACES} places: {AREA}" if PLACES != len(VALID_CITIES) else "the nine cities of the course examples"),
        base=f"http://{args.host}:{args.port}",
    )

    base = f"http://{args.host}:{args.port}"
    log.result(f"Pizza API stub is running on {base}")
    log.plain()
    log.step("  NOW, IN YOUR OTHER TERMINAL, RUN ONE OF THESE:")
    log.hint(f"export PIZZA_API_BASE={base}      macOS, Linux", indent="      ")
    log.hint(f'$env:PIZZA_API_BASE="{base}"      PowerShell', indent="      ")
    log.hint(f"set PIZZA_API_BASE={base}         cmd.exe", indent="      ")
    log.plain()
    log.warn("  Leave THIS window open -- closing it stops the stub.")
    log.detail("Stop it yourself with Ctrl+C.", indent="  ")
    log.detail(f"{len(MENU)} pizzas, {len(VALID_CITIES)} delivery cities: open {base}", indent="  ")
    log.plain()
    log.step("  Every request your bot makes is logged below, one line each:")
    try:
        HTTPServer((args.host, args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        log.plain()
        log.result("stub stopped")


if __name__ == "__main__":
    main()
