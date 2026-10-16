"""The Pizza API -- one service, one frozen version per exercise.

    https://wse-research.org/pizza-api        the latest version (the default)
    https://wse-research.org/pizza-api/v1     what Exercise 1 was written against
    ...
    https://wse-research.org/pizza-api/v6     what Exercise 6 was written against

Why versions: the exercises of the course6/course5 material call this service,
and the service kept growing under them -- ten more pizzas, all of France, a
city endpoint, pizzas that sell out. Every change was checked against the
material of its day, but a student who runs Exercise 1 in December runs it
against the service of December. So every exercise now names its own version in
its default `PIZZA_API_BASE`, and a version, once published, does not change:
its menu, its endpoints and its availability rule are fixed in `VERSIONS` below,
and `tests/` holds each of them to what its exercise needs. New behaviour goes
into `LATEST` (and, when an exercise needs it, into a new version) -- never into
an existing one.

The one thing the versions share is the delivery area (`data/cities.tsv.gz`):
every commune of France, every town and village of Greece, and Leipzig, Halle
and Dresden. The tests pin the cities each exercise relies on, so a refresh of
that file that would break an exercise fails there first.
"""

from __future__ import annotations

import gzip
import os
import random
import secrets
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# The menu -- one list; a version serves its first `menu_size` entries.
# ---------------------------------------------------------------------------

pizzas = [
    {"id": 1, "name": "Margherita"},
    {"id": 2, "name": "Pepperoni"},
    {"id": 3, "name": "Hawaiian"},
    {"id": 4, "name": "Quattro Formaggi"},
    # Ids 1-4 are stable: existing course material and student code refer to
    # them. New items are appended, never inserted -- a version serves a prefix
    # of this list, so an insertion would change every version at once.
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
    {"id": 22, "name": "Verdure"},
]


# ---------------------------------------------------------------------------
# The versions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Version:
    """One published version of the service. Frozen: never edit a published one.

    key                  path segment ("v1") -- or "latest" for the default
    number               the OpenAPI version string
    exercise             who relies on it, for the documentation page
    menu_size            the version serves pizzas[:menu_size]
    sold_out_per_minute  0: every pizza can always be ordered, GET /pizza has no
                         `available` field and POST /order never answers 409.
                         2: two pizzas are sold out every minute (since 1.3.0).
    city_endpoint        whether GET /city exists (since 1.2.0)
    area                 "full": every place of data/cities.tsv.gz;
                         "course": only COURSE_CITIES, the cities the course
                         examples use -- what Exercise 1 documents
    notes                one paragraph for the documentation page
    """

    key: str
    number: str
    exercise: str
    menu_size: int
    sold_out_per_minute: int
    city_endpoint: bool
    area: str
    notes: str

    @property
    def menu(self) -> list:
        return pizzas[: self.menu_size]

    @property
    def path(self) -> str:
        return "" if self.key == "latest" else f"/{self.key}"


