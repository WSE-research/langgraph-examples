# Exercise 6 — answers from text, and the Pizzabot you would build next

Iteration 6 of *Engineering AI-Driven Software Processes — Hands-on KGQA with LangGraph and LLMs*, Université Jean Monnet Saint-Étienne, WS 2026/2027.

**Your bot answers what the graph knows.** Ask it *“Tell me something about the Boscaiola”* and it has nothing — not because the question is hard, but because nobody models a story as triples. Most of what a restaurant knows is like that: it lives in texts nobody will ever turn into data. Today you give your process a second way to answer, behind the same contract, in the same process graph — and then you spend the last half hour on the bot you would build if this course continued.

**The session is eighty minutes of work, and then the presentations.** That is deliberate. The four tasks below are the shortest honest path to a working text branch; everything else that belongs to this iteration — hybrid routing, the measured comparison of both representations, the chunking experiment — is in the appendices, as work you can do on your own. **Task 4 is not optional and it is not the part to cut when you run late.** It is what you present, and the presentations are why the timetable stops at eighty minutes.

| | task | minutes | you are done when |
| --- | --- | --- | --- |
| ☐ | 1 — ingest the stories, and look at your chunks | 0–15 | your collection id is written down, and you have read three chunks with your own eyes |
| ☐ | 2 — a `retrieval` node behind a contract | 15–30 | *“Tell me about the Boscaiola”* returns passages with scores, and nothing below the threshold |
| ☐ | 3 — `answer_construction`: answer **plus** evidence, refusal allowed | 30–50 | an answer that cites, and a refusal where nothing was retrieved |
| ☐ | 4 — **the Pizzabot you would build next** | 50–80 | a picture and three sentences, uploaded |
| | *then:* three minutes per team, in front of everybody | 80+ | you have presented it |
| ☐ | A–D | at home | four appendices: routing, the comparison, the chunking experiment, and what the six iterations were about |

---

## What you need

* your repository as Iteration 5 left it: the QA sub-graph, the annotation helper (`annotate`), `what_happened(target)`, and the tests;
* `stories/` from this folder — 22 Markdown files, one per pizza, 600–900 words each;
* the ILaaS **RAG** key in `.env` (`ILAAS_RAG_URL`, `ILAAS_RAG_KEY`) — a different service and a different key from the inference endpoint you have used since Iteration 2;
* **read `stories/README.md` first.** Those texts are invented — which is what makes this exercise measurable: nothing in them can be answered from what a model already knows. The nine sections every file has are the other half of the point; they are what a chunking decision either keeps or destroys.

**Three rules that apply to every task below, and that are not repeated in each one:**

1. **Write the test with the code, not after it.** Every node you add today gets at least one test in `tests/`, and `pytest -q` stays green from the first minute to the last. A node without a test is a node you will be afraid to change on the day it matters.
2. **Record what the component did.** Every node annotates itself with the helper from Iteration 5 — what it was given, what it returned, how sure it was. `what_happened(target)` must explain a text answer exactly as it explains a graph answer, without one new line of code.
3. **Write the explanation down in words too.** Two or three sentences per task, in your repository (`NOTES.md` is fine): what this component is for, what it is given, what it returns, and what it does when it fails. If you cannot write it, the contract is not finished.

---

## Task 1 — Ingest the stories, and look at what came out [15 min]

**Goal:** a private collection that holds the 22 stories, and your own eyes on the chunks it produced.

### Step by step

1. **Create the collection.** Private, unique name, your team number in it:

   ```python
   from ilaas_connector import IlaasRag

   rag = IlaasRag.from_env()
   collection = rag.create_collection("pizzabot-stories-team07",   # your team number
                                      visibility="private")
   ```

2. **Upload the 22 files** and wait for indexing — it is asynchronous, and a demo that does not wait is a coin flip:

   ```python
   for path in sorted(Path("stories").glob("*.md")):
       document = rag.upload_document(collection, path=str(path),
                                      chunk_size=800, chunk_overlap=100)
       print(path.name, rag.wait_for_indexing(document), "chunks")
   ```

3. **Commit the collection id**, because the process has to know what it reads from:

   ```python
   open("docs/collection.txt", "w").write(str(collection))
   ```

4. **Look at three chunks.** This is the step everybody skips and the one the whole task is for:

   ```python
   for hit in rag.search("How is the Bufala baked?", [collection], method="hybrid")[:3]:
       print(round(hit.score, 3), "|", hit.content[:300].replace("\n", " "), "\n")
   ```

