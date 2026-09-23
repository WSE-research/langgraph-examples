# Exercise 5 — a process that repairs itself, and explains itself

Iteration 5 of *Engineering AI-Driven Software Processes — Hands-on KGQA with LangGraph and LLMs*, Université Jean Monnet Saint-Étienne, WS 2026/2027.

**Everything today is an extension of what you built in Iteration 4.** No new repository, no new graph, no rewrite: you take the process that answers factoid questions correctly and give it the two things Lecture 5 says it still lacks.

1. **Repair a dead end.** A guest names a pizza we sell and the kitchen is out of it. *“Sorry, not available”* hands the problem back to a human — and in an unattended system, that is exactly where automation stops and a ticket starts.
2. **Say what happened.** Which component was asked what, answered what, and how sure it was — recorded while the answer is produced, as data, not as a log line. That record is what makes the repair in Task 1 something you can *check* instead of something you hope for.

Then you try the result by hand in the Pizzabot frontend, and you spend the last quarter of an hour on something that is not code: **what your Pizzabot should be able to do next.** Those ideas are the raw material for the presentations at the end of Iteration 6.

## What you need from Iteration 4

This sheet continues your repository. It assumes Iteration 4 left you with:

* `pizzabot/kb.py` and `data/` — the knowledge base and the nine queries. Copies are in this folder in case you need them again.
* the **QA sub-graph** — `entity_linking → query_construction → query_execution → answer_generation` — reachable from the router.
* the router **node** that writes `question` at the start of every turn, and `route()` reading it.
* `show_menu`, and a follow-up that is answered over the previous answer.

If any of that is missing, take the Iteration 4 reference implementation rather than losing today to it.

## Definition of done

1. `pytest -q` — green, including your Iteration 3 and Iteration 4 tests.
2. `pytest -q -m gate` — green: the new nodes exist, the new state fields exist, and the new nodes sit on **plain edges**.
3. Naming an unavailable pizza ends with alternatives on the screen and an order that can carry on — not with an apology.
4. Every request to a component leaves **one annotation**, every call to the model leaves **one more**, and `what_happened(target)` prints the run of one sentence in time order.
5. One `ASK` over your process graph that would fail if the repair loop did not close.
6. You have run your own bot in the frontend and found **one thing that surprised you**.
7. Three feature ideas written down, one sentence each, for the Iteration 6 presentations.

| | task | minutes | you are done when |
| --- | --- | --- | --- |
| ☐ | 1 — repair: recognised, but not available | 0–30 | `pytest -q tests/test_task1_availability.py` green, gate green |
| ☐ | 2 — explainability: the process records itself | 30–60 | `what_happened(target)` prints your run, and one `ASK` is green |
| ☐ | 3 — try your own bot in the frontend | 60–75 | one surprise, written down in one sentence |
| ☐ | 4 — what should it do next? | 75–90 | three ideas, one sentence each, ready to present in Iteration 6 |
| ☐ | A/B — fuzzy input, and one more thing | take home | two appendices, both worth an evening |

---

## Preparation [~5 min]

```bash
cp -r data/          my-pizzabot/data/          # only if you do not have it already
cp kb.py             my-pizzabot/pizzabot/kb.py # ditto
cp tests/*.py        my-pizzabot/tests/
cd my-pizzabot && python -m pizzabot.kb --selftest      # 19/19 green
```

`tests/conftest.py` and `tests/bot_helpers.py` are the same two files as in Iteration 4; copying them again is harmless.

---

## Task 1 — Repair: recognised, but not available [30 min]

**Read first:** the scenario. A guest names a pizza correctly. It exists in the knowledge base. It cannot be delivered right now. A bot that answers *“Sorry, that is not available”* and stops has handed the problem back to the human — and in an **unattended** system, that is where automation stops and a ticket starts. The whole value of the next twenty-five minutes is that the process **does something** with the dead end instead of reporting it.

### 1a — the state grows by three fields [5 min]

Iteration 4 gave the state the keys the **answer** needs. Repair needs three more, and they are about what is **still missing**. Add them to `ChatbotState` and to `new_state()`, with the writer named in the comment, exactly as Iteration 1 did:

```python
    needs: list        # writer: any node -- information needs still open
    candidates: list   # writer: identify_pizza_by_parameters, show_pizza_options
    spoke: bool        # writer: the router node (reset) and any node that talked
```

