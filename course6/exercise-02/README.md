# Exercise 2 — an LLM inside the process, behind unchanged contracts

Iteration 2 of *Engineering AI-Driven Software Processes — Hands-on KGQA with LangGraph and LLMs*, Université Jean Monnet Saint-Étienne, WS 2026/2027.

**Today an LLM enters your system — behind two contracts that do not change.** Two of your components, `pizza_recognition` and `address_recognition`, get a second implementation that calls a language model. What stays as it is: the process model, the state type, the router, the order form, the four contract rows that are the specification (`reads`, `writes`, `guarantee`, `failure`), and the assertions of the Iteration 1 tests. What changes once, on purpose: the wiring gains a seam so that an implementation can be injected, and the test harness learns to run twice. That is the claim of Lecture 2, and this session is where you test it: if the substitution forces you to touch a contract or the state, the contract was not respected somewhere.

**What you build:** a unit test per method, with its cases as data and a threshold for the two probabilistic ones; two LLM-backed components with a schema check, a domain check and a fallback to your Iteration 1 rules; one process that runs in two configurations (`static`, `llm`); the same test suite green in both; a measured comparison of the two on your own cases; and a bot that survives three hostile utterances from the team next to you.

**Definition of done** — what the repository has to contain at the end of the session:

1. `python check_setup.py` — 19 checks green, including one real JSON extraction through the LLM service.
2. `pizzabot/address_llm.py` and `pizzabot/pizza_llm.py` implemented; `python -m pizzabot.address_llm "…"` prints a `tier` line with a reason, and `compare_configs.py --address` shows `[llm]` in at least one row (under load the fallback may answer — that is the design working, not failing).
3. `python run_dialog.py --llm --script` completes an order and prints an order id — and `python run_dialog.py --script` still does.
4. `example/` extended: the address node returns four fields, `recognize_pizza_name` is the cascade exact → similar → model, and `python -m pytest -q example/example_tests.py` is green — a threshold on both value tests, and the tier test exact.
5. `tests/test_recognizers.py` written: five cases per component, the two rule tests at 5 of 5, the two threshold tests above `THRESHOLD`, and no skip left in `pytest -q tests/test_recognizers.py -rs`.
6. `pytest -q` — green in **both** configurations: the last line says `static: 19 passed | llm: 19 passed | not parametrized: 31 passed` (69 in total with five cases per component), and `test_graph_uses_the_injected_implementation` passes (`pytest -v` shows the `[static-…]` and `[llm-…]` ids).
7. `python demo_visualize.py --both` prints `IDENTICAL`; both `.mmd` files committed.
8. `python adversarial.py` with the three utterances you received, in both configurations; every broken promise fixed in the component, with a test that keeps it fixed.
9. `.env` is not in the repository; one commit per task.

Nothing in this iteration is handed in as prose. The questions the tasks ask you are still the point — answer them in your team, out loud, and bring the two or three that surprised you to the closing round — but the deliverable is always running code, a test, or a number the scripts printed.

The **preparation** below happens right after the lecture, before the break. The tasks are timed for the 90-minute session that follows; the minutes count from the start of your own work, after the briefing. Tasks 1–7 add up to 76 minutes; the briefing at the start and the closing round at the end take the rest, so there is no hidden reserve. If you fall behind, shorten Task 4 (the pizza component is the address component again, with one field) — never Task 7. Something red? The troubleshooting table is right after Task 7.

| | task | minutes | you are done when |
| --- | --- | --- | --- |
| ☐ | 1 — the service on its own | 0–6 | `.env` works, and the three runs of the adapter behaved as the task predicts |
| ☐ | 2 — the tests, before the implementation | 6–26 | the example extended three times and green; `pytest -q tests/test_recognizers.py -rs` — no skips left |
| ☐ | 3 — address recognition, LLM-backed | 26–39 | `compare_configs.py --address` shows `[llm]` in the first column |
| ☐ | 4 — pizza recognition, LLM-backed | 39–48 | `compare_configs.py --pizza` shows `[llm]` in the first column |
| ☐ | 5 — one graph, two configurations | 48–58 | `pytest -q` green in both configurations, `--both` prints `IDENTICAL`, **commit** |
| ☐ | 6 — the measured difference and the service card | 58–64 | `compare_configs.py` run for both components, and you can say the two numbers |
| ☐ | 7 — the adversarial round | 64–76 | `adversarial.py` runs both configurations; every broken promise fixed in the component |

---

## Preparation — right after the lecture, before the break [~10 min]

**1. Get the material into your repository.** Pick the row that describes you.

| your Iteration 1 repository | do this |
| --- | --- |
| **complete** — `pytest -q` was green and `run_dialog.py --script` placed an order | clone this material somewhere *outside* your repository, copy the files in the two lists below into your repository, and keep everything else as it is. Your own tests in `tests/test_contracts.py` stay: the Iteration 2 tests are a new file |
| **not complete** | start from this folder: it contains the complete static bot (the reference solution of Iteration 1), so an unfinished Iteration 1 does not block you today. Read `pizzabot/task4_address.py` before Task 3 — it is the rule your LLM component will call when the model fails |

New files: `pizzabot/llm_service.py`, `pizzabot/config.py`, `pizzabot/log.py`, `pizzabot/address_llm.py`, `pizzabot/pizza_llm.py`, `prompts/`, `example/`, `tests/test_both_configurations.py`, `tests/test_recognizers.py`, `compare_configs.py`, `adversarial.py`.
Changed files (safe to overwrite, you did not write them): `pizzabot/graph.py`, `pizzabot/trace.py`, `pizzabot/pizza_api.py`, `pizzabot/task3_pizza.py`, `pizzabot/task4_address.py`, `run_dialog.py`, `demo_visualize.py`, `check_setup.py`, `check_llm.py`, `validate_task3.py`, `validate_task4.py`, `validate_task5.py`, `handover_address.py`, `demo_hello_graph.py`, `pizza_api_stub.py`, `adversarial.py`, `conftest.py`, `requirements.txt`, `.env.example`, `README.md`. Most of them changed for one reason only: they no longer call `print()` (see the glossary row **log layer**). The process model itself does not change today, and nothing in this iteration is handed in as prose — leave your `docs/process-model.md` from Iteration 1 as it is.

