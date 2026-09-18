"""Preparation -- does this machine have everything Iteration 3 needs?

    python check_setup.py

Run this right after the lecture, before your break. It is the Iteration 2 check
plus everything the measurement iteration adds: `rdflib`, a knowledge graph that
parses, a generator that can draw a case, an evaluator that can score one, and a
`results/` directory that can be written to.

The check that decides whether today works is the last but one: **one real JSON
extraction through the LLM service**. If it is red, the LLM configuration cannot
be measured -- but the static one still can (`python evaluate.py --config static`),
so the session is not lost. Everything else must be green.

Nothing here is magic: every check is three lines you could type yourself.
"""

from __future__ import annotations

import os
import sys
from importlib import import_module

os.environ.setdefault("LOG_LEVEL", "WARNING")     # the trace of the probe call is noise here

from pizzabot import log                          # noqa: E402  (after LOG_LEVEL)

RESULTS: list[tuple[str, str]] = []


def _installed_version(package: str) -> str:
    try:
        from importlib.metadata import version

        return version(package)
    except Exception:  # noqa: BLE001
        return "?"


def check(name: str, ok: bool, detail: str = "", fix: str = "", deferred: bool = False) -> bool:
    """One result line: green for passed, red for failed, yellow for open on purpose."""
    state = "ok" if ok else ("todo" if deferred else "fail")
    RESULTS.append((state, name))
    {"ok": log.ok, "todo": log.todo, "fail": log.fail}[state](name, detail)
    if not ok and fix:
        log.hint(f"{'when you get there' if deferred else 'fix'}: {fix}")
    return ok


def check_python() -> None:
    version = sys.version_info
    check(f"Python {version.major}.{version.minor}.{version.micro}", version >= (3, 10),
          detail=sys.executable,
          fix="install Python 3.10 or newer and recreate the virtual environment")


def check_console_unicode() -> None:
    """Can this console print an accented city name?

    Half the catalog is French. On a Windows console still set to a legacy code
    page, printing "Saint-Étienne" raises UnicodeEncodeError -- and without this
    check it would raise for the first time inside a benchmark run.
    """
    probe = "Saint-Étienne"
    encoding = sys.stdout.encoding or "utf-8"
    try:
        probe.encode(encoding)
        check(f"the console can print {probe}", True, detail=f"encoding: {encoding}")
    except UnicodeEncodeError:
        check("the console can print Saint-Etienne with its accent", False,
              detail=f"this console encodes {encoding}",
              fix=("cmd.exe    :  set PYTHONUTF8=1\n"
                   "            PowerShell :  $env:PYTHONUTF8=1\n"
                   "            then run this script again in the SAME window"))


def check_packages() -> None:
    for module, package in [
        ("langgraph", "langgraph"),
        ("langchain_core", "langchain-core"),
        ("requests", "requests"),
        ("dotenv", "python-dotenv"),
        ("openai", "openai"),
        ("pydantic", "pydantic"),
        ("rdflib", "rdflib"),                     # new in Iteration 3: the knowledge graph
        ("pytest", "pytest"),
    ]:
        try:
            imported = import_module(module)
            version = getattr(imported, "__version__", None) or _installed_version(package)
            check(f"import {module}", True, detail=f"version {version}")
        except ImportError as error:
            check(f"import {module}", False, detail=str(error), fix="pip install -r requirements.txt")


def check_graph_runs() -> None:
    """The Iteration 1 check: build, compile and run a two-node graph."""
    try:
        from typing import TypedDict

        from langgraph.graph import END, START, StateGraph

        class State(TypedDict):
            value: int

        workflow = StateGraph(State)
        workflow.add_node("double", lambda state: {"value": state["value"] * 2})
        workflow.add_node("increment", lambda state: {"value": state["value"] + 1})
        workflow.add_edge(START, "double")
        workflow.add_edge("double", "increment")
        workflow.add_edge("increment", END)
        result = workflow.compile().invoke({"value": 20})
        check("run a two-node LangGraph", result["value"] == 41,
              detail=f"20 -> double -> +1 -> {result['value']}")
    except Exception as error:  # noqa: BLE001
        check("run a two-node LangGraph", False, detail=f"{type(error).__name__}: {error}",
              fix="pip install -r requirements.txt")


