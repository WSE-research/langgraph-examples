"""The evaluator: run the bot against cases drawn from the knowledge graph, and decide.

    python evaluate.py --config static -n 40 --seed 42 --threshold 0.80   # R1, the baseline
    python evaluate.py -n 40 --seed 42 --threshold 0.80                   # R2, the candidate (MODEL_NAME)
    python evaluate.py --model <another model> -n 40 --seed 42 --threshold 0.80

What it does, in the order it does it:

1. **Read the knowledge graph** (`benchmark/data/*.ttl`, or `--data <file.ttl>`)
   and fingerprint it: a hash of the Turtle files goes into every result, so a
   number is never compared with one measured on another dataset.
2. **Draw `n` cases per method** -- `n` calls to `address_recognition`, `n` to
   `pizza_recognition`, `n` to the two of them in one sentence -- reproducibly
   from `--seed`. Before it starts, it says whether `n` can carry the threshold
   at all: at `-n 10` not even 10 of 10 reaches a lower bound of 0.80.
3. **Run the configuration** (`--config llm`, the default, or `--config static`)
   over those cases, four at a time (`--workers`), and score every one of them
   with the comparison rule (`score()`), recording which tier answered.
4. **Decide**: the quality gate, three clauses, printed and written verbatim.
5. **Write the run to `results/`** -- `last-run.json` (the full run, every case
   with what came back) and one line in `history.jsonl` (the summary) -- and
   regenerate `quality-report.md`.
6. **Pair it with the previous run**, if both ran over the same cases (same
   graph, `n` and seed): per case, which ones now pass (b) and now fail (c), and
   the exact McNemar test of b against c. A comparison over different cases is
   refused, with the reason.

The quality gate, the same sentence as on the slides of Lecture 3:

    (1) for every method, the lower end of the 95 % Wilson interval of the
        accuracy is at least the threshold written down before the run;
    (2) no refusal violation: no value is written where nothing is expected;
    (3) the p95 latency of every method is at most 3 s.

The comparison rule, also the slides': an output is correct when it names the
same catalog individual as the expected value -- any of its wordings, compared
without case, accents and stray spaces -- and a refusal is correct when nothing
is written. See `score()`: it is twelve lines, read them before you believe any
number this script prints.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from math import ceil, comb, sqrt
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
LAST_RUN = RESULTS_DIR / "last-run.json"
HISTORY = RESULTS_DIR / "history.jsonl"
REPORT = Path(__file__).parent / "quality-report.md"

#: The third clause of the quality gate.
MAX_P95_SECONDS = 3.0

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
    """Compare without accents, case or stray spaces: "Agia Paraskevi" ~ "Agía Paraskeví"."""
    stripped = unicodedata.normalize("NFKD", str(text))
    return " ".join("".join(c for c in stripped if not unicodedata.combining(c)).split()).casefold()


def score(got, expected, accepted) -> bool:
    """Is `got` the answer the case asked for? The comparison rule: the same individual.

    Three rules, and nothing else:

    * expected `None` -> only "nothing recognised" is right (`None`). This is the
      refusal case: a pizza we do not sell, a city we do not deliver to.
    * a scalar (a pizza id) -> equality.
    * a record (an address) -> the same keys, and per key any wording the graph
      lists for the individual that was drawn (`accepted`), compared folded. The
      component copies what the user wrote ("Ermou St.", "Athina", "12 b"); the
      graph knows which individual that is.
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


def accepted_for(catalog, expected) -> dict | None:
    """The wordings that count as `expected`: every wording of the individual it names.

    A generated case carries them (`accepted`); a hand-written case has only the
    expected record, so the same rule looks the individual up in the catalog --
    field by field, by any of its wordings. A value the catalog does not know
    accepts only itself. Scalars (a pizza id) need no wordings.
    """
    if not isinstance(expected, dict):
        return None
    from benchmark.catalog import TG
    from rdflib import RDF, Literal

    accepted = {}
    for field, value in expected.items():
        wordings = {value}
        for cls in catalog.g.subjects(TG.field, Literal(field)):
            for individual in catalog.g.subjects(RDF.type, cls):
                names = {catalog.name(individual), *catalog.labels(individual)} - {None}
                if fold(value) in {fold(name) for name in names}:
                    wordings |= names
        accepted[field] = sorted(wordings)
    return accepted


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95 % confidence interval for a pass rate (Wilson score).

    20 of 20 estimates 1.00, and the data are compatible with anything from 0.84
    up. The quality gate compares the LOWER end with the threshold: PASS means
    the data show an accuracy above the threshold (one-sided, about 97.5 %);
    FAIL means only that they do not show it.
    """
    if n == 0:
        return 0.0, 0.0
    p, denominator = hits / n, 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def minimum_cases(threshold: float, z: float = 1.96) -> int:
    """The smallest n at which even n of n can pass: n >= z^2 * t / (1 - t) -- 16 at 0.80, 35 at 0.90."""
    return ceil(z * z * threshold / (1 - threshold)) if threshold < 1 else 10 ** 9


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided McNemar p: b cases now pass, c now fail, on the SAME cases.

    Under "nothing changed" every discordant case is a coin toss, so b follows
    Binomial(b + c, 1/2). Concordant cases carry no information about the change.
    """
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


