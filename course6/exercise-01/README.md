# Exercise 1 — from a goal to a process a team can build

Iteration 1 of *Engineering AI-Driven Software Processes — Hands-on KGQA with LangGraph and LLMs*, Université Jean Monnet Saint-Étienne, WS 2026/2027.

**Today there is no AI in your system.** Every component you build is a rule you can read, run and predict. That is the point: you cannot tell whether an AI made your system better until you have a system whose behaviour you control. Iteration 2 replaces two of today's rules with an LLM — behind exactly the contracts you write today.

**What you build:** a console pizza-ordering bot, decomposed into contract-bound components, wired as a LangGraph process, exported as a diagram, and covered by component tests.

**Definition of done** — the list of things that must be finished for this iteration to count. It is what you show at the end of the session, and what the repository has to contain:

1. `python check_setup.py` — green (the LLM endpoint is the one check that stays red until Task 8).
2. `docs/process-model.md` — dialog, contracts, your hand-drawn process, the exported diagram, and the differences between the two.
3. `docs/pizza-process-model.mmd` and `.png` — exported from the compiled graph, committed.
4. `python run_dialog.py` — completes a full order and prints an order id.
5. `pytest -q` — green, with at least three tests you added yourself.
6. Your validation runs (Tasks 3c/4c/5c) with your own examples, and the list of cases your rules cannot handle.
7. `handover_address.py` — the neighbouring team's contract, implemented by you, and what that told you about their contract and yours (`docs/process-model.md` section 7).
8. `python check_llm.py` — the LLM endpoint answered. Needed from Iteration 2 on; finish it at home if the session runs out.

The **preparation** below happens right after the lecture, before the break. The tasks are timed for the 90-minute session that follows. The session is full: the ten minutes not spent on tasks are the briefing at the start and the closing round at the end, so there is no hidden reserve. Task 8 is the only one you may finish at home.

| | task | minutes | you are done when |
| --- | --- | --- | --- |
| ☐ | 1 — your first graph | 0–8 | three answers in `docs/process-model.md` section 0 |
| ☐ | 2 — the picture | 8–13 | `docs/demo-process-model.mmd` exists |
| ☐ | 3 — pizza recognition | 13–32 | `validate_task3.py` runs on your own cases |
| ☐ | 4 — address recognition | 32–48 | `validate_task4.py` runs; section 6 has a row |
| ☐ | 5 — form and routing | 48–62 | `validate_task5.py` replays your own dialog |
| ☐ | 6 — everything together | 62–70 | `run_dialog.py` prints an order id, `pytest -q` is green, **commit** |
| ☐ | 7 — the hand-over | 70–80 | all five ticks at the end of `handover_address.py` |
| ☐ | 8 — the LLM endpoint | at home | `check_llm.py` got an answer |

The minutes count from the start of your own work, after the briefing. If you fall behind, cut the second round of validation cases in 3c or 4c. Never cut Task 7.

Tasks 1–7 add up to 80 of the 90 minutes, which leaves ten for the things that always happen. If you fall behind, cut the *second* validation round in Task 3c or 4c — **do not cut Task 7**. Task 7 is the part of the session that teaches why contracts matter.

---

## Preparation — right after the lecture, before the break [~12 min]

Do this immediately after the lecture, not at the beginning of the exercise session: an installation that goes wrong costs you the first twenty minutes of the session, and the break is more useful once the machine is ready. When `check_setup.py` is green, go and have your break.

**1. Install Python 3.10 or newer.** Check what you have first — `python3 --version` (Windows: `python --version`).

| system | how |
| --- | --- |
| Windows | installer from <https://www.python.org/downloads/> — tick **Add python.exe to PATH** in the first dialog |
| macOS | `brew install python@3.12`, or the installer from <https://www.python.org/downloads/> |
| Linux (Debian, Ubuntu) | `sudo apt install python3 python3-venv python3-pip` |

Python 3.9 and older is not sufficient: `langgraph` does not install on them. If your system Python is too old and you cannot replace it, say so now rather than during the session.

