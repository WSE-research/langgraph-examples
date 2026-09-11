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

Endpoints used (all of them from Lecture 1, slide 24):

    GET  /pizza              -> [{"id": 1, "name": "Margherita", ...}, ...]
    POST /address/validate   -> 200 if the address exists, 4xx otherwise
    POST /order              -> {"order_id": "...", "status": "received"}
    GET  /order/{order_id}   -> the order as stored by the API
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
    """Print one readable screen instead of a 25-line traceback, then stop.

    Called from the `__main__` blocks of the scripts you run. A traceback tells
    you where the program was; this tells you what to do next.
    """
    print()
    print("=" * 72)
    print("  The Pizza API did not answer.")
    print(f"  tried : {BASE}")
    detail = str(error).splitlines()[0]
    print(f"  said  : {detail[:60] + '...' if len(detail) > 63 else detail}")
    print()
    print("  In a SECOND terminal, start the offline stub and leave it open:")
    print("      python pizza_api_stub.py")
    print()
    print("  Then, back in THIS terminal, point the bot at it:")
    print("      export PIZZA_API_BASE=http://127.0.0.1:8000      macOS, Linux")
    print('      $env:PIZZA_API_BASE="http://127.0.0.1:8000"      PowerShell')
    print("      set PIZZA_API_BASE=http://127.0.0.1:8000         cmd.exe")
    print()
    print("  Or put that line into .env, which every script reads.")
    print("=" * 72)
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