# ---------------------------------------------------------------------------
# Running one case
# ---------------------------------------------------------------------------

#: Which tier answered, per thread: `trace.tier()` is called by the LLM-backed
#: components ("llm", or "static" when the rule had to decide). The harness
#: listens to it for the case it is running -- four cases run at a time.
_TIERS = threading.local()


def _listen_to_tiers() -> None:
    from pizzabot import trace

    if getattr(trace.tier, "_listened", False):
        return
    original = trace.tier

    def tier(node: str, which: str, reason: str = "") -> None:
        heard = getattr(_TIERS, "heard", None)
        if heard is not None:
            heard[node] = which
        original(node, which, reason)

    tier._listened = True
    trace.tier = tier


def run_case(implementations: dict, method: dict, case: dict) -> tuple[dict, float, dict]:
    """Call the components of this method, in order, on one utterance.

    Each component gets the state the previous one left behind -- which is what
    makes `order_v2` a *multi-component* benchmark and not two micro-benchmarks
    that happen to share a sentence.
    """
    from pizzabot.state import new_state

    _TIERS.heard = {}
    state = new_state(case["input"])
    started = time.time()
    for name in method["components"]:
        patch = implementations[name](state)
        state = {**state, **patch}
    seconds = time.time() - started
    tiers, _TIERS.heard = _TIERS.heard, None
    return state.get("slots", {}), seconds, tiers


def p95(values: list[float]) -> float:
    ordered = sorted(values) or [0.0]
    return ordered[min(len(ordered) - 1, ceil(0.95 * len(ordered)) - 1)]


def evaluate_method(implementations: dict, name: str, cases: list[dict], verbose: bool,
                    workers: int = 4) -> dict:
    """Every case of one method, scored -- `workers` at a time, reported in case order."""
    from pizzabot import log

    method = METHODS[name]

    def one(case: dict) -> dict:
        slots, seconds, tiers = run_case(implementations, method, case)
        results = {field: score(slots.get(field), case["expected"].get(field),
                                (case.get("accepted") or {}).get(field))
                   for field in method["fields"]}
        violation = any(case["expected"].get(f) is None and slots.get(f) is not None for f in method["fields"])
        return {
            "id": case["id"], "input": case["input"], "seconds": round(seconds, 3),
            "expected": {f: case["expected"].get(f) for f in method["fields"]},
            "got": {f: slots.get(f) for f in method["fields"]},
            "per_field": results, "passed": all(results.values()),
            "refusal": not case["servable"], "refusal_violation": violation,
            "tiers": tiers,
            "answered_by_llm": bool(tiers) and all(tiers.get(c) == "llm" for c in method["components"]),
        }

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        rows = list(pool.map(one, cases))

    for row in rows:
        if verbose or not row["passed"]:
            (log.detail if row["passed"] else log.fail)(
                f"{row['input']}" if row["passed"] else
                f"{row['input']}\n            expected {row['expected']}\n"
                f"            got      {row['got']}"
                + ("   <- a value where nothing was expected" if row["refusal_violation"] else ""))

    hits = sum(row["passed"] for row in rows)
    low, high = wilson(hits, len(rows))
    latencies = [row["seconds"] for row in rows] or [0.0]
    distinct = {field: len({json.dumps(row["expected"][field], sort_keys=True, ensure_ascii=False)
                            for row in rows if row["expected"][field] is not None})
                for field in method["fields"]}
    return {
        "n": len(rows), "hits": hits,
        "accuracy": round(hits / len(rows), 4) if rows else 0.0,
        "ci": [round(low, 4), round(high, 4)],
        "latency_p50": round(statistics.median(latencies), 3),
        "latency_p95": round(p95(latencies), 3),
        "refusal_cases": sum(row["refusal"] for row in rows),
        "refusal_violations": sum(row["refusal_violation"] for row in rows),
        "answered_by_llm": sum(row["answered_by_llm"] for row in rows),
        "distinct": distinct,
        "cases": rows,
    }