5. **Write down what you saw** — three lines in `NOTES.md`: did a chunk lose its heading, so that the text no longer says *which pizza* it is about? Is `## How we bake it` whole in one chunk or split? What happened to the `## In numbers` bullet list?

### How you know you are done

* `docs/collection.txt` exists and holds an id you can paste into a search call;
* every one of the 22 files reported a chunk count above zero;
* `NOTES.md` has your three lines, and next to the collection id: `chunk_size`, `chunk_overlap`, the splitter, and today's date;
* you can point at **one** of the five pitfalls in `chunking-pitfalls.pdf` (in this folder) and say whether your ingest shows it.

Shared account: private collections, a unique name with your team suffix, and never delete a collection you did not create.

---

## Task 2 — A `retrieval` node behind a contract [15 min]

**Goal:** a node with the same shape as every other node you have built — question in, passages and scores out, nothing below the threshold, empty allowed — that records what it did.

### Step by step

1. **Write the contract down first**, in one sentence, in `NOTES.md`: *question → up to `TOP_K` passages with scores, none below `MIN_SCORE`, read-only, empty is a valid result.* Everything below is that sentence in Python.

2. **Add the state keys** the branch needs: `passages: list` and, if you do not have it yet, `path: str`. Name the writer in a comment, as in Iteration 1.

3. **Put the parameters where a reader can find them.** `TOP_K = 4` and `MIN_SCORE = 0.35` are contract parameters, not magic numbers; they belong at the top of the module, not inside the call.

4. **Write the node:**

   ```python
   TOP_K, MIN_SCORE = 4, 0.35            # contract parameters, not magic numbers

   def retrieve(state: ChatbotState) -> dict:
       """question -> passages + scores. Guarantee: nothing below MIN_SCORE."""
       hits = rag.search(state["question"], [COLLECTION], method="hybrid")
       passages = [{"id": i + 1, "text": h.content, "score": h.score}
                   for i, h in enumerate(hits[:TOP_K]) if h.score >= MIN_SCORE]
       return {"passages": passages,
               "log": annotate(state, "retrieval",
                               parameters={"question": state["question"],
                                           "k": TOP_K, "threshold": MIN_SCORE},
                               result={"scores": [p["score"] for p in passages],
                                       "n": len(passages)})}
   ```

5. **Wire it into the QA sub-graph** as a second branch: `retrieval → answer_construction` (Task 3), and for today let the router send every question to the text path so you can test it. The real decision is Appendix A.

6. **Write the tests** — `tests/test_task2_retrieval.py`, three of them:
   * a question that must hit: *“Tell me about the Boscaiola”* returns at least one passage, and `"Boscaiola"` appears in the top one;
   * the contract: **no** returned passage has a score below `MIN_SCORE`, and never more than `TOP_K` come back;
   * the empty case: *“Do you deliver to Lyon?”* returns `passages == []` and **does not raise**.

7. **Write the explanation** — the two or three sentences from rule 3, and check the record: after one run, `what_happened(target)` must show a `retrieval` line with the scores in it.

### How you know you are done

* `pytest -q tests/test_task2_retrieval.py` — green, all three;
* these four questions behave as the table says:

| question | what you expect |
| --- | --- |
| *“Tell me something about the Boscaiola”* | passages from `boscaiola.md` |
| *“Why is my Bufala not melted?”* | the *What guests ask* section of `bufala.md`, not the baking section — the corpus has an answer written for exactly this question |
| *“Tell me about the Hawaii”* | the name in the stories is *Hawaiian*: does hybrid search still find it? |
| *“Do you deliver to Lyon?”* | **nothing above the threshold** — and that must not crash |

* `what_happened(target)` prints one `retrieval` step whose record contains `k`, the threshold and the scores;
* you can say out loud what your bot does when the retriever returns nothing — and the answer is Task 3, not *“it crashes”*.

The empty result is the one to spend a minute on. It is not an error and not a bug: it is the retriever telling you the truth.

---

## Task 3 — `answer_construction`: an answer that cites, or no answer [20 min]

**Goal:** passages in, an answer with citations out — or an honest refusal, recorded as a result and not as an exception.

### Step by step

1. **Write the contract down first:** *passages → an answer and its evidence, or `NO_ANSWER`. The refusal is a first-class result.*

