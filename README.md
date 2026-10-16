# LangGraph Examples

This repository is dedicated for collecting applications examples built with LangGraph (mostly chatbots and dialogue agents).

## What is [LangGraph](https://langchain-ai.github.io/langgraph/)

LangGraph is a library to build dialogue systems. In general, it operates as a [Finite State Machine (FSM)](https://link.springer.com/chapter/10.1007/978-3-319-62533-1_4#Sec1).

In other words, a dialogue is modeled wtih:
* A list of nodes (e.g. entry node, greeting node, order node)
* A list of edges: transitions between the nodes (can also be conditional)
* A dialogue state: a dictionary with slots that are to be filled within a dialogue (e.g. client address when ordering a pizza)

**Important:** Don't mix up an "FSM State" (a node) and a "Dialogue State" (a collection of [slots](https://paperswithcode.com/task/slot-filling/latest#:~:text=The%20goal%20of,the%20target%20entity.) to be filled).

## Structure

### [Python examples](https://github.com/WSE-research/langgraph-examples/tree/main/python_examples)

### Course material

The practical sessions of *Engineering AI-Driven Software Processes — Hands-on KGQA with LangGraph and LLMs*, with their running examples in Greece (`5 Ermou, Athens`):

- [`course5/`](https://github.com/WSE-research/langgraph-examples/tree/main/course5) — the Athens edition (National and Kapodistrian University of Athens, WS 2026/2027);
- [`course6/`](https://github.com/WSE-research/langgraph-examples/tree/main/course6) — the same six exercises with the same examples (WS 2026/2027).

Both use the [Pizza API](common/) at <https://wse-research.org/pizza-api>, one frozen version per exercise (`/v1` … `/v6`).

### JavaScript examples (To be done...)


