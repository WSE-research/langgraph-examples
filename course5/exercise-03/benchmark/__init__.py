"""The benchmark data of Iteration 3, and the app that serves it.

    from benchmark import Catalog
    catalog = Catalog()                  # loads benchmark/data/*.ttl

`Catalog` is the only thing that knows the data is RDF; everything above it
sees methods. `benchmark.server` serves the same graph over HTTP when a test
environment wants a real endpoint instead of an in-process graph.
"""

from benchmark.catalog import Catalog, PZ, TG

__all__ = ["Catalog", "PZ", "TG"]
