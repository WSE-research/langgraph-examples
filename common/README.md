# Pizza API

A small ordering API used by the *Question Answering & Chatbots* course (HTWK Leipzig) and by the guest course *Engineering AI-Driven Software Processes* ([`course5/`](../course5/), the Athens edition, and [`course6/`](../course6/)): read the menu and what is sold out this minute, browse the delivery area, validate a delivery address, place an order, follow it up. `main.py` is the whole service; `llm.py` and `spacy_example.py` are separate example scripts that happen to live in the same folder and are *not* part of the deployed image.

The service is live at <https://wse-research.org/pizza-api>, which serves its own Swagger UI, so the URL that names the API also explains it. It runs on `demos.swe.htwk-leipzig.de` (port 40216, registered with the updater as `wse-research-langgraph-examples`) behind [`WSE-research/reverse-proxy-htwk-demos`](https://github.com/WSE-research/reverse-proxy-htwk-demos) (`configs/pizza-api.conf`). The path `https://demos.swe.htwk-leipzig.de/pizza-api` is *not* usable: on that virtual host the demo platform's single-page app shadows it. Same server, same service, only the `wse-research.org` route works.

## Versions: one per exercise

Every exercise of the course uses its **own version** of the service, and a version does **not change** once it is published. The service grew under the exercises — ten more pizzas, all of France and then Greece, a city endpoint, pizzas that sell out — and every change used to be checked against the material of its day; but a student who runs Exercise 1 in December runs it against the service of December. Since 2026-09-30 each exercise names its version in the default of `PIZZA_API_BASE`, and the service keeps every version it ever published beside the newest one.

| URL | exercise | menu | sells out | `GET /city` | delivery area |
| --- | --- | --- | --- | --- | --- |
| <https://wse-research.org/pizza-api/v1> | Exercise 1 — from goals to processes | 10 pizzas, `id` and `name` | never | — | the nine cities of the course examples: Leipzig, Halle, Dresden, Saint-Étienne, Saint-Priest-en-Jarez, Lyon, Athens, Piraeus, Agia Paraskevi (and the other spellings of the Greek three); `400 … Available cities: …` for anything else |
| <https://wse-research.org/pizza-api/v2> | Exercise 2 — LLMs as services | 22 pizzas, `id` and `name` | never | yes | full |
| <https://wse-research.org/pizza-api/v3> | Exercise 3 — manifesting application quality | as v2 | never | yes | full |
| <https://wse-research.org/pizza-api/v4> | Exercise 4 — dynamic data and flexible processes | as v2 | never | yes | full |
| <https://wse-research.org/pizza-api/v5> | Exercise 5 — explainability, trust, and repair | 22 pizzas, `id`, `name`, `available` | two per minute, `409` | yes | full |
| <https://wse-research.org/pizza-api/v6> | Exercise 6 — RAG, hybrid QA, and the outlook | as v5 | two per minute, `409` | yes | full |
| <https://wse-research.org/pizza-api> | none — the newest version (1.4.0) | as v5 | two per minute, `409` | yes | full |

Why v1–v4 never sell out: the Iteration 1–4 processes have no answer to a sold-out pizza — `place_order` is given, not a task, and a 409 ends the dialog with a misleading *the Pizza API did not answer* — so a sold-out pizza in those exercises is a failure the student cannot fix. It becomes the lesson in Iteration 5, which is where it starts. Why v1 has ten pizzas and nine cities: that is what the Exercise 1 sheet and its stub document, and on twenty-two names the Iteration 1 fuzzy recognizer starts finding pizzas in addresses (`…Rue de la Station…` → Quattro Stagioni).

How it is built: `VERSIONS` in `main.py` lists every published version as a frozen record (menu size, whether pizzas sell out, whether `GET /city` exists, which area); `build_app()` makes one FastAPI application of each, and the application of the newest version (`LATEST`) mounts all the others under their key. Each version has its own Swagger UI at its own URL, its own OpenAPI document and its own order store (an order placed through v2 is read back through v2). The menu is one list of which a version serves a prefix — which is why pizzas are only ever appended. The delivery area is shared; the tests pin every city an exercise relies on, so a refresh of `data/cities.tsv.gz` that would break an exercise fails in CI first.

**Changing the service:** new behaviour goes into `LATEST`. When an exercise needs it, add a new version to `VERSIONS` (v7 …), point that exercise at it, and add its row to `tests/test_versions.py`. Never edit a published version — the tests say so, because they state every published version's menu and rules literally instead of reading them from `main.py`.

## Tests

```bash
pip install -r requirements-service.txt -r requirements-test.txt
pytest tests/                     # ~800 tests, in-process, ~15 s
```