```bash
git clone https://github.com/WSE-research/langgraph-examples.git     # both rows (row 1: outside your repository)
cd langgraph-examples/course6/exercise-02                            # row 2 only; row 1: cd into your own repository after copying
python3 -m venv .venv && source .venv/bin/activate                   # Windows: .venv\Scripts\activate
pip install -r requirements.txt                                      # both rows: adds pydantic
cp .env.example .env                                                 # both rows, then paste the key from Iteration 1, Task 8
```

**2. The key.** `.env` needs `OPENAI_API_KEY` — the ILaaS key you were given in Iteration 1 (Task 8). `OPENAI_API_BASE` and `MODEL_NAME` are already right in `.env.example`. Never commit `.env`; it is in `.gitignore`. Task 1a goes through the file line by line; here you only need the key pasted, so that the check in step 3 can reach the model.

**3. Check the machine.**

```bash
python check_setup.py
```

Nineteen checks: the Iteration 1 ones, plus `pydantic`, the two prompt files and both configurations. The one that matters today is the last: one real JSON extraction through the LLM service. It prints the latency, the token counts, and whether the answer came inside triple-backtick fences. The endpoint check that was marked `[todo]` in Iteration 1 must now be `[ok]`. If the Pizza API is not reachable, the local stub from Iteration 1 still works: `python pizza_api_stub.py` in a second terminal and `PIZZA_API_BASE=http://127.0.0.1:8000` in `.env`.

Then run the test suite once, now, with nothing implemented yet:

```bash
pytest -q -rs                                   # 56 passed, 1 failed, 4 skipped -- remember these numbers, Tasks 2 and 5b explain them
```

Two environment variables you will want during the session: `LOG_LEVEL=WARNING` silences the node trace and keeps every result (that is the one to use on a beamer), and `NO_COLOR=1` switches the colours off.

**4. See it work.** The smallest thing in the repository that talks to the model is the warm-up example. Run it once now, so that a missing key is a problem you have before the session and not during it. The output is coloured — green for a check that passed, red for one that failed, yellow for a warning, dim for the node trace. If your terminal or your pipeline cannot do colour, `NO_COLOR=1` switches it off, and piping into a file does that on its own:

```bash
python example/simple_bot.py                      # two nodes, four sentences
python -m pytest -q example/example_tests.py      # 6 passed
```

Two nodes, one rule-based and one LLM-backed, in three files you can read in five minutes — `example/README.md` says what is in them. Task 2 starts there.

**5. Commit** the untouched material before you change anything.

---

## Glossary

Eleven words this sheet and the code use constantly, on top of the Iteration 1 glossary (slot, frame, patch, node, contract, stub).