# ---------------------------------------------------------------------------
# The quality gate
# ---------------------------------------------------------------------------


def quality_gate(run: dict) -> dict:
    """The three clauses, each with what was measured. PASS only if all three hold."""
    threshold, methods = run["threshold"], run["methods"]
    weakest = min(methods.items(), key=lambda item: item[1]["ci"][0])
    violations = {name: m["refusal_violations"] for name, m in methods.items() if m["refusal_violations"]}
    slowest = max(methods.items(), key=lambda item: item[1]["latency_p95"])
    clauses = [
        {"clause": f"(1) every method: lower end of the 95 % interval >= {threshold:.2f}",
         "passed": weakest[1]["ci"][0] >= threshold,
         "measured": f"weakest {weakest[0]}: {weakest[1]['hits']}/{weakest[1]['n']} = "
                     f"{weakest[1]['accuracy']:.2f}, interval [{weakest[1]['ci'][0]:.2f}, {weakest[1]['ci'][1]:.2f}]"},
        {"clause": "(2) no refusal violation: no value where nothing is expected",
         "passed": not violations,
         "measured": "none" if not violations else ", ".join(f"{n} {k}" for n, k in violations.items())},
        {"clause": f"(3) p95 latency <= {MAX_P95_SECONDS:.0f} s",
         "passed": slowest[1]["latency_p95"] <= MAX_P95_SECONDS,
         "measured": f"slowest {slowest[0]}: {slowest[1]['latency_p95']:.2f} s"},
    ]
    return {"passed": all(c["passed"] for c in clauses), "clauses": clauses}


# ---------------------------------------------------------------------------
# The two files in results/, and the comparison with the previous run
# ---------------------------------------------------------------------------


def dataset_hash(catalog) -> str:
    """A fingerprint of the Turtle files: same hash, same catalog, same cases for the same n and seed."""
    digest = hashlib.sha256()
    for path in catalog.sources:
        digest.update(Path(path).name.encode("utf-8"))
        digest.update(Path(path).read_bytes())
    return digest.hexdigest()[:8]