def check_bot_is_complete() -> None:
    """Is there a bot to measure? The material ships the Iteration 2 reference.

    If you brought your own repository, this is the check that tells you whether
    the pieces the harness calls are actually there -- both configurations, built
    from `pizzabot/config.py`, with the two recognizers behind them.
    """
    from pizzabot import config

    for name in (config.STATIC, config.LLM):
        try:
            implementations = config.implementations(name)
            missing = {"pizza_recognition", "address_recognition"} - set(implementations)
            check(f"configuration {name!r}", not missing,
                  detail=", ".join(f"{k}={v.__name__}" for k, v in implementations.items()),
                  fix=f"missing component(s): {sorted(missing)}" if missing else "")
        except Exception as error:  # noqa: BLE001
            check(f"configuration {name!r}", False, detail=f"{type(error).__name__}: {error}",
                  fix="use the reference implementation in pizzabot/ or finish Iteration 2")


def check_pizza_api() -> None:
    from pizzabot import pizza_api

    ok, detail = pizza_api.ping()
    check(f"Pizza API at {pizza_api.BASE}", ok, detail=detail,
          fix=("start the local stub in a second terminal:  python pizza_api_stub.py\n"
               "            and then:  PIZZA_API_BASE=http://127.0.0.1:8000 python check_setup.py"))


def check_city_endpoint() -> None:
    """GET /city -- the endpoint Task 3 picks its cities from.

    It arrived with service version 1.2.0 (2026-09-18). An older API answers 404
    here, and then `benchmark/fetch.py` has nothing to pick from -- which is a
    problem to find now and not in the middle of the session.
    """
    from pizzabot import pizza_api

    try:
        page = pizza_api.cities(q="saint-eti", limit=3)
        area = pizza_api.cities(limit=1)
        check("GET /city (the delivery area)", bool(page),
              detail=f"e.g. {', '.join(city['name'] for city in page)}; "
                     f"largest: {area[0]['name'] if area else '?'}")
    except Exception as error:  # noqa: BLE001
        check("GET /city (the delivery area)", False, detail=f"{type(error).__name__}: {error}",
              fix="the API is older than 1.2.0, or unreachable. The stub has the endpoint: "
                  "python pizza_api_stub.py")


def check_catalog() -> None:
    """The knowledge graph parses, and the numbers in it are the ones we expect."""
    try:
        from benchmark import Catalog

        catalog = Catalog()
        counts = {"pizzas": "PIZZA", "addresses": "ADDRESS", "cities": "CITY", "streets": "STREET"}
        check("the knowledge graph parses", len(catalog) > 0,
              detail=f"{len(catalog)} triples from {len(catalog.sources)} file(s): "
                     + ", ".join(f"{len(catalog.instances(cls))} {word}"
                                 for word, cls in counts.items()))
    except Exception as error:  # noqa: BLE001
        check("the knowledge graph parses", False, detail=f"{type(error).__name__}: {error}",
              fix="a syntax error in benchmark/data/*.ttl -- the message names the line")


def check_generator() -> None:
    """One drawn case, end to end: a sentence, and the value it expects."""
    try:
        from benchmark import Catalog
        from benchmark.generate import capacity, generate

        catalog = Catalog()
        sizes = {name: capacity(catalog, name) for name in ("address_v2", "pizza_v2", "order_v2")}
        case = generate(catalog, "address_v2", n=1, seed=42)[0]
        check("the generator draws a case", bool(case["input"]),
              detail=f"{case['input']!r} -> {case['expected']}")
        check("the catalog can produce enough sentences to measure", min(sizes.values()) >= 20,
              detail=", ".join(f"{name}: {size}" for name, size in sizes.items()),
              fix="add wordings or individuals to benchmark/data/catalog.ttl")
    except Exception as error:  # noqa: BLE001
        check("the generator draws a case", False, detail=f"{type(error).__name__}: {error}")


