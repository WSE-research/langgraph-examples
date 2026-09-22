from fastapi import FastAPI, Header, HTTPException, Query, Response
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
import gzip
import os
import random
import secrets
import time
import unicodedata
import uuid
from enum import Enum
from pathlib import Path

app = FastAPI(
    root_path='/pizza-api',
    title='Pizza API',
    description=(
        'A small ordering API for the *Question Answering & Chatbots* courses: '
        'read the menu, list the cities we deliver to, validate a delivery address, '
        'place an order, follow it up. '
        'Every minute, two pizzas of the menu are sold out: `GET /pizza` marks them '
        '`"available": false`, the same two for every request within that minute, '
        'drawn at random for the next one, and `POST /order` refuses them with HTTP 409 '
        '(a test driver may send `X-Accept-Everything: true` to order them anyway). '
        'Every endpoint is listed below and can be tried out directly from this page.'
    ),
    version='1.3.0',
)


@app.get('/', include_in_schema=False)
async def api_documentation():
    """Serve the interactive documentation at the API's own URL.

    Opening https://wse-research.org/pizza-api answered 404 before, which is a
    poor welcome for a service whose first user is a student. The same Swagger
    UI as /docs is served here, so the URL that names the API also explains it.

    The schema is referenced relatively ("openapi.json", resolved against this
    page), so the page works behind the /pizza-api proxy prefix *and* when the
    container is called directly on its port.
    """
    return get_swagger_ui_html(
        openapi_url='openapi.json',
        title='Pizza API - interactive documentation',
    )

# Enums and Models
class OrderStatus(str, Enum):
    RECEIVED = "received"
    PREPARING = "preparing"
    ON_DELIVERY = "on_delivery"
    DELIVERED = "delivered"

class Address(BaseModel):
    city: str
    street: str
    house_number: str

class OrderCreate(BaseModel):
    pizza_id: int
    city: str
    street: str
    house_number: str

class Order(BaseModel):
    id: str
    pizza_id: int
    address: Address
    status: OrderStatus

# Mock database
pizzas = [
    {"id": 1, "name": "Margherita"},
    {"id": 2, "name": "Pepperoni"},
    {"id": 3, "name": "Hawaiian"},
    {"id": 4, "name": "Quattro Formaggi"},
    # Ids 1-4 are stable: existing course material and student code refer to
    # them. New items are appended, never inserted.
    {"id": 5, "name": "Funghi"},
    {"id": 6, "name": "Salami"},
    {"id": 7, "name": "Prosciutto"},
    {"id": 8, "name": "Diavola"},
    {"id": 9, "name": "Vegetariana"},
    {"id": 10, "name": "Calzone"},
    # Appended 2026-09-18 for the Saint-Etienne exercise: a team picks its own
    # pizzas from GET /pizza, so ten names are not enough to pick from.
    {"id": 11, "name": "Capricciosa"},
    {"id": 12, "name": "Marinara"},
    # Not "Napoli": "One Pizza Napoli please" is the standing example of a name
    # that is NOT on the menu in the Iteration 2 material, and a menu that
    # contradicts the course material is worse than a shorter menu.
    {"id": 13, "name": "Siciliana"},
    {"id": 14, "name": "Tonno"},
    {"id": 15, "name": "Frutti di Mare"},
    {"id": 16, "name": "Quattro Stagioni"},
    {"id": 17, "name": "Bufala"},
    {"id": 18, "name": "Tartufo"},
    {"id": 19, "name": "Rucola"},
    # Not "Prosciutto e Funghi": the static recognizer of Iteration 1 matches menu
    # names by substring in menu order, so it would answer "Prosciutto" (id 7)
    # to every order of it -- a trap in the data, not a lesson.
    {"id": 20, "name": "Boscaiola"},
    # Appended 2026-09-20 for Iteration 4: the knowledge graph answers dietary
    # questions ("is it vegetarian?", "does it contain milk?"), and a menu
    # without a declared vegetarian *and* a declared vegan pizza cannot show the
    # difference. Ortolana carries mozzarella, Verdure carries no animal product
    # at all -- the two differ by one topping, which is what makes the derived
    # flags worth deriving. Neither name is a substring of another menu name, so
    # the Iteration 1 recognizer stays unambiguous.
    {"id": 21, "name": "Ortolana"},
    {"id": 22, "name": "Verdure"}
]

# Store orders in memory (in a real application, use a proper database)
orders = {}


class Pizza(BaseModel):
    id: int = Field(description="Stable id -- the value `POST /order` expects as `pizza_id`.")
    name: str
    available: bool = Field(description=(
        "Whether the kitchen can bake it *in this minute*. Two pizzas are false at any "
        "time; which two changes every minute, at random."))