VERSIONS = [
    Version(
        key="v1", number="v1", menu_size=10, sold_out_per_minute=0, city_endpoint=False, area="course",
        exercise="Exercise 1 -- From goals to processes (the first LangGraph process)",
        notes=("The four endpoints of Lecture 1: the menu (ten pizzas, `id` and `name`), address "
               "validation, placing an order, reading it back. The delivery area is the nine "
               "cities of the course examples, and anything else is refused. Every pizza can "
               "always be ordered -- the Iteration 1 process has no answer to a sold-out pizza, "
               "and it does not need one yet."),
    ),
    Version(
        key="v2", number="v2", menu_size=22, sold_out_per_minute=0, city_endpoint=True, area="full",
        exercise="Exercise 2 -- LLMs as services (LLM-backed components behind unchanged contracts)",
        notes=("The endpoints of Iteration 1 with the full menu of twenty-two pizzas, which the "
               "LLM-backed pizza recognizer reads into its prompt, and the full delivery area, "
               "which `GET /city` lists -- so an injected city is refused because it is outside "
               "the area, not because it is missing from a short list. Every pizza can always be "
               "ordered."),
    ),
    Version(
        key="v3", number="v3", menu_size=22, sold_out_per_minute=0, city_endpoint=True, area="full",
        exercise="Exercise 3 -- Manifesting application quality (benchmarks from a knowledge graph)",
        notes=("`GET /city` is the endpoint this exercise works with: the delivery area as a "
               "searchable, paged list, from which a team picks the cities of its benchmark. "
               "Every pizza can always be ordered."),
    ),
    Version(
        key="v4", number="v4", menu_size=22, sold_out_per_minute=0, city_endpoint=True, area="full",
        exercise="Exercise 4 -- Dynamic data and flexible processes (factoid QA over the pizza graph)",
        notes=("The same service as v3 -- Iteration 4 changes the knowledge graph, not the "
               "service. Every pizza can always be ordered: sold-out pizzas arrive with the repair "
               "of Iteration 5 (v5)."),
    ),
    Version(
        key="v5", number="v5", menu_size=22, sold_out_per_minute=2, city_endpoint=True, area="full",
        exercise="Exercise 5 -- Explainability, trust, and repair",
        notes=("Two pizzas are sold out every minute: `GET /pizza` marks them `\"available\": "
               "false` and `POST /order` refuses them with HTTP 409 -- the case the repair of "
               "Iteration 5 is built on. A test driver may send `X-Accept-Everything: true` to "
               "order them anyway."),
    ),
    Version(
        key="v6", number="v6", menu_size=22, sold_out_per_minute=2, city_endpoint=True, area="full",
        exercise="Exercise 6 -- Beyond the graph: RAG, hybrid QA, and the outlook",
        notes=("The service of Iteration 5, unchanged: the RAG branch of Iteration 6 does not call "
               "the service, and every test of Iterations 3 to 5 has to stay green against it."),
    ),
]

LATEST = Version(
    key="latest", number="1.4.0", menu_size=22, sold_out_per_minute=2, city_endpoint=True, area="full",
    exercise="none in particular -- the newest behaviour, for everything that is not an exercise",
    notes=("The newest version. It may change: an exercise uses its own version below, which "
           "does not."),
)

VERSIONS_BY_KEY = {version.key: version for version in VERSIONS}


# ---------------------------------------------------------------------------
# Availability -- a pure function of (seed, minute); see sold_out_ids()
# ---------------------------------------------------------------------------

# Every minute, a version with sold_out_per_minute > 0 has that many pizzas sold
# out. Added 2026-09-23 (1.3.0) for the repair part of the course (a guest names
# a pizza that exists and cannot be had right now), and the service-side
# counterpart of `pz:available` in the lecture graph. It is a property of the
# *minute*, not of the pizza, so a client has to ask again instead of
# remembering the answer.
#
# The draw is a pure function of (seed, minute, menu): every request in the
# same minute sees the same pizzas, with no state, no timer and no lock, and it
# stays consistent even if the service ever runs with several workers sharing
# one seed. The seed is random per process by default, so which pizzas are sold
# out cannot be predicted from this source; set PIZZA_AVAILABILITY_SEED to make
# the sequence reproducible (tests, a rehearsed demo).
AVAILABILITY_SEED = os.environ.get("PIZZA_AVAILABILITY_SEED") or secrets.token_hex(16)


