"""Tasks 2c, 3c and 5 -- the same utterances through both implementations, side by side.

    python compare_configs.py                # both components, all cases
    python compare_configs.py --address      # only address_recognition
    python compare_configs.py --pizza        # only pizza_recognition

Every case runs through the Iteration 1 rule and through the LLM-backed
component. The first column says who answered on the LLM side: [llm] (the
service answered and passed every check) or [static] (a check failed, or the
service failed, and the rule decided). A `*` marks the cases where the two
implementations disagree.

There is no PASS column on purpose -- you are the judge. A row where both
implementations keep the contract and still disagree is the interesting one:
which of the two is *right* is a question this course does not answer until
Iteration 3, when a dataset and a number exist.

At the end the script prints three blocks to read on the screen: the per-case
rows, the two-number table, and the service card. Nothing is handed in -- the
script reprints all of it whenever you need it again.

Add your own cases at the `# TODO` at the end of each list: the rows of your
section 6 of Iteration 1 (the cases your rules could not handle) come first --
they are the reason we added the LLM.
"""

from __future__ import annotations

import datetime
import os
import sys

# The trace of every node, twice per row, would drown the table. Default to a
# quiet run; LOG_LEVEL=INFO python compare_configs.py shows everything.
os.environ.setdefault("LOG_LEVEL", "WARNING")

from pizzabot import config, llm_service, log, pizza_api, trace  # noqa: E402
from pizzabot.state import new_state  # noqa: E402

# (utterance, a note on what to expect) -- the note is free text, for you to read.
ADDRESS_CASES: list[tuple[str, str]] = [
    ("deliver it to 5 Rue Michelet, Saint-Étienne",                  "both: 5 / Rue Michelet / Saint-Étienne"),
    ("Rue Michelet 5, Saint-Étienne",                                 "both: 5 / Rue Michelet / Saint-Étienne"),
    # the rows from Iteration 1, section 6 -- the reason we are here:
    ("5 Rue Michelet Saint-Étienne",                                  "rule: nothing (comma); llm: complete?"),
    ("I live at 5 Rue Michelet in Saint-Étienne",                     "rule: nothing ('in'); llm: complete?"),
    ("number 5 in the Rue Michelet here in Saint-Étienne",            "rule: nothing; llm: complete?"),
    ("5 rue Michelet 42000, Saint-Étienne",                           "rule: 42000 as the number (contract kept, wrong); llm: 5?"),
    ("5 bis rue Michelet, Saint-Étienne",                             "rule: street 'bis rue Michelet' (contract kept, wrong); llm: your pattern decides"),
    # cases where the contract must hold whatever the model thinks:
    ("deliver to Lyon",                                               "nothing -- no street, no number"),
    ("somewhere near the station",                                    "nothing"),
    ("a Margherita to 5 Rue Michelet, Saint-Etienne and a Funghi to 3 Place Jean Jaures, Lyon", "one address or nothing -- never a mix"),
    # TODO: your own cases go here -- your section 6 rows first.
]

PIZZA_CASES: list[tuple[str, str]] = [
    ("I would like a Margherita",                 "both: Margherita"),
    ("one Margaritha please",                     "both: Margherita (rule: fuzzy)"),
    ("Quatro Formagi to 5 Rue Michelet",          "both? Quattro Formaggi, two typos"),
    ("the four-cheese one please",                "rule: nothing; llm: Quattro Formaggi"),
    ("une quatre fromages s'il vous plaît",       "rule: nothing; llm: Quattro Formaggi"),
    ("the spicy one with salami",                 "rule: a literal mention; llm: ? -- is that right? (ten-pizza stub menu)"),
    ("One Pizza Napoli please",                   "nothing -- not on the menu, whatever the model says"),
    ("I want sushi",                              "nothing"),
    ("a Margherita and a Funghi please",          "one name -- the contract says which?"),
    # TODO: your own cases go here.
]

WIDTH = 78


def cut(text: str, width: int) -> str:
    text = str(text)
    return text if len(text) <= width else text[: width - 2] + ".."


def fmt_address(patch: dict) -> str:
    address = patch.get("slots", {}).get("address")
    return f"{address['house_number']} / {address['street']} / {address['city']}" if address else "(nothing)"


def fmt_pizza(patch: dict) -> str:
    return patch.get("slots", {}).get("pizza_name") or "(nothing)"