# Availability: every minute, two pizzas are sold out. Added 2026-09-23 for the
# repair part of the course (a guest names a pizza that exists and cannot be had
# right now), and the service-side counterpart of `pz:available` in the lecture
# graph. It is a property of the *minute*, not of the pizza, so a client has to
# ask again instead of remembering the answer.
#
# The draw is a pure function of (seed, minute): every request in the same
# minute sees the same two pizzas, with no state, no timer and no lock, and it
# stays consistent even if the service ever runs with several workers sharing
# one seed. The seed is random per process by default, so which pizzas are sold
# out cannot be predicted from this source; set PIZZA_AVAILABILITY_SEED to make
# the sequence reproducible (tests, a rehearsed demo).
UNAVAILABLE_PER_MINUTE = 2
AVAILABILITY_SEED = os.environ.get("PIZZA_AVAILABILITY_SEED") or secrets.token_hex(16)


def current_minute() -> int:
    """Minutes since the epoch, UTC -- the unit in which availability changes."""
    return int(time.time() // 60)


def unavailable_ids(minute: int) -> set:
    """The ids of the pizzas sold out in `minute` -- the same answer every time.

    A string seed is hashed with SHA-512 by `random.Random`, so the result does
    not depend on PYTHONHASHSEED and is identical across processes.
    """
    rng = random.Random(f"{AVAILABILITY_SEED}:{minute}")
    return set(rng.sample([pizza["id"] for pizza in pizzas], UNAVAILABLE_PER_MINUTE))


def minute_iso(minute: int) -> str:
    return datetime.fromtimestamp(minute * 60, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# The delivery area: every commune of France, plus the three German cities the
# HTWK course has used since 2024. It is a data file and not a list in this
# module -- since 2026-09-18 it holds ~32 700 names, because the Saint-Etienne
# exercise asks every team to pick its own cities from GET /city instead of
# working with the six that used to be hard-coded here. `build-cities.py`
# regenerates it from the French government's geo API; the file is committed, so
# the image builds offline and a deployment never waits on somebody else's API.
CITY_FILE = Path(__file__).parent / "data" / "cities.tsv.gz"


class City(BaseModel):
    name: str
    country: str
    population: int


def load_cities() -> List[City]:
    """Read the delivery area once, at import time.

    A flat gzipped TSV, read into memory: ~32 700 rows are a few megabytes of
    Python objects and no dependency, no database and no startup latency worth
    measuring. If the file is missing -- someone built an image without it --
    the service falls back to the six cities of the 2024 course rather than
    starting with an empty delivery area and refusing everything.
    """
    if not CITY_FILE.exists():
        return [City(name=name, country=country, population=0) for name, country in [
            ("Leipzig", "DE"), ("Halle", "DE"), ("Dresden", "DE"),
            ("Saint-\u00c9tienne", "FR"), ("Saint-Priest-en-Jarez", "FR"), ("Lyon", "FR")]]
    cities = []
    with gzip.open(CITY_FILE, "rt", encoding="utf-8") as handle:
        for line in handle:
            name, country, population = line.rstrip("\n").split("\t")
            cities.append(City(name=name, country=country, population=int(population)))
    return cities


CITIES = load_cities()
VALID_CITIES = [city.name for city in CITIES]


def normalize_city(city: str) -> str:
    """Fold a city name for comparison: no accents, no case, no stray spaces.

    Students type "saint-etienne", "Saint-Etienne" and "Saint-\u00c9tienne" for the
    same place, and a delivery service that refuses two of the three teaches
    nothing about addresses. The stored order keeps the spelling the caller
    sent; only the comparison is folded.
    """
    stripped = unicodedata.normalize("NFKD", city or "")
    stripped = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return " ".join(stripped.replace("-", " ").split()).casefold()


VALID_CITIES_NORMALIZED = {normalize_city(city): city for city in VALID_CITIES}

# Ordered the way a human wants to read a city list: the largest first, so that
# GET /city without arguments answers with places people have heard of.
CITIES_BY_SIZE = sorted(CITIES, key=lambda city: (-city.population, city.name))

@app.get("/pizza", response_model=List[Pizza])
async def list_pizzas(response: Response):
    """The menu: every pizza, and whether it can be ordered in this minute.

    The list is always complete -- a sold-out pizza is still on the menu, with
    `"available": false`. Exactly two pizzas are unavailable at any time; which
    two is drawn at random once per minute (UTC), so every request within the
    same minute gets the same answer and the next minute may get another.

    Two headers say which minute the answer belongs to:

        X-Availability-Minute        start of that minute, e.g. 2026-09-23T10:41:00Z
        X-Availability-Valid-Until   start of the next one -- ask again after it

    Read availability when you need it, not once at start-up: a pizza that was
    available a moment ago may not be any more.
    """
    minute = current_minute()
    sold_out = unavailable_ids(minute)
    response.headers["X-Availability-Minute"] = minute_iso(minute)
    response.headers["X-Availability-Valid-Until"] = minute_iso(minute + 1)
    response.headers["Cache-Control"] = "no-store"
    return [Pizza(**pizza, available=pizza["id"] not in sold_out) for pizza in pizzas]

@app.get("/city")
async def list_cities(
    response: Response,
    q: Optional[str] = Query(None, description="Substring of the city name, accent- and case-insensitive."),
    limit: int = Query(100, ge=1, le=1000, description="How many cities to return (1-1000)."),
    offset: int = Query(0, ge=0, description="How many to skip -- page through the whole area."),
):
    """The delivery area: the cities this service delivers to.

    Every commune of France, plus Leipzig, Halle and Dresden. That is about
    32 700 names, so the answer is a page and not the whole list: the largest
    cities come first, `q` searches by name, and `X-Total-Count` says how many
    matched. Nothing here is a secret -- page through it if you want all of it.

        GET /city                      the 100 largest
        GET /city?q=saint&limit=20     the 20 largest whose name contains "saint"
        GET /city?limit=1000&offset=1000   the second page of a thousand

    The search is folded the same way `POST /address/validate` folds a city
    name, so anything this endpoint returns is something that endpoint accepts.
    """
    matching = CITIES_BY_SIZE
    if q:
        needle = normalize_city(q)
        matching = [city for city in matching if needle in normalize_city(city.name)]
    response.headers["X-Total-Count"] = str(len(matching))
    return matching[offset:offset + limit]


@app.post("/address/validate")
async def validate_address(address: Address):
    """Validate delivery address"""
    # Check if city is serviceable (accent- and case-insensitive)
    if normalize_city(address.city) not in VALID_CITIES_NORMALIZED:
        raise HTTPException(
            status_code=400,
            detail=(f"We don't deliver to {address.city}. "
                    f"We deliver to {len(VALID_CITIES)} cities -- every commune of France, "
                    f"plus Leipzig, Halle and Dresden. Look yours up with "
                    f"GET /city?q={address.city[:40]}")
        )
    
    # Basic validation for street and house number
    if len(address.street) < 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid street name"
        )
    
    if not address.house_number:
        raise HTTPException(
            status_code=400,
            detail="House number is required"
        )

    return {"message": "Address is valid", "address": address}

@app.post("/order")
async def create_order(
    order: OrderCreate,
    x_accept_everything: Optional[str] = Header(
        None,
        description=("Test drivers only: `true` lets an order for a pizza that is sold out in "
                     "this minute through. A chatbot must never send it."),
    ),
):
    """Place an order -- if the pizza can be had in this minute.

    404 when the pizza id does not exist, **409 Conflict** when it exists but is
    sold out right now (`"available": false` in `GET /pizza`), 400 when the
    address is outside the delivery area. A 409 is not a broken request: the
    same order may succeed in the next minute, or with another pizza.

    Test drivers that order fixed pizza ids (course material written before
    availability existed, `verify-pizza-api.sh`) send `X-Accept-Everything: true`,
    so their result does not depend on the minute they run in.
    """
    # Validate pizza_id
    pizza = next((pizza for pizza in pizzas if pizza["id"] == order.pizza_id), None)
    if pizza is None:
        raise HTTPException(
            status_code=404,
            detail="Pizza not found"
        )

    # Sold out in this minute: the request is valid and the pizza exists, but it
    # conflicts with the current state of the kitchen -- 409, not 404 or 400.
    minute = current_minute()
    if pizza["id"] in unavailable_ids(minute) and (x_accept_everything or "").strip().lower() != "true":
        raise HTTPException(
            status_code=409,
            detail=(f"{pizza['name']} (id {pizza['id']}) is sold out right now, until "
                    f"{minute_iso(minute + 1)}. GET /pizza lists what is available."),
        )

    # Validate address
    address = Address(
        city=order.city,
        street=order.street,
        house_number=order.house_number
    )
    await validate_address(address)

    # Create order
    order_id = str(uuid.uuid4())
    new_order = Order(
        id=order_id,
        pizza_id=order.pizza_id,
        address=address,
        status=OrderStatus.RECEIVED
    )
    
    # Save order
    orders[order_id] = new_order

    return {"order_id": order_id, "status": OrderStatus.RECEIVED}

@app.get("/order/{order_id}")
async def get_order_status(order_id: str):
    """Get order status by order ID"""
    if order_id not in orders:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )
    
    return {
        "order_id": order_id,
        "status": orders[order_id].status,
        "pizza_id": orders[order_id].pizza_id,
        "address": orders[order_id].address
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