**2. Get the repository, create a virtual environment, install the dependencies.**

```bash
git clone https://github.com/WSE-research/langgraph-examples.git
cd langgraph-examples/course6/exercise-01
python3 -m venv .venv
source .venv/bin/activate                       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                            # the key for Task 8 goes in here
```

This folder is the skeleton you grow over all six iterations. Work in your **own** repository, not in the clone: either fork `WSE-research/langgraph-examples` and work in `course6/exercise-01/`, or copy this folder into a fresh repository of your own — whichever your instructor asked for. Everything below assumes your working directory is this folder.

The virtual environment has to be active in every terminal you use — the prompt shows `(.venv)`. Windows and accented characters: if the console throws a `UnicodeEncodeError` on `Saint-Étienne`, run `set PYTHONUTF8=1` (PowerShell: `$env:PYTHONUTF8=1`) once per terminal.

**3. Check the machine.**

```bash
python check_setup.py
```

Thirteen checks: the Python version, whether your console can print `Saint-Étienne`, the six packages, a two-node graph that really runs, a node that returns `{}` (the failure rule of every component you will write today), a Mermaid export, the Pizza API, and whether the LLM endpoint is configured. The last one is marked `[todo]` and stays open until Task 8; the script still finishes with `READY FOR THE SESSION`. Every failure prints the command that fixes it.

**If the Pizza API is not reachable** (university network, VPN, or the service is down), start the local stand-in in a second terminal and point the bot at it:

```bash
python pizza_api_stub.py                        # terminal 2, leave it running
PIZZA_API_BASE=http://127.0.0.1:8000 python check_setup.py     # terminal 1
```

The stub answers exactly like the university service: the same four endpoints, the same menu with the same ids, the same delivery area, the same error messages, byte for byte. The fact that you can replace one with the other is the first contract you meet today: `pizzabot/pizza_api.py` owns the contract, two different implementations satisfy it, and the process cannot tell them apart.

**Look at the API before you use it.** It documents itself at its own URL:

| | URL | what you get |
| --- | --- | --- |
| the university service | <https://wse-research.org/pizza-api> | the interactive Swagger UI: every endpoint, every payload, and a *Try it out* button that sends real requests |
| the Swagger page itself | <https://wse-research.org/pizza-api/docs> | the same HTML documentation under its own address — use this one if the base URL ever answers `404` |
| the machine-readable schema | <https://wse-research.org/pizza-api/openapi.json> | the OpenAPI document behind that page |
| your local stub | <http://127.0.0.1:8000> | the same endpoint list as a plain HTML page (no CDN, so it works offline) |

Spend five minutes with the *Try it out* button: order a pizza by hand, then read it back with `GET /order/{order_id}`. It will save you more time than that in Tasks 3 to 5.

The delivery area is part of the contract too, and the API is the only place that knows it: it delivers to Leipzig, Halle, Dresden, Saint-Étienne, Saint-Priest-en-Jarez and Lyon, and answers `400` with a message for anything else. Your `address_recognition` component must handle that `400` answer without filling the address slot. The contract is in `pizzabot/task4_address.py`.

**4. Commit.** Make your first commit now, with the untouched skeleton in it. The repository grows over all six iterations, and a first commit that already contains your changes hides which parts you wrote yourself.

---

## Reference — the six parts of a contract

Read this once now. It is the shape every skeleton in `pizzabot/` is written in, so you will meet it again in Tasks 3, 4 and 5, and you will need it in Task 7.

### The six parts

Six statements about one component. You have been reading them all session — every skeleton in `pizzabot/` opens with one:

