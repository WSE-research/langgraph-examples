"""Task 3c -- validate pizza recognition by hand, with examples you choose.

    python validate_task3.py
    LOG_LEVEL=WARNING python validate_task3.py     # table only, no node trace

Manual validation means: you predict the outcome, then you look. Fill the
`expectation` column *before* you run the script -- a case whose expectation you
write afterwards proves nothing.

Add at least three cases of your own, and make one of them a case you expect the
component to get wrong. Keep it: in Iteration 3 these examples become the first
rows of the benchmark dataset, and in Iteration 2 the case you could not solve
with a rule is the one that shows what an LLM buys you.
"""

from __future__ import annotations

from pizzabot import log, pizza_api
from pizzabot.state import new_state
from pizzabot.task3_pizza import build_graph

CASES: list[tuple[str, str]] = [
    # utterance                                     what you expect to happen
    ("I would like a Margherita",                   "pizza_name = Margherita (exact)"),
    ("one Margaritha please",                       "pizza_name = Margherita (one typo)"),
    ("do you have Quattro Formaggi?",               "pizza_name = Quattro Formaggi"),
    ("I want sushi",                                "nothing recognised, silent"),
    ("I am hungry",                                 "nothing recognised, silent"),
    # TODO: three cases of your own. Ideas: two pizzas in one sentence, a pizza
    #       written in lower case, a name with a French article, a typo in the
    #       middle of a long word, a pizza that is not on the menu.
]


def cut(text: str, width: int) -> str:
    """Truncate to `width` characters, visibly: a cut row ends in '..'."""
    text = str(text)
    return text if len(text) <= width else text[: width - 2] + ".."


def main() -> None:
    graph = build_graph()
    # Column widths in one place: the rule can then never be the wrong length.
    UTTERANCE, RECOGNISED, EXPECTED = 40, 24, 34
    header = f"{'utterance':{UTTERANCE}s} {'recognised':{RECOGNISED}s} {'you expected'}"
    log.plain()
    log.title(header)
    log.rule(width=UTTERANCE + RECOGNISED + EXPECTED + 2)
    for utterance, expectation in CASES:
        result = graph.invoke(new_state(utterance))
        slots = result["slots"]
        recognised = (
            f"{slots['pizza_name']} (id {slots['pizza_id']})" if "pizza_name" in slots else "- nothing -"
        )
        log.plain(f"{cut(utterance, UTTERANCE - 1):{UTTERANCE}s} "
                  f"{cut(recognised, RECOGNISED - 1):{RECOGNISED}s} {cut(expectation, EXPECTED)}")
    log.plain()
    log.block(
        "There is no PASS column on purpose -- you are the judge.\n"
        "A row passes when you can name the rule that produced it; a row that is\n"
        "right for the wrong reason is a failure. The trace above says which rule\n"
        "was applied. Write the rows that surprised you into section 6 of\n"
        "docs/process-model.md."
    )


if __name__ == "__main__":
    try:
        main()
    except pizza_api.PizzaApiError as error:
        pizza_api.explain_and_exit(error)
