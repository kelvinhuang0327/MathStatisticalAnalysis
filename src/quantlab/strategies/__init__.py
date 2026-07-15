"""Strategy catalog and executable registry.

Two deliberately separate concerns:

- :mod:`quantlab.strategies.catalog` — lifecycle metadata lookup; never
  imports adapter implementations.
- :mod:`quantlab.strategies.executable_registry` — loads adapters for
  executable (ONLINE) strategies only; never fabricates stubs for the rest.
"""
