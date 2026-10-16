"""Task 8 -- is the LLM endpoint reachable, and does it answer?

    python check_llm.py                    # three checks against the endpoint
    python check_llm.py --model gemma-4-31b

Iteration 1 does not use an LLM: every component you build today is a rule.
This check exists so that the *infrastructure* is proven working before
Iteration 2 depends on it -- finding out that a key is wrong costs five minutes
today and half a session next week.

Configuration -- put it in .env (see .env.example)::

    OPENAI_API_BASE=https://llm.ilaas.fr/v1     # ILaaS inference service
    OPENAI_API_KEY=<the key you were given>
    MODEL_NAME=mistral-small-4-119b

Both services of ILaaS speak the OpenAI wire protocol, which is why the
official `openai` package can talk to them: an OpenAI-compatible endpoint is a
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

DEFAULT_BASE = "https://llm.ilaas.fr/v1"
DEFAULT_MODEL = "mistral-small-4-119b"

# A question with exactly one short, checkable answer -- so the check is a check
# and not a vibe.
QUESTION = "What is the capital of France? Answer with the city name only."
EXPECTED = "paris"


def config() -> tuple[str, str, str]:
    """Read the endpoint configuration; ILaaS names work as a fallback."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        print("[warn] python-dotenv is not installed -- reading real environment variables only")

    base = os.environ.get("OPENAI_API_BASE") or os.environ.get("ILAAS_INFERENCE_BASE_URL") or DEFAULT_BASE
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ILAAS_API_KEY") or ""
    model = os.environ.get("MODEL_NAME") or os.environ.get("ILAAS_CHAT_MODEL") or DEFAULT_MODEL
    if "--model" in sys.argv:
        model = sys.argv[sys.argv.index("--model") + 1]
    return base.rstrip("/"), key, model


def main() -> None:
    base, key, model = config()
    print(f"endpoint : {base}")
    print(f"model    : {model}")
    print(f"key      : {'set (' + key[:4] + '...' + key[-2:] + ')' if key else 'NOT SET'}")
    print()

    if not key:
        print("[fail] No API key. Copy .env.example to .env and paste the key you were given.")
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        print("[fail] the openai package is missing -- pip install openai")
        sys.exit(1)

    client = OpenAI(base_url=base, api_key=key)

    # --- check 1: which models does the endpoint offer? ---------------------
    try:
        models = sorted(m.id for m in client.models.list().data)
    except Exception as error:  # noqa: BLE001
        print(f"[fail] GET {base}/models -> {type(error).__name__}: {error}")
        print("       Check the base URL, the key, and whether you are behind a proxy or VPN.")
        sys.exit(1)
    print(f"[ok  ] the endpoint offers {len(models)} models: {', '.join(models)}")

    if model not in models:
        print(f"[warn] your MODEL_NAME {model!r} is not in that list -- pick one of the names above")

    # --- check 2: one question, one answer ----------------------------------
    print(f"\n>>> sending: {QUESTION}")
    started = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": QUESTION}],
            temperature=0,          # deterministic: the same answer every time
            max_tokens=20,
        )
    except Exception as error:  # noqa: BLE001
        print(f"[fail] POST {base}/chat/completions -> {type(error).__name__}: {error}")
        sys.exit(1)
    answer = (response.choices[0].message.content or "").strip()
    seconds = time.time() - started
    print(f"<<< received: {answer!r}   ({seconds:.1f} s)")

    if EXPECTED in answer.lower():
        print(f"[ok  ] the answer contains {EXPECTED!r} -- the endpoint works")
    else:
        print(f"[warn] the answer does not contain {EXPECTED!r}. The endpoint answers, but check the model.")

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
        print(f"\n>>> follow-up: {messages[-1]['content']}")
        print(f"<<< received : {second!r}")
        print("[ok  ] the endpoint has no memory of its own -- the history in `messages` is what it sees")
    except Exception as error:  # noqa: BLE001
        print(f"[warn] the follow-up call failed: {type(error).__name__}: {error}")

    usage = getattr(response, "usage", None)
    if usage:
        print(f"\ntokens used by the first call: {usage.prompt_tokens} in, {usage.completion_tokens} out")
    print("\nendpoint check finished -- note the model name that worked, you need it in Iteration 2.")


if __name__ == "__main__":
    main()
