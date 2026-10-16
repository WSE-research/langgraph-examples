"""Serve the catalog inside the test environment.

The default path needs no server at all: `Catalog()` reads the Turtle files
in-process, which is what the harness and the tests use. This module is the
upgrade for the case where something has to talk to the data over HTTP -- a
second process, a notebook, the chat frontend, or a team that wants to point
their own SPARQL client at it.

    from benchmark.server import serve
    with serve() as endpoint:          # port 0 -> a free port is chosen
        requests.get(endpoint.url + "/health")

    python -m benchmark.server --port 8030      # or from the command line

Three read-only routes:

    GET  /health            {"status": "ok", "triples": 234}
    GET|POST /sparql        ?query=... -> SPARQL 1.1 JSON results
    GET  /graph             the whole graph as Turtle

Nothing writes: a benchmark that a test run can modify is not a benchmark.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from benchmark.catalog import Catalog

SPARQL_JSON = "application/sparql-results+json"


class _Handler(BaseHTTPRequestHandler):
    catalog: Catalog = None          # set by serve()

    def do_GET(self) -> None:        # noqa: N802  (http.server's spelling)
        route = urlparse(self.path)
        params = parse_qs(route.query)
        if route.path == "/health":
            self._json(200, {"status": "ok", "triples": len(self.catalog)})
        elif route.path == "/sparql":
            self._sparql(params.get("query", [""])[0])
        elif route.path == "/graph":
            self._text(200, self.catalog.serialize("turtle"), "text/turtle")
        else:
            self._json(404, {"error": f"no route {route.path}"})

    def do_POST(self) -> None:       # noqa: N802
        if urlparse(self.path).path != "/sparql":
            self._json(404, {"error": "only POST /sparql"})
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        self._sparql(parse_qs(body).get("query", [body])[0])

    def _sparql(self, query: str) -> None:
        if not query.strip():
            self._json(400, {"error": "no query given"})
            return
        try:
            result = self.catalog.query(query)
        except Exception as error:                      # a bad query is a 400
            self._json(400, {"error": f"{type(error).__name__}: {error}"})
            return
        payload = result.serialize(format="json")
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        self._text(200, payload, SPARQL_JSON)

    def _json(self, status: int, payload: dict) -> None:
        self._text(status, json.dumps(payload), "application/json")

    def _text(self, status: int, body: str, content_type: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_args) -> None:
        """Quiet: a test run is not a web server log."""


class Endpoint:
    """A running server, and the URL the test environment talks to."""

    def __init__(self, httpd: ThreadingHTTPServer, thread: threading.Thread, catalog: Catalog):
        self.httpd, self.thread, self.catalog = httpd, thread, catalog
        host, port = httpd.server_address[:2]
        self.url = f"http://{host}:{port}"

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def __enter__(self) -> "Endpoint":
        return self

    def __exit__(self, *_exc) -> None:
        self.stop()


def serve(catalog: Catalog | None = None, host: str = "127.0.0.1", port: int = 0) -> Endpoint:
    """Start the endpoint in a background thread. `port=0` picks a free port."""
    handler = type("_BoundHandler", (_Handler,), {"catalog": catalog or Catalog()})
    httpd = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=httpd.serve_forever, name="catalog-server", daemon=True)
    thread.start()
    return Endpoint(httpd, thread, handler.catalog)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8030)
    args = parser.parse_args()

    endpoint = serve(host=args.host, port=args.port)
    print(f"catalog: {endpoint.catalog}")                      # a CLI may print
    print(f"serving {endpoint.url}/sparql  (Ctrl-C to stop)")
    try:
        endpoint.thread.join()
    except KeyboardInterrupt:
        endpoint.stop()


if __name__ == "__main__":
    main()
