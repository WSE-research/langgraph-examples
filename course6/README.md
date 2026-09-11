# Course 6 — Engineering AI-Driven Software Processes

Hands-on KGQA with LangGraph and LLMs — guest course at Université Jean Monnet Saint-Étienne, WS 2026/2027 (Prof. Dr. Andreas Both, HTWK Leipzig).

Six lectures, each followed by a 90-minute practical session. The students build one system across all six iterations: a pizza-ordering dialogue system that starts as a set of hand-written rules bound by explicit contracts, and then has its components replaced by LLM calls behind exactly those contracts. The recurring question of the course is not "does it answer?" but "how do you know it still does what you agreed it would?".

## Contents

| folder | iteration | what the students build |
| --- | --- | --- |
| [`exercise-01/`](exercise-01/) | 1 — from a goal to a process a team can build | a console pizza bot: contract-bound components, wired as a LangGraph process, exported as a diagram, covered by component tests — deliberately with no AI in it |

The later iterations are added here as the course progresses.

## Getting started (students)

```bash
git clone https://github.com/WSE-research/langgraph-examples.git
cd langgraph-examples/course6/exercise-01
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python check_setup.py
```

`exercise-01/README.md` is the exercise sheet: preparation, eight tasks with their time budget, a reference section on what a contract is, a glossary, and a reading list. Do the preparation right after the lecture, not at the start of the session.

Work in your own repository rather than in this clone — fork this one, or copy the exercise folder into a fresh repository. The folder is the initial commit of a repository that grows over all six iterations, so the first commit should still contain the untouched skeleton.

## The Pizza API

The exercises order from a live service at <https://wse-research.org/pizza-api>, which serves its own interactive Swagger UI at that address. Its source is [`common/main.py`](../common/main.py) in this repository.

The session also runs offline: `exercise-01/pizza_api_stub.py` mirrors that service endpoint for endpoint — same menu and ids, same delivery area, same error shapes — so a network failure costs nobody their session. That substitutability is the first contract the students meet.

## Sample solutions

Sample solutions, the teaching guide, the reference runner and the expected output stay with the instructor and are not published here.
