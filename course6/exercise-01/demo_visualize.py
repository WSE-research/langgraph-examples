"""Task 2 -- export the process model with the LangGraph tooling.

The compiled graph knows its own structure, so the diagram does not have to be
drawn by hand and cannot drift away from the code: it *is* the code.

    python demo_visualize.py                 # the demo graph from Task 1
    python demo_visualize.py --pizza         # your pizza bot (Tasks 3-5)
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
"""

from __future__ import annotations

import sys
from pathlib import Path

OUT_DIR = Path("docs")


def export(graph, stem: str) -> None:
    """Write <stem>.mmd and <stem>.png into docs/, and print an ASCII view."""
    OUT_DIR.mkdir(exist_ok=True)

    # `graph.get_graph()` returns the *drawable* representation of the compiled
    # process: nodes, edges, and which edges are conditional.
    drawable = graph.get_graph()

    mermaid_source = drawable.draw_mermaid()
    mmd_path = OUT_DIR / f"{stem}.mmd"
    mmd_path.write_text(mermaid_source, encoding="utf-8")
    lines = mermaid_source.splitlines()
    print(f"[ok  ] {mmd_path}  ({len(lines)} lines of Mermaid)")
    print("       open the file, or add --show-source to print it here")
    if "--show-source" in sys.argv:
        print()
        print(mermaid_source)

    try:
        png = drawable.draw_mermaid_png()          # renders via mermaid.ink
        png_path = OUT_DIR / f"{stem}.png"
        png_path.write_bytes(png)
        print(f"[ok  ] {png_path}  ({len(png)} bytes)")
    except Exception as error:                     # offline, proxy, rate limit
        print(f"[skip] PNG rendering failed ({type(error).__name__}: {error}).")
        print("       Not a problem: open the .mmd file in https://mermaid.live")
        print("       or the 'Markdown Preview Mermaid Support' VS Code extension.")

    print()
    try:
        print(drawable.draw_ascii())               # needs `pip install grandalf`
    except (ImportError, ModuleNotFoundError):
        print("[skip] ASCII view needs `pip install grandalf`.")


def main() -> None:
    if "--pizza" in sys.argv:
        from pizzabot.graph import build_graph     # your process (Tasks 3-5)
        export(build_graph(), "pizza-process-model")
    else:
        from demo_hello_graph import build_graph   # the demo process (Task 1)
        export(build_graph(), "demo-process-model")


if __name__ == "__main__":
    main()
