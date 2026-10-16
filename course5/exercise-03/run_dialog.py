"""Run the ordering bot in the terminal -- one graph run per user turn.

    python run_dialog.py                          # the static configuration (Iteration 1)
    python run_dialog.py --config llm             # the LLM-backed configuration (Iteration 2)
    python run_dialog.py --llm --script           # replay the lecture example, LLM-backed
    LOG_LEVEL=WARNING python run_dialog.py --llm  # hide the node trace

The loop below is deliberately dumb: read a line, invoke the graph once, print
what the bot said. Which implementation answers behind `pizza_recognition` and
`address_recognition` is decided by one dictionary (`pizzabot/config.py`); the
loop, the graph and the other components cannot tell the difference.
"""

from __future__ import annotations

import sys
import textwrap

from pizzabot import config, llm_service, log, pizza_api
from pizzabot.graph import build_graph
from pizzabot.state import new_state

# The walkthrough from Lecture 1, Part C -- and from Lecture 2, Part C.
SCRIPT = [
    "Hello",
    "I would like a Margherita",
    "deliver it to 5 Rue Michelet, Saint-Étienne",
]
SCRIPT_LLM = [
    "Hello",
    "can I order the four-cheese one to number 5 in the Rue Michelet here in Saint-Étienne?",
]
# Why "can I order" and not "can I get": the ROUTER is still the Iteration 1
# rule, and "can I get" is not one of its intent phrases -- the turn would go to
# help and the two LLM-backed components would never run. Routing is not what
# changes today; remember that case -- Iteration 3 measures it.


def main() -> None:
    configuration = config.from_argv(sys.argv)
    graph = build_graph(config.implementations(configuration))
    log.step(f"configuration: {configuration}")
    if configuration == config.LLM and not llm_service.configured():
        log.warn("no API key in .env -- every LLM call will fall back to the rule")
    state = new_state()
    scripted = iter(SCRIPT_LLM if configuration == config.LLM else SCRIPT) if "--script" in sys.argv else None
    spoken = 0

    while not state["ended"]:
        if scripted is not None:
            try:
                state["input"] = next(scripted)
            except StopIteration:
                log.plain()
                log.warn("script exhausted -- the dialog did not finish"
                         + ("; without a key the rule cannot parse the lecture "
                            "sentence, so the form keeps asking"
                            if configuration == config.LLM and not llm_service.configured() else ""))
                break
            log.plain()
            log.say("you", state["input"])
        else:
            try:
                state["input"] = log.prompt("\nyou: ")
            except (EOFError, KeyboardInterrupt):
                log.plain()
                log.say("bot", "bye")
                break
            if state["input"].strip().lower() in {"quit", "exit"}:
                break

        state = graph.invoke(state)

        if len(state["messages"]) > spoken:
            for message in state["messages"][spoken:]:
                log.block(textwrap.fill(message.content, width=79,
                                        initial_indent="bot: ", subsequent_indent="     "))
            spoken = len(state["messages"])
        else:
            log.say("bot", "(nothing to say -- look at the trace above to see why)")

    if state["ended"]:
        log.plain()
        log.result(f"=== dialog finished (configuration: {configuration}) ===")
        for slot, value in state["slots"].items():
            log.plain(f"    {slot:11s}: {value}")
        log.plain(f"    {'order_id':11s}: {state['order_id']}")
    if configuration == config.LLM:
        log.plain(f"    {'llm usage':11s}: {llm_service.service().usage.summary()}")


if __name__ == "__main__":
    try:
        main()
    except pizza_api.PizzaApiError as error:
        pizza_api.explain_and_exit(error)