* **`needs`** is the field this whole iteration turns on. A node that cannot finish its job writes down *what is still missing*, not *who should fix it*: `{"needs": state["needs"] + ["pizza_alternatives"]}`. Another node picks it up, does the work, and **removes it**. An information need that is satisfied and left in the state is satisfied again on the next turn, and on every turn after that.
* **`candidates`** is a list of `{"name": …, "id": …, "available": bool}`. More than one candidate is a question, not an answer.
* **`spoke`** exists because Iteration 1 gave `order_form` the monopoly on asking questions, and today two other nodes may talk. The **router node** — which since Iteration 4 already writes `question` and is the first node of every turn — resets it; a node that talks sets it to `True`; and `order_form` gets **one new first line**: if somebody already spoke this turn, say nothing. Without it your bot answers a question and then asks *“Which pizza would you like?”* in the same breath.

**The rule that makes the rest of this sheet short:** every node you add today starts by asking whether its information need is in `needs`, and returns `{}` when it is not. A node that decides for itself whether it applies is a node the router never has to be clever about — which is why the wiring below is plain edges and not conditions, and why Task 2 gets three of its four outcomes for free.

### 1b — availability is not a constant [4 min]

Two facts, both of which you can check right now:

```bash
python -c "from pizzabot import pizza_api; m = pizza_api.menu(refresh=True); print(len(m), 'on the menu, sold out now:', [p['name'] for p in m if not p['available']])"
python -c "from pizzabot import kb; print(len(kb.all_pizzas()), 'in the graph')"                # 22
```

Run the first line twice, a minute apart. `GET /pizza` lists all 22 pizzas, and since version 1.3.0 of the Pizza API every entry carries `"available": true` or `false`: **two pizzas are sold out every minute**, drawn at random, the same two for every request within that minute (the headers `X-Availability-Minute` and `X-Availability-Valid-Until` say which minute an answer belongs to). The graph says what a pizza *is* — it carries `pz:available` on the lecture slides, but the value that counts is the service's. The service says whether you can *have* it, now. Two systems, two answers, and neither is wrong.

This goes in a new `pizzabot/availability.py` and **not** in `kb.py`: `kb.py` talks to the graph and to nothing else, and the moment it imports `pizza_api` you have glued the knowledge base to the order service and you can no longer swap either one.

```python
"""Is it on the menu *right now*? The only module that asks both sources."""
import os
from pizzabot import kb, pizza_api


def sold_out() -> set[str]:
    """Forced sold out for a demo or a test -- SOLD_OUT="Hawaiian,Tartufo"."""
    return {name.strip().lower()
            for name in os.environ.get("SOLD_OUT", "").split(",") if name.strip()}


def _sellable_now() -> set[str]:
    """GET /pizza, asked NOW: the names the service marks "available": true."""
    return {pizza["name"].lower() for pizza in pizza_api.menu(refresh=True)
            if pizza.get("available", True)}


def is_available(name: str) -> bool:
    """Available in this minute, minus what is forced sold out. Never a list in here."""
    return name.lower() in _sellable_now() and name.lower() not in sold_out()


def available_pizzas() -> list[dict]:
    """The graph's pizzas, filtered by what the service sells in this minute."""
    sellable = _sellable_now() - sold_out()
    return [pizza for pizza in kb.all_pizzas() if pizza["name"].lower() in sellable]
```

Note the `refresh=True`. Since Iteration 1, `pizza_api.menu()` caches the menu for the lifetime of the process, and for the *names* that was right — they do not change while a dialog runs. For availability it is wrong: a cached flag is a flag from some earlier minute. Ask every time you need the answer, and only then.

`SOLD_OUT` stays, as a lever: the service's draw is random, so you cannot make *the Hawaiian* sold out when you want to show the repair to someone. One environment variable can:

```bash
SOLD_OUT="Hawaiian,Tartufo" python run_dialog.py
```

> **Remark — HTTP 409 Conflict, and why the service uses it here.** Checking availability when the guest names the pizza does not make the order safe. The order is placed turns later — after the address, perhaps in another minute — and by then the pizza may be sold out. That gap between checking and acting is the classic *check-then-act* race, and the service closes it on its side: `POST /order` for a pizza that is sold out in this minute answers **`409 Conflict`**, with a body that names the pizza and the minute it is sold out until. RFC 9110 (§15.5.10) defines 409 as *“the request could not be completed due to a conflict with the current state of the target resource”*, sent *“in situations where the user might be able to resolve the conflict and resubmit the request”*. Both halves fit, and the neighbouring codes do not: the request is well-formed (so not `400 Bad Request`), the pizza exists and `GET /pizza` lists it (so not `404 Not Found`), nothing is permanently gone (so not `410 Gone`), and the service itself is fine (so not `503 Service Unavailable`). **The code carries the repair:** a 409 says *the same request may succeed with a different pizza, or in a minute*. That is exactly the information need `pizza_alternatives`, arriving from the service instead of from your recogniser. Your `pizza_api.place_order()` raises it as a `PizzaApiError` whose message contains `HTTP 409`. Turning that into a need instead of a crash — so that `order_placement` hands the dialog back to `show_pizza_options` — is one of the candidates for Task 3.
>
> The tests order fixed pizzas, and they must not fail in the one minute out of eleven in which their pizza happens to be drawn. So `tests/conftest.py` sets `PIZZA_API_ACCEPT_EVERYTHING=true`, and `pizza_api.py` then sends the request header `X-Accept-Everything: true`, with which the service accepts a sold-out pizza anyway. That header is for **test drivers only**. A bot talking to a guest must never send it: it would turn the service's honest 409 back into an order the kitchen cannot bake.

