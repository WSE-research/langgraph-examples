# Course 6 — Engineering AI-Driven Software Processes

Hands-on KGQA with LangGraph and LLMs — guest course at Université Jean Monnet Saint-Étienne, WS 2026/2027 (Prof. Dr. Andreas Both, HTWK Leipzig).

Six lectures, each followed by a 90-minute practical session. The students build one system across all six iterations: a pizza-ordering dialogue system that starts as a set of hand-written rules bound by explicit contracts, and then has its components replaced by LLM calls behind exactly those contracts. The recurring question of the course is not "does it answer?" but "how do you know it still does what you agreed it would?".

## Contents

| folder | iteration | what the students build |
| --- | --- | --- |
| [`exercise-01/`](exercise-01/) | 1 — from a goal to a process a team can build | a console pizza bot: contract-bound components, wired as a LangGraph process, exported as a diagram, covered by component tests — deliberately with no AI in it |
| [`exercise-02/`](exercise-02/) | 2 — an LLM inside the process, behind unchanged contracts | two of those components get a second, LLM-backed implementation: a schema check, a domain check and a fallback to the Iteration 1 rule. One process model, two configurations (`static`, `llm`), the same test suite green in both, and a measured comparison of the two |
| [`exercise-03/`](exercise-03/) | 3 — manifesting application quality | the iteration where the bot gets a *number*: hand-written test cases first, then test cases **generated** from a knowledge graph whose cities and pizzas are picked from the Pizza API itself; an evaluator that runs a configuration over them, stores every run and compares it with the previous one; and a generated `quality-report.md` whose last line says pass or fail against a threshold written down before the run |
| [`exercise-04/`](exercise-04/) | 4 — dynamic data and flexible processes | the iteration where the bot stops knowing things and starts **looking them up**: a knowledge graph of 22 pizzas behind the counter, factoid question answering decomposed into four contract-bound nodes and compiled as a **sub-graph** invoked as one step of the dialogue, a menu read from the graph on *every* turn with follow-up questions answered over the previous answer, and a factoid benchmark whose **four** metrics exist because they can disagree — a bot that answers nothing refuses perfectly |

The later iterations are added here as the course progresses.

Each folder is self-contained and starts where the previous iteration ended: `exercise-02/` ships the complete Iteration 1 bot, `exercise-03/` the complete Iteration 2 one. An unfinished iteration therefore never costs a team the next session.

`exercise-04/` is the exception, because from Iteration 4 on the material is **additive**: the knowledge base (`kb.py` and `data/`), the two test files and the benchmark are copied into the repository a team already has. A team that did not finish Iteration 3 starts from `exercise-03/` and copies `exercise-04/data/` into it — the sheet says so in its first table.

**Iteration 4 also needs the frontend.** Its first task runs the team's own compiled graph behind the [pizzabot Streamlit frontend](https://github.com/WSE-research/pizzabot), which is cloned *beside* the repository and never into it: the UI loads the graph, reads the process model out of it and draws what it finds, so nothing in `pizzabot/` ever learns that a browser exists.

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

The session also runs offline: `pizza_api_stub.py` mirrors that service endpoint for endpoint — same menu and ids, same delivery area, same error shapes — so a network failure costs nobody their session. That substitutability is the first contract the students meet. From Iteration 3 on the stub also serves `GET /city` from `exercise-03/data/cities.tsv.gz`, the same delivery area the service uses: every commune of France plus Leipzig, Halle and Dresden.

## Sample solutions

Sample solutions, the teaching guide, the reference runner and the expected output stay with the instructor and are not published here.