2. **Guard the model call.** No passages → return the refusal **without asking the model**. A model given nothing will invent something, and every hour you spend on prompts afterwards is spent on the wrong problem:

   ```python
   if not state["passages"]:
       return {"answer": None, "evidence": [],
               "log": annotate(state, "answer_construction",
                               parameters={"n_passages": 0},
                               result={"answer": "NO_ANSWER", "reason": "nothing retrieved"},
                               confidence=0.0)}
   ```

3. **Write the prompt, and bound it:**

   ```python
   PROMPT = """Answer the question using ONLY the passages below.
   Cite the passage number for every statement, like [2].
   If the passages do not contain the answer, reply exactly: NO_ANSWER.

   Question: %(question)s

   Passages:
   %(passages)s"""
   ```

4. **Call the model through the wrapper of Iteration 5** (`ask_llm`), never directly — that is what puts the prompt and the answer into the record as an `LLMrequest`.

5. **Validate what comes back**, exactly as you validated the LLM output in Iteration 2: if the answer is `NO_ANSWER`, it is a refusal; if it cites a number no passage has, treat it as a refusal too. Keep the passages that were actually cited as `evidence`.

6. **Write the tests** — `tests/test_task3_answer.py`, three of them:
   * **grounded:** *“Tell me about the Boscaiola”* → an answer containing at least one `[n]` citation, and every cited `n` exists in `passages`;
   * **refusal without a model call:** with `passages == []`, the node returns `NO_ANSWER`, and the stub LLM records **zero** calls (assert on the call counter — this is the test that catches the mistake);
   * **unsupported:** *“How much does the Boscaiola cost?”* — the price lives in the graph, not in the stories — must end in a refusal, not in a number.

7. **Write the explanation** and check the record: one `answer_construction` annotation plus one `LLMrequest` annotation per model call, and `what_happened(target)` reading like a sentence a guest could follow.

### How you know you are done

* `pytest -q tests/test_task3_answer.py` — green, all three;
* on screen: one answer with `[1]`-style citations, and one refusal where nothing was retrieved;
* the price question is refused. **A bot that answers it has failed this task in the most interesting way** — keep that transcript, it is worth showing in your presentation;
* `what_happened(target)` for a text answer has the same shape as for a graph answer: component, parameters, result, confidence, in time order;
* your `NOTES.md` says, in one sentence, what your process does when the model returns something it cannot support.

---

## Task 4 — The Pizzabot you would build next [30 min]

**This is not a coding task.** Nothing in it is graded on feasibility, data availability, budget or model choice — and it is the task the rest of the session was shortened for. You have thirty minutes; the instruction is to think past what six iterations have allowed so far.

### Step by step

1. **Five minutes, no drawing:** each person says one thing the bot should be able to do and cannot. Nobody evaluates anything yet. Write them all down.

2. **Pick one.** The most interesting, not the most feasible. If the team cannot agree, take the one that would change the most for the guest.

3. **Draw it [10 min].** The process: the components, what talks to whom, where the AI sits, where the data comes from. Paper and a phone camera, a whiteboard photo, a diagram tool — all fine. It is a process model, so it looks like the ones you have been drawing since Iteration 1.

4. **Write the process in words [10 min]:** the components, and for each one what it is **given** and what it **returns**. Same shape as Iteration 1's contracts, one level more ambitious. Mark the components where you would put an AI — and, for each of those, one line on how you would bound it.

5. **Three sentences [5 min]** on what is *interesting* about it: what could this bot do that ours cannot, and why is that worth building?

6. **Upload** one file, named with your team number:

   > https://cloud.imn.htwk-leipzig.de/index.php/s/bkfS9wokW8i2cee

Ideas that have come up in earlier years, to start you off and not to limit you: a bot that reads the kitchen's stock and re-plans the menu; one that explains a bill to a guest who disputes it; one that negotiates a delivery time with a courier service; one that learns a returning guest's constraints without being told them twice; one that runs the whole restaurant's ordering in three languages and proves it answered the same thing in each.

**Do not worry about whether the data exists.** Assume it does. The question is what process you would build if it did.

### How you know you are done

* one file in the shared folder, with your team number in its name;
* the picture shows **components with names**, not boxes labelled *“AI”*;
* every component in your description says what it is given and what it returns — and for the AI-backed ones, how they are bounded;
* your three sentences answer *why is this worth building*, not *how would we build it*;
* you can present it in **three minutes** without reading from the page.

Then present it: three minutes, the picture on the screen, the three sentences out loud. The best ideas in this session have never been the most detailed ones.

---

## Definition of done

