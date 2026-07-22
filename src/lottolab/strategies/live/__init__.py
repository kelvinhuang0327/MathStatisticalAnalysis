"""Internal, unregistered legacy-live compatibility strategies.

Nothing under this package is registered in ``production_catalog`` or
``ExecutableRegistry``, reachable via CLI, HTTP, or the frontend. See
docs/migration/migration-ledger.yaml (``lottery.prediction.generate``) for
the P605C compatibility-track rationale: shared zone geometry with an
existing ONLINE strategy does not imply behavioral equivalence, and no
catalog, CLI, HTTP, frontend, or cutover claim is made for anything here.
"""

from __future__ import annotations