### 1c — `recognize_pizza` expresses an information need [7 min]

**First, the change that makes the scenario possible.** Since Iteration 1 your recogniser has matched against `pizza_api.menu_names()` — the service's names, spelled the service's way, and one list for two questions: *is this a pizza?* and *can we sell it?* Recognising and being able to sell are two different questions, and from today they get two different sources:

| question | the source, from today |
| --- | --- |
| *did the guest name a pizza?* | the **graph** — `kb.pizza_iri(word)`, 22 pizzas and every alias they carry |
| *can we sell it?* | the **service** — `availability.is_available(name)` |
| *what id does the order need?* | the **service** — `pizza_api.pizza_id_for(name)`, as before |

The third row is not a detail. The graph carries `pz:apiId` too, and it is tempting to read the id from there — do not. `POST /order` is the consumer of that number, so the service is its authority; the copy in the graph exists so that the *graph* can be joined to the service, not so that the service can be second-guessed. A copied id that has drifted fails at the last node of the process, which is the worst place to find out.

That split is the *“the variable Pizza names cannot be static”* line of the briefing, and it is two lines of code. Note what you gain for free: the graph's aliases are now part of recognition, so *“pizza hawaii”* and *“hawaii”* resolve where they used to need a fuzzy-match rule.

Then the recogniser gets **one more job and no more responsibility**: when the name it recognised is not available, it must **not** fill the slots, it must say so, and it must write down what is missing.

```
    name        pizza_recognition (extended)
    reads       state["input"], state["slots"], state["expected"]
    writes      slots.pizza_name, slots.pizza_id   (only for an AVAILABLE pizza)
                messages, needs, spoke             (when the pizza is not available)
    changed     the candidate names come from kb.all_pizzas() / kb.pizza_iri(),
                not from pizza_api.menu_names()
    new rule    a name that the graph knows but the service cannot sell right now:
                  - say it plainly, by name
                  - do NOT write the slots (an unorderable pizza in the frame
                    would reach order_placement and fail there, far from here)
                  - append "pizza_alternatives" to needs
```

Run `pytest -q` the moment you have changed the recogniser. Anything that goes red is telling you about a place that assumed *recognisable* and *orderable* were one list — read it before you fix it, and write down which assumption it was. That is a sentence for your report and it took you no extra work to find.

The message is one sentence, and it is the last thing this node does about it: *“The Ortolana is on our card, but we cannot deliver it right now.”* Naming **which** pizza matters — it tells the guest they were understood, which is the difference between a system that refuses and a system that disagrees.

Note what this node does **not** do: it does not fetch alternatives. Fetching is a different job, it is useful to more than one caller, and Task 2 is going to need it too. This is the reuse the lecture's final remark is about.

### 1d — the node: `show_pizza_options` [8 min]

```
    name        show_pizza_options
    reads       state["needs"], state["candidates"]
    writes      messages, candidates, expected, needs (removes what it served), spoke
    rules       1. "pizza_alternatives" not in needs and "pizza_choice" not in
                   needs -> return {} and cost nothing        <- THE SKIP RULE
                2. "pizza_choice": the candidates are already in the state
                   (Task 2 put them there) -- show them
                3. "pizza_alternatives": there are none yet -- fetch them with
                   available_pizzas(), show a handful, not all twenty
                4. set expected = "pizza_name", so the next turn routes back
                   into pizza_recognition
                5. remove the need you just served from `needs`
    guarantee   after this node ran, either the guest has names in front of them
                or this node did nothing at all
```

Rule 1 is the one to write first and the one to test first. **A node that can be called at any time and decides for itself whether it applies is a node the router never has to be clever about** — and that is why the next line is a fixed edge and not a condition.

Rule 3 has a judgement call in it: twenty names is a wall of text. Show four or five, say how many there are, and offer the rest — *“We can deliver 20 pizzas today, for instance Margherita, Funghi, Marinara and Rucola. Say a name, or ask me to list them all.”* Note that *“list them all”* is already answerable: that is the `menu` question your `show_menu` node already answers from Iteration 4, and you get it for free.

### 1e — wiring, and the loop that closes [6 min]

`show_pizza_options` goes **between** `pizza_recognition` and `address_recognition`, as a fixed edge:

