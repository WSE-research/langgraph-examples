"""The evaluator: run the bot against cases drawn from the knowledge graph, and say what changed.

    python evaluate.py --model mistral-small-4-119b -n 10
    python evaluate.py --model mistral-small-4-119b -n 25 --seed 7
    python evaluate.py --config static -n 25                 # the baseline, no model, no key

What it does, in the order it does it:

1. **Read the knowledge graph** (`benchmark/data/*.ttl`, or `--data <file.ttl>`).
2. **Draw `n` cases per method** -- `n` calls to `address_recognition`, `n` to
   `pizza_recognition`, `n` to the two of them in one sentence -- randomly, from
   the individuals and wordings that are in the graph, reproducibly from `--seed`.
   If the graph cannot produce `n` *different* sentences for a method, it says so
   and measures what it can: **that warning is a finding about your data**, not an
   error in the harness.
3. **Run the configuration** (`--config llm`, the default, or `--config static`)
   over those cases and score every one of them.
4. **Write the run to `results/`** -- `last-run.json` (the full run, every case
   with what came back) and one line in `history.jsonl` (the summary).
5. **Compare with the previous run**, if `results/last-run.json` was there when
   this one started: accuracy before and after, per method, and -- for the
   sentences both runs happen to contain -- which ones flipped, in which
   direction. A measurement you cannot compare with anything decides nothing.

The two numbers that make a run mean something are both on the command line:
the **model id** (`--model`) and the **number of cases** (`-n`). A different
model is a different implementation; a different `n` is a different confidence.
Both are written into the result file, next to the seed and the date, so no
number in `results/` is ever orphaned from the run that produced it.

Scoring is deliberately simple and deliberately lenient in exactly one way: a
component *copies* what the user wrote ("R. Michelet"), the graph stores what it
means ("Rue Michelet"), and both count as right. Every other difference is a
miss. See `score()` -- it is twelve lines, and you should read them before you
believe any number this script prints.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import unicodedata
from datetime import datetime
from math import sqrt
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
LAST_RUN = RESULTS_DIR / "last-run.json"
HISTORY = RESULTS_DIR / "history.jsonl"
REPORT = Path(__file__).parent / "quality-report.md"

#: What a "method" is for this harness: one benchmark, the components that run,
#: and the state fields whose value is scored. The third row is the pyramid's
#: middle floor -- two components measured in one utterance.
METHODS: dict[str, dict] = {
    "address_recognition": {
        "benchmark": "address_v2",
        "components": ("address_recognition",),
        "fields": ("address",),
    },
    "pizza_recognition": {
        "benchmark": "pizza_v2",
        "components": ("pizza_recognition",),
        "fields": ("pizza_id",),
    },
    "pizza_and_address": {
        "benchmark": "order_v2",
        "components": ("pizza_recognition", "address_recognition"),
        "fields": ("pizza_id", "address"),
    },
}


# ---------------------------------------------------------------------------
# Scoring -- read this before you believe a number
# ---------------------------------------------------------------------------


def fold(text) -> str:
    """Compare without accents, case or stray spaces: "St. Etienne" ~ "St. Étienne"."""
    stripped = unicodedata.normalize("NFKD", str(text))
    return " ".join("".join(c for c in stripped if not unicodedata.combining(c)).split()).casefold()


def score(got, expected, accepted) -> bool:
    """Is `got` the answer the case asked for?

    Three rules, and nothing else:

    * expected `None` -> only "nothing recognised" is right (`None`). This is the
      refusal case: a pizza we do not sell, a city we do not deliver to.
    * a scalar (a pizza id) -> equality.
    * a record (an address) -> the same keys, and per key any wording the graph
      lists for the individual that was drawn (`accepted`), compared folded.
    """
    if expected is None:
        return got is None
    if got is None:
        return False
    if not isinstance(expected, dict):
        return got == expected
    if set(got) != set(expected):
        return False
    return all(fold(value) in {fold(w) for w in (accepted or {}).get(key, [expected[key]])}
               for key, value in got.items())


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95 % confidence interval for a pass rate (Wilson score).

    20 of 20 is not "100 %": it is [0.84, 1.00]. The interval is what turns a
    number into a statement -- and what shrinks when you add cases, which is the
    whole reason this harness generates them instead of asking you to type them.
    """
    if n == 0:
        return 0.0, 0.0
    p, denominator = hits / n, 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


# ---------------------------------------------------------------------------
# Running one case
# ---------------------------------------------------------------------------


def run_case(implementations: dict, method: dict, case: dict) -> tuple[dict, float]:
    """Call the components of this method, in order, on one utterance.

    Each component gets the state the previous one left behind -- which is what
    makes `order_v2` a *multi-component* benchmark and not two micro-benchmarks
    that happen to share a sentence.
    """
    from pizzabot.state import new_state

    state = new_state(case["input"])
    started = time.time()
    for name in method["components"]:
        patch = implementations[name](state)
        state = {**state, **patch}
    seconds = time.time() - started
    return state.get("slots", {}), seconds


