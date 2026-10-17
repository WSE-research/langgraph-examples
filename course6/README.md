# Course 6 — Engineering AI-Driven Software Processes

Hands-on KGQA with LangGraph and LLMs, WS 2026/2027 (Prof. Dr. Andreas Both, HTWK Leipzig), with its running examples in Greece (`5 Ermou, Athens`). [`course5/`](../course5/) is the Athens edition of the same course (National and Kapodistrian University of Athens) and holds the same six exercises with the same examples; the versions of the Pizza API are the same in both.

Six lectures, each followed by a 90-minute practical session. The students build one system across all six iterations: a pizza-ordering dialogue system that starts as a set of hand-written rules bound by explicit contracts, and then has its components replaced by LLM calls behind exactly those contracts. The recurring question of the course is not "does it answer?" but "how do you know it still does what you agreed it would?".

## Contents

| folder | iteration | what the students build |
| --- | --- | --- |
| [`exercise-01/`](exercise-01/) | 1 — from a goal to a process a team can build | a console pizza bot: contract-bound components, wired as a LangGraph process, exported as a diagram, covered by component tests — deliberately with no AI in it |
| [`exercise-02/`](exercise-02/) | 2 — an LLM inside the process, behind unchanged contracts | two of those components get a second, LLM-backed implementation: a schema check, a domain check and a fallback to the Iteration 1 rule. One process model, two configurations (`static`, `llm`), the same test suite green in both, and a measured comparison of the two |
| [`exercise-03/`](exercise-03/) | 3 — manifesting application quality | the iteration where the bot gets a *number*: hand-written test cases first, then test cases **generated** from a knowledge graph whose cities and pizzas are picked from the Pizza API itself; an evaluator that runs a configuration over them, stores every run and compares it with the previous one; and a generated `quality-report.md` whose last line says pass or fail against a threshold written down before the run |
| [`exercise-04/`](exercise-04/) | 4 — dynamic data and flexible processes | the iteration where the bot stops knowing things and starts **looking them up**: a knowledge graph of 22 pizzas behind the counter, factoid question answering decomposed into four contract-bound nodes and compiled as a **sub-graph** invoked as one step of the dialogue, a menu read from the graph on *every* turn with follow-up questions answered over the previous answer, and a factoid benchmark whose **four** metrics exist because they can disagree — a bot that answers nothing refuses perfectly |
| [`exercise-05/`](exercise-05/) | 5 — explainability, trust, and repair | the iteration where the process starts **accounting for itself**: a dead end becomes a declared information need that another component answers, every request to a component leaves one **W3C Web Annotation** carrying what it was given, what it returned and how sure it was, every call to the model leaves one of its own, and `what_happened(target)` reads a whole turn back in time order — then the team runs its own bot in the Pizzabot frontend and writes down what surprised them |
| [`exercise-06/`](exercise-06/) | 6 — answers from text, and what you would build next | the iteration where the bot gets a **second representation**: 22 invented pizza stories ingested into a RAG collection, a retrieval node behind a contract (top-k, a score threshold, an empty result that is not an error), an answer that **cites its passages or refuses**, and a closing half hour in which each team designs, draws and presents the Pizzabot they would build next |

All six iterations are here.

Each folder is self-contained and starts where the previous iteration ended: `exercise-02/` ships the complete Iteration 1 bot, `exercise-03/` the complete Iteration 2 one. An unfinished iteration therefore never costs a team the next session.

`exercise-04/` is where that changes, because from Iteration 4 on the material is **additive**: the knowledge base (`kb.py` and `data/`), the test files and the benchmark are copied into the repository a team already has. A team that did not finish Iteration 3 starts from `exercise-03/` and copies `exercise-04/data/` into it — the sheet says so in its first table. `exercise-05/` and `exercise-06/` work the same way: the first ships the knowledge base and the tests of its tasks again, the second ships only the story corpus the teams retrieve from.

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