```python
workflow.add_node("show_pizza_options", show_pizza_options)
# was: workflow.add_edge("pizza_recognition", "address_recognition")
workflow.add_edge("pizza_recognition", "show_pizza_options")
workflow.add_edge("show_pizza_options", "address_recognition")
```

No new condition, because the node decides for itself. Open the **Floor plan** after this and look at it: the process grew by one box on a line that already existed, and every path through the graph still ends where it ended before.

The loop closes on the **next** turn: `expected == "pizza_name"` sends the router into `pizza_recognition`, the guest's new name is recognised, it is available, the slots get filled, and the order carries on as if nothing had happened. That is the repair.

**Check it by hand first:**

```
$ SOLD_OUT="Ortolana" python run_dialog.py
> I would like an Ortolana
The Ortolana is on our card, but we cannot deliver it right now.
We can deliver 19 pizzas right now, for instance Margherita, Funghi, Marinara and Rucola.
Say a name, or ask me to list them all.
> Funghi
Where should we deliver? ...
```

Two turns, no apology, no dead end.

### 1f — run the tests [6 min]

```bash
pytest -q tests/test_task1_availability.py
pytest -q -m gate tests/test_task1_availability.py
```

**These cases do not depend on the minute they run in.** The service's draw is random, so every test in `test_task1_availability.py` (and in Task 2) first **pins** it: a fixture replaces `pizza_api.menu` with the live menu in which every pizza is `"available": true`, and the test then makes exactly the pizza it needs sold out — with `SOLD_OUT`, or by setting the service's own flag to `false`. One test does the opposite and runs against the **live draw**: whatever two pizzas the service marks sold out right now, `is_available()` has to say no to both. A test that only passes in some minutes is not a test.

| group | cases | what it would catch |
| --- | --- | --- |
| **the module** | `available_pizzas()` before and after one pizza is sold out, by `SOLD_OUT` and by the service's flag; the two pizzas of the live draw; `kb.py` read with `inspect.getsource` | a list of names hard-coded somewhere, an answer computed once at import, a menu read from the cache instead of asked now, the `available` field ignored, or `kb.py` importing `pizza_api` — which would glue the knowledge base to the order service and undo the seam of 1b |
| **the repair** | four pizzas forced sold out (`Funghi`, `Quattro Formaggi`, `Salami`, `Frutti di Mare`), one marked sold out by the service's flag, plus every pizza the graph knows and the service does not list at all (none today; the case skips with a reason) | four things per case: the bot **says the name back**, the slots stay **empty**, alternatives are offered, and every alternative offered can **actually be ordered**. Offering a second dead end is worse than the first. |
| **the loop** | the same, then a second turn with an available name | `needs` must be empty afterwards and `expected` must be `pizza_name`, or the guest's answer routes nowhere. A need left in the state is served again next turn, forever. |
| **what must not have changed** | Margherita, Hawaiian, Marinara ordered plainly | the new rules are for the unavailable case only; an ordinary order must reach the frame exactly as it did in Iteration 1, with no candidates and no needs left behind |

The four names in the second group are not arbitrary: one word, two words, and `Salami` and `Frutti di Mare`, whose local names are `pz:SalamiPizza` and `pz:FruttiDiMare`. If you rebuilt a local name with `.replace(" ", "")` anywhere, those two are where it shows.

---


## Task 2 — Explainability: the process records itself [30 min]

**Read first:** you are not adding a feature. You are making the process you already have say *what it did* — and in the format the rest of the world reads, so that the record is useful to somebody who did not write your code.

One **request to a component** leaves one **annotation**. Five properties, nothing optional:

| property | what it holds |
| --- | --- |
| `oa:hasTarget` | the IRI of **the user's input** — the same for every step of one turn |
| `oa:annotatedBy` | which component ran |
| `oa:annotatedAt` | when it answered |
| `ex:confidence` | how sure it was — a number something computed, never a feeling |
| `oa:hasBody` | `ex:parameters` (the state it was given) and `ex:result` (the state it returned) |

That vocabulary is the W3C **Web Annotation Data Model**, and it is what the Qanary QA framework is built on. You are writing something other people's tools can already read.

### 2a — the helper, and one new state key [6 min]

```python
def annotate(state, component, parameters, result, confidence=1.0, kind="ComponentRun"):
    """One WADM annotation per request to a component."""
    return state["log"] + [{
        "kind": kind,                      # ComponentRun or LLMrequest
        "target": state["input_iri"],      # the IRI of this user input
        "annotatedBy": component,          # which component ran
        "annotatedAt": now(),              # when it answered
        "confidence": confidence,          # how sure it is
        "body": {"parameters": parameters, # the state it was given
                 "result": result}}]       # the state it returned
```

`input_iri` is one new state key, minted by the router node at the start of every turn: `f"urn:input:{uuid4().hex[:8]}"`. Everything else you already have — `log` has been in the state since Iteration 1.