def evaluate_method(implementations: dict, name: str, cases: list[dict], verbose: bool) -> dict:
    """Every case of one method, scored."""
    from pizzabot import log

    method, rows = METHODS[name], []
    for case in cases:
        slots, seconds = run_case(implementations, method, case)
        results = {field: score(slots.get(field), case["expected"].get(field),
                                (case.get("accepted") or {}).get(field))
                   for field in method["fields"]}
        passed = all(results.values())
        rows.append({
            "id": case["id"], "input": case["input"], "seconds": round(seconds, 3),
            "expected": {f: case["expected"].get(f) for f in method["fields"]},
            "got": {f: slots.get(f) for f in method["fields"]},
            "per_field": results, "passed": passed, "refusal": not case["servable"],
        })
        if verbose or not passed:
            (log.detail if passed else log.fail)(
                f"{case['input']}" if passed else
                f"{case['input']}\n            expected {rows[-1]['expected']}\n"
                f"            got      {rows[-1]['got']}")

    hits = sum(row["passed"] for row in rows)
    low, high = wilson(hits, len(rows))
    latencies = [row["seconds"] for row in rows] or [0.0]
    return {
        "n": len(rows), "hits": hits,
        "accuracy": round(hits / len(rows), 4) if rows else 0.0,
        "ci": [round(low, 4), round(high, 4)],
        "latency_p50": round(statistics.median(latencies), 3),
        "latency_max": round(max(latencies), 3),
        "refusal_cases": sum(row["refusal"] for row in rows),
        "cases": rows,
    }


# ---------------------------------------------------------------------------
# The two files in results/
# ---------------------------------------------------------------------------


def load_previous() -> dict | None:
    """The run before this one -- or None the first time, which is not an error."""
    if not LAST_RUN.exists():
        return None
    try:
        return json.loads(LAST_RUN.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def store(run: dict) -> None:
    """`last-run.json` is replaced; `history.jsonl` only ever grows."""
    RESULTS_DIR.mkdir(exist_ok=True)
    LAST_RUN.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: run[k] for k in ("timestamp", "config", "model", "cases_per_method", "seed")}
    summary["accuracy"] = {name: result["accuracy"] for name, result in run["methods"].items()}
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False) + "\n")


def report_difference(previous: dict, run: dict) -> None:
    """What changed since the previous run -- the reason this script keeps a file.

    Two comparisons, because they answer different questions. The *metric* diff
    says whether the configuration got better; the *case* diff says which
    sentence changed its mind, and only counts sentences both runs contain --
    with a different `n` or a different seed, most of them will not.
    """
    from pizzabot import log

    log.plain()
    log.rule()
    log.step(f"compared with the previous run: {previous['timestamp']} · "
             f"config {previous['config']} · model {previous['model']} · "
             f"n={previous['cases_per_method']} · seed {previous['seed']}")
    if (previous["config"], previous["model"]) != (run["config"], run["model"]):
        log.warn("different configuration or model: this is a comparison of two implementations, "
                 "not of two runs of the same one.")
    if previous["cases_per_method"] != run["cases_per_method"] or previous["seed"] != run["seed"]:
        log.hint("different sample: the interval moved because n or the seed changed, not only the bot.")
    log.plain()
    log.plain(f"    {'method':<22}{'before':>8}{'after':>8}{'delta':>9}   {'interval now':>16}")
    for name, result in run["methods"].items():
        before = previous["methods"].get(name)
        if before is None:
            log.plain(f"    {name:<22}{'--':>8}{result['accuracy']:>8.2f}{'(new)':>9}")
            continue
        delta = result["accuracy"] - before["accuracy"]
        arrow = "=" if abs(delta) < 1e-9 else ("+" if delta > 0 else "")
        log.plain(f"    {name:<22}{before['accuracy']:>8.2f}{result['accuracy']:>8.2f}"
                  f"{arrow + format(delta, '.2f'):>9}   "
                  f"[{result['ci'][0]:.2f}, {result['ci'][1]:.2f}]")

    flipped = _flipped_cases(previous, run)
    log.plain()
    if not flipped["shared"]:
        log.detail("no sentence occurs in both runs -- a different n or seed draws different cases.", indent="    ")
        return
    log.detail(f"{flipped['shared']} sentence(s) occur in both runs: "
               f"{len(flipped['now_pass'])} now pass, {len(flipped['now_fail'])} now fail.", indent="    ")
    for direction, label in (("now_fail", "regression"), ("now_pass", "repaired  ")):
        for text in flipped[direction][:5]:
            log.plain(f"      {label}: {text}")


