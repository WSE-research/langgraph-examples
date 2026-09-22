# Pizza API

A small ordering API used by the *Question Answering & Chatbots* course (HTWK Leipzig) and the guest course in Saint-Étienne ([`course6/`](../course6/)): read the menu and what is sold out this minute, browse the delivery area, validate a delivery address, place an order, follow it up. `main.py` is the whole service; `llm.py` and `spacy_example.py` are separate example scripts that happen to live in the same folder and are *not* part of the deployed image.

The service is live at <https://wse-research.org/pizza-api>, which serves its own Swagger UI, so the URL that names the API also explains it. It runs on `demos.swe.htwk-leipzig.de` (port 40216, registered with the updater as `wse-research-langgraph-examples`) behind [`WSE-research/reverse-proxy-htwk-demos`](https://github.com/WSE-research/reverse-proxy-htwk-demos) (`configs/pizza-api.conf`). The path `https://demos.swe.htwk-leipzig.de/pizza-api` is *not* usable: on that virtual host the demo platform's single-page app shadows it. Same server, same service, only the `wse-research.org` route works.

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

Twenty-two checks: the Swagger UI at the base URL, the schema, the twenty-two pizzas with stable ids, exactly two of them unavailable and the same two for two requests within one minute, `GET /city` (search, paging, `X-Total-Count`, largest first), cities of the delivery area including the spellings students actually type (`saint etienne`, `SAINT-ETIENNE`), a refusal outside it, a real order and reading it back, a sold-out pizza refused with 409 and accepted with `X-Accept-Everything: true`, and an unknown order id. Exit code 0 means the deployed version is the current one. Run it after every deployment: a course starts on time or not at all.

## The data

| what | where | how many |
| --- | --- | --- |
| the menu | `main.py`, the `pizzas` list | 22, ids 1–22. Ids are stable: new pizzas are appended, never inserted, because student code and course material refer to them. 11–20 were appended on 2026-09-18, 21–22 (`Ortolana`, `Verdure` — a declared vegetarian and a declared vegan pizza) on 2026-09-20 for the Iteration 4 knowledge graph. The facts *about* a pizza — toppings, dietary flags, who invented it — are not served here: they live in the graph, joined on the id. Whether it can be ordered right now *is* served: see *Availability* below. |
| the delivery area | `data/cities.tsv.gz` | ~32 700: **every commune of France** (from the French government's geo API, Etalab open licence) plus Leipzig, Halle and Dresden, which the HTWK course has used since 2024. |

`build-cities.py` regenerates the city file from <https://geo.api.gouv.fr/communes>; the result is committed, so the image builds offline and a deployment never waits on somebody else's API. The file is read once at startup and matched accent- and case-folded, exactly as `POST /address/validate` folds what a caller sends.

Two consequences worth knowing before you write material against this service. **Paris is now a delivery city** — until 2026-09-18 it was the standard "we do not deliver there" example, and anything that still relies on that will see a 200 where it expects a 400; the exercises use `Barcelona` instead. And **`GET /city` answers a page, not the whole area**: 100 by default, at most 1000, ordered by population, `?q=` to search, `X-Total-Count` for the size of the match.

## Availability: two pizzas sold out, every minute

Since version 1.3.0 (2026-09-23) every pizza in `GET /pizza` carries a third field, `available` — the service-side counterpart of `pz:available` in the lecture graph:

```json
[{"id": 1, "name": "Margherita", "available": true},
 {"id": 18, "name": "Tartufo", "available": false}, ...]
```

- **Exactly two pizzas are `false` at any time.** Which two is drawn at random once per minute (UTC). Every request within the same minute gets the same two; the next minute draws again, and may draw one of the same pizzas or both.
- **The menu stays complete.** A sold-out pizza is still listed, so a client can recognise the name the guest said and still has to find out that it cannot be had right now. That is the case the repair part of the course is built on: recognised, but not available.
- **Two response headers say which minute an answer belongs to:** `X-Availability-Minute` (its start, e.g. `2026-09-23T10:41:00Z`) and `X-Availability-Valid-Until` (the start of the next one). The response is sent with `Cache-Control: no-store`. A client that caches the menu must not cache the flag beyond that time — and a process should read availability when it needs it, not once at start-up.
- **`POST /order` refuses a sold-out pizza with `409 Conflict`.** The request is well-formed and the pizza exists — so neither 400 nor 404 — but it conflicts with the current state of the kitchen, and the same order may succeed a minute later or with another pizza. The body names the pizza and the minute it is sold out until: `{"detail": "Tartufo (id 18) is sold out right now, until 2026-09-23T10:42:00Z. GET /pizza lists what is available."}`. The checks run in this order: unknown id → 404, sold out → 409, address outside the area → 400.
- **Test drivers send `X-Accept-Everything: true`.** With that request header `POST /order` accepts a sold-out pizza as well. It exists for code that orders *fixed* pizza ids and must not fail in the two minutes out of twenty-two when its pizza happens to be drawn — `verify-pizza-api.sh`, and the tests and validation scripts of the course material, which set `PIZZA_API_ACCEPT_EVERYTHING=true` so that the course's `pizzabot/pizza_api.py` adds the header. A chatbot talking to a guest must never send it: the 409 is exactly what the repair part of Exercise 5 is about.
- **How it is drawn.** The sold-out set is a pure function of a seed and the minute number (`unavailable_ids()` in `main.py`): no state, no timer, and the same answer from every worker that shares the seed. By default the seed is random per process, so the draw cannot be predicted from the source; a restart of the container starts a new sequence (and may change the set in the middle of a minute). Set `PIZZA_AVAILABILITY_SEED` to make the sequence reproducible for tests or a rehearsed demo:

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