The helper **returns a new list**. A node that forgets to annotate produces a visible gap, not a silent one.

### 2b — four nodes record themselves [10 min]

Take the four nodes of your QA sub-graph and give each one the same four lines. The node's own logic does not change:

```python
def entity_linking(state: ChatbotState) -> dict:
    """Iteration 4's node -- now it also records what it was asked."""
    parameters = {"question": state["question"]}
    entities, confidence = link(state["question"])        # unchanged
    result = {"entities": entities}
    return {"entities": entities,
            "log": annotate(state, "entity_linking", parameters, result, confidence)}
```

Build `parameters` and `result` **explicitly**. Not `locals()`, not the whole `state`: what the contract says goes in, what the contract says comes out. That is the difference between a record and a dump.

Then do the same for **the repair nodes of Task 1** — and watch what appears: `recognize_pizza` returns `{"needs": ["pizza_alternatives"]}`, so the dead end is in the record before the guest has answered, and `show_pizza_options` was *given* that need and does not return it. **That pair is the repair**, written down as data.

### 2c — every call to the model, once, centrally [5 min]

```python
def ask_llm(state, component, prompt: str) -> str:
    """Every request to the model is an annotation of its own."""
    answer = llm.ask(prompt)                     # the adapter of iteration 2
    state["log"] = annotate(state, component, parameters=prompt, result=answer,
                            kind="LLMrequest")
    return answer
```

Wrapped **once**, so no node in your system can call the model unrecorded. The prompt is part of the record, not of the debugger — which is what makes *“which step was AI, on which data?”* a query instead of an interview.

### 2d — read it back [6 min]

Two functions, and the second one is what the frontend asks for in Task 3:

```python
def explain(target: str) -> list[dict]:
    """All that was recorded for one input, in time order."""
    return sorted((a for a in ALL_ANNOTATIONS if a["target"] == target),
                  key=lambda a: a["annotatedAt"])

def what_happened(target: str) -> str:
    """The same explanation as one text, one numbered line per request."""
    return "\n".join(f'{n}. {step["annotatedBy"]}: {step["body"]["result"]}'
                     for n, step in enumerate(explain(target), start=1))
```

If you have a triplestore running from Iteration 4, export the annotations as Turtle into **one named graph per user input** and query them with SPARQL instead — that is the version the lecture shows, and the one an auditor can use. If you do not, the two functions above are the same idea over dicts, and Task 3 works either way.

**Have the model verbalize one step, and nothing else:** one annotation per prompt, with the instruction *“answer in one sentence, only what these values say”*. The model was not there when the process ran; it may say what the record says, and nothing more.

### 2e — one assertion over the record [3 min]

The record is data, so a test can ask it a question. Write **one** assertion that would have caught a broken repair:

```python
def test_a_declared_need_is_answered():
    """Some request returned the need; another was given it and did not return it."""
    run = explain(TARGET)
    declared = [a for a in run if "pizza_alternatives" in str(a["body"]["result"])]
    answered = [a for a in run if "pizza_alternatives" in str(a["body"]["parameters"])
                and "pizza_alternatives" not in str(a["body"]["result"])]
    assert declared and answered
```

Note what it does **not** do: it does not compare timestamps — two components can answer within the same millisecond, and an assertion that depends on a clock is a flaky test — and it does not name a node, so it holds for every implementation that answers that need. That is why it belongs in your Iteration 3 benchmark and not in one test file about one node.

---

## Task 3 — Try your own bot in the frontend [15 min]

Stop writing code. Run your bot in the **Pizzabot frontend** and use it the way a guest would.

```bash
git clone https://github.com/WSE-research/pizzabot.git
cd pizzabot && cp .env-example .env       # point the app entries at your own graph
streamlit run streamlit_chat.py
```

The frontend is implementation-agnostic: it loads *your* graph, draws it from your node and edge definitions, and shows your bot's own explanation in the **What happened** tab when your implementation exposes `what_happened(target)` — which, since Task 2, it does.

Work through this list and write **one sentence per line**:

| try this | what you are looking for |
| --- | --- |
| *“I would like a Tartufo”* | the repair: does the bot offer alternatives, and can the order carry on? |
| open **What happened** for that turn | is every step there, in order, with a confidence you believe? |
| ask the same thing a second time | is the second run identical? if not, **why** — and is the difference visible in the record? |
| the **Floor plan** tab | is the graph that is drawn the one you think you built? |
| something your bot cannot do | does it say so, or does it invent? |

**One surprise, written down.** Every team finds one: a node that runs twice, a confidence of 1.0 that nothing measured, an annotation whose result is `{}`, a question that takes the wrong path. That sentence is a deliverable of this session, and it is usually the most valuable thing on this sheet.