- `tests/test_versions.py` — every version against its published contract: the menu, the fields, the availability rule (simulated over many minutes, including the check order 404 → 409 → 400 and the draw of 1.3.0), the delivery area with the spellings the courses use and the refusals they rely on, `GET /city`, orders, the documentation at each version's own URL.
- `tests/test_exercise_material.py` — reads `course5/` and `course6/`: every service URL inside an exercise names that exercise's version (and no other), exercise 1's client and `.env.example` default to v1, every exercise 2–6 ships an adapter `pizzabot/pizza_api.py` whose `VERSION` is its own and which ignores a `PIZZA_API_BASE` naming another version, no `.env.example` from exercise 2 on pins a version, the Iteration 4/5 `tests/conftest.py` stops the run while the adapter is an older one, the sheets of Exercises 2–6 tell the team to take the adapter and delete the old line, Exercise 6 names the RAG client (`rag_client.RagClient`) and its settings as the slides do, the menu snapshots and the knowledge graphs join on the ids of the version, every `:deliverable` flag of the Exercise 3 catalog is what v3 answers, and every city the material writes as data (`"city": "…"` in code, tests and benchmark files) is delivered to by its version.
- `tests/test_stubs.py` — starts the offline stub of Exercises 1–3 of both editions as a real process and asks it what the service is asked: the same menu, the same accept/refuse decisions and the same refusal text, every pizza orderable, the same `GET /city` answers.

`.github/workflows/test_pizza_api.yml` runs them on every pull request that touches `common/`, `course5/` or `course6/`, then starts the service and runs `verify-pizza-api.sh` against it; the deployment workflow runs the same job first and deploys only when it passes.

## Run it locally

```bash
docker build -t pizza-api .
docker run --rm -p 8000:8000 pizza-api
bash verify-pizza-api.sh http://127.0.0.1:8000
```

Without Docker: `pip install -r requirements-service.txt && uvicorn main:app --port 8000`.

## Verify a deployment

```bash
bash verify-pizza-api.sh                        # the live service
bash verify-pizza-api.sh http://127.0.0.1:8000  # a container you just built
```

Forty-six checks. For the newest version: the Swagger UI at the base URL, the schema, the twenty-two pizzas with stable ids, exactly two of them unavailable and the same two for two requests within one minute, `GET /city` (search, paging, `X-Total-Count`, largest first), cities of the delivery area including the spellings students actually type (`saint etienne`, `SAINT-ETIENNE`, `Athina`, `Αθήνα`), a refusal outside it, a real order and reading it back, a sold-out pizza refused with 409 and accepted with `X-Accept-Everything: true`, and an unknown order id. Then, for each of v1 … v6: the size of its menu and whether it sells out, its own Swagger UI, and one accepted city (`Αθήνα`), Paris (refused only by v1) and `GET /city` (absent only in v1). Exit code 0 means the deployed version is the current one. Run it after every deployment: a course starts on time or not at all. The in-process tests (`tests/`) check far more; this script is what can be checked from outside.

## The data

