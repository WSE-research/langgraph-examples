# The warm-up example — two nodes, two unit tests

A working LLM-backed process in three files, small enough to read before the coffee is cold. It is the shape of Iteration 2 with everything else taken out: no Pizza API, no order form, no router, no fallback, no configurations.

| file | what it is |
| --- | --- |
| `simple_bot.py` | two nodes and the graph that runs them: `recognize_pizza_name` (rule-based, the name has to be on the menu) and `recognize_address` (LLM-backed, a postcode and a city) |
| `example_tests.py` | one unit test per node, with the cases as data: the rule is checked on every case, the model against a threshold |
| `../prompts/example_address_v1.txt` | the prompt the address node sends — a file with a version in its name, not a string in the code |
| `../prompts/example_pizza_v1.txt` | the prompt of the third stage of the pizza cascade (Task 2d), with a `<MENU>` placeholder the component fills |

## Run it

The key is the one handed out in the lecture hall. Paste it into `.env` in the repository root (never into a file you commit — `.env` is in `.gitignore`):

```bash
cp .env.example .env                     # if you have not done it yet
# then edit .env: OPENAI_API_KEY=<the key from the lecture hall>
python example/simple_bot.py --interactive   # you type the sentences -- start here
python example/simple_bot.py             # four sentences through both nodes
python example/simple_bot.py "one Diavola to 42000 Saint-Étienne"
```

You should see the pizza recognised by the rule, the address recognised by the model, and a usage line at the end with the latency and the token counts. If it says "No key in .env", the key is missing or the line in `.env` is misspelled; `python check_setup.py` says which.

## Test it

```bash
python -m pytest -q example/example_tests.py       # 6 passed
python -m pytest example/example_tests.py -v       # one line per case
```

Six tests: five for the rule — `parametrize` makes one test per case, so a failure names the sentence that broke — and one for the model, which runs all five of its cases and asserts the **rate**. Without a key the model's test is skipped, not failed.

The file is called `example_tests.py`, not `test_something.py`, so that `pytest -q` in the repository root does not pick it up. This is a sandbox with its own run.

## Why two different bars

The rule is **exact**: every case has one right answer and the rule produces it, every time. Its test asserts equality, and the bar is all five.

The model is **approximate**: it is right most of the time, and "most" is a number you have to write down. Its test asserts `rate >= ADDRESS_THRESHOLD`.

The dividing line is exactness, not who wrote the method — which is what Task 2c shows: as soon as the pizza rule becomes a similarity function, it is approximate too, and it needs a threshold for exactly the same reason.

Five cases cannot measure anything: at four of five the true rate lies roughly between 38 % and 96 %. It is a smoke alarm, and only if you also assert *who answered*: in the real bot (Task 2e) the LLM-backed components fall back to the rule on every failure, so a rate-only test stays green with the network unplugged. The measurement is Iteration 3.

## What you change (Task 2 of the sheet)

* **2b** — the address is only a postcode and a city today. Make it a street, a house number, a postcode and a city: one constant, one new prompt version, and the test cases, which are the specification and therefore change first.
* **2c** — `recognize_pizza_name` only finds a menu name spelled correctly. Replace the lookup by a **similarity function**, so that `Margaritha` is understood — then extend the cases with more near misses and give that test a threshold too.
* **2d** — put all three options into that one method, cheapest first: exact, then similarity, then the model. Each step may say "not me"; only the last may say "nobody". Record which one answered in `LAST_TIER` and assert it case by case — *which* option answered is exact even when *what* the model answers is not.

All three are changes of the implementation. `pizza_name` is still a menu name or nothing, `address` is still complete or nothing: the contracts do not move — which is the only reason three implementations may hide behind one method.

## The cascade, measured

On the four demonstration sentences (2026-09-14, five-item menu, `mistral-small-4-119b`):

| the customer says | answered by | cost (tokens in / out) |
| --- | --- | --- |
| "I would like a Margherita" | 1 exact | 0.01 ms |
| "one Margaritha please" | 2 similarity (score 0.80) | 0.4 ms |
| "the four-cheese one please" | 3 the model → Quattro Formaggi | 1.0 s, 159 / **16** |
| "I want sushi" | nobody → `""` | 0.4 s, 157 / **2** |

Two of the four never reach the network. And look at the two that do: they cost almost the same to *ask* — the menu is in the prompt either way — and differ in the *answer*, 16 tokens against 2. What you send is the expensive half, which is why a prompt is configuration and not a place for prose. And the last row is not a failure of the cascade: "nothing on the menu" is an answer the contract allows, and the process asks.

The **other** direction is what the real bot builds in Tasks 3 and 4: the model first, your Iteration 1 rule as the fallback. Same three pieces, opposite order — escalation buys latency and tokens, fallback buys coverage. Which belongs in production is two numbers, and that is Iteration 3.