---

## Task 4 — What should your Pizzabot do next? [15 min]

**Not code. Not today, and not a promise.** Fifteen minutes, as a team, on what your bot *should be able to do* — and three of those ideas written down, one sentence each.

Write them from what you now have: a process of named components, each with a contract, each recording what it did. The useful question is not *“which feature would be nice”* but **“which component would a new capability belong to, and what would it have to be given?”** One line is enough.

To start you off, and not to limit you:

* the kitchen runs out of something mid-order — who finds out, and who decides what to offer instead?
* a guest who ordered last week says *“the same as last time”*;
* the bill is disputed, and the bot has to explain **why** it charged what it charged;
* three languages, and a proof that the answer was the same in each;
* the bot says *“I am not sure”* — and the record says what it was not sure about;
* a second restaurant, with a different menu, on the same process.

Keep the list. **Iteration 6 ends with every team presenting the Pizzabot they would build next** — a picture, a process, three sentences — and this quarter of an hour is where that presentation starts. The ideas do not have to be feasible. They have to be interesting.

---

## Appendix A — Fuzzy input: described, not named [take it home]

**Read first:** the scenario. With 22 pizzas — imagine 200 — a guest often cannot name what they want. They describe it: *“a pizza with pineapple”*, *“something vegan”*, *“vegetarian, with mushrooms, no tomato”*. Your recogniser looks for **names** and will find nothing at all in any of those sentences. But something is obviously being described, and the graph can be asked about descriptions.

Note the honest caveat in the lecture notes: with the LLM configuration, *“pizza with pineapple”* may well be recognised as the Hawaiian by the recogniser itself, because it is that obvious. Build the path anyway — *“vegetarian with mushrooms”* has three answers and no model can pick one for you.

### A1 — `recognize_pizza` hands over [5 min]

One more extension, of the same shape as 4b: when the node recognised **nothing**, but the utterance is clearly *about* a pizza, it writes an information need instead of staying silent.

```
    new rule    nothing recognised, but the utterance describes a pizza
                (it contains "pizza" and at least one more content word, or
                 the guest was asked for a pizza last turn) ->
                  append "pizza_by_description" to needs
```

Keep the test cheap and explainable. The point is not to detect descriptions perfectly — the point is that the recogniser **declares what it could not do** instead of failing quietly, so that a node that *can* do it gets a turn.

### A2 — the node: `identify_pizza_by_parameters` [15 min]

The substitutable part, again, is understanding — add a fourth component to `config.py`:

```
    name        description_understanding
    reads       the utterance
    returns     {"with": ["pineapple"], "without": ["tomato"], "flags": [("vegan", True)]}
    guarantee   every word it returns is a word the guest wrote; it invents
                nothing and it looks nothing up
```

Static: the negation-window trick from Iteration 1 (*no / without / free of* in the three words before a term, or *free* right after it) over the list of topping names and flag words. LLM: one prompt returning that JSON, static as its fallback. The topping words are all in `data/pizza-data.md` and every one of them has aliases in the graph — which is why the **next** step is a lookup and not a string comparison.

Then the node:

```
    name        identify_pizza_by_parameters
    reads       state["needs"], state["input"]
    writes      slots.*, messages, candidates, needs, spoke
    rules       1. "pizza_by_description" not in needs -> return {}    <- SKIP
                2. description_understanding -> constraints
                3. every word becomes a THING first: kb.topping_iri(word).
                   A word that resolves to nothing is reported, not dropped
                   silently: "I do not know a topping called kale."
                4. kb.matching(...) -> candidates
                5. remove "pizza_by_description" from needs -- it is served
                   whatever the outcome was
    guarantee   it never fills a slot with a pizza that is not available
```

Rule 3 is the *string versus thing* slide, arriving as a line of code. `"pineapple"` is a word; `pz:Pineapple` is a topping; Q8 is the bridge; and a guest who asks for kale deserves to be told that we do not know the word, rather than silently getting a pizza without it.

### A3 — four outcomes, and three of them are already built [15 min]

This is the part worth the whole task. Count the candidates and hand the work on:

| candidates | what this node does | what happens next |
| --- | --- | --- |
| **exactly 1, available** | fill `slots.pizza_name` / `pizza_id`, say which one and why — *“That is the Hawaiian — tomato, mozzarella, ham and pineapple.”* | `order_form` asks for the address. Done. |
| **exactly 1, not available** | say so by name, append `pizza_alternatives` to `needs` | **`show_pizza_options` from Task 1 runs.** No new code. |
| **more than 1** | write them to `candidates`, append `pizza_choice` to `needs` | **`show_pizza_options` from Task 1 runs**, rule 2. No new code. |
| **0** | drop the **narrowest** constraint, ask again, and name what you dropped: *“Nothing is vegan and has olives. Without the olives I have Marinara and Verdure.”* Put those in `candidates` and append `pizza_choice`. | **`show_pizza_options` runs.** No new code. |