| what | where | how many |
| --- | --- | --- |
| the menu | `main.py`, the `pizzas` list | 22, ids 1–22. Ids are stable: new pizzas are appended, never inserted, because student code and course material refer to them. 11–20 were appended on 2026-09-18, 21–22 (`Ortolana`, `Verdure` — a declared vegetarian and a declared vegan pizza) on 2026-09-20 for the Iteration 4 knowledge graph. The facts *about* a pizza — toppings, dietary flags, who invented it — are not served here: they live in the graph, joined on the id. Whether it can be ordered right now *is* served: see *Availability* below. |
| the delivery area | `data/cities.tsv.gz` | ~43 000: **every commune of France** (from the French government's geo API, Etalab open licence), **every town and village of Greece** (~10 300 names from [GeoNames](https://www.geonames.org), CC BY 4.0, added 2026-09-30 for the Athens edition), plus Leipzig, Halle and Dresden, which the HTWK course has used since 2024. A Greek place carries its other spellings in a fourth column — accented, older transliterations, other languages, Greek script (`Athina`, `Athen`, `Αθήνα` for Athens) — and each is accepted like the name itself. |

`build-cities.py` regenerates the city file from <https://geo.api.gouv.fr/communes> and GeoNames (`python3 build-cities.py GR` refreshes Greece alone and leaves every other row as it is); the result is committed, so the image builds offline and a deployment never waits on somebody else's API. The file is read once at startup and matched accent- and case-folded, exactly as `POST /address/validate` folds what a caller sends; `GET /city?q=` searches the other spellings too and answers with the name (`?q=athina` → `Athens`).

Two consequences worth knowing before you write material against this service. **Paris and Thessaloniki are delivery cities** (except in v1) — until 2026-09-18 Paris was the standard "we do not deliver there" example, and anything that still relies on that will see a 200 where it expects a 400; the exercises use `Barcelona` instead. And **`GET /city` answers a page, not the whole area**: 100 by default, at most 1000, ordered by population, `?q=` to search, `X-Total-Count` for the size of the match.

## Availability: two pizzas sold out, every minute

Since version 1.3.0 (2026-09-23) — and in the versions v5, v6 and the newest one; v1–v4 never sell out and have no such field — every pizza in `GET /pizza` carries a third field, `available` — the service-side counterpart of `pz:available` in the lecture graph:

```json
[{"id": 1, "name": "Margherita", "available": true},
 {"id": 18, "name": "Tartufo", "available": false}, ...]
```

- **Exactly two pizzas are `false` at any time.** Which two is drawn at random once per minute (UTC). Every request within the same minute gets the same two; the next minute draws again, and may draw one of the same pizzas or both.
- **The menu stays complete.** A sold-out pizza is still listed, so a client can recognise the name the guest said and still has to find out that it cannot be had right now. That is the case the repair part of the course is built on: recognised, but not available.
- **Two response headers say which minute an answer belongs to:** `X-Availability-Minute` (its start, e.g. `2026-09-23T10:41:00Z`) and `X-Availability-Valid-Until` (the start of the next one). The response is sent with `Cache-Control: no-store`. A client that caches the menu must not cache the flag beyond that time — and a process should read availability when it needs it, not once at start-up.
- **`POST /order` refuses a sold-out pizza with `409 Conflict`.** The request is well-formed and the pizza exists — so neither 400 nor 404 — but it conflicts with the current state of the kitchen, and the same order may succeed a minute later or with another pizza. The body names the pizza and the minute it is sold out until: `{"detail": "Tartufo (id 18) is sold out right now, until 2026-09-23T10:42:00Z. GET /pizza lists what is available."}`. The checks run in this order: unknown id → 404, sold out → 409, address outside the area → 400.
- **Test drivers send `X-Accept-Everything: true`.** With that request header `POST /order` accepts a sold-out pizza as well. It exists for code that orders *fixed* pizza ids and must not fail in the two minutes out of twenty-two when its pizza happens to be drawn — `verify-pizza-api.sh`, and the tests and validation scripts of the course material, which set `PIZZA_API_ACCEPT_EVERYTHING=true` so that the course's `pizzabot/pizza_api.py` adds the header. A chatbot talking to a guest must never send it: the 409 is exactly what the repair part of Exercise 5 is about.
- **How it is drawn.** The sold-out set is a pure function of a seed, the minute number and the menu (`sold_out_ids()` in `main.py`; v5, v6 and the newest version share the menu, so they draw the same two): no state, no timer, and the same answer from every worker that shares the seed. By default the seed is random per process, so the draw cannot be predicted from the source; a restart of the container starts a new sequence (and may change the set in the middle of a minute). Set `PIZZA_AVAILABILITY_SEED` to make the sequence reproducible for tests or a rehearsed demo:

```bash
docker run --rm -p 8000:8000 -e PIZZA_AVAILABILITY_SEED=demo pizza-api
```

## Deploy

The container is managed by the [microservice-updater](https://github.com/WSE-research/microservice-updater) on its host. A redeploy rebuilds the image from this repository and swaps the container:

```bash
curl -k -X POST "https://<updater-host>:9000/service/$SERVICE_ID" \
     -H 'Content-Type: application/json' \
     -d '{"API-KEY": "'"$UPDATER_KEY"'"}'
curl -k "https://<updater-host>:9000/service/$SERVICE_ID"   # state, and the reason if it failed
bash verify-pizza-api.sh                                     # then prove it from outside
```

The updater's port is not reachable from outside the university network, so this runs on the host or through the VPN. If the build fails, the previous container keeps serving and the state becomes `UPDATE FAILED` — which is why the image has to be *built* successfully before it is deployed, not after.

## Dependencies

`requirements-service.txt` is what the image installs, and it is pinned. Until 2026-09-11 the image was unpinned on `python:3.9-slim`, and the build had quietly stopped working: `spacy` — a dependency of one of the example scripts, not of the service — resolved to a version requiring Python 3.10, so pip could not satisfy it and every rebuild failed. Nobody noticed, because the running container had been built long before. A service a course depends on must rebuild to the same thing tomorrow; upgrade the pins deliberately, rebuild, and run `verify-pizza-api.sh` against the new container before deploying it.

`requirements.txt` stays with the example scripts.
