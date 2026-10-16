"""Task 7 -- contract hand-over: implement the OTHER team's contract.

    python handover_address.py

The rule of this task: you may read the other team's contract and their
validation examples. You may not read their code, and you may not ask them a
question. Whatever is unclear, you have to decide yourself -- and then find out
whether you decided the way the authors meant it.

This is the claim of Lecture 1, slides 15-17, put to the test: a contract is
what lets somebody who did not design the process implement a component for it.
If your implementation passes their examples, the contract did its job. If it
does not, the contract was incomplete -- and the fix belongs in the contract,
not in your code.

The six parts of a contract (reads, writes, calls, rules, guarantee, failure) are
in the sheet: see "Reference -- the five parts of a contract" in README.md. This
file is where you find out whether somebody else's five parts are enough.

Three steps, ten minutes:

    1. paste the other team's contract into CONTRACT below, verbatim
    2. implement find_address_theirs() so that it satisfies *their* contract
    3. paste their validation examples into THEIR_CASES and run this file

Then sit together for two minutes and compare: which rows differ, and was the
difference in the contract or in the implementation?
"""

from __future__ import annotations

import re
import sys

from pizzabot import log          # the log layer: no script here calls print()

# --- step 1: their contract, copied word for word ---------------------------
CONTRACT = """
    name        address_recognition
    reads       ...
    writes      ...
    calls       ...
    rules       ...
    guarantee   ...
    failure     ...
"""

# --- step 2: your implementation of THEIR contract ---------------------------
# You may reuse the building blocks from your own task4_address.py, but the
# behaviour must follow their contract, not yours.
WORD = r"[^\W\d_][\w'’\-\.]*"
STREET = rf"{WORD}(?: {WORD}){{0,4}}"
NUMBER = r"\d+\s?[a-zA-Z]?"
CITY = rf"{WORD}(?:[ \-]{WORD}){{0,3}}"


def find_address_theirs(text: str) -> dict | None:
    """Their contract, your implementation.

    Returns {"street": ..., "house_number": ..., "city": ...} or None.
    """
    # TODO: implement what their contract describes
    return None


# --- step 3: their validation examples --------------------------------------
# (utterance, what THEY say should happen -- copy their expectations, not yours)
THEIR_CASES: list[tuple[str, str]] = [
    ("deliver it to 5 Rue Michelet, Saint-Étienne", "5 / Rue Michelet / Saint-Étienne"),
    # paste the rest here
]


def looks_the_same(got: str | None, expectation: str) -> bool:
    """Compare loosely: their expectation is free text, not a specification.

    "5 / Rue Michelet / Saint-Étienne" and "5/Rue Michelet/Saint-Etienne  " mean
    the same thing, and a difference in spacing is not a contract difference.
    Anything this function is unsure about lands in the "look at it together"
    pile, which is where the interesting rows belong anyway.
    """
    def fold(text: str) -> str:
        return " ".join(str(text).lower().replace("/", " ").split()).strip(" .")

    if got is None:
        return any(word in fold(expectation) for word in ("nothing", "none", "no address"))
    return fold(got) in fold(expectation) or fold(expectation) in fold(got)


def main() -> int:
    log.title("the contract you implemented:")
    log.block(CONTRACT)

    if "..." in CONTRACT:
        log.warn("CONTRACT still contains the template dots -- paste their contract in "
                 "first, word for word. Implementing against a half-copied contract "
                 "measures nothing.")
    if len(THEIR_CASES) < 2:
        log.warn("THEIR_CASES holds the single example from the template. Paste the case "
                 "list from their validate_task4.py, or you are testing your own "
                 "expectations, not their contract.")
    # Column widths in one place, so the rule is always the right length.
    UTTERANCE, GOT, EXPECTED = 38, 30, 30
    header = f"{'utterance':{UTTERANCE}s} {'your result':{GOT}s} {'they expect'}"
    log.title(header)
    log.rule(width=UTTERANCE + GOT + EXPECTED + 2)
    differences = 0
    for utterance, expectation in THEIR_CASES:
        found = find_address_theirs(utterance)
        got = (
            f"{found['house_number']} / {found['street']} / {found['city']}"
            if found
            else None
        )
        if not looks_the_same(got, expectation):
            differences += 1
        shown = got if got is not None else "- nothing -"
        log.plain(f"{utterance[:UTTERANCE - 1]:{UTTERANCE}s} "
                  f"{shown[:GOT - 1]:{GOT}s} {expectation[:EXPECTED]}")
    ready = len(THEIR_CASES) >= 2 and "..." not in CONTRACT
    log.plain()
    if not ready:
        log.warn("Nothing to compare yet -- paste their contract and their case list first.")
    elif differences:
        log.block(f"{differences} of {len(THEIR_CASES)} rows came out differently. That is not a\n"
              "score and not a failure: those rows are the material for the next two\n"
              "minutes. For each one, was their contract silent about it, or did you read\n"
              "it differently than they meant it? Name the part that failed you -- reads,\n"
              "writes, calls, guarantee or failure -- and write the sentence that would\n"
              "have prevented it into docs/process-model.md section 7.")
    else:
        log.block("Every row came out the way they expect. Now the harder question: could you\n"
                  "have got any of them wrong and still passed? Ask them for the case they\n"
                  "thought you would fail, and run that one too.")

    log.block(f"""
--------------------------------------------------------------------------
 Self-check -- the task is done when all five are true. You decide, not us.

  {"[auto]" if ready else "[ ?  ]"} every case they gave you produced a result ({len(THEIR_CASES)} case(s) run)
  [   ]  for each row you can say FROM THEIR CONTRACT ALONE whether your
         result is the one they promised ("I think they meant" is not a tick)
  [   ]  you implemented it without asking them a single question -- one
         question asked is one sentence missing; write that sentence down
  [   ]  every differing row has a named cause: which of the six parts
         (reads, writes, calls, rules, guarantee, failure) was silent or vague
  [   ]  at least one sentence went into YOUR OWN contract, section 7 of
         docs/process-model.md

 Passing every row is not the goal. Matching behaviour by luck is exactly
 the failure this exercise exists to expose -- if you cannot explain a row
 from their contract, the task is not finished.
--------------------------------------------------------------------------""")
    # Always 0: "rows differ" is the material of this task, not an error.
    return 0


if __name__ == "__main__":
    sys.exit(main())
