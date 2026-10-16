"""The factoid benchmark: cases drawn from the graph, four metrics, one report. GIVEN.

Copy to `my-pizzabot/factoid_benchmark.py`.

    python factoid_benchmark.py                 # every case, static configuration
    python factoid_benchmark.py --config llm    # the other implementation
    python factoid_benchmark.py -n 20 --seed 7  # a sample, reproducibly
    python factoid_benchmark.py --show          # print every case and stop

Iteration 3 measured two *recognizers* against sentences drawn from a catalog.
This measures a *process* against questions drawn from the same graph it
answers out of -- and nobody typed an expected value. `pizzas_with_flag(...)`
is the call your `query_construction` makes, so the benchmark and the bot read
one source; a pizza added to the menu adds cases here on its own.

**Four numbers, not one**, because your process has four nodes and "the bot was
wrong" is not a sentence anybody can act on:

    entities_linked    did entity_linking find the right things?
    template_chosen    did query_construction pick the right question type?
    answer_set         did the answer contain exactly the right pizzas?
    honest_refusal     when there was no answer, did it say so -- without
                       inventing one?

The last one has its own number on purpose. A process that answers everything
scores well on the first three and is useless: **2 of 22** pizzas have an
inventor in the graph, so twenty of those questions have no answer, and a bot
that produces a plausible name for them is confidently wrong about a checkable
fact. `honest_refusal` is the metric that notices.

The confidence interval is Iteration 3's `wilson()`, imported rather than
copied: 20 of 20 is not 1.00, it is [0.84, 1.00], and a threshold is compared
against the *lower* end.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date
from pathlib import Path

from pizzabot import kb

try:                                    # Iteration 3's harness, reused
    from evaluate import wilson
except ImportError:                     # pragma: no cover - standalone fallback
    def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
        if n == 0:
            return 0.0, 1.0
        p = hits / n
        d = 1 + z * z / n
        c = p + z * z / (2 * n)
        s = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
        return max(0.0, (c - s) / d), min(1.0, (c + s) / d)


HERE = Path(__file__).resolve().parent
FLAG_WORDS = {
    "vegan": ("vegan", True),
    "vegetarian": ("vegetarian", True),
    "without milk": ("containsMilk", False),
    "free of meat": ("containsMeat", False),
    "free of fish": ("containsFish", False),
    "without egg": ("containsEgg", False),
}


# =========================================================================
# the cases -- generated, never typed
# =========================================================================


def cases() -> list[dict]:
    """Every case the current graph supports. Grows when the menu grows.

    A case is what the process has to get right, in four parts:

        template    the question type query_construction must pick
        entities    the local names entity_linking must find
        answer      the local names the answer must be about -- or None,
                    which means "there is no answer and saying so is correct"
    """
    pizzas = kb.all_pizzas()
    out: list[dict] = []

    # --- set questions over the whole menu --------------------------------
    out.append({"id": "menu", "utterance": "What pizzas do you have?",
                "template": "menu", "entities": [],
                "answer": sorted(p["local"] for p in pizzas)})

    for word, (prop, value) in FLAG_WORDS.items():
        out.append({"id": f"flag/{prop}={value}",
                    "utterance": f"Which pizzas are {word}?",
                    "template": "flag", "entities": [],
                    "answer": sorted(p["local"]
                                     for p in kb.pizzas_with_flag(prop, value))})

    # --- one pizza, one fact ---------------------------------------------
    for pizza in pizzas:
        local, name = pizza["local"], pizza["name"]
        out.append({"id": f"toppings/{local}",
                    "utterance": f"What toppings does the {name} have?",
                    "template": "toppings", "entities": [local],
                    "answer": [local]})
        inventor = kb.invented_by(local).get("inventor")
        out.append({"id": f"inventor/{local}",
                    "utterance": f"Who invented the {name}?",
                    "template": "inventor", "entities": [local],
                    "answer": [local] if inventor else None,
                    "note": "no inventor in the graph" if not inventor else inventor})
        out.append({"id": f"about/{local}",
                    "utterance": f"Tell me about the {name}.",
                    "template": "about", "entities": [local], "answer": [local]})

    # --- questions the graph cannot answer, and must refuse ---------------
    for name in ("Napoli", "Calabrese", "Pizza Bianca"):
        out.append({"id": f"unknown/{name}",
                    "utterance": f"What toppings does the {name} have?",
                    "template": "toppings", "entities": [], "answer": None,
                    "note": "not a pizza we have"})
    for utterance in ("How much does the Margherita cost?",
                      "When do you open?",
                      "Which pizza is the spiciest?"):
        out.append({"id": f"no-template/{utterance[:18]}", "utterance": utterance,
                    "template": None, "entities": [], "answer": None,
                    "note": "no template covers this question"})
    return out


# =========================================================================
# running one case
# =========================================================================


def ask(bot, utterance: str) -> dict:
    """One question, from a fresh dialog -- no case may inherit another's state."""
    from pizzabot.state import new_state

    return bot.invoke({**new_state(""), "input": utterance})


def said(state: dict) -> str:
    return " ".join(str(getattr(m, "content", m)) for m in state.get("messages", []))


