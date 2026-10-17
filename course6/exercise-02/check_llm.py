"""Task 8 -- is the LLM endpoint reachable, and does it answer?

    python check_llm.py                    # three checks against the endpoint
    python check_llm.py --model <a name>   # try another model the endpoint offers

Iteration 1 does not use an LLM: every component you build today is a rule.
This check exists so that the *infrastructure* is proven working before
Iteration 2 depends on it -- finding out that a key is wrong costs five minutes
today and half a session next week.

Configuration -- put it in .env (see .env.example). All three values are
provided on-site, independently of this repository::

    OPENAI_API_BASE=<provided on-site>          # an OpenAI-compatible endpoint
    OPENAI_API_KEY=<provided on-site>           # its access code
    MODEL_NAME=<provided on-site>               # one of the models it offers

Without MODEL_NAME this script still lists the models the endpoint offers, and
asks you to put the one you were given into .env -- it never picks one itself.

The endpoint speaks the OpenAI wire protocol, which is why the official
`openai` package can talk to it: an OpenAI-compatible endpoint is a
*contract*, and several providers implement it. That is the same idea as the
Pizza API stub -- and, in Iteration 2, the reason an LLM can step into a
component without the process noticing.

Install what this needs::

    pip install openai python-dotenv          # or: pip install -r requirements.txt
"""

from __future__ import annotations

import os
import sys
import time

from pizzabot import log          # the log layer: no script here calls print()


# A question with exactly one short, checkable answer -- so the check is a check
# and not a vibe.
QUESTION = "What is the capital of Greece? Answer with the city name only."
EXPECTED = "athens"


def setting(name: str) -> str:
    """A setting, or "" when it is unset or still the `<placeholder>` of .env.example."""
    value = (os.environ.get(name) or "").strip()
    return "" if value.startswith("<") else value


def config() -> tuple[str, str, str]:
    """Read the endpoint configuration from .env and the environment."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        log.warn("python-dotenv is not installed -- reading real environment variables only")

    base, key, model = setting("OPENAI_API_BASE"), setting("OPENAI_API_KEY"), setting("MODEL_NAME")
    if "--model" in sys.argv:
        model = sys.argv[sys.argv.index("--model") + 1]
    return base.rstrip("/"), key, model


def main() -> None:
    base, key, model = config()
    log.plain(f"endpoint : {base or 'NOT SET'}")
    log.plain(f"model    : {model or 'NOT SET'}")
    log.plain(f"key      : {'set (' + key[:4] + '...' + key[-2:] + ')' if key else 'NOT SET'}")
    log.plain()

    unset = [name for name, value in (("OPENAI_API_BASE", base), ("OPENAI_API_KEY", key)) if not value]
    if unset:
        log.fail(f"not configured: {' and '.join(unset)} -- .env still has the placeholder of .env.example, or no .env at all")
        log.hint("copy .env.example to .env and fill in the endpoint and its access code -- both are provided on-site")
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        log.fail("the openai package is missing")
        log.hint("pip install openai")
        sys.exit(1)

    client = OpenAI(base_url=base, api_key=key)

    # --- check 1: which models does the endpoint offer? ---------------------
    try:
        models = sorted(m.id for m in client.models.list().data)
    except Exception as error:  # noqa: BLE001
        log.fail(f"GET {base}/models", f"{type(error).__name__}: {error}")
        log.hint("check the base URL, the key, and whether you are behind a proxy or VPN")
        sys.exit(1)
    log.ok(f"the endpoint offers {len(models)} models", ", ".join(models))

    if not model:
        log.fail("MODEL_NAME is not set", "a model is chosen, never guessed")
        log.hint("put the model name you were given into .env (MODEL_NAME=...) -- it is one of the names above")
        sys.exit(1)
    if model not in models:
        log.warn(f"your MODEL_NAME {model!r} is not in that list -- pick one of the names above")

    # --- check 2: one question, one answer ----------------------------------
    log.plain()
    log.step(f">>> sending: {QUESTION}")
    started = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": QUESTION}],
            temperature=0,          # greedy decoding: stable in our runs, not guaranteed
            max_tokens=20,
        )
    except Exception as error:  # noqa: BLE001
        log.fail(f"POST {base}/chat/completions", f"{type(error).__name__}: {error}")
        sys.exit(1)
    answer = (response.choices[0].message.content or "").strip()
    seconds = time.time() - started
    log.plain(f"<<< received: {answer!r}   ({seconds:.1f} s)")

    if EXPECTED in answer.lower():
        log.ok(f"the answer contains {EXPECTED!r}", "the endpoint works")
    else:
        log.warn(f"the answer does not contain {EXPECTED!r}. The endpoint answers, but check the model.")

    # --- check 3: does it keep a dialogue? ----------------------------------
    # The second turn only resolves if the history is sent along -- the endpoint
    # itself is stateless. Remember that: in this course *you* own the state.
    messages = [
        {"role": "user", "content": QUESTION},
        {"role": "assistant", "content": answer},
        {"role": "user", "content": "And in which country is it? One word."},
    ]
    try:
        follow_up = client.chat.completions.create(
            model=model, messages=messages, temperature=0, max_tokens=20
        )
        second = (follow_up.choices[0].message.content or "").strip()
        log.plain()
        log.step(f">>> follow-up: {messages[-1]['content']}")
        log.plain(f"<<< received : {second!r}")
        log.ok("the endpoint has no memory of its own",
               "the history in `messages` is what it sees")
    except Exception as error:  # noqa: BLE001
        log.warn(f"the follow-up call failed: {type(error).__name__}: {error}")

    usage = getattr(response, "usage", None)
    if usage:
        log.plain()
        log.detail(f"tokens used by the first call: {usage.prompt_tokens} in, "
                   f"{usage.completion_tokens} out", indent="")
    log.plain()
    log.result("endpoint check finished -- note the model name that worked, "
               "you need it in Iteration 2.")


if __name__ == "__main__":
    main()
