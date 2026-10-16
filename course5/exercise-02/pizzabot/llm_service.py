"""The LLM behind one small component -- the only door to the model. GIVEN.

Every call to the language model in this process goes through this file, the
way every HTTP call to the Pizza API goes through `pizzabot/pizza_api.py`. The
reason is the same: the process must not know *which* provider or model answers,
only what the call promises. That promise is the contract of this module:

    name        llm_service (a service adapter, not a node)
    input       a system prompt and one user message, both plain text
    output      a dict parsed from the model's JSON answer -- or None
    rules       1. one call per extract(), at temperature 0, with a token limit
                   and a timeout; the model is asked for a JSON object
                2. transient faults -- a timeout, an HTTP 5xx, an error body
                   inside an HTTP 200 -- are retried up to RETRIES times, with a
                   growing pause in between. Faults that cannot change are NOT
                   retried: a 4xx (unknown model, bad key) and an answer that
                   was cut off at max_tokens. Nothing with a side effect is
                   ever retried (POST /order is not this module's business).
                3. the answer is parsed on our side: a code fence around the
                   JSON is removed first, because "JSON mode" is a request, not
                   a guarantee (measured on ILaaS 2026-09-12: the default model
                   fences about every second answer)
    guarantee   extract() returns a dict or None and never raises; a dict is
                whatever the model said -- SCHEMA-VALID IS NOT CHECKED HERE,
                that is the component's job (Tasks 2 and 3)
    failure     None -- "the service could not answer"; the caller decides
                what that means (fallback to the static rule)

Why a fault that cannot change is not retried, and why nothing with a side
effect ever is: RFC 9110 section 9.2.2 (idempotent methods); Nygard, "Release
It!" (2018), ch. 5; Brooker, "Exponential backoff and jitter" (2015). Why the
boundary is strict about what it accepts from the model: RFC 9413 -- the
reverse of Postel's law for a producer that may be wrong.

Configuration -- `.env`, see `.env.example` (the names used by the course's
`ilaas-connector` package, ILAAS_*, are accepted as well)::

    OPENAI_API_BASE=https://llm.ilaas.fr/v1     # the ILaaS inference service
    OPENAI_API_KEY=<the key you were given>
    MODEL_NAME=mistral-small-4-119b             # pinned; re-measure when you change it
    LLM_TIMEOUT=20                              # seconds per attempt
    LLM_RETRIES=2                               # extra attempts after the first

Run it on its own (Task 1)::

    python -m pizzabot.llm_service
    python -m pizzabot.llm_service "Answer with JSON {\"city\": <city>}" "I live in Lyon"
    python -m pizzabot.llm_service --model no-such-model          # 404: the defined failure, no retry
    python -m pizzabot.llm_service --max-tokens 5                 # cut off: the defined failure, no retry

Everything the service does is logged in the node trace under the label `llm`,
including the numbers you will need to document the step: latency, tokens in,
tokens out, and whether the answer had to be unfenced.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from pizzabot import log, trace

# The HTTP client logs every request at INFO; inside the node trace that is noise.
for _name in ("httpx", "httpx2", "httpcore", "openai"):
    logging.getLogger(_name).setLevel(logging.WARNING)

DEFAULT_BASE = "https://llm.ilaas.fr/v1"
DEFAULT_MODEL = "mistral-small-4-119b"

# ```json ... ``` around the answer: some models add it even when asked for JSON.
FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")

PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


def load_prompt(name: str) -> str:
    """Read prompts/<name>.txt -- a prompt is configuration, versioned by its file name.

    Lines starting with `#` are comments for the reader and are not sent.
    """
    path = os.path.join(PROMPT_DIR, f"{name}.txt")
    with open(path, encoding="utf-8") as handle:
        lines = [line for line in handle.read().splitlines() if not line.startswith("#")]
    return "\n".join(lines).strip()


def configured() -> bool:
    """Is a key set? Without one the LLM configuration is not available.

    The template value from .env.example (`<the key ...>`) does not count.
    """
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ILAAS_API_KEY") or ""
    return bool(key.strip()) and not key.strip().startswith("<")


def parse_json(text: Optional[str]) -> Any:
    """Parse the model's answer; strips a code fence first. Raises ValueError."""
    if not text:
        raise ValueError("empty answer")
    cleaned = FENCE.sub("", text)
    return json.loads(cleaned)


