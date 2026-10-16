"""The log layer: every line this repository writes goes through here. GIVEN.

No script in this repository calls `print()`. There are two reasons, and the
second one is the one that matters in a real system.

**One place decides what output looks like.** Colour, indentation, the `[ok  ]`
markers, the 79-column frame: they are defined once, in this file, and every
script inherits them. Change the format here and twenty files change.

**Output has kinds, and the kinds are not interchangeable.** A `print()` makes
a progress note, a warning, a result and the bot's own reply look exactly the
same, and the difference is then only in the words. Here every line is written
with the role it plays -- `log.step`, `log.ok`, `log.warn`, `log.result`,
`log.say` -- so the role is in the code, visible to a reader and usable by a
machine. That is the same move the contracts make: say what a thing *is*,
not just what it looks like.

Two channels, on purpose:

    report   what the tool says to the person running it: progress, results,
             tables, the bot's replies. Always shown.
    trace    what the process did inside: the `received / doing / returns`
             block of every node (pizzabot/trace.py builds on this channel).
             Controlled by LOG_LEVEL, because it is diagnostics.

That is why `LOG_LEVEL=WARNING python compare_configs.py` still prints its
table but drops the node trace: silencing diagnostics must never silence the
answer. Both channels write to **stdout**, so redirecting `>` a file keeps the
lines in the order they were written.

Environment:

    LOG_LEVEL=INFO      the trace channel (DEBUG, INFO, WARNING, ERROR)
    NO_COLOR=1          never colour (the convention of https://no-color.org)
    FORCE_COLOR=1       colour even when stdout is not a terminal
    TRACE_WIDTH=50      how wide a value may be in the node trace

Colour is on when stdout is a terminal and NO_COLOR is unset. Piping the
output into a file or into `less` therefore gives plain text with no escape
sequences in it -- which is also why the instructor transcripts are readable.

Usage::

    from pizzabot import log

    log.title("Exercise 2 -- environment check")
    log.step("asking the model for one address")
    log.ok("import pydantic", "version 2.13.5")
    log.fail("import grandalf", "optional")
    log.hint("pip install grandalf")
    log.warn("no API key in .env -- the LLM column would be all fallbacks")
    log.plain("| a markdown row | to paste |")
    log.result("READY FOR THE SESSION")
"""

from __future__ import annotations

import logging
import os
import sys

# --------------------------------------------------------------- the colours --
# ANSI SGR codes. Eight colours and two attributes is all a terminal can be
# relied on to have; anything fancier is not worth a broken line on a beamer.
_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}

# Which role is painted how. A role is a *meaning* ("this line reports a
# failure"), never a colour ("this line is red") -- so that NO_COLOR, a
# log file and a colour-blind reader all still get the information.
_ROLES = {
    "title": ("bold",),
    "rule": ("dim",),
    "step": ("cyan",),
    "ok": ("green",),
    "fail": ("bold", "red"),
    "skip": ("yellow",),
    "warn": ("yellow",),
    "hint": ("dim",),
    "detail": ("dim",),
    "result": ("bold",),
    "user": ("cyan",),
    "bot": ("green",),
    "trace": ("dim",),
    "plain": (),
}


def colour_enabled() -> bool:
    """True when it is safe and wanted to write escape sequences to stdout."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def paint(text: str, role: str) -> str:
    """Wrap one line in the codes of its role, or return it unchanged."""
    codes = _ROLES.get(role, ())
    if not codes or not colour_enabled():
        return text
    return "".join(_CODES[c] for c in codes) + text + _CODES["reset"]


class RoleFormatter(logging.Formatter):
    """Formats a record by the ``role`` attribute attached to it."""

    def format(self, record: logging.LogRecord) -> str:
        return paint(record.getMessage(), getattr(record, "role", "plain"))


# --------------------------------------------------------------- the channels --
REPORT = logging.getLogger("pizzabot.report")   # what the tool says
TRACE = logging.getLogger("pizzabot.trace")     # what the process did

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
_configured = False


def configure() -> None:
    """Attach one stdout handler per channel. Idempotent: importing twice is fine."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(RoleFormatter())
    for channel, level in ((REPORT, logging.INFO), (TRACE, LOG_LEVEL)):
        channel.setLevel(level)
        channel.handlers = [handler]
        # Do not hand the record up to the root logger as well: a library that
        # calls basicConfig() would otherwise print every line a second time.
        channel.propagate = False
    _configured = True


configure()


def _emit(role: str, message: str = "") -> None:
    REPORT.info("%s", message, extra={"role": role})


# ---------------------------------------------------------------- the report --
def plain(message: str = "") -> None:
    """A line with no role of its own: table rows, Markdown to paste, blank lines."""
    _emit("plain", message)


def title(message: str) -> None:
    """The headline of a script or of a section of its output."""
    _emit("title", message)


def rule(message: str = "", width: int = 79, char: str = "-") -> None:
    """A separator, optionally with a caption: ``-- caption -----``."""
    if message:
        _emit("rule", f"{char * 2} {message} {char * max(0, width - len(message) - 4)}")
    else:
        _emit("rule", char * width)


def step(message: str) -> None:
    """Something is about to happen, or is happening: progress, not a result."""
    _emit("step", message)


def ok(name: str, detail: str = "") -> None:
    """A check that passed."""
    _emit("ok", f"[ok  ] {name}" + (f" -- {detail}" if detail else ""))


def fail(name: str, detail: str = "") -> None:
    """A check that failed. The caller says what to do about it with ``hint``."""
    _emit("fail", f"[fail] {name}" + (f" -- {detail}" if detail else ""))


def skip(name: str, detail: str = "") -> None:
    """A check that was not run, and that is not an error."""
    _emit("skip", f"[skip] {name}" + (f" -- {detail}" if detail else ""))


def todo(name: str, detail: str = "") -> None:
    """A check that is open on purpose -- something a later task will do."""
    _emit("skip", f"[todo] {name}" + (f" -- {detail}" if detail else ""))


def warn(message: str) -> None:
    """Something is wrong, but the program goes on."""
    _emit("warn", message)


def hint(message: str, indent: str = "       ") -> None:
    """The command or the sentence that resolves the line above it."""
    _emit("hint", f"{indent}{message}")


def detail(message: str, indent: str = "       ") -> None:
    """A continuation line: subordinate to the line before it."""
    _emit("detail", f"{indent}{message}")


def result(message: str) -> None:
    """The answer the script was run for. One per run, at the end."""
    _emit("result", message)


def say(who: str, message: str) -> None:
    """A line of the conversation itself -- the bot's output, not a log line.

    It goes through this layer too, so that there is exactly one way out of
    the process, but it keeps its own role: `you` and `bot` are the program's
    product, not its diagnostics.
    """
    _emit("user" if who == "you" else "bot", f"{who}: {message}")


def prompt(question: str) -> str:
    """Ask the person at the keyboard for a line, with the prompt in the user colour.

    The only place in the repository that writes without `logging`: a prompt
    must stay on the same line as the cursor, which a log record cannot do.
    It is still part of this layer, so the rule holds -- nothing outside
    pizzabot/log.py writes to stdout.
    """
    return input(paint(question, "user"))


def block(text: str) -> None:
    """Several lines of verbatim content (a diagram, a file, a table)."""
    for line in str(text).splitlines() or [""]:
        _emit("plain", line)
