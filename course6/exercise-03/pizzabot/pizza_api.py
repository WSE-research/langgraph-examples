"""The Pizza API behind one small component -- the only door to the outside.

Every HTTP call this process makes lives in this file. Nodes call the functions
below, never `requests` directly. That is not tidiness for its own sake:

  * the process stays testable -- a test replaces this module, not the network;
  * an outage has exactly one place to be handled;
  * the switch between the university API and the local stub is one variable.

Configuration (see .env.example)::

    PIZZA_API_BASE=https://wse-research.org/pizza-api   # the university service
    PIZZA_API_BASE=http://127.0.0.1:8000                # the local stub

The service documents itself: open https://wse-research.org/pizza-api in a
browser and you get the interactive Swagger UI for exactly these endpoints,
with a "Try it out" button; https://wse-research.org/pizza-api/openapi.json is
the same thing machine-readable. The local stub answers its own URL
(http://127.0.0.1:8000) with a plain HTML version of the same list.

Endpoints used:

    GET  /pizza              -> [{"id": 1, "name": "Margherita", ...}, ...]
    GET  /city               -> [{"name": "Paris", "country": "FR", "population": ...}, ...]
    POST /address/validate   -> 200 if the address exists, 4xx otherwise
    POST /order              -> {"order_id": "...", "status": "received"}
    GET  /order/{order_id}   -> the order as stored by the API

`GET /city` is the one that arrived in Iteration 3 (service version 1.2.0): the
delivery area is every commune of France plus Leipzig, Halle and Dresden --
about 32 700 names -- so it answers a *page*, searched with `q` and sized with
`limit`. That is what lets a team pick its own benchmark cities from the
service instead of from a list somebody wrote for them.
"""

from __future__ import annotations

import os
from typing import Optional

import requests

BASE = os.environ.get("PIZZA_API_BASE", "https://wse-research.org/pizza-api").rstrip("/")
TIMEOUT = float(os.environ.get("PIZZA_API_TIMEOUT", "10"))

_MENU_CACHE: Optional[list[dict]] = None


class PizzaApiError(RuntimeError):
    """The API did not behave as its contract promises.

    Defined failure behaviour is part of a contract: a component that cannot
    keep its guarantee says so loudly instead of returning something wrong.
    """


def _get(path: str) -> requests.Response:
    try:
        response = requests.get(f"{BASE}{path}", timeout=TIMEOUT)
    except requests.RequestException as error:
        raise PizzaApiError(
            f"GET {BASE}{path} failed: {error}\n"
            f"Is PIZZA_API_BASE correct? For the offline stub run: "
            f"python pizza_api_stub.py"
        ) from error
    return response


def _post(path: str, payload: dict) -> requests.Response:
    try:
        response = requests.post(f"{BASE}{path}", json=payload, timeout=TIMEOUT)
    except requests.RequestException as error:
        raise PizzaApiError(
            f"POST {BASE}{path} failed: {error}\n"
            f"Is PIZZA_API_BASE correct? For the offline stub run: "
            f"python pizza_api_stub.py"
        ) from error
    return response


def menu(refresh: bool = False) -> list[dict]:
    """GET /pizza -- the menu is data, not code.

    Cached for the lifetime of the process: the menu does not change while one
    dialog runs, and a node should not cause an HTTP request per word it looks
    at. Pass `refresh=True` to force a reload.
    """
    global _MENU_CACHE
    if _MENU_CACHE is None or refresh:
        response = _get("/pizza")
        if response.status_code != 200:
            raise PizzaApiError(f"GET /pizza -> HTTP {response.status_code}")
        try:
            _MENU_CACHE = response.json()
        except ValueError as error:
            raise PizzaApiError(
                f"GET /pizza did not return JSON but "
                f"{response.headers.get('content-type')!r}. "
                f"The API at {BASE} is probably not the Pizza API."
            ) from error
    return _MENU_CACHE


def menu_names() -> list[str]:
    """Just the names, in menu order."""
    return [item["name"] for item in menu()]


def pizza_id_for(name: str) -> Optional[int]:
    """The id the order endpoint wants, for a name that is on the menu."""
    for item in menu():
        if item["name"].lower() == name.lower():
            return item["id"]
    return None