def check_evaluator() -> None:
    """The scorer, on a case whose answer we already know -- and a writable results/."""
    try:
        from evaluate import RESULTS_DIR, score, wilson

        ok = (score(1, 1, None) and not score(None, 1, None) and score(None, None, None)
              and score({"city": "St. Etienne"}, {"city": "Saint-Étienne"},
                        {"city": ["St. Etienne", "Saint-Étienne"]}))
        low, high = wilson(20, 20)
        check("the evaluator scores and computes an interval", ok and low < 0.9 < high,
              detail=f"20 of 20 is not 1.00 but [{low:.2f}, {high:.2f}] -- that is the point of the interval")

        RESULTS_DIR.mkdir(exist_ok=True)
        probe = RESULTS_DIR / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        check(f"results/ is writable", True, detail=str(RESULTS_DIR))
    except Exception as error:  # noqa: BLE001
        check("the evaluator scores and computes an interval", False,
              detail=f"{type(error).__name__}: {error}")


def check_tests_collect() -> None:
    """`pytest` finds the suite -- and knows the `gate` marker this iteration adds."""
    try:
        import subprocess

        result = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                                capture_output=True, text=True, timeout=120,
                                cwd=os.path.dirname(os.path.abspath(__file__)))
        check("pytest collects the test suite", result.returncode == 0,
              detail=(result.stdout.strip().splitlines() or ["(no output)"])[-1],
              fix="run `pytest -q` and read the first error")
    except Exception as error:  # noqa: BLE001
        check("pytest collects the test suite", False, detail=f"{type(error).__name__}: {error}")


def check_llm_config() -> bool:
    base = os.environ.get("OPENAI_API_BASE") or os.environ.get("ILAAS_INFERENCE_BASE_URL")
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ILAAS_API_KEY")
    return check("LLM endpoint configured", bool(base and key),
                 detail=f"base={base or '(unset)'} key={'set' if key else '(unset)'} "
                        f"model={os.environ.get('MODEL_NAME', '(unset)')}",
                 fix="copy .env.example to .env and paste the key you were given in Iteration 1")


def check_llm_json() -> None:
    """One real call -- the same one Iteration 2 ended with, because today measures it."""
    from pizzabot import llm_service

    service = llm_service.LlmService()
    system = "Answer with a JSON object with exactly the key city. Example: {\"city\": \"Lyon\"}"
    result = service.extract(system, "I live in Saint-Étienne")
    usage = service.usage
    if result is None:
        check("LLM service: one JSON extraction", False,
              detail="the service answered None after all retries",
              fix="run `python check_llm.py`; check the key, the base URL and MODEL_NAME. "
                  "Until it works, measure the baseline: python evaluate.py --config static")
        return
    seconds = usage.latencies[-1] if usage.latencies else 0.0
    check("LLM service: one JSON extraction", isinstance(result, dict) and "city" in result,
          detail=f"{result} in {seconds:.1f} s, {usage.prompt_tokens} tokens in / "
                 f"{usage.completion_tokens} out"
                 + (", answer was fenced (stripped)" if usage.fenced else ""),
          fix="the model answered but not with the key we asked for -- try MODEL_NAME=qwen-3.6-35b-instruct")
    log.hint(f"one call took {seconds:.1f} s. `python evaluate.py -n 10` makes 40 of them "
             f"(10 per method, and the third method calls two components): "
             f"budget roughly {seconds * 40:.0f} s per run.")


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()          # read .env if it exists; real env variables win
    except ImportError:
        pass

    log.title("Exercise 3 -- environment check")
    log.plain()
    check_python()
    check_console_unicode()
    check_packages()
    check_graph_runs()
    check_bot_is_complete()
    check_pizza_api()
    check_city_endpoint()
    check_catalog()
    check_generator()
    check_evaluator()
    check_tests_collect()
    if check_llm_config():
        check_llm_json()
    else:
        check("LLM service: one JSON extraction", False, detail="skipped: no key (see the line above)")

    passed = [name for state, name in RESULTS if state == "ok"]
    deferred = [name for state, name in RESULTS if state == "todo"]
    failed = [name for state, name in RESULTS if state == "fail"]

    log.plain()
    log.plain(f"{len(RESULTS)} checks: {len(passed)} passed, "
              f"{len(deferred)} open for later, {len(failed)} failed.")
    if failed:
        log.warn("NOT READY yet -- fix the lines marked [fail] above, they each name the command.")
        sys.exit(1)
    log.result("READY FOR THE SESSION -- enjoy the break.")


if __name__ == "__main__":
    main()