| part | the question it answers | from `pizzabot/task4_address.py` | the classical name |
| --- | --- | --- | --- |
| **reads** | which parts of the state may this component look at? | `state["input"]`, `state["slots"]`, `state["expected"]` | the component's view of the state (Parnas 1972) |
| **writes** | which slots may it change, and by omission which it must never touch | `slots.address` | the frame condition, the *modifies* clause |
| **calls** | which service does it talk to, and what for? | `POST /address/validate` | the dependency you can substitute — in Iteration 2 an LLM appears in this row |
| **rules** | by which decidable rules does the output follow from the input? | two patterns, filler stripped, then the validation call | the functional specification (Hoare 1969) |
| **guarantee** | what will it never do, whatever arrives? | complete address or no slot at all, never a partial one | the **postcondition** (Meyer 1992) |
| **failure** | what happens when no rule applies? | empty patch `{}`; the order form asks | the decision to make the contract **total** instead of stating a precondition |

A contract is not a description of your code. It is the smallest text that lets a stranger write that code — and lets another stranger *rely* on it without reading it.

### Why all six are needed

Take a component nobody in this room has built, so you can judge it without defending it: `quantity_recognition`, which is supposed to find out how many pizzas the user wants.

```text
name     quantity_recognition
input    the user's message
output   the number of pizzas
rules    find the number in the text
```

This looks acceptable, and it is useless. Hand it to three teams and you get three different systems, because it does not say:

| the utterance | what should happen? |
| --- | --- |
| "I'd like a pizza" | `1`, because "a" is a quantity? Or nothing, because there is no digit? |
| "2 or 3 pizzas" | `2`? `3`? Nothing, because it is ambiguous? |
| "I want 500 pizzas" | `500`? A refusal? Is the limit this component's job at all? |
| "just a pizza please" | who asks the follow-up question — this component, or the order form? |
| nothing recognised | an empty patch, a message, or an exception? |

Now the same component, as a contract:

```text
name        quantity_recognition
reads       state["input"], state["slots"]
writes      slots.quantity, expected
rules       1. a digit sequence -> that number            ("3 pizzas" -> 3)
            2. the words one..ten, and the articles a/an  ("a pizza"  -> 1)
            3. several candidates -> the first one in the utterance wins
guarantee   slots.quantity is an int in 1..10, or the slot is not written at all;
            no other slot is ever touched; this component never asks a question
failure     no number found        -> {} (the order form asks)
            a number outside 1..10 -> {} and expected = "quantity"
```

Every row of the table above now has exactly one answer, and two strangers implementing this produce the same behaviour. That is what "promise" means — and it is why the contract, not the code, is what you hand over.

You will see the word *contract* used at three scales in this course, and the shape is the same at each: a **component** (this section), a **module** (`pizzabot/pizza_api.py` owns the contract with the Pizza API, and the offline stub satisfies the same one), and a **protocol** (the OpenAI wire format that Task 8 talks to, which several providers implement).

None of the six parts has a precondition, and that is a decision, not an oversight: a component that reads natural language cannot demand anything of its input, so it states a **failure** behaviour instead and accepts everything. The one precondition in this process is in `pizzabot/task5_form.py` — `order_placement` needs a full frame — and it is established by the condition on the edge, not by an `if`.

