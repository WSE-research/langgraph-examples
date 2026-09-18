"""The state -- and with it the contract of every component in this process.

Read this file before you write a single node. In LangGraph the state *is* the
interface between components: a node receives it, returns a patch, and never
talks to another node directly. So "who may write which field" is the whole
design, and it is written down here, once.

Slot ownership (exactly one writer per slot -- this is what makes parallel work
in a team possible):

    input       the runner        the current user utterance, raw
    messages    every node        append-only history; use `say()` to add one
    slots
      pizza_name / pizza_id   pizza_recognition   (Task 3)
      address                 address_recognition (Task 4)
    expected    order_form      which slot was asked for last turn (Task 5)
    order_id    order_placement the id returned by POST /order
    ended       confirmation    True once the dialog is finished
"""

from __future__ import annotations

from typing import Optional, TypedDict

from langchain_core.messages import AIMessage


class Address(TypedDict):
    """A *complete* postal address. There is no half address in this process."""

    street: str
    house_number: str
    city: str


class OrderSlots(TypedDict, total=False):
    """The frame we are filling. `total=False` means: a slot may be missing."""

    pizza_name: str      # writer: pizza_recognition -- always a name from the menu
    pizza_id: int        # writer: pizza_recognition -- the id POST /order needs
    address: Address     # writer: address_recognition -- complete or absent


class ChatbotState(TypedDict):
    """Everything the process knows. One run of the graph = one user turn."""

    input: str                 # the current utterance
    messages: list             # history, append only
    slots: OrderSlots          # the frame
    expected: Optional[str]    # the slot the bot asked for last turn
    order_id: Optional[str]    # set once the order was placed
    ended: bool                # True -> the runner stops


def new_state(user_input: str = "") -> ChatbotState:
    """A fresh state. Every field exists from the start -- no surprises later."""
    return {
        "input": user_input,
        "messages": [],
        "slots": {},
        "expected": None,
        "order_id": None,
        "ended": False,
    }


def say(state: ChatbotState, text: str) -> dict:
    """Build the patch that appends one bot message.

    The only way a component talks to the user. Returning a *new* list instead
    of appending to the old one keeps nodes free of side effects.
    """
    return {"messages": state["messages"] + [AIMessage(text)]}


def last_message(state: ChatbotState) -> str:
    """The text of the last message, or '' if the bot said nothing this turn."""
    return state["messages"][-1].content if state["messages"] else ""