Three of the four outcomes are a two-line patch to the state, because Task 1 already built the node that shows options and the wiring already passes through it. **That is the payoff of the skip rule**: you did not write a router condition for any of this, and you did not write a second "show the options" node. If you find yourself writing one, stop and look at why your `show_pizza_options` cannot be reused.

Wiring is one line, on the same chain:

```python
workflow.add_node("identify_pizza_by_parameters", identify_pizza_by_parameters)
workflow.add_edge("pizza_recognition", "identify_pizza_by_parameters")     # replaces 1e's edge
workflow.add_edge("identify_pizza_by_parameters", "show_pizza_options")
```

So the final chain is `pizza_recognition → identify_pizza_by_parameters → show_pizza_options → address_recognition → order_form`, and on a turn where the guest simply said “Margherita”, the two middle nodes run, skip, and add about a millisecond. Look at that in the frontend's **Ticket** tab, the one you set up in Iteration 4: two nodes with *“no state change”* beside them is not waste, it is the design working.

**Check it by hand first:**

```
> a pizza with pineapple            -> That is the Hawaiian ...
> something vegan                   -> Two match: Marinara and Verdure. Which one?
> vegetarian with mushrooms         -> Three match: Funghi, Vegetariana, Tartufo.
> vegetarian with aubergine         -> Two match, and neither can be delivered today ...
> something vegan with olives       -> Nothing is vegan and has olives. Without ...
```

### A4 — run the tests [7 min]

```bash
pytest -q tests/test_task2_description.py
pytest -q -m gate tests/test_task2_description.py
BOT_CONFIG=llm pytest -q tests/test_task2_description.py     # and again, other implementation
```

**The expected answers are produced by the same `kb.matching()` call your node makes.** A case does not say *“‘a pizza with pineapple’ must give the Hawaiian”* — it says *“whatever the graph answers for these constraints, the bot has to end up with that”*. Add a topping to a pizza tomorrow and both sides move together. One test, `test_the_cases_still_mean_what_they_say`, pins the three cases the sheet quotes, so if the data ever stops offering a unique match and an ambiguous one you find out in that file and not in your node.

Seven descriptions are parameterized, and they cover all four outcomes of 5c:

| outcome | the cases | what it would catch |
| --- | --- | --- |
| **one match** | `with pineapple` → Hawaiian, `with tuna` → Tonno | the frame must be filled **and** the bot must say which pizza it decided on: a guest who described something and is then asked for their address has no idea what they just ordered |
| **several matches** | `something vegan` (2), `vegetarian with mushrooms` (3), `with mushrooms and ham` (2), `with olives` (3), `vegetarian with aubergine` (2) | no slot may be filled — several candidates are a question; every matching name must be offered; **no non-matching name may be**; and `candidates` must hold exactly that set, because `show_pizza_options` reads it |
| **one match, unavailable** | `vegetarian with aubergine` → Ortolana, Verdure | try it with `SOLD_OUT="Ortolana,Verdure"` — or in a minute in which the service draws them: both are in the graph and neither can be ordered, so this case walks straight into Task 1's node |
| **no match** | `something vegan with olives`, `a vegan pizza with ham` | the bot has to **name the constraint it dropped** and offer what is left. An empty result is a sentence, not a failure. |

Plus two that guard the seam: a named pizza (`I would like a Margherita`) must **never** take the description path — that is the skip rule of A2, rule 1 — and *“a pizza with kale”* must mention kale, because `topping_iri("kale")` is `None` and dropping an unknown constraint silently hands back a pizza that does not meet the request.

The `gate` test for this appendix is the one worth reading twice: it asserts that `pizza_recognition → identify_pizza_by_parameters → show_pizza_options → address_recognition` are **plain edges**. If you had to add a router condition to make any of this work, it fails — and that is the design claim of the whole iteration, written as an assertion.

---

## Appendix B — one more thing: extend it [take it home]

*Came from Iteration 4 on 2026-09-21. It is an appendix since 2026-09-23, when the session was re-cut around repair, explainability, the frontend and your own ideas -- the tasks below are the best of the leftovers, and every one of them is a real evening's work.*

Pick **at least one** and build it. The point is not the feature; it is that you now have a QA process with four named steps, plus the two that repair and identify, and you can tell which of them a new capability belongs to. **Say which node yours touches before you write it** — that sentence is the deliverable, not the code.

**Rules for your extension:** it uses the graph (not a constant in your code); it goes into one of the four nodes or adds one template; and you can demonstrate it with one sentence in the browser.

### Easier — one more template