1. `pytest -q` — green, including every test from Iterations 3, 4 and 5, plus the two new files from Tasks 2 and 3.
2. *“Tell me something about the Boscaiola”* — an answer that cites a passage from `boscaiola.md`.
3. *“Do you deliver to Lyon?”* — a refusal, with the scores that produced it visible in `what_happened(target)`.
4. *“How much does the Boscaiola cost?”* — a refusal, not a guess.
5. `NOTES.md` — one short explanation per task: what the component is for, what it is given, what it returns, what it does when it fails.
6. One page in the shared folder, and three minutes said out loud.

---

## Appendix A — Routing: graph, text, or both [~30 min at home]

*This was a task in the session until 2026-09-23, when the sheet was cut to eighty minutes so that the presentations have room. It is the first thing to do at home, and it is short.*

Two branches are not a process until something decides between them. Iteration 4's questions must keep working exactly as they did, so add the decision, not a rewrite:

```python
TEXT_CUES  = ("tell me", "story", "why", "how do you", "where does", "origin")
GRAPH_CUES = ("which", "how many", "is the", "price", "contains", "vegan", "vegetarian")

def decide_path(state: ChatbotState) -> dict:
    text = state["question"].lower()
    if any(cue in text for cue in GRAPH_CUES):
        return {"path": "graph"}
    if any(cue in text for cue in TEXT_CUES):
        return {"path": "text"}
    return {"path": "both"}        # graph first; text if the graph found nothing
```

Step by step: write the rule sets at the top of the module where a reader can see them; put `decide_path` in front of the sub-graph as its own node; send `graph` to `entity_linking`, `text` to `retrieval`, and `both` to the graph first with the text path as the follow-up when the graph found nothing; annotate the decision, because the choice of representation is itself something the bot has to explain; then write `tests/test_appendix_routing.py` with one case per branch plus one that must stay on the graph path, and the explanation in `NOTES.md`.

* keep it static. A rule set you can read is a rule set you can test, and an LLM classifier fits behind the same contract tomorrow;
* **how you know you are done:** `pytest -q` green, one `decide_path` line in `what_happened(target)` saying which path was chosen and why, and — the real check — your Iteration 4 factoid benchmark rerun with **no answer changed**. If a single one moved, your routing is wrong, and that regression is what this appendix is really about.

---

## Appendix B — Measure both paths [~45 min at home]

You now have two ways to answer and no evidence about which belongs where. The harness from Iteration 3 already does the work; what is missing is the data.

1. **Extend the benchmark.** Add a family of *text-answerable* questions — twenty is enough — drawn from the stories: origins, motivations, preparation, baking, the FAQ answers. Keep the graph-answerable family of Iteration 4 exactly as it is.
2. **Tag every case** with the path you expect: `graph`, `text` or `both`. That tag is the ground truth of your router.
3. **Run every case through both branches**, not just the one the router picks, and record four numbers per case: correctness, whether evidence was produced, latency, and cost.
4. **Report it per question type**, not as one average. An average over two representations is a number that describes nothing.

Then answer, in writing, the question the comparison exists for: **which question types belong to which path** — and where the two disagree, which one you would trust in front of a guest. That paragraph is worth more than the table it rests on.

Two results to expect, because they are the ones that surprise people: the graph path usually wins on factoid questions *by a distance* and is far cheaper; and the text path answers questions the graph cannot touch, while being the one that fails quietly. A process that knows which is which is the deliverable of this whole course.

---

## Appendix C — The chunking experiment [~20 min at home]

One corpus, two collections, one difference.

If your RAG service can split on Markdown headings, ingest `stories/` a **second time** into a second collection with that setting, and leave everything else identical. Then run the same four questions through both and compare, in writing:

* which collection returned the passage that actually answers *“Why is my Bufala not melted?”*;
* what happened to the `## In numbers` list in each — one piece, or cut between two bullets;
* whether a chunk in the window-split collection still says **which pizza** it is about;
* how many chunks each file produced, and how many of them you would be willing to show a guest as a citation.

The five pitfalls in `chunking-pitfalls.pdf` are all reproducible on this corpus. Reproducing one of them on purpose, and then removing it, teaches more than reading about all five.

**Why this is worth an evening:** chunking is the one decision in a RAG system that is made once, silently, by a default parameter — and that then limits every answer the system will ever give. Nobody notices it in a demo. Everybody pays for it in production.

---

## Appendix D — What the six iterations were about, and how to get good at it