def run(component: str, cases: list[tuple[str, str]], fmt) -> tuple[dict[str, int], list[tuple]]:
    static = config.implementations(config.STATIC)[component]
    llm = config.implementations(config.LLM)[component]
    tiers: dict[str, int] = {}
    rows = []
    log.plain()
    log.title(f"== {component} ==" + " " * max(1, WIDTH - len(component) - 45) + "* = the two disagree")
    log.plain(f"{'#':>2}  {'tier':9s} utterance")
    log.detail("rule -> llm", indent=" " * 14)
    log.rule(width=WIDTH)
    for number, (utterance, note) in enumerate(cases, start=1):
        rule_result = fmt(static(new_state(utterance)))
        trace.TIERS.pop(component, None)
        llm_result = fmt(llm(new_state(utterance)))
        tier = trace.last_tier(component)
        tiers[tier] = tiers.get(tier, 0) + 1
        mark = "*" if rule_result != llm_result else " "
        log.plain(f"{number:>2}  [{tier}]{'':{7 - len(tier)}s}{mark} {cut(utterance, WIDTH - 15)}")
        log.plain(f"{'':14s}rule: {cut(rule_result, 28):28s}  llm: {cut(llm_result, WIDTH - 50)}")
        log.detail(f"note: {cut(note, WIDTH - 20)}", indent=" " * 14)
        rows.append((number, utterance, rule_result, llm_result, tier, mark))
    return tiers, rows


def main() -> None:
    which = {"--address": ["address"], "--pizza": ["pizza"]}
    selected = [c for flag, comps in which.items() if flag in sys.argv for c in comps] or ["address", "pizza"]
    if not llm_service.configured():
        log.fail("no API key in .env", "the LLM column would be all fallbacks")
        log.hint("fill in .env first (see .env.example)")
        sys.exit(1)

    summary: dict[str, dict[str, int]] = {}
    all_rows: dict[str, list[tuple]] = {}
    if "address" in selected:
        summary["address_recognition"], all_rows["address_recognition"] = run("address_recognition", ADDRESS_CASES, fmt_address)
    if "pizza" in selected:
        summary["pizza_recognition"], all_rows["pizza_recognition"] = run("pizza_recognition", PIZZA_CASES, fmt_pizza)

    today = datetime.date.today().isoformat()
    usage = llm_service.service().usage
    total = sum(sum(t.values()) for t in summary.values())
    by_llm = sum(t.get("llm", 0) for t in summary.values())
    by_rule = total - by_llm

    log.plain()
    log.title("== one row per case; the starred ones are where the two implementations disagree ==")
    for component, rows in all_rows.items():
        log.plain(f"| {component} |  |  |  |  |  |")
        for number, utterance, rule_result, llm_result, tier, mark in rows:
            log.plain(f"| {number} | {utterance} | {rule_result} | {llm_result} | {tier}{' *' if mark == '*' else ''} |  |")

    log.plain()
    log.title("== the two numbers; 'correct' is your judgement today ==")
    log.plain("| date | configuration | cases | correct | answered by the model | answered by the rule |")
    log.plain("| --- | --- | --- | --- | --- | --- |")
    log.plain(f"| {today} | static | {total} | ___ | -- | all |")
    log.plain(f"| {today} | llm | {total} | ___ | {by_llm} | {by_rule} |")
    log.result(f"service usage: {usage.summary()}")

    log.plain()
    log.title("== the service card: what a colleague needs to maintain this step ==")
    from pizzabot import address_llm, pizza_llm   # noqa: E402 -- prompt versions and checks live there
    card = llm_service.service().describe()
    card["prompts"] = f"{address_llm.PROMPT_VERSION}.txt, {pizza_llm.PROMPT_VERSION}.txt"
    card["fallback"] = "the Iteration 1 rules (task3_pizza.py, task4_address.py)"
    card["domain checks"] = "; ".join(getattr(address_llm, "DOMAIN_CHECKS", ()) + getattr(pizza_llm, "DOMAIN_CHECKS", ()))
    tokens_in, tokens_out = usage.per_call()
    latencies = sorted(usage.latencies)
    card["measured latency (median / max)"] = (f"{latencies[len(latencies) // 2]:.2f} s / {latencies[-1]:.2f} s"
                                               if latencies else "no answer measured")
    card["measured tokens per call (in / out)"] = f"{tokens_in} / {tokens_out}"
    card["measured on (date)"] = today
    card["measured by"] = "____"
    log.plain("| what | value |")
    log.plain("| --- | --- |")
    for key, value in card.items():
        log.plain(f"| {key} | {value} |")


if __name__ == "__main__":
    try:
        main()
    except pizza_api.PizzaApiError as error:
        pizza_api.explain_and_exit(error)
