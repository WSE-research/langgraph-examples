# Pizza API

A small ordering API used by the *Question Answering & Chatbots* course (HTWK Leipzig) and the guest course in Saint-Étienne ([`course6/`](../course6/)): read the menu, validate a delivery address, place an order, follow it up. `main.py` is the whole service; `llm.py` and `spacy_example.py` are separate example scripts that happen to live in the same folder and are *not* part of the deployed image.

The service is live at <https://wse-research.org/pizza-api>, which serves its own Swagger UI, so the URL that names the API also explains it. It runs on `demos.swe.htwk-leipzig.de` (port 40161) behind [`WSE-research/reverse-proxy-htwk-demos`](https://github.com/WSE-research/reverse-proxy-htwk-demos) (`configs/pizza-api.conf`). The path `https://demos.swe.htwk-leipzig.de/pizza-api` is *not* usable: on that virtual host the demo platform's single-page app shadows it. Same server, same service, only the `wse-research.org` route works.

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

Thirteen checks: the Swagger UI at the base URL, the schema, the ten pizzas with stable ids 1–4, every city of the delivery area including the spellings students actually type (`saint etienne`, `SAINT-ETIENNE`), a refusal outside it, a real order and reading it back, and an unknown order id. Exit code 0 means the deployed version is the current one. Run it after every deployment: a course starts on time or not at all.

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
