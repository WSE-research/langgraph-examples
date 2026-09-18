from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import BaseModel
from typing import List, Optional
import gzip
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
        'Every endpoint is listed below and can be tried out directly from this page.'
    ),
    version='1.2.0',
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
    {"id": 20, "name": "Boscaiola"}
]

# Store orders in memory (in a real application, use a proper database)
orders = {}

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

@app.get("/pizza")
async def list_pizzas():
    """List all available pizzas"""
    return pizzas

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
async def create_order(order: OrderCreate):
    """Create a neworder"""
    # Validate pizza_id
    if not any(pizza["id"] == order.pizza_id for pizza in pizzas):
        raise HTTPException(
            status_code=404,
            detail="Pizza not found"
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