def cities(q: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    """GET /city -- the delivery area, a page at a time.

    Returns `[{"name": ..., "country": ..., "population": ...}, ...]`, largest
    first. `q` searches the name accent- and case-insensitively, exactly as the
    service folds a city in `POST /address/validate`, so anything this returns
    is something that endpoint accepts.

        cities(q="saint-eti", limit=5)      # the five biggest Saint-Étienne-ish names
        cities(limit=1000, offset=1000)     # the second page of a thousand
    """
    query = f"?limit={int(limit)}&offset={int(offset)}"
    if q:
        from urllib.parse import quote

        query += f"&q={quote(q)}"
    response = _get(f"/city{query}")
    if response.status_code == 404:
        raise PizzaApiError(
            f"GET /city -> HTTP 404. This API does not know the endpoint: it is older "
            f"than service version 1.2.0 (2026-09-18). Update it, or use the stub: "
            f"python pizza_api_stub.py"
        )
    if response.status_code != 200:
        raise PizzaApiError(f"GET /city -> HTTP {response.status_code}")
    return response.json()


def city_names(q: str | None = None, limit: int = 100) -> list[str]:
    """Just the names, largest city first."""
    return [city["name"] for city in cities(q=q, limit=limit)]


def delivers_to(city: str) -> bool:
    """Is this city in the delivery area? (the name alone, no street, no number)

    Asked through the same door as everything else. Used by `benchmark/fetch.py`
    to refuse to write a city into the knowledge graph that the service has
    never heard of -- a benchmark full of places nobody delivers to measures the
    error message, not the bot.
    """
    from unicodedata import combining, normalize

    def fold(text: str) -> str:
        stripped = normalize("NFKD", text or "")
        stripped = "".join(ch for ch in stripped if not combining(ch))
        return " ".join(stripped.replace("-", " ").split()).casefold()

    return any(fold(found["name"]) == fold(city) for found in cities(q=city, limit=1000))


def validate_address(street: str, house_number: str, city: str) -> bool:
    """POST /address/validate -- True if the API delivers to this address.

    "The service says no" and "the service is broken" are different failures and
    must not look the same: a 4xx is an answer (this address is outside the
    delivery area), a 5xx is an outage, and a component that treats an outage as
    a rejection silently tells the user their address is wrong.
    """
    response = _post(
        "/address/validate",
        {"street": street, "house_number": house_number, "city": city},
    )
    if response.status_code >= 500:
        raise PizzaApiError(
            f"POST /address/validate -> HTTP {response.status_code}: the service is "
            f"not answering properly. This is an outage, not a rejected address."
        )
    return response.status_code == 200


def place_order(pizza_id: int, address: dict) -> dict:
    """POST /order -- the only side effect this process has on the world.

    Guarantee: returns a dict with "order_id" and status "received", or raises.
    """
    payload = {
        "pizza_id": pizza_id,
        "street": address["street"],
        "house_number": address["house_number"],
        "city": address["city"],
    }
    response = _post("/order", payload)
    if response.status_code != 200:
        raise PizzaApiError(f"POST /order -> HTTP {response.status_code}: {response.text[:200]}")
    body = response.json()
    if body.get("status") != "received":
        raise PizzaApiError(f"POST /order -> unexpected status {body.get('status')!r}")
    return body


def get_order(order_id: str) -> dict:
    """GET /order/{id} -- used by the confirmation and by your validation runs."""
    response = _get(f"/order/{order_id}")
    if response.status_code != 200:
        raise PizzaApiError(f"GET /order/{order_id} -> HTTP {response.status_code}")
    return response.json()


def explain_and_exit(error: PizzaApiError) -> "NoReturn":  # noqa: F821
    """Log one readable screen instead of a 25-line traceback, then stop.

    Called from the `__main__` blocks of the scripts you run. A traceback tells
    you where the program was; this tells you what to do next.
    """
    from pizzabot import log        # here, not at the top: pizza_api is imported very early

    log.plain()
    log.rule(width=72, char="=")
    log.fail("The Pizza API did not answer.")
    log.detail(f"tried : {BASE}", indent="  ")
    detail = str(error).splitlines()[0]
    log.detail(f"said  : {detail[:60] + '...' if len(detail) > 63 else detail}", indent="  ")
    log.plain()
    log.step("  In a SECOND terminal, start the offline stub and leave it open:")
    log.hint("python pizza_api_stub.py", indent="      ")
    log.plain()
    log.step("  Then, back in THIS terminal, point the bot at it:")
    log.hint("export PIZZA_API_BASE=http://127.0.0.1:8000      macOS, Linux", indent="      ")
    log.hint('$env:PIZZA_API_BASE="http://127.0.0.1:8000"      PowerShell', indent="      ")
    log.hint("set PIZZA_API_BASE=http://127.0.0.1:8000         cmd.exe", indent="      ")
    log.plain()
    log.detail("Or put that line into .env, which every script reads.", indent="  ")
    log.rule(width=72, char="=")
    raise SystemExit(2)


def ping() -> tuple[bool, str]:
    """Is the configured API reachable and does it speak JSON? (checked by check_setup.py)"""
    try:
        items = menu(refresh=True)
    except PizzaApiError as error:
        return False, str(error).splitlines()[0]
    if not items or "name" not in items[0]:
        return False, f"GET /pizza returned {items!r:.80s}"
    return True, f"{len(items)} pizzas, e.g. {', '.join(menu_names()[:3])}"
