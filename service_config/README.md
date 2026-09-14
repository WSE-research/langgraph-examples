# Deployment of the Pizza API

`service_config.json` is the payload the [microservice-updater](https://github.com/WSE-research/microservice-updater) needs to build and run the Pizza API. `.github/workflows/deploy_service.yml` sends it on every push to `main` that touches `common/`.

**`mode: docker`** — the updater clones this repository and builds the image itself from `common/Dockerfile`; `docker_root` is that build context. There is no image on Docker Hub, and the course does not need one: the source of truth is this repository.

**The service id is derived, not chosen.** The updater action builds it from the clone URL, so this registration is `wse-research-langgraph-examples`. Use that id when asking the updater about the deployment state:

    curl -sk "$UPDATER_HOST/service/wse-research-langgraph-examples"

**Port 40216.** The extended version deliberately does *not* take 40161. That port is held by a container that predates this configuration and is not registered with the updater, so a registration binding it would fail. 40216 was free when this was written (40162 and 40163 are in use by other, unproxied containers). Once the reverse proxy points at 40216 and the extended version is confirmed live, the old container on 40161 can be removed by hand on the host.

The public URL `https://wse-research.org/pizza-api` is the reverse proxy in `WSE-research/reverse-proxy-htwk-demos`, `configs/pizza-api.conf`; that file decides which port the outside world reaches.

**After every deployment run `common/verify-pizza-api.sh`** — against the container's own port while cutting over, against the public URL afterwards. Exit code 0 means the deployed version is the current one.
