"""Task 4c -- validate address recognition by hand, with examples you choose.

    python validate_task4.py
    LOG_LEVEL=WARNING python validate_task4.py

The guarantee to check in every row: *complete or nothing*. A row that produces
a street without a city is a broken contract, not a small inaccuracy -- it would
send a pizza to a place that does not exist.
"""

from __future__ import annotations

from pizzabot import log, pizza_api
from pizzabot.state import new_state
from pizzabot.task4_address import build_graph

CASES: list[tuple[str, str]] = [
    # utterance                                             what you expect
    ("deliver it to 5 Rue Michelet, Saint-Étienne",         "5 / Rue Michelet / Saint-Étienne"),
    ("please deliver to 12b Rue de la Paix, Lyon",          "12b / Rue de la Paix / Lyon"),
    ("Karl-Liebknecht-Strasse 132, Leipzig",                "132 / Karl-Liebknecht-Strasse / Leipzig"),
    ("my address is 7 Avenue de la Libération, Saint-Priest-en-Jarez", "7 / Avenue ... / Saint-Priest-en-Jarez"),
    ("somewhere near the station",                          "nothing -- not an address"),
    ("Rue Michelet",                                        "nothing -- no number, no city"),
    ("5 Rue Michelet Saint-Étienne",                        "nothing -- the comma is missing (known limitation)"),
    # TODO: three cases of your own. Ideas: a flat number, a postcode, an
    #       address in a language you speak, a second address in the same
    #       sentence, a city written in lower case.
]


def cut(text: str, width: int) -> str:
    """Truncate to `width` characters, visibly: a cut row ends in '..'."""
    text = str(text)
    return text if len(text) <= width else text[: width - 2] + ".."


def main() -> None:
    graph = build_graph()
    # Column widths in one place: the rule can then never be the wrong length.
    UTTERANCE, RECOGNISED, EXPECTED = 38, 30, 30
    header = f"{'utterance':{UTTERANCE}s} {'recognised address':{RECOGNISED}s} {'you expected'}"
    log.plain()
    log.title(header)
    log.rule(width=UTTERANCE + RECOGNISED + EXPECTED + 2)
    for utterance, expectation in CASES:
        result = graph.invoke(new_state(utterance))
        address = result["slots"].get("address")
        recognised = (
            f"{address['house_number']} / {address['street']} / {address['city']}"
            if address
            else "- nothing -"
        )
        log.plain(f"{cut(utterance, UTTERANCE - 1):{UTTERANCE}s} "
                  f"{cut(recognised, RECOGNISED - 1):{RECOGNISED}s} {cut(expectation, EXPECTED)}")
    log.plain()
    log.block(
        "There is no PASS column on purpose -- you are the judge.\n"
        "Check the guarantee in every row: all three fields, or no slot at all.\n"
        "A partial address must never reach slots.address. Write the rows your\n"
        "rules cannot win into section 6 of docs/process-model.md."
    )


if __name__ == "__main__":
    try:
        main()
    except pizza_api.PizzaApiError as error:
        pizza_api.explain_and_exit(error)