def judge(case: dict, state: dict) -> dict:
    """The four metrics for one case. A metric that does not apply is None."""
    question = state.get("question") or {}
    linked = {item.get("iri") for item in state.get("linked") or [] if item.get("iri")}
    topic = set(state.get("topic") or [])
    text = said(state).strip()

    result: dict = {"entities_linked": None, "template_chosen": None,
                    "answer_set": None, "honest_refusal": None}

    if case["entities"]:
        result["entities_linked"] = set(case["entities"]) <= linked
    if case["template"] is not None:
        result["template_chosen"] = question.get("type") == case["template"]

    if case["answer"] is None:
        # nothing to answer: it must say something, and claim nothing
        result["honest_refusal"] = bool(text) and not topic
    else:
        result["answer_set"] = topic == set(case["answer"])
    return result


METRICS = ("entities_linked", "template_chosen", "answer_set", "honest_refusal")


def measure(bot, chosen: list[dict]) -> tuple[dict, list[dict]]:
    scores = {metric: [0, 0] for metric in METRICS}     # hits, n
    failures = []
    for case in chosen:
        try:
            state = ask(bot, case["utterance"])
        except Exception as error:                      # a crash is a score of 0
            state = {"messages": [f"(the process raised {error!r})"]}
        verdict = judge(case, state)
        for metric, ok in verdict.items():
            if ok is None:
                continue
            scores[metric][1] += 1
            scores[metric][0] += int(ok)
        if any(ok is False for ok in verdict.values()):
            failures.append({"case": case, "verdict": verdict,
                             "topic": sorted(state.get("topic") or []),
                             "said": said(state)[:160]})
    return scores, failures


# =========================================================================
# the report
# =========================================================================


def report(scores: dict, failures: list[dict], configuration: str,
           total: int, threshold: float) -> str:
    lines = [f"# Factoid quality report — {date.today().isoformat()}", "",
             f"Configuration **{configuration}**, {total} cases generated from "
             f"`data/menu-facts.ttl` ({len(kb.all_pizzas())} pizzas). "
             f"Nothing on this page was typed by hand: change the graph and "
             f"every number here changes with it.", "",
             "| metric | cases | passed | rate | 95% CI | gate |",
             "| --- | --- | --- | --- | --- | --- |"]
    gate_ok = True
    for metric in METRICS:
        hits, n = scores[metric]
        if not n:
            lines.append(f"| `{metric}` | 0 | — | — | — | — |")
            continue
        rate = hits / n
        low, high = wilson(hits, n)
        passed = low >= threshold
        gate_ok = gate_ok and passed
        lines.append(f"| `{metric}` | {n} | {hits} | {rate:.2f} | "
                     f"[{low:.2f}, {high:.2f}] | {'pass' if passed else 'FAIL'} |")

    lines += ["", f"The gate compares the **lower end** of the interval against "
                  f"{threshold:.2f}, written down before the run. Twenty of twenty "
                  f"is not 1.00.", ""]
    if failures:
        lines += [f"## The {len(failures)} case(s) that failed something", "",
                  "| case | what failed | topic | what it said |",
                  "| --- | --- | --- | --- |"]
        for item in failures[:40]:
            broke = ", ".join(m for m, ok in item["verdict"].items() if ok is False)
            text = item["said"].replace("|", "/").replace("\n", " ")
            lines.append(f"| `{item['case']['id']}` | {broke} | "
                         f"{', '.join(item['topic']) or '—'} | {text} |")
        if len(failures) > 40:
            lines.append(f"| … | {len(failures) - 40} more | | |")
    else:
        lines.append("Nothing failed.")
    lines += ["", f"**Gate: {'PASS' if gate_ok else 'FAIL'}** — "
                  f"{'this configuration ships' if gate_ok else 'this configuration does not ship'}."]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None, help="static | llm")
    parser.add_argument("-n", type=int, default=None, help="draw this many cases")
    parser.add_argument("--seed", type=int, default=0, help="makes -n reproducible")
    parser.add_argument("--threshold", type=float, default=0.80)
    parser.add_argument("--show", action="store_true", help="print the cases and stop")
    parser.add_argument("--out", default="factoid-report.md")
    args = parser.parse_args(argv)

    all_cases = cases()
    if args.show:
        for case in all_cases:
            answer = "REFUSE" if case["answer"] is None else ",".join(case["answer"])
            print(f"{case['id']:<28} {case['utterance']:<48} -> {answer[:60]}")
        print(f"\n{len(all_cases)} cases from {len(kb.all_pizzas())} pizzas")
        return 0

    chosen = all_cases
    if args.n:
        chosen = random.Random(args.seed).sample(all_cases, min(args.n, len(all_cases)))

    import os

    from pizzabot import config
    from pizzabot.graph import build_graph

    configuration = (args.config or os.environ.get("BOT_CONFIG") or "static").lower()
    bot = build_graph(config.implementations(configuration))

    scores, failures = measure(bot, chosen)
    text = report(scores, failures, configuration, len(chosen), args.threshold)
    Path(HERE / args.out).write_text(text)
    print(text)

    history = HERE / "factoid-history.jsonl"
    with history.open("a") as handle:
        handle.write(json.dumps({
            "date": date.today().isoformat(), "configuration": configuration,
            "cases": len(chosen), "seed": args.seed, "threshold": args.threshold,
            "scores": {m: scores[m] for m in METRICS}}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
