"""Strategy catalog and executable registry.

Two deliberately separate concerns:

- :mod:`lottolab.strategies.catalog` — lifecycle metadata lookup; never
  imports adapter implementations.
- :mod:`lottolab.strategies.executable_registry` — loads adapters for
  executable (ONLINE) strategies only; never fabricates stubs for the rest.
"""
