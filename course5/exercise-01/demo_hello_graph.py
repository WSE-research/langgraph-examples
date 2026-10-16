"""Task 1 -- the smallest useful LangGraph program, commented line by line.

Run it:

    python demo_hello_graph.py
    python demo_hello_graph.py "Ada"
    python demo_hello_graph.py "Dr. Ada Lovelace"

Nothing here is about pizza yet. The point is to see the four moving parts of
LangGraph once, in isolation, before the domain arrives:

    1. the STATE   -- one typed dictionary that travels through the process
    2. the NODES   -- plain Python functions: state in, *patch* out
    3. the EDGES   -- who runs after whom; a conditional edge is a decision
    4. the GRAPH   -- the compiled, runnable, *drawable* process

The whole process below is deterministic. No AI, no API, no randomness: the
same input always produces the same log. That is deliberate -- Iteration 1 is
about having full control before any model is involved.
"""

from __future__ import annotations

import sys
from typing import Optional, TypedDict

# `START` and `END` are the two virtual nodes every graph has: where a run
# enters and where it leaves. `StateGraph` is the builder we add nodes to.
from langgraph.graph import END, START, StateGraph

from pizzabot import trace

# ---------------------------------------------------------------------------
# 1. THE STATE -- the contract of the whole process
# ---------------------------------------------------------------------------
# Everything a node may read and everything it may write is declared here, in
# one place. A `TypedDict` gives us editor completion and type checking; at
# runtime it is an ordinary dict. Write down *who owns which field* in a
# comment -- that single habit prevents most of the bugs in a team project.
class GreetingState(TypedDict):
    name: str                    # written by: the caller (the raw input)
    clean_name: Optional[str]    # written by: normalize
    greeting: Optional[str]      # written by: casual_greeting / formal_greeting
    style: Optional[str]         # written by: normalize (the routing criterion)


# ---------------------------------------------------------------------------
# 2. THE NODES -- one component each, and each one logs what it does
# ---------------------------------------------------------------------------
# A node is a function of the state with no side effects *on the state*: it
# receives the whole state and returns a **patch** -- a dict with only the fields it changes. LangGraph
# merges that patch into the state. Returning `{}` is perfectly legal and means
# "I had nothing to contribute".
#
# Never mutate `state` in place. Returning a patch is what makes a node
# testable in isolation (you call it with a hand-written dict) and what makes
# the process reviewable.

def normalize(state: GreetingState) -> dict:
    """Clean the raw input and decide which greeting style is appropriate.

    Contract
        input       : state["name"] -- raw, may have spaces or a title
        output      : clean_name (str), style ("formal" | "casual")
        guarantee   : clean_name is never empty; style is always one of the two
        failure     : an empty input becomes the placeholder "stranger"
    """
    trace.received("normalize", state, "name")

    raw = (state["name"] or "").strip()
    if not raw:
        trace.doing("normalize", "input was empty -- falling back to 'stranger'")
        raw = "stranger"

    # Rule: a title or a multi-part name is treated as formal. One simple,
    # decidable rule -- that is exactly the decomposition criterion from the
    # lecture: refine until a sub-task is solvable by one simple rule.
    title = raw.split()[0] if raw.split()[0] in ("Dr.", "Prof.", "Mr.", "Ms.") else None
    formal = title is not None or len(raw.split()) > 1
    style = "formal" if formal else "casual"
    trace.doing(
        "normalize",
        f"{len(raw.split())} word(s), title={title!r} -> style={style!r}",
    )

    return trace.returns(
        "normalize",
        {"clean_name": raw, "style": style},
        next_step="choose_style (conditional edge) -> casual_greeting | formal_greeting",
    )


def casual_greeting(state: GreetingState) -> dict:
    """Contract: reads clean_name, writes greeting. Never fails."""
    trace.received("casual_greeting", state, "clean_name", "style")
    trace.doing("casual_greeting", "short, informal wording")
    return trace.returns(
        "casual_greeting",
        {"greeting": f"Hi {state['clean_name']}!"},
        next_step="END",
    )


def formal_greeting(state: GreetingState) -> dict:
    """Contract: reads clean_name, writes greeting. Never fails."""
    trace.received("formal_greeting", state, "clean_name", "style")
    trace.doing("formal_greeting", "polite wording, full name kept as given")
    return trace.returns(
        "formal_greeting",
        {"greeting": f"Good day, {state['clean_name']}. A pleasure."},
        next_step="END",
    )


# ---------------------------------------------------------------------------
# 3. THE ROUTER -- a decision is a component, not a scattered `if`
# ---------------------------------------------------------------------------
# A routing function does not change the state. It reads it and returns the
# *name of the next node*. Keeping every routing rule in such a function is
# what makes the process drawable: the diagram you export later is only as
# honest as this function.

def choose_style(state: GreetingState) -> str:
    """Return the name of the node that should run next."""
    if state["style"] == "formal":
        return trace.decision("choose_style", "formal_greeting", "style == 'formal'")
    return trace.decision("choose_style", "casual_greeting", "style == 'casual'")


# ---------------------------------------------------------------------------
# 4. THE GRAPH -- wiring the components into a process
# ---------------------------------------------------------------------------
def build_graph():
    """Wire the components together and compile the process.

    Building and compiling is separated from running on purpose: the compiled
    graph is the artifact we visualize in Task 2 and the artifact a reviewer
    looks at -- independently of any single run.
    """
    workflow = StateGraph(GreetingState)

    # Nodes: a name (used in the diagram and the log) and a function.
    workflow.add_node("normalize", normalize)
    workflow.add_node("casual_greeting", casual_greeting)
    workflow.add_node("formal_greeting", formal_greeting)

    # Fixed edge: after START, always run `normalize`.
    workflow.add_edge(START, "normalize")

    # Conditional edge: after `normalize`, ask `choose_style` where to go.
    # The list names every branch that may be chosen -- LangGraph needs it to
    # draw the diagram, and a reader needs it to see the alternatives.
    workflow.add_conditional_edges(
        "normalize", choose_style, ["casual_greeting", "formal_greeting"]
    )

    # Both branches finish the run.
    workflow.add_edge("casual_greeting", END)
    workflow.add_edge("formal_greeting", END)

    return workflow.compile()


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "Ada"
    graph = build_graph()

    print(f"\n=== running the process for name={name!r} ===")
    # `invoke` runs the process once and returns the final state.
    final_state = graph.invoke({"name": name, "clean_name": None, "greeting": None, "style": None})

    print("\n=== final state ===")
    for key, value in final_state.items():
        print(f"    {key:11s} = {value!r}")
    print(f"\nthe bot would say: {final_state['greeting']}")


if __name__ == "__main__":
    main()