*Read this one when the code is finished. It is the part of the course that survives the course.*

Six weeks produced one working bot, which is not the point. The point is six claims that hold well beyond pizza, and each of them is something you can practise until it becomes the way you work.

### The six findings

**1 — A process a team can build.** Decomposition first, contracts second, implementation last. The process model is an *artifact*: committed, drawn, reviewed, argued about. Everything else in this course is only possible because the work was cut into named components with agreed inputs and outputs.
*The claim:* control comes from structure you can see, and you can have all of it before any AI is involved.

**2 — AI inside, behind unchanged contracts.** An LLM became the implementation of a component whose contract did not move. Validation, fallback, a tier that gives up honestly. The static implementation stayed in the repository and stayed green.
*The claim:* an AI step that cannot be replaced is not a component, it is a dependency — and dependencies you cannot replace are the ones that decide your architecture for you.

**3 — Quality as a manifested number.** A benchmark, a baseline, a delta, an interval, and a gate that can say no. The hardest part was never the statistics; it was writing down what *better* means before measuring it.
*The claim:* “better” is a number with an interval, or it is an opinion with a slide.

**4 — Structured data answers, and gives its reason.** A knowledge graph, SPARQL, evidence triples per answer, and a menu that changes underneath the process. The moment the data moved, every hard-coded assumption in the bot showed itself.
*The claim:* if the data cannot say it, no prompt can — and the evidence for an answer is a query result, not a paragraph.

**5 — A process that records itself can explain itself, and repair itself.** One annotation per request, in a vocabulary other tools already read. The record turned “what happened?” into a query, turned a dead end into a declared need, and turned “did the repair close?” into one `ASK`.
*The claim:* a step that is not recorded did not happen — and never say no without a next step.

**6 — The representation decides what you can answer and explain.** Text answers what the graph cannot, refuses differently, cites differently, costs differently and fails more quietly. Choosing between them is an engineering decision with evidence behind it, not a preference.
*The claim:* choose the representation that can answer *and* explain, and measure both paths before you believe either.

### How to train them

Reading these six claims takes four minutes and changes nothing. They become yours the way any engineering skill does — by being used on something that can fail in front of somebody.

**Build the same thing again, alone, without the sheet.** A week after the course, rebuild the dialog process from an empty repository in an evening. You will discover which parts you understood and which parts you copied. Repeat until the process model comes out of your hands without being looked up; that is the difference between having done an exercise and having a skill.

**Take one AI feature that already exists at your work or in your own projects, and draw its process.** Find the component boundaries. Write the contracts nobody wrote. You will usually find one giant component with an LLM inside it and no contract at all — that is the normal state of the world, and now you know what to do about it.

**Write the benchmark before the feature.** Thirty cases and a gate, before a line of the implementation. It feels slow for about two days and then it is the only reason you can change anything with confidence. The habit is worth more than any particular metric.

**Practise the refusal path first.** Build *“I cannot answer that”* before you build the answer. Systems that can say no are the ones that can be trusted with a yes, and the refusal is where nearly all of the real engineering lives.

**Do a record audit once a month.** Take one run of something you built, and answer *what happened* using only what the system recorded — no debugger, no logs you added afterwards, no memory of what you wrote. Whatever you could not answer is a hole in the record. Fill it. Repeat.

**Break it on purpose.** Remove a `fulfilled()` call, split a table across two chunks, drop a validator, make a service answer 409. Watch what your process does, and whether your tests notice. An engineer who has seen their own system fail in six specific ways is not the same engineer who has only seen it work.

**Reproduce one number from one paper a month.** Not a whole paper — one number. It is the fastest way to learn what claims in this field actually mean, and the cheapest way to stop being impressed by the wrong things.

**Explain it in three minutes to somebody who does not build software.** Your process, why the AI step is bounded, how you know it got better. If you cannot, you do not yet understand it — and the explanation, not the diagram, is what gets a project approved.

### And the confidence part

Confidence in this work does not come from knowing more about models. It comes from three things you can actually acquire: **you have measured something and the number moved**; **you have bounded an AI step and watched the fallback save you**; **you have explained a failure from a record instead of a guess.** Each of those is one weekend of work, and each one is worth more than a year of following model releases.

The systems that matter are rarely the most sophisticated ones. They are the ones somebody can still explain, still measure and still repair two years later, after the people who built them have moved on and the model underneath has been replaced twice. That is what you practised here, and it is what will still be true when every model in this course is obsolete.