The exercises order from a live service at <https://wse-research.org/pizza-api>. Its source is [`common/main.py`](../common/main.py) in this repository, and every address below serves its own interactive Swagger UI.

**Every exercise uses its own version of the service**, and a version does not change once it is published: the service grows during the course — more pizzas, a larger delivery area, pizzas that sell out — and what a team built in Iteration 1 keeps working against the version it was built for. **The version lives in the adapter, not in `.env`.** Every exercise from 2 on ships its Pizza API adapter, `pizzabot/pizza_api.py`, whose `VERSION` is the version of that exercise (exercise 1 names v1 in its client and in its `.env.example`). A team takes the adapter with the material of each iteration — from Iteration 4 on, where the material is copied into the team's repository, the sheet lists it and `tests/conftest.py` stops the run while the adapter is still an older one — and deletes any `PIZZA_API_BASE` line an earlier iteration left in `.env`. `PIZZA_API_BASE` is for the local stub only; a line that names another version of the service is ignored, with a warning on the first request. The address without a version is the newest one, and no exercise uses it.

| version | exercise | what it serves |
| --- | --- | --- |
| <https://wse-research.org/pizza-api/v1> | `exercise-01/` | the four endpoints of Lecture 1; the menu of ten pizzas (`id`, `name`); the nine cities of the course examples — Leipzig, Halle, Dresden, Saint-Étienne, Saint-Priest-en-Jarez, Lyon, Athens, Piraeus, Agia Paraskevi — and `400` for anything else; every pizza can always be ordered |
| <https://wse-research.org/pizza-api/v2> | `exercise-02/` | the menu of twenty-two pizzas, which the LLM-backed recognizer reads into its prompt; the full delivery area and `GET /city`; every pizza can always be ordered |
| <https://wse-research.org/pizza-api/v3> | `exercise-03/` | as v2 — `GET /city` is the endpoint the teams pick their benchmark cities from |
| <https://wse-research.org/pizza-api/v4> | `exercise-04/` | as v3 |
| <https://wse-research.org/pizza-api/v5> | `exercise-05/` | as v4, and **two pizzas are sold out every minute**: `GET /pizza` marks them `"available": false` (the same two for every request within that minute, drawn at random for the next) and `POST /order` refuses them with `409 Conflict` — the case the repair of Iteration 5 is built on |
| <https://wse-research.org/pizza-api/v6> | `exercise-06/` | as v5 — the RAG branch does not call the service, and every test of Iterations 3 to 5 stays green against it |

The full delivery area is every commune of France and every town and village of Greece, plus Leipzig, Halle and Dresden — about 43 000 names, compared without accents and without case; a Greek place is also accepted under its other spellings (`Athina`, `Αθήνα`). A city outside it has to come from elsewhere: the exercises use Barcelona.

Test drivers — every `conftest.py`, `validate_task5.py`, `adversarial.py` — set `PIZZA_API_ACCEPT_EVERYTHING=true`, and `pizzabot/pizza_api.py` then sends `X-Accept-Everything: true`, with which v5 and v6 accept a sold-out pizza anyway, so that a test that orders a fixed pizza does not fail in the minutes that pizza is drawn; the earlier versions ignore the header. An interactive dialog never sends it — it meets the 409, and Iteration 5 turns that into a repair. `PIZZA_AVAILABILITY_SEED` makes the draw reproducible.

The session also runs offline: `pizza_api_stub.py` mirrors the exercise's version endpoint for endpoint — same menu and ids, same error shapes — so a network failure costs nobody their session. That substitutability is the first contract the students meet. The stub of Iteration 1 knows the nine cities of the course examples; from Iteration 2 on the stub loads the full delivery area from its `data/cities.tsv.gz`, the same file the service uses, and from Iteration 3 on it also answers `GET /city`. `common/tests/` holds every version, and every stub, to what its exercise needs.

## Sample solutions

Sample solutions, the teaching guide, the reference runner and the expected output stay with the instructor and are not published here.