If you want the original: Meyer, B. (1992), *Applying "Design by Contract"*, IEEE Computer 25(10), 40–51, [doi:10.1109/2.161279](https://doi.org/10.1109/2.161279) — where preconditions, postconditions and invariants come from, and why they belong in the interface rather than in the code. The rule that a component either *does* something or *decides* something, never both, is Meyer's command–query separation.

## Glossary

Ten words this sheet and the code use constantly. If a sentence stops making sense, the reason is usually in this list.

| word | what it means here |
| --- | --- |
| **utterance** | one message typed by the user; the raw text in `state["input"]` |
| **slot** | one named piece of information the bot must collect (`pizza_name`, `address`). Filling slots is what this bot does. |
| **frame** | the set of slots belonging to one task — here: pizza + address. "The frame is full" means every required slot has a value. |
| **patch** | what a node returns: a dict with only the fields it changes, which LangGraph merges into the state. `{}` is a legal patch and means "I had nothing to contribute". |
| **node** | one component in the graph; a function `state -> patch` |
| **edge** | who runs after whom. A **conditional edge** asks a function which node comes next. |
| **router** | a component that only decides: it returns the *name* of the next node and never changes the state |
| **stub** | a stand-in implementation that satisfies the same contract as the real thing — here `pizza_api_stub.py` for the university Pizza API |
| **fuzzy match** | accepting a word that is close enough to a known one ("Margarita" for "Margherita"), measured here with `difflib` |
| **golden reference** | a stored expected result that a test compares against — your validation cases become the first one of the course |

## Task 1 — read, then run your first LangGraph [8 min]

> **One component, two names.** In LangGraph a node is registered as `workflow.add_node("pizza_recognition", recognize_pizza)`. The **string** (`"pizza_recognition"`) is the component's name in the process model — it is what appears in the diagram, in the edges and in the trace. The **function** (`recognize_pizza`) is the implementation. They are the same component; the lecture slides name it one way and the code the other, and that is the only difference.

**Files for this task:** `demo_hello_graph.py` — read it before you run it. It uses `pizzabot/trace.py`, the logging helper every component in this repository shares. Your three answers go into section 0 of `docs/process-model.md`.

```bash
python demo_hello_graph.py "Ada"
python demo_hello_graph.py "Dr. Ada Lovelace"
```

Read `demo_hello_graph.py` **before** you run it. It is under 200 lines and every one of them is commented. It contains the four things LangGraph is made of, and nothing else: the typed **state**, three **nodes** (`state -> patch`), a fixed and a **conditional edge**, and the **compiled graph**.

Then run it and read the trace. Every node logs the same three lines (`received`, `doing`, `returns`), so the log *is* the process:

```
--- normalize -----------------------------------------------------------------
    received: name      = 'Dr. Ada Lovelace'
    doing   : 3 word(s), title='Dr.' -> style='formal'
    returns : clean_name = 'Dr. Ada Lovelace'
    returns : style     = 'formal'
    next    : choose_style (conditional edge) -> casual_greeting | formal_greeting
```

Answer these three questions in section 0 of `docs/process-model.md` (three sentences are enough):

1. A node returns `{"style": "formal"}` — what happens to the other fields of the state?
2. `choose_style` returns a string. Why is that *not* a state change, and why does it matter for the diagram?
3. Where would you have to look to find out why the bot chose the formal branch — in the code, or in the log? What does your answer imply for a system that runs in production?

---

## Task 2 — the process as a picture [5 min]

**Files for this task:** `demo_visualize.py`. It writes into `docs/` — `demo-process-model.mmd` and `.png` now, `pizza-process-model.*` later, once Tasks 3-5 are implemented and `pizzabot/graph.py` has something to draw.

```bash
python demo_visualize.py                  # exports the demo graph
```

Three exports, three purposes: `docs/demo-process-model.mmd` (text, so a pull request shows which edge changed), `docs/demo-process-model.png` (rendered, for the design review), and an ASCII view in the terminal (no network needed).

Later, when Tasks 3–5 are implemented, do the same for your own process and commit both files:

```bash
python demo_visualize.py --pizza          # -> docs/pizza-process-model.{mmd,png}
```

If PNG rendering fails (it uses the public server `mermaid.ink`), that is not a problem: open the `.mmd` file at <https://mermaid.live>, or install the *Markdown Preview Mermaid Support* extension in VS Code. The `.mmd` file is the artifact that matters.

---

## Task 3 — pizza recognition [19 min]

**Files for this task:** the skeleton and its contract are in `pizzabot/task3_pizza.py`. That is the only file you edit here. It reads the menu through `pizzabot/pizza_api.py` (data from `GET /pizza` — try that endpoint yourself at <https://wse-research.org/pizza-api>, never hard-code the list), the state is declared in `pizzabot/state.py`, the logging helper is `pizzabot/trace.py`. Your validation template is `validate_task3.py`, your drawing goes into `docs/process-model.md` (sections 2 and 3).

The contract is in `pizzabot/task3_pizza.py`. Do not change it — implement it.

**3a — draw it first (5 min).** One box for the component, one arrow in, one arrow out, and write on the arrows *what they carry*: which state fields come in, which patch goes out, and what happens in the case where nothing is recognised. Where does the menu come from — is it an input of the component or part of it? Put the drawing into `docs/process-model.md`.

**3b — implement (8 min).** Three TODOs: exact match, fuzzy match, and the patch. Run the component on its own while you work:

```bash
python -m pizzabot.task3_pizza "one Margaritha please"
```

**3c — validate by hand (6 min).** Open `validate_task3.py` and add at least three cases of your own, including one you expect to fail. Write down what you expect **before** you run it, then run:

```bash
python validate_task3.py
```

Judge each row yourself. A row is a failure if the result is correct but the rule that produced it is the wrong one. The log shows you which rule was applied.

---

## Task 4 — address recognition [16 min]

**Files for this task:** the skeleton and its contract are in `pizzabot/task4_address.py`. The address check goes out through `pizzabot/pizza_api.py` (`POST /address/validate`, which knows the delivery area — try it with your own address at <https://wse-research.org/pizza-api>). Validation template: `validate_task4.py`. The cases your rules cannot handle belong in section 6 of `docs/process-model.md`.

The contract is in `pizzabot/task4_address.py`. Its guarantee is the interesting part: **complete or nothing**. A half-recognised address is worse than none — it silently delivers a pizza to a place that does not exist.

**4a — draw it first (4 min).** Same as 3a, plus: draw the *second* output arrow, the one that goes to the Pizza API for validation, and mark what happens when the API says no.

**4b — implement (7 min).** Two TODOs, and the first one is half done: `NUMBER_FIRST` is given, you assemble `NUMBER_LAST` from the same blocks, then write `find_address` — try both patterns, clean the result, return three fields or nothing.

```bash
python -m pizzabot.task4_address "deliver it to 5 Rue Michelet, Saint-Étienne"
```

**4c — validate by hand (5 min).** `validate_task4.py`, again with three cases of your own. One case in the list is expected to fail (the missing comma). Do not fix it by adding a third pattern: write it into section 6 of `docs/process-model.md` instead. That list is the specification for Iteration 2.

Make one of your three cases a real French address **with the postcode in the middle**: `5 rue Michelet 42000, Saint-Étienne`. Your rules will produce a complete, validated, contract-conform address with `house_number = 42000` — and a pizza would be delivered to a house number that does not exist. Nothing in the contract is broken; the answer is simply wrong. Write that row into section 6 and mark it as the third kind: *the rule applies and the answer is still wrong*. That is the kind Iteration 3 will have to measure.

The API compares city names without accents and without case, so `saint-etienne` works as well as `Saint-Étienne`. Your regular expression does not care either; your **expectations** should be written the way you type, so use whichever spelling your keyboard gives you.

---

## Task 5 — the order form and the routing [14 min]

**Files for this task:** the skeletons and contracts are in `pizzabot/task5_form.py`. The wiring that uses them is `pizzabot/graph.py` — given, and worth reading before you draw. Validation template: `validate_task5.py`; the whole dialog runs with `run_dialog.py`.

The contract is in `pizzabot/task5_form.py`. Two components are yours (`route`, `order_form`, plus the edge condition `slots_complete`), three are given (`place_order`, `confirm`, `help_message`).

**5a — draw the whole process (5 min).** Every node, every edge, both conditional edges, and next to each node what the state looks like after it. This is the drawing you will compare with the exported diagram in Task 2 — so draw what you *believe* the process is, not what you would like it to be.

**5b — implement (6 min).** Three TODOs. Note that the router never changes the state: it returns the name of the next node, and it logs *why* with `trace.decision`. A routing rule that is not logged is a rule nobody can review.

**5c — validate by hand (3 min).** `validate_task5.py` replays whole dialogs, because a form is about sequences, not single utterances. Add one dialog of your own.

```bash
python validate_task5.py
```

---

## Task 6 — the whole thing, running [8 min]

**Files for this task:** `run_dialog.py`, the component tests in `tests/test_contracts.py`, and `demo_visualize.py --pizza`, which writes `docs/pizza-process-model.mmd` and `.png`. What you compare and what you find goes into `docs/process-model.md` section 5.

```bash
python run_dialog.py --script     # the walkthrough from the lecture
python run_dialog.py              # your own turns
pytest -q                         # the contracts, as executable statements
python demo_visualize.py --pizza  # export and commit the process model
```

Two things to look at, and to commit before Task 7. From here on another team reads what you wrote.

**Compare your drawing from 5a with `docs/pizza-process-model.png`.** Compare **only the nodes and the edges**: the export carries no rules, no slot names and no annotations, and that is not a difference. A difference is a node that exists in one and not in the other, an edge that exists in one and not in the other, or an edge that runs the other way. Each one is a bug in exactly one of the two. Write into section 5 which one, and fix that one.

**Run the test suite against the empty skeleton.** Do this *before* you commit Task 5, or `git stash` will have nothing to stash:

```bash
git stash            # put your implementation aside
pytest -q            # -> 8 passed, 10 failed
git stash pop        # bring it back
```

Eight of eighteen tests pass with no implementation at all. What does that say about those eight? Add one test that the empty skeleton would kill. You have just done by hand what the literature calls **mutation testing**: the empty implementation is a mutant, and a test suite is only as good as the mutants it kills (DeMillo, Lipton & Sayward 1978, [doi:10.1109/C-M.1978.218136](https://doi.org/10.1109/C-M.1978.218136); survey: Jia & Harman 2011, [doi:10.1109/TSE.2010.62](https://doi.org/10.1109/TSE.2010.62)).

---

## Task 7 — hand your contract to another team [10 min]

**Files for this task:** `handover_address.py` — everything happens in that one file. What you need from the other team: their `address_recognition` contract (section 2 of their `docs/process-model.md`) and their validation cases (the `CASES` list in their `validate_task4.py`). What you learned goes into your own `docs/process-model.md` section 7.

A contract is a promise between developers. You cannot decide whether your contract is a real promise: the person who has to implement it, without asking you a single question, decides that.

This exercise has a name in industry: a **consumer-driven contract** ([Robinson 2006](https://martinfowler.com/articles/consumerDrivenContracts.html), and the tool that automates it, [Pact](https://docs.pact.io/)). The team that *uses* a component decides whether its contract is adequate, not the team that wrote it. There is also a law behind it: Conway ([1968](http://www.melconway.com/Home/Committees_Paper.html)) observed that the structure of a system copies the communication structure of the team that built it. This is why you exchange the contract and not the code.

The six parts of a contract, and the worked example of a contract that is missing three of them, are in the [reference section](#reference--the-six-parts-of-a-contract) at the top of this sheet. Re-read it now if Task 3 feels long ago; everything below assumes it.

### Now do it

Pair up with the team next to you and exchange two things about `address_recognition`: the **contract** (section 2 of your `docs/process-model.md`) and your **validation examples** (the case list of Task 4c). Nothing else. No code, no explanations, no questions — if something is unclear, the contract is unclear, and that is the finding.

```bash
python handover_address.py
```

Paste their contract into `CONTRACT`, implement `find_address_theirs()` so that it satisfies *their* contract, paste their examples into `THEIR_CASES`, and run it. **Start from your own `find_address`** and change what their contract says differently: you have ten minutes, and writing a second address parser from nothing is not the point of the task. Then sit together for two minutes:

* Which rows differ? For each one: was their contract silent about it, or did you read it differently than they meant it?
* Which sentence would have prevented the difference? Write that sentence into **your own** contract — `docs/process-model.md` section 7 holds the notes.

Ten minutes is short on purpose. You are not supposed to finish a perfect implementation; you are supposed to find out how much of a component lives in the contract and how much lived only in the head of whoever wrote the code.

### You are done when you can tick all five

Decide this yourselves — nobody will come round and mark it.

1. `python handover_address.py` runs and prints a verdict for **every** case the other team gave you.
2. For each row you can say, **from their contract alone**, whether your result is the one they promised. "I think they probably meant" is not a tick.
3. You implemented it **without asking them anything**. One question asked means one sentence missing — go and write that sentence down instead.
4. Every differing row has a named cause: *which of the five parts* (reads, writes, rules, guarantee, failure) was silent or ambiguous.
5. At least one sentence has been added to **your own** contract in section 7 of `docs/process-model.md`. If the hand-over produced none, either your contract was already perfect (rare) or it was not tested hard enough: ask them for the case they thought you would fail, and try that one.

If you cannot tick 2 or 4, you have not finished the task even if your implementation passes every row: matching behaviour by luck is exactly the failure this exercise is built to expose.

---

## Task 8 — the LLM endpoint [5 min, or at home]

**Files for this task:** `check_llm.py`, and your `.env` with the key you were given in the session.

You do not need an LLM today — Iteration 1 has no AI in it at all. You check the endpoint so that Iteration 2 does not start with half a session of key trouble. **If the session runs out, do this one at home**; it needs nothing from the room except the key, and it has to be green before the next lecture.

```bash
pip install openai python-dotenv          # already in requirements.txt
python check_llm.py
```

The script lists the models the endpoint offers, asks one question with a checkable answer, and then sends a second turn to show that the endpoint has **no memory of its own** — the history in `messages` is everything it sees. Note down the model name that worked; you need it in Iteration 2.

The endpoint is [ILaaS](https://www.ilaas.fr) (`https://llm.ilaas.fr/v1`), the key comes from your instructor; it speaks the OpenAI protocol, which is why the `openai` package can talk to it. Never commit the key: it belongs in `.env`, which is in `.gitignore`.

---

---

## If you still have time

* **See the process run step by step.** Replace `graph.invoke(state)` with `for step in graph.stream(state, stream_mode="values"): print(step)` and watch the state grow node by node.
* **A second process for free.** Wire `pizza_recognition` and `address_recognition` into a *second*, different graph — for example one that only extracts data from a written order and never asks anything. If your components are contract-bound, this costs ten lines. That is what reuse means.
* **Count your baseline.** Run all your validation cases, count how many the bot gets right, and write the number and the date into `docs/process-model.md`. In Iteration 3 you will compare against exactly this number.

---

---

## Where this comes from, and where to go next

Nothing in this session is new. Every idea here has a paper, and most of them are older than you are. If you read one thing, read the first.

**Before the next lecture (20 minutes each, pick one):**

* Kästner, C., *Machine Learning in Production*, chapter 8, *Thinking like a software architect* — the decomposition criterion this whole exercise uses, free and CC-licensed: <https://mlip-cmu.github.io/book/>
* Jurafsky, D., & Martin, J. H., *Speech and Language Processing*, 3rd ed., Appendix K, *Frame-based dialogue systems* — six pages, and the reason your bot has slots and a form: <https://web.stanford.edu/~jurafsky/slp3/K.pdf>

**The sources of the ideas you used today:**

| what you did | where it comes from |
| --- | --- |
| wrote contracts with a guarantee and a failure behaviour | Meyer, B. (1992), *Applying "Design by Contract"*, IEEE Computer 25(10), [doi:10.1109/2.161279](https://doi.org/10.1109/2.161279); the pre/postcondition idea itself is Hoare, C. A. R. (1969), [doi:10.1145/363235.363259](https://doi.org/10.1145/363235.363259) |
| gave every slot exactly one writer | Parnas, D. L. (1972), *On the Criteria To Be Used in Decomposing Systems into Modules*, [doi:10.1145/361598.361623](https://doi.org/10.1145/361598.361623) |
| filled a frame slot by slot | Bobrow, D. G., et al. (1977), *GUS, a frame-driven dialog system*, [doi:10.1016/0004-3702(77)90018-2](https://doi.org/10.1016/0004-3702(77)90018-2) — your bot is a 1977 design with better tooling |
| let one component ask all the questions | Bohus, D., & Rudnicky, A. I. (2009), *The RavenClaw dialog management framework*, [doi:10.1016/j.csl.2008.10.001](https://doi.org/10.1016/j.csl.2008.10.001) |
| swapped the API for a stub behind the same contract | Liskov, B. H., & Wing, J. M. (1994), *A Behavioral Notion of Subtyping*, [doi:10.1145/197320.197383](https://doi.org/10.1145/197320.197383) |
| brought the drawing back into agreement with the code | Parnas, D. L., & Clements, P. C. (1986), *A Rational Design Process: How and Why to Fake It*, [doi:10.1109/TSE.1986.6312940](https://doi.org/10.1109/TSE.1986.6312940) |
| killed mutants with tests you added | DeMillo, R. A., Lipton, R. J., & Sayward, F. G. (1978), [doi:10.1109/C-M.1978.218136](https://doi.org/10.1109/C-M.1978.218136) |
| handed your contract to somebody who could not ask you | Robinson, I. (2006), *Consumer-Driven Contracts*: <https://martinfowler.com/articles/consumerDrivenContracts.html>; Conway, M. E. (1968): <http://www.melconway.com/Home/Committees_Paper.html> |
| exported the process as data you can diff and review | van der Aalst, W. M. P., et al. (2003), *Workflow Patterns*, [doi:10.1023/A:1022883727209](https://doi.org/10.1023/A:1022883727209) |
| built a workflow, deliberately, instead of an agent | Anthropic (2024), *Building effective agents*: <https://www.anthropic.com/engineering/building-effective-agents> |
| logged every decision, because somebody may have to explain it | EU AI Act, Art. 86 (the right to an explanation): <https://artificialintelligenceact.eu/article/86/> |

**If you liked this and want more of it:** Stanford CS 224V, *Building Conversational Virtual Assistants* (<https://web.stanford.edu/class/cs224v/>) and CS 329Z, *Engineering AI Agents* (<https://cs329z.stanford.edu/>) are the two public courses closest to this one.

**Two things to try when the contracts start to feel real:** property-based testing with [Hypothesis](https://hypothesis.readthedocs.io/) — "complete or nothing" is a property, not a list of examples — and [icontract](https://github.com/Parquery/icontract), which turns a contract from a docstring into something Python enforces at runtime. Both answer the question a good student asks at the end of this session: *if the contract matters so much, why is it a comment?*


## Troubleshooting

| symptom | cause and fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'pizzabot'` | you are not in the repository root; run the scripts from the folder that contains `README.md` |
| `PizzaApiError: ... did not return JSON` | `PIZZA_API_BASE` points at something that is not the Pizza API — open <https://wse-research.org/pizza-api> to see whether the service answers at all, or start the stub and use `http://127.0.0.1:8000` |
| the PNG export fails | `mermaid.ink` is unreachable from the university network; use the `.mmd` file, it is the artifact that counts |
| `UnicodeEncodeError` on Windows | `set PYTHONUTF8=1` before running |
| the node trace floods the terminal | `LOG_LEVEL=WARNING python run_dialog.py`, or put `LOG_LEVEL=WARNING` into `.env` |
| `InvalidUpdateError: Must write to at least one of ...` | your `langgraph` is older than the pinned version and rejects the empty patch `{}` that every component here returns: `pip install -r requirements.txt --upgrade` |
| the trace lines are cut off | they are cut to fit an 80-column terminal; `TRACE_WIDTH=88 python run_dialog.py` shows more of each value |
| you changed `.env` and nothing happened | `.env` is read when `pizzabot` is imported, so restart the script; and remember that a real environment variable overrides the file |
| `check_llm.py` says 401 | the key in `.env` is wrong or has a trailing space; keys are handed out in the session |