* **“Is the Hawaiian vegetarian?”** — a yes/no question that answers *and explains*: *“No — it has ham.”* The flag answers; the toppings are the evidence. Here is the query, because this one is the explainability thread of the course in ten lines:

  ```sparql
  PREFIX pz: <http://example.org/pizza/>
  SELECT ?name ?vegetarian (GROUP_CONCAT(?topping; separator=", ") AS ?because) WHERE {
    VALUES ?pizza { pz:Hawaiian }
    ?pizza pz:name ?name ; pz:vegetarian ?vegetarian .
    OPTIONAL { ?pizza pz:hasTopping ?t .
               { ?t pz:containsMeat true } UNION { ?t pz:containsFish true }
               ?t pz:name ?topping }
  } GROUP BY ?name ?vegetarian
  ```

  Hawaiian → `false`, because `ham`. Siciliana → `false`, because `anchovies` — which is why the `UNION` is there and why *free of meat* was never the same question. Margherita → `true`, and `?because` is empty, which is the shape of *“yes, and there is nothing to explain”*.
* **“What is the difference between the Ortolana and the Verdure?”** — two `toppings_of` calls and a set difference. One topping, mozzarella, and it is the reason one is vegetarian and the other is vegan. Note what it needs from `entity_linking`: **two** mentions in one question.
* **“Which pizza has the most toppings?”** — `COUNT` in the `SELECT`, `GROUP BY ?name`, `ORDER BY DESC(?n)`. A lesson for free: the answer is a **tie** (Capricciosa and Verdure, seven each), so your sentence has to survive two winners.
* **“How many pizzas are vegan?”** — a count, not a list. Same template as the flag question, a different answer sentence, and it is the cheapest way to see that *finding* and *saying* really are two nodes.

### Medium — a node gets better

* **Disambiguation, asked out loud.** `entity_linking` keeps both records for *“pepperoni”*. Use them: when a question is ambiguous, ask — *“the Pepperoni pizza, or pizzas with pepperoni on them?”* — instead of guessing. One new question type and one branch, and it is the slide about ambiguity living in the data.
* **A confidence and a refusal.** Give `question_understanding` a confidence and, below a threshold, answer *“I am not sure whether you are asking about toppings or ordering — which is it?”* You now have a number to put in the report, and `honest_refusal` should go **up**.
* **Say what you cannot answer.** When no template fits, do not stop at *“I do not know”*: *“I can tell you toppings, dietary flags, inventors and descriptions.”* Listing your own competence is harder than it looks and it is the most professional thing on this page — and Iteration 4's `honest_refusal` measures it.
* **More question wordings, measured.** Add five wordings per type to `question_understanding` and re-run Iteration 4's `factoid_benchmark.py`. Did `template_chosen` move? By how much, and is the interval's lower end above where it was? That is an experiment, not a change.
* **A second flag question the graph supports and nobody asked for.** Read `data/pizza-data.md` and find one. Then add the case to the benchmark generator — four lines — and watch the case count grow on its own.

### Harder — the process changes shape

* **Two entities in one question.** *“Do the Hawaiian and the Prosciutto both have ham?”* — `linked` holds two, the template takes two, the answer compares them. Find out which of your four nodes assumed there would be exactly one.
* **Generated SPARQL, bounded.** Let the model propose a query for a question with no template — and then **refuse to run it** unless it parses, touches only known predicates, and has a `LIMIT`. The lecture's point is not that generation is forbidden; it is that it must be bounded, and the bound is code you can read.
* **A 409 is a need, not a crash.** Order a pizza, then wait for it to be drawn sold out before you give the address — or force it with the service's seed — and your turn ends in a `PizzaApiError` from `order_placement` (the remark on HTTP 409 in Task 1b). Make `order_placement` catch it, say *“we just sold the last Tartufo”*, empty the pizza slots and append `pizza_alternatives` to `needs`; `show_pizza_options` does the rest. This one bends the rule above — it touches `order_placement`, not one of the four QA nodes — because it is Task 1's repair arriving from the service instead of from your recogniser, and it is the first edge in the course that goes *backwards*.
* **The query in the answer.** Offer *“why?”* and print the query and the rows that produced the last answer. You already keep both in the state. This is the smallest possible version of the explainability thread that Iteration 5 takes seriously, and it costs about fifteen lines.
* **A second benchmark family.** Add *comparison* questions (*“is the Funghi cheaper than the Tartufo?”* — the graph has no prices, so this is a refusal family) and measure whether your bot refuses all of them. A family that should score 1.00 on `honest_refusal` and scores 0.4 is the most useful red number you will see today.

### Hand in

For Task 3: the one sentence that demonstrates it, a screenshot of the **Order pad** tab while it runs, and two lines saying **which of the four nodes it changed** and what the benchmark did afterwards. If it changed more than one node, say why — that is a real answer, not a failure.

---
