# The pizza stories — invented for teaching, not history

**Every text in this folder is made up.** The pizzerias, the people (Mario, his grandmother Assunta, his uncle Nino, his wife Elena, the dairy in the Sele plain), the years, the villages, the oven temperatures and the house rules were written for this course as a retrieval corpus. They are **not** the history of these pizzas, they are not sourced, and nothing in them should be repeated as fact outside this exercise.

Two details are real and are marked as such in the text itself, because the knowledge graph of Iteration 4 already contains them and the two sources must not contradict each other:

* the **Hawaiian** was invented by Sam Panopoulos in Ontario in 1962;
* the **Marinara** is named after sailors, not after seafood.

Everything else — regions, motivations, preparation steps, baking times — is fiction with a plausible surface. That is deliberate: a retrieval corpus that can be answered from general world knowledge cannot show you whether your retriever worked. If your bot answers a question about the Boscaiola correctly **without** retrieving `boscaiola.md`, the model is inventing, and the exercise has just shown you exactly the failure mode Lecture 6 is about.

## What is here

One Markdown file per pizza, 22 files, the file name is the pizza in lower case with hyphens (`quattro-formaggi.md`). Every file has the same nine sections, in the same order:

```markdown
# Da Mario — the story of the <Name>
## Where it comes from
## What the creator had in mind
## Why these ingredients
## How we prepare it
## How we bake it
## In numbers          <- a bullet list: weights, temperatures, times
## What guests ask     <- three questions with their answers
## How it goes wrong   <- the failure modes, as bullets
## House note
```

The shape is not decoration, and neither is the format. Markdown headings are what a **structure-aware splitter** can see: it keeps *How we bake it* together with its heading and its pizza, while a fixed 800-character window cuts wherever character 800 happens to fall. Ingest the same folder twice, once with each setting, and the difference is the exercise.

Three of the sections exist because of what they do to retrieval:

* **In numbers** is a bullet list of weights, temperatures and times. Bullets are short, so a window splitter is likely to cut the list in half — the table pitfall of slide 6.7 in a form you can reproduce in one minute.
* **What guests ask** is a small FAQ. It is the section a question like *“why is my cheese not melted?”* should retrieve, and a good check of whether your retriever matches on meaning or on words.
* **How it goes wrong** is a list of failure modes. Ask *“what happens if the mushrooms go on raw?”* and see whether the passage that comes back is the one that answers it.

At 600–900 words each, one file is roughly **four to eight chunks** at `chunk_size=800`, which is small enough that you can print every chunk your ingest produced and read them all. Do that once. It is the fastest way to understand what your retriever is actually searching.

## Keeping them consistent with the knowledge graph

The toppings and the quantities named in the stories match `data/menu-facts.ttl` of Iteration 4. The **Verdure** and the **Marinara** carry no dairy (they are the vegan ones), the **Ortolana** does. If you change a story, check it against the graph — a corpus that contradicts the graph is a useful exercise in hybrid QA, but only when you did it on purpose.