def load_previous() -> dict | None:
    """The run before this one -- or None the first time, which is not an error."""
    if not LAST_RUN.exists():
        return None
    try:
        return json.loads(LAST_RUN.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def pair_with(previous: dict | None, run: dict) -> dict:
    """The paired comparison with the previous run -- or why there is none.

    Pairing needs the same cases: the same knowledge graph (hash), the same n and
    the same seed draw the same sentences under the same ids. Then b counts the
    cases that now pass, c the ones that now fail, and McNemar tests b against c.
    """
    if previous is None:
        return {"paired": False, "why": "no previous run: this is the first one"}
    differences = [what for what, key in (("knowledge graph", "dataset_hash"), ("n", "cases_per_method"),
                                          ("seed", "seed"))
                   if previous.get(key) != run.get(key)]
    if differences:
        return {"paired": False,
                "why": f"different {', '.join(differences)}: the two runs did not see the same cases"}
    per_method, total_b, total_c = {}, 0, 0
    for name, result in run["methods"].items():
        before = {row["id"]: row["passed"] for row in previous["methods"].get(name, {}).get("cases", [])}
        b = [row["input"] for row in result["cases"] if row["id"] in before and row["passed"] and not before[row["id"]]]
        c = [row["input"] for row in result["cases"] if row["id"] in before and not row["passed"] and before[row["id"]]]
        per_method[name] = {"b": len(b), "c": len(c), "p": round(mcnemar(len(b), len(c)), 4),
                            "now_pass": b[:5], "now_fail": c[:5]}
        total_b, total_c = total_b + len(b), total_c + len(c)
    return {"paired": True, "against": f"{previous['config']} · {previous['model']} · {previous['timestamp']}",
            "methods": per_method, "b": total_b, "c": total_c, "p": round(mcnemar(total_b, total_c), 4),
            "same_implementation": (previous["config"], previous["model"]) == (run["config"], run["model"])}


def report_pairing(previous: dict | None, pairing: dict) -> None:
    from pizzabot import log

    log.plain()
    log.rule()
    if previous is not None:
        log.step(f"previous run: {previous['timestamp']} · config {previous['config']} · "
                 f"model {previous['model']} · n={previous['cases_per_method']} · seed {previous['seed']}")
    if not pairing["paired"]:
        log.detail(f"not paired -- {pairing['why']}. Accuracies can be read side by side in "
                   f"quality-report.md, but no case-by-case comparison is made.", indent="    ")
        return
    if pairing["same_implementation"]:
        log.hint("the same implementation on the same cases: every flip below is nondeterminism, "
                 "not a change -- a later comparison must flip more cases than this to show anything.")
    else:
        log.warn("a different configuration or model on the same cases: this is the paired comparison "
                 "of two implementations.")
    log.plain()
    log.plain(f"    {'method':<22}{'now pass (b)':>14}{'now fail (c)':>14}{'McNemar p':>12}")
    for name, m in pairing["methods"].items():
        log.plain(f"    {name:<22}{m['b']:>14}{m['c']:>14}{m['p']:>12.4f}")
    log.plain(f"    {'all three':<22}{pairing['b']:>14}{pairing['c']:>14}{pairing['p']:>12.4f}")
    for name, m in pairing["methods"].items():
        for text in m["now_fail"]:
            log.plain(f"      now fails ({name}): {text}")
        for text in m["now_pass"]:
            log.plain(f"      now passes ({name}): {text}")


def store(run: dict, pairing: dict) -> None:
    """`last-run.json` is replaced; `history.jsonl` only ever grows."""
    RESULTS_DIR.mkdir(exist_ok=True)
    LAST_RUN.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: run[k] for k in ("timestamp", "config", "model", "cases_per_method", "seed",
                                   "threshold", "dataset_hash", "commit")}
    summary["accuracy"] = {name: m["accuracy"] for name, m in run["methods"].items()}
    summary["ci_low"] = {name: m["ci"][0] for name, m in run["methods"].items()}
    summary["latency_p95"] = {name: m["latency_p95"] for name, m in run["methods"].items()}
    summary["refusal_violations"] = {name: m["refusal_violations"] for name, m in run["methods"].items()}
    summary["answered_by_llm"] = {name: m["answered_by_llm"] for name, m in run["methods"].items()}
    summary["gate"] = "PASS" if run["gate"]["passed"] else "FAIL"
    summary["paired_with_previous"] = (
        {k: pairing[k] for k in ("b", "c", "p")} if pairing["paired"] else None)
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False) + "\n")


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


def gate_lines(gate: dict) -> list[str]:
    lines = [f"**{'PASS' if gate['passed'] else 'FAIL'}**", ""]
    for clause in gate["clauses"]:
        lines.append(f"- {'pass' if clause['passed'] else 'FAIL'}: {clause['clause']} -- {clause['measured']}")
    return lines


