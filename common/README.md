# Pizza API

A small ordering API used by the *Question Answering & Chatbots* course (HTWK Leipzig) and the guest course in Saint-Étienne ([`course6/`](../course6/)): read the menu, browse the delivery area, validate a delivery address, place an order, follow it up. `main.py` is the whole service; `llm.py` and `spacy_example.py` are separate example scripts that happen to live in the same folder and are *not* part of the deployed image.

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

Eighteen checks: the Swagger UI at the base URL, the schema, the twenty-two pizzas with stable ids, `GET /city` (search, paging, `X-Total-Count`, largest first), cities of the delivery area including the spellings students actually type (`saint etienne`, `SAINT-ETIENNE`), a refusal outside it, a real order and reading it back, and an unknown order id. Exit code 0 means the deployed version is the current one. Run it after every deployment: a course starts on time or not at all.

## The data

| what | where | how many |
| --- | --- | --- |
| the menu | `main.py`, the `pizzas` list | 22, ids 1–22. Ids are stable: new pizzas are appended, never inserted, because student code and course material refer to them. 11–20 were appended on 2026-09-18, 21–22 (`Ortolana`, `Verdure` — a declared vegetarian and a declared vegan pizza) on 2026-09-20 for the Iteration 4 knowledge graph. The facts *about* a pizza — toppings, dietary flags, who invented it — are not served here: they live in the graph, joined on the id. |
| the delivery area | `data/cities.tsv.gz` | ~32 700: **every commune of France** (from the French government's geo API, Etalab open licence) plus Leipzig, Halle and Dresden, which the HTWK course has used since 2024. |

`build-cities.py` regenerates the city file from <https://geo.api.gouv.fr/communes>; the result is committed, so the image builds offline and a deployment never waits on somebody else's API. The file is read once at startup and matched accent- and case-folded, exactly as `POST /address/validate` folds what a caller sends.

Two consequences worth knowing before you write material against this service. **Paris is now a delivery city** — until 2026-09-18 it was the standard "we do not deliver there" example, and anything that still relies on that will see a 200 where it expects a 400; the exercises use `Barcelona` instead. And **`GET /city` answers a page, not the whole area**: 100 by default, at most 1000, ordered by population, `?q=` to search, `X-Total-Count` for the size of the match.

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