def _flipped_cases(previous: dict, run: dict) -> dict:
    before = {(name, row["input"]): row["passed"]
              for name, result in previous["methods"].items() for row in result.get("cases", [])}
    shared, now_pass, now_fail = 0, [], []
    for name, result in run["methods"].items():
        for row in result["cases"]:
            key = (name, row["input"])
            if key not in before:
                continue
            shared += 1
            if before[key] and not row["passed"]:
                now_fail.append(row["input"])
            elif not before[key] and row["passed"]:
                now_pass.append(row["input"])
    return {"shared": shared, "now_pass": now_pass, "now_fail": now_fail}


# ---------------------------------------------------------------------------
# quality-report.md -- generated, never typed
# ---------------------------------------------------------------------------


def git_commit() -> str:
    """The commit the numbers belong to. A metric without one is an anecdote."""
    import subprocess

    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, timeout=5,
                                cwd=Path(__file__).parent)
        return result.stdout.strip() or "(not a git repository)"
    except Exception:  # noqa: BLE001
        return "(git not available)"


def write_report(run: dict, previous: dict | None, threshold: float) -> Path:
    """The artifact that travels with the process model.

    Generated on every run, so it can never disagree with `results/`. The header
    carries what makes a number honest -- commit, model, seed, sample size, date,
    wall clock -- and the last line is the gate: one sentence that says ship or
    do not ship, against a threshold that was written down before the run.
    """
    lines = [
        f"# Quality report -- {run['config']} configuration",
        "",
        f"Generated by `evaluate.py` on {run['timestamp']}. Do not edit by hand: "
        f"the next run overwrites this file.",
        "",
        "| | |", "| --- | --- |",
        f"| configuration | `{run['config']}` |",
        f"| model | `{run['model']}` |",
        f"| cases per method | {run['cases_per_method']} |",
        f"| seed | {run['seed']} |",
        f"| knowledge graph | {run['data']}, {run['catalog_triples']} triples |",
        f"| commit | `{run['commit']}` |",
        f"| wall clock | {run['wall_clock_seconds']:.1f} s |",
        f"| threshold (written down before the run) | {threshold:.2f} |",
        "",
        "## Results",
        "",
        "| method | n | hits | accuracy | 95% CI | refusal cases | p50 latency | previous | delta |",
        "| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for name, result in run["methods"].items():
        before = (previous or {}).get("methods", {}).get(name)
        previous_cell = f"{before['accuracy']:.2f}" if before else "--"
        delta_cell = f"{result['accuracy'] - before['accuracy']:+.2f}" if before else "--"
        lines.append(
            f"| `{name}` | {result['n']} | {result['hits']} | {result['accuracy']:.2f} | "
            f"[{result['ci'][0]:.2f}, {result['ci'][1]:.2f}] | "
            f"{result['refusal_cases']} | {result['latency_p50']:.2f} s | "
            f"{previous_cell} | {delta_cell} |")

    worst = min(run["methods"].items(), key=lambda item: item[1]["ci"][0], default=None)
    lines += ["", "## Gate", ""]
    if worst is None:
        lines.append("Nothing was measured.")
    else:
        name, result = worst
        passed = result["ci"][0] >= threshold
        lines.append(
            f"**{'PASS' if passed else 'FAIL'}** -- the weakest method is `{name}`: "
            f"{result['hits']}/{result['n']} = {result['accuracy']:.2f}, "
            f"95% CI [{result['ci'][0]:.2f}, {result['ci'][1]:.2f}]. "
            f"The gate compares the LOWER end of the interval with the threshold "
            f"{threshold:.2f}: a measurement over {result['n']} cases is a statement about "
            f"those {result['n']} cases, and the interval is how much of it carries over to "
            f"the ones nobody has typed yet.")
        if not passed:
            lines.append("")
            lines.append("Two honest ways out, and only two: make the component better, "
                         "or measure more cases and see whether the interval alone was the problem. "
                         "Lowering the threshold after seeing the number is not one of them.")
    lines += ["", "## Runs so far", "",
              "| when | config | model | n | seed | " +
              " | ".join(f"`{name}`" for name in run["methods"]) + " |",
              "| --- | --- | --- | ---: | ---: | " + " | ".join("---:" for _ in run["methods"]) + " |"]
    for entry in history_entries():
        lines.append(
            f"| {entry['timestamp']} | {entry['config']} | `{entry['model']}` | "
            f"{entry['cases_per_method']} | {entry['seed']} | "
            + " | ".join(f"{entry['accuracy'].get(name, float('nan')):.2f}"
                         if name in entry["accuracy"] else "--" for name in run["methods"]) + " |")
    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return REPORT


def history_entries() -> list[dict]:
    """Every run this repository has recorded, oldest first."""
    if not HISTORY.exists():
        return []
    return [json.loads(line) for line in HISTORY.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# The command line
# ---------------------------------------------------------------------------


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate one configuration of the bot against cases generated from the knowledge graph.",
        epilog="Every run is written to results/ and compared with the one before it.")
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "mistral-small-4-119b"),
                        help="the LLM id to measure (default: MODEL_NAME from .env). "
                             "A different model is a different implementation -- re-measure it.")
    parser.add_argument("-n", "--cases", type=int, default=10,
                        help="how many test-case instances PER METHOD (default: 10)")
    parser.add_argument("--seed", type=int, default=42, help="the randomizer seed (default: 42)")
    parser.add_argument("--config", default="llm", choices=("llm", "static"),
                        help="which implementation to measure (default: llm; static is the baseline)")
    parser.add_argument("--data", default=None,
                        help="the knowledge graph: a .ttl file or a directory (default: benchmark/data/)")
    parser.add_argument("--method", default=None, choices=list(METHODS),
                        help="measure one method only (default: all three)")
    parser.add_argument("--threshold", type=float, default=0.80,
                        help="the gate: the lower end of the interval must reach it (default: 0.80). "
                             "Decide it BEFORE the run, not after you have seen the number.")
    parser.add_argument("--verbose", action="store_true", help="print every case, not only the failures")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)

    # The model id has to be in the environment BEFORE the service is built:
    # `pizzabot.llm_service` reads MODEL_NAME when it first constructs itself.
    if arguments.config == "llm":
        os.environ["MODEL_NAME"] = arguments.model
    os.environ.setdefault("LOG_LEVEL", "WARNING")            # the node trace would drown the report

    from benchmark import Catalog
    from benchmark.generate import capacity, generate
    from pizzabot import config, log

    catalog = Catalog(arguments.data) if arguments.data else Catalog()
    model = arguments.model if arguments.config == "llm" else "(none: static configuration)"

    log.title(f"Evaluation -- config {arguments.config} · model {model} · "
              f"{arguments.cases} case(s) per method · seed {arguments.seed}")
    log.detail(f"knowledge graph: {catalog!r}", indent="  ")

    previous = load_previous()                               # read it BEFORE we overwrite it
    implementations = config.implementations(arguments.config)
    selected = [arguments.method] if arguments.method else list(METHODS)

    started = time.time()
    run = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "commit": git_commit(),
        "config": arguments.config, "model": model,
        "cases_per_method": arguments.cases, "seed": arguments.seed,
        "data": str(arguments.data or "benchmark/data/"),
        "catalog_triples": len(catalog),
        "threshold": arguments.threshold,
        "capacity": {name: capacity(catalog, METHODS[name]["benchmark"]) for name in selected},
        "methods": {},
    }

    for name in selected:
        benchmark = METHODS[name]["benchmark"]
        log.plain()
        log.step(f"{name} -- benchmark {benchmark}, "
                 f"{run['capacity'][name]} different sentences available")
        cases = generate(catalog, benchmark, n=arguments.cases, seed=arguments.seed,
                         on_warning=log.warn)
        run["methods"][name] = evaluate_method(implementations, name, cases, arguments.verbose)

    run["wall_clock_seconds"] = round(time.time() - started, 1)

    log.plain()
    log.rule()
    log.plain(f"    {'method':<22}{'n':>4}{'hits':>6}{'accuracy':>10}{'95% CI':>18}{'p50 s':>8}")
    for name, result in run["methods"].items():
        interval = "[{:.2f}, {:.2f}]".format(*result["ci"])
        log.plain(f"    {name:<22}{result['n']:>4}{result['hits']:>6}{result['accuracy']:>10.2f}"
                  f"{interval:>18}{result['latency_p50']:>8.2f}")
    log.plain()
    log.detail(f"refusal cases (the right answer is 'nothing'): "
               + ", ".join(f"{name} {result['refusal_cases']}/{result['n']}"
                           for name, result in run["methods"].items()), indent="    ")

    if previous is not None:
        report_difference(previous, run)
    else:
        log.plain()
        log.detail(f"no previous run in {LAST_RUN} -- this one is the baseline. "
                   f"Run the script again to see a difference.", indent="    ")

    store(run)
    report = write_report(run, previous, arguments.threshold)

    weakest = min(run["methods"].items(), key=lambda item: item[1]["ci"][0], default=None)
    log.plain()
    if weakest is not None:
        name, result = weakest
        passed = result["ci"][0] >= arguments.threshold
        message = (f"GATE {'PASS' if passed else 'FAIL'}: weakest method {name}, "
                   f"lower end of the interval {result['ci'][0]:.2f} "
                   f"{'>=' if passed else '<'} threshold {arguments.threshold:.2f}")
        (log.result if passed else log.warn)(message)
    log.detail(f"written: {LAST_RUN}, one line in {HISTORY}, and {report}", indent="    ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