def write_report(run: dict, previous: dict | None, pairing: dict) -> Path:
    """The artifact that travels with the process model.

    Generated on every run, so it can never disagree with `results/`. The header
    carries what makes a number honest -- commit, model, seed, sample size, the
    graph's fingerprint, date, wall clock -- and the quality gate is printed with
    every clause and what was measured for it.
    """
    lines = [
        f"# Quality report -- {run['config']} configuration",
        "",
        f"Generated by `evaluate.py` on {run['timestamp']}. Do not edit by hand: "
        f"the next run overwrites this file -- hand-written notes go into `quality-notes.md`.",
        "",
        "| | |", "| --- | --- |",
        f"| configuration | `{run['config']}` |",
        f"| model | `{run['model']}` |",
        f"| cases per method | {run['cases_per_method']} |",
        f"| seed | {run['seed']} |",
        f"| knowledge graph | {run['data']}, {run['catalog_triples']} triples, hash `{run['dataset_hash']}` |",
        f"| commit | `{run['commit']}` |",
        f"| wall clock | {run['wall_clock_seconds']:.1f} s |",
        f"| threshold (written down before the run) | {run['threshold']:.2f} |",
        "",
        "## Results",
        "",
        "| method | n | hits | accuracy | 95% CI | refusal cases | refusal violations | answered by the LLM "
        "| distinct individuals | p95 latency | previous | change |",
        "| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for name, m in run["methods"].items():
        before = (previous or {}).get("methods", {}).get(name)
        previous_cell = f"{before['accuracy']:.2f}" if before else "--"
        change_cell = f"{m['accuracy'] - before['accuracy']:+.2f}" if before else "--"
        distinct = ", ".join(f"{field} {count}" for field, count in m["distinct"].items())
        llm = f"{m['answered_by_llm']}/{m['n']}" if run["config"] == "llm" else "--"
        lines.append(
            f"| `{name}` | {m['n']} | {m['hits']} | {m['accuracy']:.2f} | "
            f"[{m['ci'][0]:.2f}, {m['ci'][1]:.2f}] | {m['refusal_cases']} | {m['refusal_violations']} | "
            f"{llm} | {distinct} | {m['latency_p95']:.2f} s | {previous_cell} | {change_cell} |")
    lines += ["", "The interval is about the generator's distribution: further sentences drawn from this "
              "catalog, not your users' sentences. Cases drawn from the same individual fail together -- "
              "count the distinct individuals, not only the sentences.", ""]

    lines += ["## Quality gate", ""] + gate_lines(run["gate"])
    if not run["gate"]["passed"]:
        lines += ["", "Two honest ways out, and only two: make the component better, or decide on a "
                  "larger n -- before the next run, with a fresh seed, and report every run. Lowering "
                  "the threshold after seeing the number is not one of them."]
    lines += ["", "Decision rule: ship the cheapest configuration that passes the quality gate; a costlier "
              "one ships only with a paired win over it on the same cases (McNemar p < 0.05)."]

    lines += ["", "## Paired with the previous run", ""]
    if pairing["paired"]:
        lines += [f"Against: {pairing['against']}. b = cases that now pass, c = cases that now fail; "
                  f"exact McNemar test of b against c.", "",
                  "| method | b | c | McNemar p |", "| --- | ---: | ---: | ---: |"]
        lines += [f"| `{name}` | {m['b']} | {m['c']} | {m['p']:.4f} |" for name, m in pairing["methods"].items()]
        lines.append(f"| all three | {pairing['b']} | {pairing['c']} | {pairing['p']:.4f} |")
    else:
        lines.append(f"Not paired: {pairing['why']}.")

    names = list(run["methods"])
    lines += ["", "## Runs so far", "",
              "| when | config | model | n | seed | graph | " + " | ".join(f"`{n}` acc [low]" for n in names)
              + " | gate | paired with the run before (b / c, p) |",
              "| --- | --- | --- | ---: | ---: | --- | " + " | ".join("---" for _ in names) + " | --- | --- |"]
    for entry in history_entries():
        cells = []
        for name in names:
            if name in entry.get("accuracy", {}):
                low = entry.get("ci_low", {}).get(name)
                cells.append(f"{entry['accuracy'][name]:.2f}" + (f" [{low:.2f}]" if low is not None else ""))
            else:
                cells.append("--")
        paired = entry.get("paired_with_previous")
        paired_cell = f"{paired['b']} / {paired['c']}, p {paired['p']:.3f}" if paired else "--"
        lines.append(
            f"| {entry['timestamp']} | {entry['config']} | `{entry['model']}` | {entry['cases_per_method']} | "
            f"{entry['seed']} | `{entry.get('dataset_hash', '--')}` | " + " | ".join(cells)
            + f" | {entry.get('gate', '--')} | {paired_cell} |")
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
        epilog="Every run is written to results/, decided by the quality gate and paired with the run before it.")
    parser.add_argument("--model", default=None,
                        help="the LLM id to measure (default: MODEL_NAME from .env, provided on-site). "
                             "A different model is a different implementation -- re-measure it.")
    parser.add_argument("-n", "--cases", type=int, default=40,
                        help="how many test-case instances PER METHOD (default: 40 -- the n a decision rests on)")
    parser.add_argument("--seed", type=int, default=42, help="the randomizer seed (default: 42)")
    parser.add_argument("--config", default="llm", choices=("llm", "static"),
                        help="which implementation to measure (default: llm; static is the baseline)")
    parser.add_argument("--data", default=None,
                        help="the knowledge graph: a .ttl file or a directory (default: benchmark/data/)")
    parser.add_argument("--method", default=None, choices=list(METHODS),
                        help="measure one method only (default: all three)")
    parser.add_argument("--threshold", type=float, default=0.80,
                        help="clause (1) of the quality gate (default: 0.80). Write it into quality-notes.md "
                             "and commit it BEFORE the run, then pass it here.")
    parser.add_argument("--workers", type=int, default=int(os.environ.get("EVAL_WORKERS", "4")),
                        help="cases run at the same time (default: 4; EVAL_WORKERS)")
    parser.add_argument("--verbose", action="store_true", help="print every case, not only the failures")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)

    # The model id has to be in the environment BEFORE the service is built:
    # `pizzabot.llm_service` reads MODEL_NAME when it first constructs itself.
    if arguments.config == "llm":
        import pizzabot  # noqa: F401 -- importing the package reads .env, so MODEL_NAME there counts
        from pizzabot import llm_service, log

        named = (os.environ.get("MODEL_NAME") or "").strip()
        arguments.model = arguments.model or ("" if named.startswith("<") else named)
        if arguments.model:
            os.environ["MODEL_NAME"] = arguments.model
        missing = [name for name in llm_service.missing() if not (name == "MODEL_NAME" and arguments.model)]
        if missing:
            log.fail(f"no LLM configuration to measure: {', '.join(missing)} not set in .env",
                     "a run without an endpoint would measure the rule and call it the LLM")
            log.hint("put the three values provided on-site into .env (python check_llm.py checks them), "
                     "or measure the baseline: python evaluate.py --config static")
            return 2
    os.environ.setdefault("LOG_LEVEL", "WARNING")            # the node trace would drown the report

    from benchmark import Catalog
    from benchmark.generate import capacity, generate
    from pizzabot import config, log

    catalog = Catalog(arguments.data) if arguments.data else Catalog()
    model = arguments.model if arguments.config == "llm" else "(none: static configuration)"

    log.title(f"Evaluation -- config {arguments.config} · model {model} · "
              f"{arguments.cases} case(s) per method · seed {arguments.seed} · threshold {arguments.threshold:.2f}")
    log.detail(f"knowledge graph: {catalog!r}, hash {dataset_hash(catalog)}", indent="  ")
    needed = minimum_cases(arguments.threshold)
    if arguments.cases < needed:
        best = wilson(arguments.cases, arguments.cases)[0]
        log.warn(f"at n={arguments.cases} not even {arguments.cases} of {arguments.cases} can pass "
                 f"the threshold {arguments.threshold:.2f} (best lower bound {best:.2f}; it takes n >= {needed}). "
                 f"This run shows the width of the interval -- it cannot decide.")

    previous = load_previous()                               # read it BEFORE we overwrite it
    implementations = config.implementations(arguments.config)
    _listen_to_tiers()
    selected = [arguments.method] if arguments.method else list(METHODS)

    started = time.time()
    run = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "commit": git_commit(),
        "config": arguments.config, "model": model,
        "cases_per_method": arguments.cases, "seed": arguments.seed,
        "data": str(arguments.data or "benchmark/data/"),
        "catalog_triples": len(catalog),
        "dataset_hash": dataset_hash(catalog),
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
        run["methods"][name] = evaluate_method(implementations, name, cases, arguments.verbose,
                                               workers=arguments.workers)

    run["wall_clock_seconds"] = round(time.time() - started, 1)
    run["gate"] = quality_gate(run)

    log.plain()
    log.rule()
    log.plain(f"    {'method':<22}{'n':>4}{'hits':>6}{'accuracy':>10}{'95% CI':>15}{'p95 s':>7}"
              f"{'refusal viol.':>15}{'LLM answered':>14}")
    for name, m in run["methods"].items():
        interval = "[{:.2f}, {:.2f}]".format(*m["ci"])
        llm = f"{m['answered_by_llm']}/{m['n']}" if arguments.config == "llm" else "--"
        log.plain(f"    {name:<22}{m['n']:>4}{m['hits']:>6}{m['accuracy']:>10.2f}{interval:>15}"
                  f"{m['latency_p95']:>7.2f}{m['refusal_violations']:>15}{llm:>14}")
    log.plain()
    log.detail("distinct individuals drawn: " + "; ".join(
        f"{name} " + ", ".join(f"{field} {count}" for field, count in m["distinct"].items())
        for name, m in run["methods"].items()), indent="    ")

    pairing = pair_with(previous, run)
    report_pairing(previous, pairing)
    store(run, pairing)
    write_report(run, previous, pairing)

    log.plain()
    log.rule()
    for clause in run["gate"]["clauses"]:
        (log.ok if clause["passed"] else log.fail)(clause["clause"], clause["measured"])
    (log.result if run["gate"]["passed"] else log.warn)(
        f"QUALITY GATE {'PASS' if run['gate']['passed'] else 'FAIL'}")
    log.detail(f"written: results/last-run.json, one line in results/history.jsonl, and {REPORT.name}",
               indent="    ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