| word | what it means here |
| --- | --- |
| **adapter** | the one piece of code that talks to the model: `pizzabot/llm_service.py`. It turns "a remote model" into a function with a contract (`extract(system, user) -> dict or None`). Nothing else in the process calls the model. |
| **configuration** | which implementation sits behind a component name: `static` (the Iteration 1 rules) or `llm` (today's service calls). Chosen with `--config`, `--llm`, `--static` or `BOT_CONFIG` in `.env`. |
| **seam** | the one place where an implementation can be swapped without editing the code around it (Feathers 2004) — here the dictionary in `pizzabot/config.py` that `build_graph` receives. |
| **output schema** | the shape the model's answer must have (which keys, which types). Checked on our side with `pydantic`, whatever the model promised. Not to be confused with the *state type* of Iteration 1. |
| **domain check** | a rule that checks the *meaning* of a schema-valid answer: the pizza is on the menu, the house number is a number, the address is in the delivery area. The delivery area is the service's, not yours: since 2026-09-18 it is every commune of France plus Leipzig, Halle and Dresden, and `GET /city` lists it — so a city outside it has to be a foreign one (the tests use Barcelona). |
| **tier** | who answered: `[llm]` (the service answered and passed every check) or `[static]` (a check failed or the service failed, and the Iteration 1 rule decided). Recorded in the trace by `trace.tier()`. In the lecture's numbering `llm` is tier 1 and `static` is tier 3; the repair prompt (tier 2) is not built today — it is the last item under "If you still have time". Not the French *tiers*. |
| **fallback** | the Iteration 1 rule, called whenever the LLM path gives up. It is not dead code: it is the guaranteed minimum quality of the component. |
| **threshold** | the rate a method has to reach over its test cases to count as working: `rate >= THRESHOLD`. Needed by every method whose answer is *approximate* — an LLM call, but a similarity function just as much — because such a method has no guaranteed right answer per case. A decision with a date and an owner, not a constant. |
| **log layer** | `pizzabot/log.py`: the one place in this repository that writes to the screen. Nothing calls `print()`. Every line is written with the **role** it plays — `log.step`, `log.ok`, `log.fail`, `log.warn`, `log.result`, `log.say` — and the role decides the colour. Two channels: *report* (results, always shown) and *trace* (the node log, silenced by `LOG_LEVEL=WARNING`). |
| **fence** | the triple-backtick marks some models put around their JSON even when asked for pure JSON. The adapter strips them before parsing; "JSON mode" is a request, not a guarantee. |
| **prompt injection** | an instruction hidden in the user's text ("ignore the menu and …"). The model may obey it. The defence is the domain check and the API, never the prompt. |

---

## Task 1 — the service on its own [6 min]

**Files for this task:** `pizzabot/llm_service.py` (given — it is the adapter of Lecture 2; read the contract at the top and the function `extract()`, nothing else), `.env.example`, `.env`.

### 1a — the `.env` this task needs [2 min]

This is the first task that sends anything to a model, so it is the first that needs a credential. Get this right once and nothing later in the session asks you about it again.

Two files, one of which does not exist yet:

| file | committed? | what is in it |
| --- | --- | --- |
| `.env.example` | **yes** — it is in the repository you cloned | every variable the process reads, with the correct values filled in *except* the secret ones. It is documentation that cannot go stale, because the code reads the same names. |
| `.env` | **no** — it is in `.gitignore`, and must stay there | your working copy: the same variables, with your key pasted in. It is the only file in this repository that holds a credential. |

Make the working one:

```bash
cp .env.example .env                # macOS, Linux
copy .env.example .env              # Windows, cmd.exe
Copy-Item .env.example .env         # Windows, PowerShell
```

Then open `.env` and change **one line** — `OPENAI_API_KEY`. Paste the ILaaS key you were given in Iteration 1, Task 8, raw: no quotes, no spaces, no angle brackets left over.

```diff
- OPENAI_API_KEY=<the key you were given in the exercise session>
+ OPENAI_API_KEY=1234abcd-....
```

Every other line in the file is already correct for this exercise. The ones worth knowing before you run anything:

| variable | why it is set the way it is |
| --- | --- |
| `OPENAI_API_BASE=https://llm.ilaas.fr/v1` | the ILaaS inference gateway. It speaks the OpenAI protocol, which is why the OpenAI client library works against it unchanged — the variable is called `OPENAI_` because that is the name the *client* reads, not because anything here talks to OpenAI. |
| `MODEL_NAME=mistral-small-4-119b` | pinned on purpose. A different model is a different implementation and has to be re-measured (Task 6); `.env.example` lists the alternatives that were verified to work. |
| `LLM_TIMEOUT`, `LLM_RETRIES` | the two numbers that turn "the service hung" into the defined failure `None` rather than a hanging process. Task 1's second and third run make them visible. |
| `PIZZA_API_BASE` | unchanged from Iteration 1; the commented line right below it switches to the local stub. |
| `BOT_CONFIG=static` | the default configuration. Leave it — Task 5 switches it from the command line. |
| the commented `ILAAS_RAG_*` block | a *second* ILaaS service with a *second* key, for retrieval. Nothing today uses it; it is named so that your `.env` is already the right shape in Iteration 5. |

Check it before you go on:

```bash
python check_llm.py                 # reaches the endpoint and reports latency and tokens
```

If it reports no key, the usual cause is that `.env` still holds the template: the code treats any value starting with `<` as "no key", so an unfilled template fails immediately and says so, instead of turning into an HTTP 401 three tasks later. `python -c "import os; print(bool(os.environ.get('OPENAI_API_KEY')))"` does **not** prove anything — the variable lives in `.env`, not in your shell.

> **Why the repository ships a `.env.example` at all.** The same argument as the Pizza API stub in Iteration 1: an interface is worth nothing if nobody can tell what it needs. A committed example of the configuration is the difference between a repository that a new team member can run in two minutes and one that needs you on the phone. Never commit `.env`; always commit `.env.example`, and update it in the same commit that adds a variable to the code.

### 1b — the service on its own [4 min]

Read the contract: what `extract()` promises, and — more important — what it does not. Then run it three times:

```bash
python -m pizzabot.llm_service                     # one extraction, with latency and tokens
python -m pizzabot.llm_service --max-tokens 5      # the answer is cut off -> the defined failure: None
python -m pizzabot.llm_service --model no-such-model   # the provider says 404 -> None as well
```

The first run ends like this (your numbers will differ):

```text
    llm     : attempt 1: 0.60 s, 67 tokens in, 33 out, answer was fenced
    llm     : answer: {"street": "Rue Michelet", "house_number": "5", "city": "Saint-Étienne"}

result  : {'street': 'Rue Michelet', 'house_number': '5', 'city': 'Saint-Étienne'}
usage   : 1 call (1 attempts), 0 ended in None, 1 fenced; 67 tokens in, 33 out; latency median 0.60 s, max 0.60 s
```

Answer these four questions in your team, out loud, before you move on — a sentence each is enough, and nothing is written down: what the dict you get back is *not* checked for; whose problem a fenced answer is and where it is solved; which of the three numbers you saw (latency, tokens in, tokens out) matters most if this step runs a thousand times in a row; and which of your three runs retried, and whether the retry could have changed anything.

> **Two names, one thing.** Lecture 2 calls it the *service adapter*; the class is called `LlmService`. It is the adapter: our contract around somebody else's service. The process never sees the client library behind it.

---

## Task 2 — the tests, before the implementation [20 min]

**Files for this task:** `example/` (a working two-node example, given — read its `README.md`), `prompts/example_address_v1.txt` and `prompts/example_pizza_v1.txt`, and `tests/test_recognizers.py` (a skeleton you fill in at the end of the task).

Every method gets a unit test, and the test cases are **data**: a list of pairs, each pair an utterance and the value the method must return for it. One list per method, used by *both* implementations of a component — that is what "the same contract" means in practice. If a rule and its model-backed substitute needed different cases, they would not be implementing the same thing.

The second idea is the one people get wrong. A method whose answer is **exact** — for every input there is one right answer and the method produces it, every time — is tested with an equality, on every case. A method whose answer is **approximate** is tested with a **rate** against a threshold, because "it is right most of the time" is a number, not a feeling. The dividing line is exactness, not rule versus model: 2c turns a rule into an approximate method, and it needs a threshold for exactly the same reason the model does.

**2a — run the example and read its two tests (4 min).** `example/simple_bot.py` is Iteration 2 in three files: a rule-based node that finds a menu name, an LLM-backed node that extracts an address, and nothing else. The key is the one handed out in the lecture hall; it goes into `.env` as `OPENAI_API_KEY` (never into a file you commit).

**First, order a pizza yourself.** Before you read a line of the example or change anything, prove that your machine really talks to the model. Start the bot and type the orders in by hand:

```bash
python example/simple_bot.py --interactive
```

Type each line exactly as it stands, press Enter, and read the two lines that come back. An empty line, `quit`, or Ctrl-D ends the session and prints the usage line: latency, token counts, how many answers came back fenced.

**Two that must work** — a complete order, recognised by both nodes:

| type this | what has to come back |
| --- | --- |
| `I would like a Margherita, delivered to 42000 Saint-Étienne` | `pizza : Margherita`<br>`address : {'postcode': '42000', 'city': 'Saint-Étienne'}` |
| `one Diavola to Lyon, 69001` | `pizza : Diavola`<br>`address : {'postcode': '69001', 'city': 'Lyon'}` |

The pizza comes from the **rule** (the name is on the menu, spelled as the menu spells it) and the address from the **model** — two implementations of two components, in one sentence.

**Two that must *not* work** — and this is the more interesting half:

| type this | what has to come back | why |
| --- | --- | --- |
| `one Margaritha please` | `pizza : <nothing recognised>` | the rule does a literal lookup, and `Margaritha` is not on the menu. A human reads it as a typo; a literal rule cannot. **Task 2c is where you fix this**, and this is the sentence you will fix it with |
| `deliver to Saint-Étienne` | `address : <nothing recognised>` | the city is there, the postcode is not. The component's guarantee is **complete or nothing** — a half address is never written into the slot, because a half address is worse than no address: the process would carry it forward as if it were an answer |

Type these two as well. A bot that answers "nothing" to them is a bot that is working: refusing is a contract-conforming outcome, not a failure. If either of them *does* return a value, you have found something worth reporting — say so at the closing round.

**If any of the four lines does not look like the table, stop here and fix it before going on.** Everything in the rest of this iteration assumes they behave like this. The three things that go wrong, in the order they happen: no key in `.env` (the bot says so and exits — go back to Task 1a), the endpoint unreachable (`python check_llm.py` says which), or a missing package (`python check_setup.py` names it). If the two `pizza` lines are right while *every* `address` line is empty, the rule works and the model does not — that is the key or the endpoint, never the code.

Now run it without `--interactive`, and run the tests:

```bash
python example/simple_bot.py                        # four sentences through both nodes
python -m pytest example/example_tests.py -v        # 6 passed: five for the rule, one for the model
```

Those four sentences are the four you just typed. That is not a coincidence — the file runs exactly the cases the sheet asked you for, and the point of typing them first was to see them answered *to you* before reading them in somebody else's code. Compare the two outputs: they must agree, sentence for sentence. If your typed run and the scripted run disagree, the difference is the model, not the code, and that is the first thing this iteration is about.

Now read `example/example_tests.py`, top to bottom. Five cases for the rule and five for the model, in two lists; the rule asserted case by case with `@pytest.mark.parametrize`, so a failure names the sentence that broke; the model asserted once, over all five, against `ADDRESS_THRESHOLD`.

**2b — the address gains a street and a house number (4 min).** Today the example's address is a postcode and a city. Make it four fields. In this order:

1. **The cases first.** The three complete addresses gain a street and a house number — in the sentence *and* in the expected value. And one sentence changes sides: `"deliver it to 42000 Saint-Étienne"` was a complete address this morning and is an incomplete one now, so its expected value becomes `{}`. Nothing about the model changed; the specification did, and the cases are where a specification is written down.
2. `ADDRESS_FIELDS` in `simple_bot.py` — one line. The schema check and the domain check are written over that tuple, so neither needs an edit. If you find yourself editing them, look again.
3. The prompt. Copy `prompts/example_address_v1.txt` to `example_address_v2.txt`, change the `Output:` line and the examples, and point `ADDRESS_PROMPT` at the new name. A prompt is configuration: a new field list is a new version, and a version lives in the file name.

```bash
python -m pytest -q example/example_tests.py        # still green, or the misses name the case
```

The threshold does not move. The specification did.

**2c — the pizza rule becomes a similarity function (5 min).** `recognize_pizza_name` only finds a menu name that is spelled correctly, which is why `"one Margaritha please"` expects `""` today. Replace the literal lookup by a **similarity function** — [`difflib.SequenceMatcher`](https://docs.python.org/3/library/difflib.html) is in the standard library — comparing every word (and every pair of consecutive words, so that `Quattro Formaggi` is still findable) with every menu name, and keep the best match above a `SIMILARITY` constant. The guarantee does not move: what the method returns is still a name from `MENU`, or `""`.

Then extend `PIZZA_CASES`: `"one Margaritha please"` now expects `"Margherita"`, and you add near misses of your own — a missing letter, a wrong last letter, a `k` for a `c` — plus at least one sentence that must still return `""`.

And now the point of the whole task: **that test needs a threshold too.** A similarity function has no guaranteed right answer per case; which near misses it catches depends on `SIMILARITY`, and moving that number trades one kind of mistake for the other. So the pizza test loses its `parametrize` and gains a `PIZZA_THRESHOLD`, exactly like the model's test — and for exactly the same reason. Being a rule was never what made it exact.

```bash
python -m pytest -q example/example_tests.py        # both tests are rates now
```

Try `SIMILARITY = 0.85` and `0.5` and read the misses each time. Keep the value you chose as a named constant with a comment saying what the other two did — the constant *is* the record, which is why nothing else has to be written down.

**2d — all three, cascaded: try the cheap option first (5 min).** You now have two of the three options from slide 2.7 — the exact lookup you started with and the similarity function you just wrote — and the model is the third. Put all three into `recognize_pizza_name`, in cost order:

```
1  exact        the menu name is in the message          microseconds
2  similar      the closest menu name, if close enough   microseconds
3  the model    the menu goes into the prompt            a billed round trip
```

Each step may say "not me" and hand on; only the last one may say "nobody". `prompts/example_pizza_v1.txt` is given (it has a `<MENU>` placeholder the component fills), and the membership check after the model's answer does not move: the model chooses from a list, and we check anyway. Record which option answered in the module-level `LAST_TIER` — a **diagnostic**, not process data, which is why it is not in the state. The contract does not change at all: still a menu name, or nothing.

```bash
python example/simple_bot.py      # the pizza line now ends in [exact], [similar], [llm] or [none]
```

Two of the five sentences never reach the network. Read the usage line at the end: that is what the cascade buys.

And one more test, of a different kind. Which option *answered* is **exact** even though what option 3 answers is not: stages 1 and 2 are deterministic, so whether a sentence gets as far as the network is a fact, and a fact is asserted case by case. Add a `CASCADE_CASES` list of `(utterance, expected tier)` — one sentence per tier, including one that must end in `"none"` — and a parametrized test over it. It is the test that goes red if somebody reorders the stages.

> **The other direction exists too, and it is the one your bot builds.** Tasks 3 and 4 wire the model *first* with your Iteration 1 rule as the fallback. Same three pieces, opposite order: escalation buys latency and tokens, fallback buys coverage. Which one belongs in production is two numbers, and Iteration 3 measures them.

**2e — the same two lists for your own bot (4 min).** `tests/test_recognizers.py` is the skeleton, with the helpers written and four tests empty: `recognize_address` and `recognize_pizza` (your Iteration 1 rules, exact, so equality on every case) and `recognize_address_llm` and `recognize_pizza_llm` (approximate, so a rate against `THRESHOLD`). Five cases per component, the same list for both implementations.

The two threshold tests need **two** assertions, and the first is the one everybody forgets. Your LLM-backed components fall back to the rule on *every* failure — no key, a timeout, a bad schema, a failed domain check — and TODO 1 told you to pick five cases the rule gets right. So a test that only checks the hit rate is green with the network unplugged: the rule answered all five, correctly, and you measured the rule. Assert first that the service itself answered at least `ANSWERED` of the cases (`trace.TIERS` records who answered), then the rate. Prove it to yourself:

```bash
LLM_TIMEOUT=0.01 LLM_RETRIES=0 pytest -q tests/test_recognizers.py   # must be RED
```

If that run is green, your test does not test what you think it tests.

Pick the five the way the example does: two typical, one awkward but still inside what your rule can do, and two that must return nothing — with one of those two a case that *looks* like a good answer and is rejected for a reason only the domain knows (an address outside the delivery area, a pizza that is not on the menu). **All five must be cases your rule gets right**: the rule test asserts equality, so a case the rule cannot do makes it red and tells you nothing about the model. Your section 6 rows from Iteration 1 are not test cases for that reason — they are what Task 6 compares and what Iteration 3 measures.

```bash
pytest -q tests/test_recognizers.py -rs             # no skips left: you wrote all four
```

The two threshold tests are green immediately, and that is worth a minute: the empty skeletons of Tasks 3 and 4 fall back to your rule, so they inherit the rule's answers. They only begin to mean something once the service call is in. Watch the rate — in both directions.

> **Why before the implementation?** Because after Task 3 you would write the cases you already know your model passes. And keep the number honest: five cases cannot measure anything — at four of five the true rate lies roughly between 38 % and 96 %. With both assertions in place it is a smoke alarm: it catches a silent fallback and a collapse, not a regression. The measurement is Iteration 3.

---

## Task 3 — address recognition, LLM-backed [13 min]

**Files for this task:** the skeleton and its contract are in `pizzabot/address_llm.py` — the only file you edit. The prompt it sends is `prompts/address_v1.txt` (given; version it if you change it). The fallback is your own `recognize_address` from `pizzabot/task4_address.py`; the delivery-area check is your own `pizza_api.validate_address`. Comparison template: `compare_configs.py`. The drawing in 3a stays on paper — it is for your team, not for the repository.

The contract in `address_llm.py` is the Iteration 1 contract, copied. Do not change it — implement it a second time. Two rows of it changed, **calls** and **rules**: they describe the implementation, and for a model the `rules` row can only list the checks and the fallback. The other four rows — `reads`, `writes`, `guarantee`, `failure` — are the contract, and they did not change. If you need to change one of those four, stop and ask why.

**3a — draw it first (3 min).** The component as a box, and inside it the chain: the service call, the schema check, the domain check, the fallback. Draw where a wrong answer *can* go (back to the rule) and where it *cannot* go (into the slot). Mark the two places the component talks to the outside: the model, and the Pizza API. Paper is enough — the drawing is how your team agrees on the chain before anyone types, and it stays with you.

**3b — implement (8 min).** Two TODOs. `plausible()` is the domain check: three rules — the house-number pattern with its digits copied from the utterance, "street and city occur in the utterance" (compared with the given `fold()` helper, so accents and case do not matter — the API compares the same way), and the delivery-area call. `recognize_address_llm()` is the tiered flow: call, schema check, domain check, fallback — the comment block in the skeleton spells out the order. Run the component on its own while you work:

```bash
python -m pizzabot.address_llm "number 5 in the Rue Michelet here in Saint-Étienne"
python -m pizzabot.address_llm "deliver to Lyon"                  # tier: [static], and why
```

Read the `tier` line every time: it says who answered and, if the rule had to, why. When the rule runs, it logs its own block, so the component appears twice in the trace — that is the fallback, not a bug.

**3c — compare (2 min).** `compare_configs.py --address` runs a case list through your rule *and* your LLM component, side by side, and shows in the first column which tier answered. The given list starts with the rows of the reference section 6 of Iteration 1 — the cases the rules could not handle. Add three of your own at the `# TODO` at the end of the list, starting with the rows of *your* section 6.

```bash
python compare_configs.py --address
```

Rows marked `*` are the ones where the two implementations disagree. Both may keep the contract; which one is *right* is a question this course does not answer until Iteration 3. If a row broke a promise (a half address, an invented city), fix the check in the component now and add the row as a test.

Two French cases are in the list: `5 rue Michelet 42000, Saint-Étienne` — your rule stores 42000 as the house number (contract kept, delivery wrong), the model stores 5; that row is the first entry of Iteration 3's dataset. And `5 bis rue Michelet, Saint-Étienne` — your rule stores the street as `bis rue Michelet` (contract kept, wrong again), and the skeleton's house-number pattern rejects the model's `5 bis`, so the rule decides. The pattern is yours: extend it, and notice that the fallback is not a neutral floor — when the model is rejected, the rule's wrong answer wins.

---

## Task 4 — pizza recognition, LLM-backed [9 min]

**Files for this task:** `pizzabot/pizza_llm.py` (skeleton and contract), `prompts/pizza_v1.txt` (given; it has a `<MENU>` placeholder that the component fills from `GET /pizza`), the fallback `recognize_pizza` from `pizzabot/task3_pizza.py`. Comparison: `compare_configs.py --pizza`.

Same shape as Task 3, one field instead of three, so the schema check is one line and the domain check is membership: the name the model answers must be on the menu, spelled as the menu spells it. The menu goes *into the prompt* — the model chooses, it does not invent — and the membership check stays, because "less likely to invent" is not a guarantee.

**4a — draw (2 min):** where does the menu enter, and where is it checked? Two arrows into the box from the Pizza API, or one? Section 10.

**4b — implement (5 min):** two TODOs. Note the case `{}`: the model says "no menu item fits". Fall back to the rule in that case too: the rule is the guaranteed minimum, and it always runs last.

```bash
python -m pizzabot.pizza_llm "the four-cheese one please"
python -m pizzabot.pizza_llm "One Pizza Napoli please"           # tier: static, "not on the menu"
```

**4c — compare (2 min):** `python compare_configs.py --pizza`. On the ten-pizza menu, `the spicy one with salami` is a row where the rule (a literal mention: Salami) and the model (Diavola) both keep the contract and disagree. Which is right? Settle it in your team and be able to say how you know — that question is the hardest one on the sheet, and it is the one the closing round asks for.

---

## Task 5 — one graph, two configurations [10 min]

**Files for this task:** `pizzabot/graph.py` (one TODO), `pizzabot/config.py` (given: the two dictionaries), `run_dialog.py`, `tests/test_contracts.py` and `conftest.py` (given, changed), `demo_visualize.py --both`.

**5a — the seam (3 min).** `build_graph` still imports the two recognizers itself. Replace the two `add_node` lines by the loop in the TODO, so that the graph wires whatever dictionary it is given, and delete the two imports. Then:

```bash
python run_dialog.py --script            # the Iteration 1 walkthrough, unchanged
python run_dialog.py --llm --script      # "can I order the four-cheese one to number 5 in the Rue Michelet here in Saint-Étienne?"
```

The order completes in the turn after `Hello`. The script says "can I *order*", not "can I get". Why? The router is still your Iteration 1 rule. "can I get" is not one of its intent phrases, so the turn would go to `help`, and the two LLM-backed components would never run. The LLM improves recognition, not routing; routing did not change today. Say that sentence out loud in your team — it is the one sentence of Task 5 worth remembering, and it is what the closing round asks about.

**5b — the suite, twice (4 min).**

```bash
pytest -q                               # now: 69 passed. In the preparation, with the empty skeletons: 56 passed, 1 failed, 4 skipped
pytest -v -k llm | head -5              # the [llm-...] test ids; -k static shows the other half
```

The last line pytest prints says `static: 19 passed | llm: 19 passed | not parametrized: 31 passed` — the last group is the twelve tests you wrote in Task 2 plus the nineteen that are not parametrized over the configurations. In the preparation, with the empty LLM skeletons and the four unwritten tests skipped, fifty-six of the fifty-seven that ran passed already, because the skeleton falls back to the rule and the rule keeps every contract. Only `test_graph_uses_the_injected_implementation` failed — it fails until Task 5a is done. What does that tell you about what the contract tests can and cannot see? (They cannot see whether the model ever answered. That is what the first column of `compare_configs.py` is for today, and what Iteration 3's metric is for.)

Read `conftest.py` and the top of `tests/test_both_configurations.py`: nothing in the recognizer tests says which implementation is under test. They take the component from the `implementation` fixture, which pytest fills once per configuration. If a test had to know which implementation runs, the contract would have leaked into the test. The assertions are the same statements as in your Iteration 1 tests; only the entry point moved from the pure helper to the node. Without a key in `.env` the LLM half is *skipped*, not failed — `pytest -q -rs` shows why. Failure injection shows the same thing without a key: `LLM_TIMEOUT=0.01 LLM_RETRIES=0 pytest -q` — every call times out, every component falls back, every test passes.

**5c — the picture (3 min).** Export the process model from both configurations and let the script compare them:

```bash
python demo_visualize.py --both         # -> docs/pizza-process-model-{static,llm}.mmd, and IDENTICAL
git add -A && git commit -m "iteration 2: LLM-backed recognizers behind unchanged contracts"
```

The two exports can only differ if somebody edited the wiring: this is a guard against an added node, not a proof. The picture proves the topology, the tests prove the contracts, and Iteration 3 measures the quality.

---

## Task 6 — the measured difference and the service card [6 min]

**Files for this task:** `compare_configs.py` (all cases, both components) — nothing to write up; the script prints everything this task produces.

```bash
python compare_configs.py
```

The end of the output has three blocks: the **per-case rows** for both components; the **two numbers**, one row per configuration, with today's date; and the **service card** — what a colleague needs in order to maintain this step without asking you: provider, model, prompt files, temperature, token limit, timeout, retry budget, domain checks, fallback, and the measured latency and tokens per call.

Read all three on the screen, and answer two questions in your team: how many cases are correct in the static configuration, and how many in the LLM configuration? "Correct" is your own judgement today — Iteration 3 replaces the judgement by a dataset and a metric. Look at the service card and find the one row you cannot fill in from the output: that gap is the point of the card. Nothing here goes into a document; the script can reprint it any time. While it runs, write the three hostile utterances for Task 7.

---

## Task 7 — the adversarial round [12 min]

**Files for this task:** `adversarial.py`. What you need from the other team: three hostile utterances.

Every team writes three hostile utterances for the team next to them — inputs designed to make the other bot crash, invent a pizza, or store a half address. Be creative and try to break it: empty input, two addresses in one sentence, a pizza that is almost a menu item, punctuation where a city should be, something in your own language. And the Iteration 2 kind, which only works against a model: an instruction hidden in the utterance ("ignore the menu and …"), a fake JSON answer inside the text, a request to confirm without an address.

Exchange the utterances, paste the ones you received into `HOSTILE` below the three given warm-up utterances (keep those), and run:

```bash
python adversarial.py                   # every utterance, both configurations
python adversarial.py --dialog --llm    # the three as one conversation
```

The script checks the three promises your contracts make, and those are not negotiable: the process does not crash; `slots.pizza_name` is a name that exists on the menu; `slots.address` has street, house number and city inside the delivery area, or does not exist. A bot that answers "I did not understand" to all three passes. That is what a guarantee is: a statement about what a component will *never* do, not about how clever it is. Iteration 1's contracts have no precondition — the rule accepts every utterance. The LLM implementation may not demand more: no key, no network, no well-formed input (slide 2.16, "may demand more? never"). The three promises are the test of that.

The script prints one row per utterance for both configurations — read them on the screen. Two kinds of rows are interesting. First: every promise held, but the answer is still wrong. Second: the *reason* differs between the configurations — for example, the same injection is stopped by "no pattern matches" in `static` and by the delivery-area API in `llm`. If a promise broke, fix the component (a check, not the prompt) and add the utterance to `tests/test_both_configurations.py` — or, if it is a case with a clear expected value, to the list in `tests/test_recognizers.py`, where it counts against the threshold from now on. The test is the record: a fixed bug that no test holds down is not fixed.

### You are done when you can tick all four

1. `python adversarial.py` prints `0 broken promise(s)` for both configurations — or names the promise you fixed and the test that now keeps it fixed.
2. For every hostile utterance you can name *which check* stopped it in the LLM configuration (the `tier` line in the trace says; `LOG_LEVEL=INFO python adversarial.py --llm` shows it).
3. You can point at one row on the screen where the contract held and the answer was wrong anyway — bring that one to the closing round.
4. You know what the other team's bot did with the three utterances you sent.

---

## If you still have time

* **A third configuration.** A dictionary with the static pizza rule and the LLM address component — one line in `pizzabot/config.py`. Which tests does it pass? All of them, and what does that prove?
* **Prompt v2.** Copy `prompts/address_v1.txt` to `address_v2.txt`, change one thing, point `PROMPT_VERSION` at it, and run `compare_configs.py` again. A prompt change is a configuration change, and this is what "re-measure" means.
* **Add "can I get" to the router's intent phrases** — and notice that you just changed Iteration 1 code. Was the router's contract wrong, or its implementation?
* **The other client.** `ilaas_connector.py` from the course's `ilaas-connector` folder (handed out with the lecture material, not in this repository) talks to the same endpoint and already handles its known problems. Swap it in behind `LlmService.extract` without touching any node.
* **`json_schema` mode.** Change `response_format` in the adapter to `{"type": "json_schema", "json_schema": {...}}` with the schema from Lecture 2 and count the fenced answers again — and check whether the values moved: constrained decoding can change answers, not only their shape (Tam et al., EMNLP 2024, arXiv:2408.02442).
* **The repair prompt (the lecture's tier 2).** Before falling back on a schema failure, ask the model once more with "Your last answer did not have the shape asked for" appended to the prompt — slide 2.34 shows the function. Measure how often it helps; on 2026-09-12 it would have helped zero times in sixty calls.
* **Let a machine write the hostile utterances.** The three promises of `adversarial.py` are properties; [Hypothesis](https://hypothesis.readthedocs.io/) can generate thousands of utterances against them.
* **Let a machine write the test cases.** Five cases per method is what a pair can write in five minutes, and it is far too few to measure anything — the confidence interval in Task 2c says so. Take one of your cases and produce ten paraphrases of it (by hand, with a script, or by asking the model itself), keep the expected value, and run the threshold test again. Where does the rate go, and is the number you now have any more trustworthy? Growing a test set automatically for an LLM-driven service is a topic of Iteration 3.

---

## Troubleshooting

| symptom | cause and fix |
| --- | --- |
| every row of `compare_configs.py` says `[static]` | nothing implemented yet (the trace says `not implemented`) — or no key, or the wrong key: `python check_setup.py`, the last check does one real extraction and says what went wrong |
| `check_llm.py` or `check_setup.py` says 401 | the key in `.env` is wrong or has a trailing space; keys were handed out in Iteration 1 |
| `NotFoundError ... Unknown model` | `MODEL_NAME` is not offered by the endpoint; `python check_llm.py` lists the models that are |
| the trace says `answer was fenced` | normal for the default model; the adapter stripped the fences. Count it: it belongs on the service card |
| the trace says `answer is not JSON ... finish_reason=length` | `max_tokens` too small for the answer; 200 is enough for an address |
| the LLM component always falls back with "does not occur in the utterance" | your copy check compares with case or accents; use the given `fold()` on both sides — the API does not care either |
| the component appears twice in the trace | the fallback: the rule logs its own block after the `tier` line |
| `pytest -q` takes minutes | the endpoint is loaded; `LLM_TIMEOUT=5 LLM_RETRIES=0` in `.env` keeps the suite short — the fallback makes it green either way |
| `run_dialog.py --llm --script` prints `script exhausted` | no key: the rule cannot parse the lecture sentence, so the form keeps asking — the fallback's floor, demonstrated |
| `pytest -q` ends with `llm: 19 skipped` | no key configured (the template value does not count); `pytest -rs` prints the reason. Fill in `.env` |
| `test_graph_uses_the_injected_implementation` fails | Task 5a is not done: `build_graph` still wires the imported rules instead of the dictionary |
| `run_dialog.py --llm` sends a good sentence to `help` | the router is still the Iteration 1 rule; the sentence has no intent phrase and no menu name. Routing did not change today |
| a call takes 20 s and then falls back | `LLM_TIMEOUT` in `.env`; the shared endpoint is slow when the whole room calls it at once — the fallback is doing its job |
| `PizzaApiError` in the domain check | the delivery-area call needs the Pizza API; start the stub and set `PIZZA_API_BASE` |
| `UnicodeEncodeError` on Windows | `set PYTHONUTF8=1` before running |

---

## Where this comes from, and where to go next

**Before the next lecture (20 minutes, pick one):**

* Kästner, C., *Machine Learning in Production*, chapter 7, *Planning for mistakes* — guardrails and graceful degradation as design topics, free and CC-licensed: <https://mlip-cmu.github.io/book/07-planning-for-mistakes.html>
* Kästner, C., *Machine Learning in Production*, chapter 15, *Model quality* — what Lecture 3 opens with: measuring instead of judging: <https://mlip-cmu.github.io/book/15-model-quality.html>

**The sources of the ideas you used today:**

| what you did | where it comes from |
| --- | --- |
| kept the process and swapped one implementation | Martin, R. C. (2003), *Agile Software Development: Principles, Patterns, and Practices*, Prentice Hall, chs. 8–12 (the five SOLID principles; the open/closed idea is Meyer, B. (1988), *Object-Oriented Software Construction*); the word *seam*: Feathers, M. C. (2004), *Working Effectively with Legacy Code*, Prentice Hall, ch. 4 |
| checked that the substitute keeps every guarantee | Liskov, B. (1988), *Data Abstraction and Hierarchy*, [doi:10.1145/62139.62141](https://doi.org/10.1145/62139.62141); Liskov, B. H., & Wing, J. M. (1994), *A Behavioral Notion of Subtyping*, [doi:10.1145/197320.197383](https://doi.org/10.1145/197320.197383); Meyer, B. (1992), *Applying "Design by Contract"*, [doi:10.1109/2.161279](https://doi.org/10.1109/2.161279) |
| put the model behind an adapter with our own contract | Cockburn, A. (2005), *Hexagonal architecture (ports and adapters)*: <https://alistair.cockburn.us/hexagonal-architecture/>; Gamma, E., et al. (1994), *Design Patterns* — Adapter, Strategy |
| injected the implementation through a dictionary | Fowler, M. (2004), *Inversion of Control Containers and the Dependency Injection pattern*: <https://martinfowler.com/articles/injection.html> |
| treated the model as a remote, fallible, billed service | Kästner, C., *Machine Learning in Production*, ch. 10, *Deploying a model*: <https://mlip-cmu.github.io/book/10-deploying-a-model.html>; Chen, L., Zaharia, M., & Zou, J. (2024), *How Is ChatGPT's Behavior Changing over Time?*, Harvard Data Science Review 6(2), arXiv:2307.09009 — why the model id is pinned |
| validated shape first, then meaning, then fell back | Randell, B. (1975), *System structure for software fault tolerance*, IEEE TSE SE-1(2), [doi:10.1109/TSE.1975.6312842](https://doi.org/10.1109/TSE.1975.6312842) — recovery blocks: primary, acceptance test, alternate; the same structure fifty years later: Instructor, <https://python.useinstructor.com/> |
| asked for structured output and checked it anyway | Willard, B. T., & Louf, R. (2023), *Efficient Guided Generation for Large Language Models*, arXiv:2307.09702 (how constrained decoding works); OpenAI (2024), *Introducing Structured Outputs in the API* (the two modes; on this endpoint `json_object` is a request, not a guarantee — measured) |
| retried with a budget and a pause, and never on a call with side effects | Nygard, M. T. (2018), *Release It!*, 2nd ed., Pragmatic Bookshelf, ch. 5; Brooker, M. (2015), *Exponential Backoff and Jitter*, AWS Architecture Blog; RFC 9110 §9.2.2 (idempotent methods); the strict boundary: RFC 9413, *Maintaining Robust Protocols* (Postel's law, reversed) |
| survived a hostile utterance | Perez, F., & Ribeiro, I. (2022), *Ignore Previous Prompt*, NeurIPS 2022 ML Safety Workshop, arXiv:2211.09527; Greshake, K., et al. (2023), *Not what you've signed up for*, AISec '23, [doi:10.1145/3605764.3623985](https://doi.org/10.1145/3605764.3623985); OWASP (2025), *Top 10 for LLM Applications*, LLM01; the three promises as properties: Claessen, K., & Hughes, J. (2000), *QuickCheck*, ICFP 2000, [doi:10.1145/351240.351266](https://doi.org/10.1145/351240.351266) |
| versioned the prompt like code | Sclar, M., et al. (2024), *Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design*, ICLR 2024, arXiv:2310.11324 — formatting alone moves accuracy by tens of points |
| documented the step next to its contract | Mitchell, M., et al. (2019), *Model Cards for Model Reporting*, FAT* 2019, [doi:10.1145/3287560.3287596](https://doi.org/10.1145/3287560.3287596) — the service card is a model card for one step |
| ran the same tests against two implementations, and killed a mutant | pytest, *Parametrizing fixtures*: <https://docs.pytest.org/en/stable/how-to/fixtures.html#parametrizing-fixtures>; DeMillo, R. A., Lipton, R. J., & Sayward, F. G. (1978), [doi:10.1109/C-M.1978.218136](https://doi.org/10.1109/C-M.1978.218136) |
| left hand-written rules where they stop converging | Church, K. W., & Mercer, R. L. (1993), *Introduction to the Special Issue on Computational Linguistics Using Large Corpora*, Computational Linguistics 19(1): <https://aclanthology.org/J93-1001/>; the LLM step is the NLU component of the frame-based system you built: Jurafsky & Martin, SLP3, App. K |

**The measured facts on the slides** (fenced JSON, latency, the injection that passed the model, "Pizza Napoli" with and without the menu) were all measured against ILaaS on 2026-09-12 with `mistral-small-4-119b` and `qwen-3.6-35b-instruct`; so was the pizza prompt that answered Margherita to "I am hungry" in 2 of 10 runs at temperature 0 before it got its never-guess rule (Ouyang et al., TOSEM 2025, arXiv:2308.02828, on why temperature 0 is not determinism). Your numbers will differ. That is the point of writing them down with a date.