@dataclass
class Usage:
    """What the service cost so far -- the data Iteration 3 computes a metric from.

    `attempts` counts every request sent, `answers` every reply that arrived,
    `failures` every extract() that ended in None. Latencies are recorded per
    attempt, timeouts included, so the median is not flattered.
    """

    attempts: int = 0
    answers: int = 0
    failures: int = 0
    fenced: int = 0              # answers that arrived inside code fences
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latencies: list[float] = field(default_factory=list)

    @property
    def calls(self) -> int:
        """Number of extract() calls (answers plus failures)."""
        return self.answers + self.failures

    def per_call(self) -> tuple[int, int]:
        """Average tokens in and out per answered call, for the service card."""
        if not self.answers:
            return 0, 0
        return round(self.prompt_tokens / self.answers), round(self.completion_tokens / self.answers)

    def summary(self) -> str:
        if not self.attempts:
            return "no LLM calls made"
        noun = "call" if self.calls == 1 else "calls"
        text = (f"{self.calls} {noun} ({self.attempts} attempts), {self.failures} ended in None, "
                f"{self.fenced} fenced; {self.prompt_tokens} tokens in, {self.completion_tokens} out")
        if self.latencies:
            median = sorted(self.latencies)[len(self.latencies) // 2]
            text += f"; latency median {median:.2f} s, max {max(self.latencies):.2f} s"
        return text


class LlmService:
    """Our contract around a remote model: text in, dict or None out."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        *,
        temperature: float = 0.0,
        max_tokens: int = 200,
        timeout: float | None = None,
        retries: int | None = None,
    ) -> None:
        env = os.environ
        self.base_url = (base_url or env.get("OPENAI_API_BASE")
                         or env.get("ILAAS_INFERENCE_BASE_URL") or DEFAULT_BASE).rstrip("/")
        self.api_key = api_key or env.get("OPENAI_API_KEY") or env.get("ILAAS_API_KEY") or ""
        self.model = model or env.get("MODEL_NAME") or env.get("ILAAS_CHAT_MODEL") or DEFAULT_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = float(env.get("LLM_TIMEOUT", "20")) if timeout is None else timeout
        self.retries = int(env.get("LLM_RETRIES", "2")) if retries is None else retries
        self.usage = Usage()
        self._client = None                     # created on first use

    # -- the one public method ------------------------------------------------
    def extract(self, system: str, user: str) -> dict | None:
        """Ask for a JSON object. None means: the service could not answer."""
        if not self.api_key or self.api_key.strip().startswith("<"):
            trace.service("no API key configured -> None (see .env.example)")
            self.usage.attempts += 1
            self.usage.failures += 1
            return None
        client = self._get_client()
        # `system` carries the instructions (the prompt file), `user` the utterance.
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        for attempt in range(1, self.retries + 2):
            started = time.time()
            self.usage.attempts += 1
            try:
                reply = client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,           # 0 = greedy decoding: stable, not guaranteed
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"},  # "JSON mode": a request for JSON
                    messages=messages,
                    timeout=self.timeout,
                )
                seconds = time.time() - started
                self.usage.latencies.append(seconds)
                if getattr(reply, "object", "") == "error":     # HTTP 200 with an error body
                    trace.service(f"attempt {attempt}: the gateway answered 200 with an error body -> retry")
                    self._pause(attempt)
                    continue
                choice = reply.choices[0]                       # we asked for one answer
                content = choice.message.content or ""
                fenced = content.lstrip().startswith("```")
                self.usage.answers += 1
                self.usage.fenced += 1 if fenced else 0
                if reply.usage:
                    self.usage.prompt_tokens += reply.usage.prompt_tokens or 0
                    self.usage.completion_tokens += reply.usage.completion_tokens or 0
                # finish_reason: "stop" = the model finished; "length" = cut off at max_tokens
                cut_off = choice.finish_reason == "length"
                trace.service(f"attempt {attempt}: {seconds:.2f} s, "
                              f"{reply.usage.prompt_tokens if reply.usage else '?'} tokens in, "
                              f"{reply.usage.completion_tokens if reply.usage else '?'} out"
                              + (", answer was fenced" if fenced else "")
                              + (", cut off at max_tokens" if cut_off else ""))
                value = parse_json(content)
                if not isinstance(value, dict):
                    trace.service(f"attempt {attempt}: JSON, but not an object ({type(value).__name__}) -> retry")
                    self._pause(attempt)
                    continue
                trace.service(f"answer: {json.dumps(value, ensure_ascii=False)[:70]}")
                return value
            except ValueError as error:                         # not JSON
                if "cut_off" in locals() and cut_off:
                    trace.service(f"attempt {attempt}: cut off at max_tokens={self.max_tokens}, "
                                  f"not JSON -> no retry, that cannot change")
                    break
                trace.service(f"attempt {attempt}: answer is not JSON ({error}) -> retry")
                self._pause(attempt)
            except Exception as error:  # noqa: BLE001 -- timeout, 4xx/5xx, network
                self.usage.latencies.append(time.time() - started)
                status = getattr(error, "status_code", None)
                if status is not None and 400 <= status < 500:
                    trace.service(f"attempt {attempt}: HTTP {status} {type(error).__name__} -> no retry, that cannot change")
                    break
                trace.service(f"attempt {attempt}: {type(error).__name__}: {str(error)[:80]} -> retry")
                self._pause(attempt)
        self.usage.failures += 1
        trace.service("gave up -> None (the caller falls back)")
        return None                                             # the defined failure

    # -- what a colleague needs to know to maintain the step ------------------
    def describe(self) -> dict[str, Any]:
        """The service card: everything about this step that is configuration.

        A model card for one processing step (Mitchell et al., "Model cards for
        model reporting", FAT* 2019); `compare_configs.py` prints it at the end
        of its run.
        """
        return {
            "provider": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout_s": self.timeout,
            "retries": self.retries,
            "response_format": "json_object (fences stripped on our side)",
        }

    def card_lines(self) -> str:
        """The description as four labelled lines, for the terminal."""
        return (f"provider  {self.base_url}\n"
                f"          model     {self.model}\n"
                f"          settings  temperature {self.temperature}, max_tokens {self.max_tokens}, "
                f"timeout {self.timeout:g} s, retries {self.retries}\n"
                f"          format    json_object (fences stripped on our side)")

    # -- internals ------------------------------------------------------------
    def _pause(self, attempt: int) -> None:
        """A growing pause before the next attempt -- the quota is shared by the room."""
        if attempt <= self.retries:
            time.sleep(0.5 * attempt)

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI      # imported here so the static configuration never needs it

            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            # The client library logs every request at INFO ("HTTP Request: POST ...");
            # its loggers exist only from here on, so silence them again now.
            for name in ("httpx", "httpx2", "httpcore", "openai", "openai._base_client"):
                logging.getLogger(name).setLevel(logging.WARNING)
        return self._client


# One shared instance per process, created on first use, so that every
# LLM-backed component talks to the same configured service and the usage
# numbers add up in one place.
_SERVICE: LlmService | None = None


def service() -> LlmService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = LlmService()
    return _SERVICE


def extract(system: str, user: str) -> dict | None:
    """Module-level shortcut used by the components: llm_service.extract(...)."""
    return service().extract(system, user)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    model = None
    max_tokens = 200
    if "--model" in args:
        model = args[args.index("--model") + 1]
        del args[args.index("--model"):args.index("--model") + 2]
    if "--max-tokens" in args:
        max_tokens = int(args[args.index("--max-tokens") + 1])
        del args[args.index("--max-tokens"):args.index("--max-tokens") + 2]
    system_prompt = args[0] if len(args) > 0 else (
        "Extract the delivery address from the message. Answer with JSON keys "
        "street, house_number, city. If a part is missing, answer {}.")
    user_text = args[1] if len(args) > 1 else "can I order the four-cheese one to number 5 in the Rue Michelet here in Saint-Étienne?"

    svc = LlmService(model=model, max_tokens=max_tokens)
    log.plain(f"service : {svc.card_lines()}")
    log.plain(f"system  : {system_prompt}")
    log.plain(f"user    : {user_text}")
    log.plain()
    result = svc.extract(system_prompt, user_text)
    log.plain()
    if result is None:
        log.warn("result  : None  <- the defined failure; a component would now fall back")
    else:
        log.result(f"result  : {result}")
    log.detail(f"usage   : {svc.usage.summary()}", indent="")
