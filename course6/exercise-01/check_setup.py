"""Preparation -- does this machine have everything the exercise needs?

    python check_setup.py

Run this right after the lecture, before your break: an installation that goes
wrong costs you the first twenty minutes of the session. Eleven checks, each
printing [ ok ] or [fail] and, when it fails, the one command that fixes it.
The script exits with code 1 if anything failed.

One check is allowed to stay red until the end of the session: the LLM endpoint
belongs to Task 8, which you may also do at home.

Nothing here is magic: every check is three lines you could type yourself.
"""

from __future__ import annotations

import os
import sys
from importlib import import_module

RESULTS: list[tuple[str, str]] = []


def _installed_version(package: str) -> str:
    """Some packages carry no __version__ attribute -- ask the package metadata."""
    try:
        from importlib.metadata import version

        return version(package)
    except Exception:  # noqa: BLE001
        return "?"


def check(name: str, ok: bool, detail: str = "", fix: str = "", deferred: bool = False) -> bool:
    """Print one result line. `deferred` = not done yet, and that is fine for now."""
    state = "ok" if ok else ("todo" if deferred else "fail")
    RESULTS.append((state, name))
    print(f"[{state:4s}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok and fix:
        print(f"       {'when you get there' if deferred else 'fix'}: {fix}")
    return ok


def check_console_unicode() -> None:
    """Can this console print an accented city name?

    Every example address in the exercise is 5 Rue Michelet, Saint-Étienne. On a
    Windows console still set to a legacy code page, printing that raises
    UnicodeEncodeError -- and without this check it would raise for the first
    time in Task 5, an hour into the session instead of during preparation.
    """
    probe = "Saint-Étienne"
    encoding = sys.stdout.encoding or "utf-8"
    try:
        probe.encode(encoding)
        check(f"the console can print {probe}", True, detail=f"encoding: {encoding}")
    except UnicodeEncodeError:
        check(
            "the console can print Saint-Etienne with its accent", False,
            detail=f"this console encodes {encoding}",
            fix=("cmd.exe    :  set PYTHONUTF8=1\n"
                 "            PowerShell :  $env:PYTHONUTF8=1\n"
                 "            then run this script again in the SAME window"),
        )


def check_empty_patch() -> None:
    """A node returning {} must be accepted -- that is this exercise's failure rule.

    Every component in the exercise says "nothing recognised -> return {}", and
    the router node is `lambda state: {}`. Older LangGraph versions reject an
    empty update with InvalidUpdateError, which would break Task 3 with an error
    message that names neither the cause nor the fix.
    """
    try:
        from typing import TypedDict

        from langgraph.graph import END, START, StateGraph

        class State(TypedDict):
            value: int

        workflow = StateGraph(State)
        workflow.add_node("silent", lambda state: {})      # the failure rule
        workflow.add_edge(START, "silent")
        workflow.add_edge("silent", END)
        result = workflow.compile().invoke({"value": 1})
        check("a node may return {} (the 'nothing recognised' rule)", result["value"] == 1)
    except Exception as error:  # noqa: BLE001
        check(
            "a node may return {} (the 'nothing recognised' rule)", False,
            detail=f"{type(error).__name__}: {error}",
            fix="your langgraph is too old: pip install -r requirements.txt --upgrade",
        )


def check_python() -> None:
    version = sys.version_info
    check(
        f"Python {version.major}.{version.minor}.{version.micro}",
        version >= (3, 10),
        detail=sys.executable,
        fix="install Python 3.10 or newer and recreate the virtual environment",
    )


def check_packages() -> None:
    for module, package in [
        ("langgraph", "langgraph"),
        ("langchain_core", "langchain-core"),
        ("requests", "requests"),
        ("dotenv", "python-dotenv"),
        ("openai", "openai"),
    ]:
        try:
            imported = import_module(module)
            version = getattr(imported, "__version__", None) or _installed_version(package)
            check(f"import {module}", True, detail=f"version {version}")
        except ImportError as error:
            check(f"import {module}", False, detail=str(error), fix="pip install -r requirements.txt")
    try:
        import_module("grandalf")
        check("import grandalf (ASCII diagrams)", True)
    except ImportError:
        check("import grandalf (ASCII diagrams)", False, detail="optional", fix="pip install grandalf")


def check_graph_runs() -> None:
    """The real test: build, compile and run a two-node graph."""
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
        check("run a two-node LangGraph", result["value"] == 41, detail=f"20 -> double -> +1 -> {result['value']}")
    except Exception as error:  # noqa: BLE001 -- we want to report anything
        check("run a two-node LangGraph", False, detail=f"{type(error).__name__}: {error}",
              fix="pip install -r requirements.txt")


def check_mermaid() -> None:
    """Can we export the process model? (Task 2 needs this.)"""
    try:
        from demo_hello_graph import build_graph

        mermaid = build_graph().get_graph().draw_mermaid()
        check("export a Mermaid diagram", "graph TD" in mermaid, detail=f"{len(mermaid)} characters")
    except Exception as error:  # noqa: BLE001
        check("export a Mermaid diagram", False, detail=f"{type(error).__name__}: {error}")


def check_pizza_api() -> None:
    from pizzabot import pizza_api

    ok, detail = pizza_api.ping()
    check(
        f"Pizza API at {pizza_api.BASE}",
        ok,
        detail=detail,
        fix=("start the local stub in a second terminal:  python pizza_api_stub.py\n"
             "            and then:  PIZZA_API_BASE=http://127.0.0.1:8000 python check_setup.py"),
    )


def check_llm_config() -> None:
    """Only the configuration -- check_llm.py does the real call."""
    base = os.environ.get("OPENAI_API_BASE") or os.environ.get("ILAAS_INFERENCE_BASE_URL")
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ILAAS_API_KEY")
    check(
        "LLM endpoint configured",
        bool(base and key),
        detail=f"base={base or '(unset)'} key={'set' if key else '(unset)'}",
        fix="copy .env.example to .env, paste the key, then run python check_llm.py",
        deferred=True,          # belongs to Task 8; staying open here is expected
    )


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()          # read .env if it exists; real env variables win
    except ImportError:
        pass

    print("Exercise 1 -- environment check\n")
    check_python()
    check_console_unicode()
    check_packages()
    check_graph_runs()
    check_empty_patch()
    check_mermaid()
    check_pizza_api()
    check_llm_config()

    passed = [name for state, name in RESULTS if state == "ok"]
    deferred = [name for state, name in RESULTS if state == "todo"]
    failed = [name for state, name in RESULTS if state == "fail"]

    print()
    print(f"{len(RESULTS)} checks: {len(passed)} passed, "
          f"{len(deferred)} open for later, {len(failed)} failed.")
    if failed:
        print("NOT READY yet -- fix the lines marked [fail] above, they each name the command.")
        sys.exit(1)
    print("READY FOR THE SESSION -- enjoy the break.")


if __name__ == "__main__":
    main()
