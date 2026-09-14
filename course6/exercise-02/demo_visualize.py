"""Task 2 -- export the process model with the LangGraph tooling.

The compiled graph knows its own structure, so the diagram does not have to be
drawn by hand and cannot drift away from the code: it *is* the code.

    python demo_visualize.py                 # the demo graph from Iteration 1, Task 1
    python demo_visualize.py --pizza         # your pizza bot, static configuration
    python demo_visualize.py --pizza --llm   # the same process, LLM-backed configuration
    python demo_visualize.py --both          # export both and say whether they differ
    python demo_visualize.py --show-source   # print the Mermaid text as well

Three exports, three purposes:

    .mmd   Mermaid source -- plain text, so a diff in a pull request shows
           exactly which edge a commit added or removed. Commit this one.
    .png   rendered picture -- for the design review, the slide, the report.
           Rendering happens on the public server https://mermaid.ink, so it
           needs internet; if that is blocked, use the .mmd file with any
           Mermaid renderer (VS Code extension, mermaid.live, GitLab, GitHub).
    ASCII  printed to the terminal -- no network, no tooling, good enough to
           check a wiring mistake in five seconds. Needs the `grandalf` package.

Compare the exported diagram with the process you drew by hand in Task 3a/4a/5a.
Every difference is a design bug in one of the two -- find out which.

Iteration 2: `--both` exports the static and the LLM-backed configuration and
compares them. The two exports can only differ if somebody edited the wiring:
this is a guard against an added node, not a proof. The picture proves the
topology; the tests prove the contracts; Iteration 3 measures the quality.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pizzabot import log

OUT_DIR = Path("docs")


def export(graph, stem: str, quiet: bool = False) -> str:
    """Write <stem>.mmd and <stem>.png into docs/, log an ASCII view, return the Mermaid source."""
    OUT_DIR.mkdir(exist_ok=True)

    # `graph.get_graph()` returns the *drawable* representation of the compiled
    # process: nodes, edges, and which edges are conditional.
    drawable = graph.get_graph()

    mermaid_source = drawable.draw_mermaid()
    mmd_path = OUT_DIR / f"{stem}.mmd"
    mmd_path.write_text(mermaid_source, encoding="utf-8")
    lines = mermaid_source.splitlines()
    log.ok(str(mmd_path), f"{len(lines)} lines of Mermaid")
    log.hint("open the file, or add --show-source to show it here")
    if "--show-source" in sys.argv:
        log.plain()
        log.block(mermaid_source)

    try:
        png = drawable.draw_mermaid_png()          # renders via mermaid.ink
        png_path = OUT_DIR / f"{stem}.png"
        png_path.write_bytes(png)
        log.ok(str(png_path), f"{len(png)} bytes")
    except Exception as error:                     # offline, proxy, rate limit
        log.skip("PNG rendering", f"{type(error).__name__}: {error}")
        log.hint("not a problem: open the .mmd file in https://mermaid.live")
        log.hint("or the 'Markdown Preview Mermaid Support' VS Code extension")

    if quiet:
        return mermaid_source
    log.plain()
    try:
        log.block(drawable.draw_ascii())           # needs `pip install grandalf`
    except (ImportError, ModuleNotFoundError):
        log.skip("ASCII view", "needs `pip install grandalf`")
    return mermaid_source


def main() -> None:
    if "--both" in sys.argv:
        from pizzabot import config
        from pizzabot.graph import build_graph
        sources = {}
        for name in (config.STATIC, config.LLM):
            sources[name] = export(build_graph(config.implementations(name)), f"pizza-process-model-{name}", quiet=True)
        if sources[config.STATIC] == sources[config.LLM]:
            log.plain()
            log.ok("the two exported process models are IDENTICAL", "the wiring was not touched")
        else:
            log.plain()
            log.fail("the two exported process models DIFFER")
            log.hint("diff docs/pizza-process-model-static.mmd docs/pizza-process-model-llm.mmd")
        return
    if "--pizza" in sys.argv:
        from pizzabot import config
        from pizzabot.graph import build_graph     # your process (Tasks 3-5)
        export(build_graph(config.implementations(config.from_argv(sys.argv))), "pizza-process-model")
    else:
        from demo_hello_graph import build_graph   # the demo process (Task 1)
        export(build_graph(), "demo-process-model")


if __name__ == "__main__":
    main()