def current_minute() -> int:
    """Minutes since the epoch, UTC -- the unit in which availability changes."""
    return int(time.time() // 60)


def sold_out_ids(minute: int, menu: list, count: int) -> set:
    """The ids of the pizzas sold out in `minute` -- the same answer every time.

    A string seed is hashed with SHA-512 by `random.Random`, so the result does
    not depend on PYTHONHASHSEED and is identical across processes. For the
    22-pizza menu this is exactly the draw of version 1.3.0.
    """
    if count <= 0:
        return set()
    rng = random.Random(f"{AVAILABILITY_SEED}:{minute}")
    return set(rng.sample([pizza["id"] for pizza in menu], count))


def minute_iso(minute: int) -> str:
    return datetime.fromtimestamp(minute * 60, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# The delivery area -- shared by every version
# ---------------------------------------------------------------------------

# Every commune of France, every town and village of Greece, plus the three
# German cities the HTWK course has used since 2024. It is a data file and not
# a list in this module -- ~43 000 names -- because the exercises ask every team
# to pick its own cities from GET /city. `build-cities.py` regenerates it; the
# file is committed, so the image builds offline and a deployment never waits on
# somebody else's API. Greek places carry their other spellings (Athina, Athen,
# Αθήνα for Athens) in a fourth column, and those are accepted too.
CITY_FILE = Path(__file__).parent / "data" / "cities.tsv.gz"

AREA_SUMMARY = "every commune of France, every town and village of Greece, plus Leipzig, Halle and Dresden"

# The small area of version 1: the cities the examples of the course use --
# three for the HTWK course, three for the Saint-Etienne edition, three for the
# Athens edition. Exercise 1 documents exactly these and "400 for anything
# else", and its stub serves exactly these; the other versions deliver to the
# whole file.
COURSE_CITIES = [
    "Leipzig", "Halle", "Dresden",
    "Saint-\u00c9tienne", "Saint-Priest-en-Jarez", "Lyon",
    "Athens", "Piraeus", "Agia Paraskevi",
]


class City(BaseModel):
    name: str
    country: str
    population: int


def normalize_city(city: str) -> str:
    """Fold a city name for comparison: no accents, no case, no stray spaces.

    Students type "saint-etienne", "Saint-Etienne" and "Saint-Étienne" for the
    same place -- or "agia paraskevi" and "Agía Paraskeví" -- and a delivery
    service that refuses two of the three teaches nothing about addresses. The
    stored order keeps the spelling the caller sent; only the comparison is
    folded.
    """
    stripped = unicodedata.normalize("NFKD", city or "")
    stripped = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return " ".join(stripped.replace("-", " ").split()).casefold()


def load_cities() -> list:
    """Read the delivery area once, at import time: [(City, [other spellings])].

    A flat gzipped TSV, read into memory: a few megabytes of Python objects, no
    dependency, no database, no startup latency worth measuring. If the file is
    missing -- someone built an image without it -- the service falls back to
    the cities of the course examples rather than starting with an empty
    delivery area and refusing everything.
    """
    if not CITY_FILE.exists():
        return [(City(name=name, country=country, population=0), []) for name, country in [
            ("Leipzig", "DE"), ("Halle", "DE"), ("Dresden", "DE"),
            ("Saint-Étienne", "FR"), ("Saint-Priest-en-Jarez", "FR"), ("Lyon", "FR"),
            ("Athens", "GR"), ("Piraeus", "GR"), ("Agia Paraskevi", "GR")]]
    cities = []
    with gzip.open(CITY_FILE, "rt", encoding="utf-8") as handle:
        for line in handle:
            name, country, population, *rest = line.rstrip("\n").split("\t")
            aliases = rest[0].split("|") if rest and rest[0] else []
            cities.append((City(name=name, country=country, population=int(population)), aliases))
    return cities


_AREA = load_cities()
CITIES = [city for city, _ in _AREA]
VALID_CITIES = [city.name for city in CITIES]


def accepted_spellings(area: list) -> set:
    """Every accepted spelling of an area, folded: the names and the other spellings."""
    return {normalize_city(name) for city, aliases in area for name in [city.name, *aliases]}


ACCEPTED_CITIES = accepted_spellings(_AREA)
_BY_NAME = {city.name: (city, aliases) for city, aliases in _AREA}
COURSE_AREA = [_BY_NAME.get(name, (City(name=name, country="?", population=0), []))
               for name in COURSE_CITIES]
ACCEPTED_COURSE_CITIES = accepted_spellings(COURSE_AREA)

# Ordered the way a human wants to read a city list: the largest first, so that
# GET /city without arguments answers with places people have heard of. Each
# entry carries one search key -- the folded name and spellings, one per line --
# so that ?q=athina finds Athens and the answer still says "Athens".
CITIES_BY_SIZE = sorted(
    ((city, "\n".join(normalize_city(n) for n in [city.name, *aliases])) for city, aliases in _AREA),
    key=lambda entry: (-entry[0].population, entry[0].name),
)


# ---------------------------------------------------------------------------
# Models shared by every version
# ---------------------------------------------------------------------------

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


class Pizza(BaseModel):
    """A menu entry of a version that knows no availability (v1-v4)."""
    id: int = Field(description="Stable id -- the value `POST /order` expects as `pizza_id`.")
    name: str


class PizzaWithAvailability(Pizza):
    """A menu entry of a version in which pizzas sell out (v5, v6, latest)."""
    available: bool = Field(description=(
        "Whether the kitchen can bake it *in this minute*. Two pizzas are false at any "
        "time; which two changes every minute, at random."))


# ---------------------------------------------------------------------------
# One FastAPI application per version
# ---------------------------------------------------------------------------

def _description(version: Version) -> str:
    lines = [
        "A small ordering API for the *Question Answering & Chatbots* courses: read the menu, "
        "validate a delivery address, place an order, follow it up.",
        "",
        f"**This is version `{version.key}`**, the service {version.exercise}. {version.notes}",
        "",
        (f"The delivery area is {AREA_SUMMARY} -- about {len(CITIES):,} places; Greek places are "
         "accepted in their other spellings too (Athina, Αθήνα)." if version.area == "full" else
         "The delivery area is " + ", ".join(COURSE_CITIES) + "; Greek places are accepted in "
         "their other spellings too (Athina, Αθήνα).")
        + " Every endpoint is listed below and can be tried out directly from this page.",
    ]
    if version.key == "latest":
        lines += ["", "Every exercise has its own version, which does not change once published:", ""]
        lines += [f"* [`{v.key}`]({v.key}/) -- {v.exercise}" for v in VERSIONS]
    else:
        lines += ["", "Other versions: [latest](../) " + " ".join(
            f"[`{v.key}`](../{v.key}/)" for v in VERSIONS if v.key != version.key)]
    return "\n".join(lines)


def build_app(version: Version, **fastapi_options) -> FastAPI:
    """The service as `version` defines it -- its own menu, endpoints, orders and docs."""
    menu = version.menu
    menu_ids = {pizza["id"] for pizza in menu}
    sells_out = version.sold_out_per_minute > 0
    orders: dict = {}

    app = FastAPI(
        title="Pizza API" if version.key == "latest" else f"Pizza API {version.key}",
        description=_description(version),
        version=version.number,
        **fastapi_options,
    )

    @app.get("/", include_in_schema=False)
    async def api_documentation(request: Request):
        """Serve the interactive documentation at the version's own URL.

        The schema is referenced through the root path of this request, so the
        page works behind the /pizza-api proxy prefix, for every mounted version
        (/pizza-api/v1), and when the container is called directly on its port.
        """
        root = request.scope.get("root_path", "").rstrip("/")
        return get_swagger_ui_html(
            openapi_url=f"{root}/openapi.json",
            title=f"{app.title} - interactive documentation",
        )

    if sells_out:
        @app.get("/pizza", response_model=List[PizzaWithAvailability])
        async def list_pizzas(response: Response):
            """The menu: every pizza, and whether it can be ordered in this minute.

            The list is always complete -- a sold-out pizza is still on the menu,
            with `"available": false`. Exactly two pizzas are unavailable at any
            time; which two is drawn at random once per minute (UTC), so every
            request within the same minute gets the same answer and the next
            minute may get another.

            Two headers say which minute the answer belongs to:

                X-Availability-Minute        start of that minute, e.g. 2026-09-23T10:41:00Z
                X-Availability-Valid-Until   start of the next one -- ask again after it

            Read availability when you need it, not once at start-up: a pizza
            that was available a moment ago may not be any more.
            """
            minute = current_minute()
            sold_out = sold_out_ids(minute, menu, version.sold_out_per_minute)
            response.headers["X-Availability-Minute"] = minute_iso(minute)
            response.headers["X-Availability-Valid-Until"] = minute_iso(minute + 1)
            response.headers["Cache-Control"] = "no-store"
            return [PizzaWithAvailability(**pizza, available=pizza["id"] not in sold_out)
                    for pizza in menu]
    else:
        @app.get("/pizza", response_model=List[Pizza])
        async def list_pizzas():
            """The menu: every pizza, with the id `POST /order` expects.

            In this version every pizza on the menu can always be ordered.
            """
            return [Pizza(**pizza) for pizza in menu]

    if version.city_endpoint:
        @app.get("/city", response_model=List[City])
        async def list_cities(
            response: Response,
            q: Optional[str] = Query(None, description=(
                "Substring of the city name, accent- and case-insensitive; other spellings of "
                "a Greek place match too (athina finds Athens).")),
            limit: int = Query(100, ge=1, le=1000, description="How many cities to return (1-1000)."),
            offset: int = Query(0, ge=0, description="How many to skip -- page through the whole area."),
        ):
            """The delivery area: the cities this service delivers to.

            Every commune of France, every town and village of Greece, plus
            Leipzig, Halle and Dresden. That is about 43 000 names, so the answer
            is a page and not the whole list: the largest cities come first, `q`
            searches by name, and `X-Total-Count` says how many matched. Nothing
            here is a secret -- page through it if you want all of it.

                GET /city                      the 100 largest
                GET /city?q=saint&limit=20     the 20 largest whose name contains "saint"
                GET /city?q=athina             Athens -- found by another spelling
                GET /city?limit=1000&offset=1000   the second page of a thousand

            The search is folded the same way `POST /address/validate` folds a
            city name, so anything this endpoint returns is something that
            endpoint accepts.
            """
            matching = CITIES_BY_SIZE
            if q:
                needle = normalize_city(q)
                matching = [entry for entry in matching if needle in entry[1]]
            response.headers["X-Total-Count"] = str(len(matching))
            return [city for city, _ in matching[offset:offset + limit]]

    if version.area == "course":
        accepted = ACCEPTED_COURSE_CITIES
        refusal = "We don't deliver to {city}. Available cities: " + ", ".join(COURSE_CITIES)
    else:
        accepted = ACCEPTED_CITIES
        refusal = (f"We don't deliver to {{city}}. We deliver to {len(CITIES)} places -- "
                   f"{AREA_SUMMARY}.")
        if version.city_endpoint:
            refusal += " Look yours up with GET /city?q={query}"

    @app.post("/address/validate")
    async def validate_address(address: Address):
        """Validate a delivery address: 200 if we deliver there, 400 if not.

        The city is compared accent- and case-insensitively, and a Greek place
        is accepted in any of its known spellings.
        """
        if normalize_city(address.city) not in accepted:
            raise HTTPException(
                status_code=400,
                detail=refusal.format(city=address.city, query=address.city[:40]),
            )
        if len(address.street) < 2:
            raise HTTPException(status_code=400, detail="Invalid street name")
        if not address.house_number:
            raise HTTPException(status_code=400, detail="House number is required")
        return {"message": "Address is valid", "address": address}

    async def create_order(order: OrderCreate, accept_everything: bool = False):
        if order.pizza_id not in menu_ids:
            raise HTTPException(status_code=404, detail="Pizza not found")
        pizza = next(pizza for pizza in menu if pizza["id"] == order.pizza_id)
        # Sold out in this minute: the request is valid and the pizza exists,
        # but it conflicts with the current state of the kitchen -- 409, not 404
        # or 400.
        if sells_out and not accept_everything:
            minute = current_minute()
            if pizza["id"] in sold_out_ids(minute, menu, version.sold_out_per_minute):
                raise HTTPException(
                    status_code=409,
                    detail=(f"{pizza['name']} (id {pizza['id']}) is sold out right now, until "
                            f"{minute_iso(minute + 1)}. GET /pizza lists what is available."),
                )
        address = Address(city=order.city, street=order.street, house_number=order.house_number)
        await validate_address(address)
        order_id = str(uuid.uuid4())
        orders[order_id] = Order(id=order_id, pizza_id=order.pizza_id, address=address,
                                 status=OrderStatus.RECEIVED)
        return {"order_id": order_id, "status": OrderStatus.RECEIVED}

    if sells_out:
        @app.post("/order")
        async def place_order(
            order: OrderCreate,
            x_accept_everything: Optional[str] = Header(None, description=(
                "Test drivers only: `true` lets an order for a pizza that is sold out in this "
                "minute through. A chatbot must never send it.")),
        ):
            """Place an order -- if the pizza can be had in this minute.

            404 when the pizza id does not exist, **409 Conflict** when it exists
            but is sold out right now (`"available": false` in `GET /pizza`), 400
            when the address is outside the delivery area. A 409 is not a broken
            request: the same order may succeed in the next minute, or with
            another pizza.

            Test drivers that order fixed pizza ids send `X-Accept-Everything:
            true`, so their result does not depend on the minute they run in.
            """
            accept = (x_accept_everything or "").strip().lower() == "true"
            return await create_order(order, accept_everything=accept)
    else:
        @app.post("/order")
        async def place_order(order: OrderCreate):
            """Place an order: 404 for an unknown pizza id, 400 for an address outside the area."""
            return await create_order(order)

    @app.get("/order/{order_id}")
    async def get_order_status(order_id: str):
        """Get an order's status by its id -- orders are kept per version."""
        if order_id not in orders:
            raise HTTPException(status_code=404, detail="Order not found")
        stored = orders[order_id]
        return {"order_id": order_id, "status": stored.status, "pizza_id": stored.pizza_id,
                "address": stored.address}

    return app


class AcceptUnprefixedPaths:
    """Answer /pizza as well as /pizza-api/pizza, /v1/pizza as well as /pizza-api/v1/pizza.

    The reverse proxy passes the full path (/pizza-api/v1/pizza) and the app is
    configured with that root path. Called directly on its port -- a container
    you just built, `verify-pizza-api.sh http://127.0.0.1:8000` -- the prefix is
    missing, and Starlette does not find a mounted version under a root path it
    was not given. So an unprefixed path gets the prefix before routing.
    """

    def __init__(self, app, prefix: str):
        self.app, self.prefix = app, prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope["path"]
            if path != self.prefix and not path.startswith(self.prefix + "/"):
                scope = {**scope, "path": self.prefix + path,
                         "raw_path": (self.prefix + path).encode()}
        await self.app(scope, receive, send)


# The default is the latest version; every frozen version is mounted beside it.
app = build_app(LATEST, root_path="/pizza-api")


def _slash_redirect(key: str):
    async def redirect():
        # Relative on purpose: behind the proxy the absolute URL is not ours to
        # build. "v1/" resolved against ".../pizza-api/v1" is ".../pizza-api/v1/".
        return RedirectResponse(url=f"{key}/", status_code=307)
    return redirect


for _version in VERSIONS:
    app.add_api_route(f"/{_version.key}", _slash_redirect(_version.key), include_in_schema=False)
    app.mount(f"/{_version.key}", build_app(_version))

app.add_middleware(AcceptUnprefixedPaths, prefix="/pizza-api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
