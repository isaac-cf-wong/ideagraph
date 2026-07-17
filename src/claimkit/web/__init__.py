"""Optional web UI for exploring a claimkit provenance graph.

Requires the ``web`` extra (``pip install claimkit[web]``). The heavy import
(Flask) lives in :mod:`claimkit.web.app`, imported lazily so the core package
stays dependency-light.
"""

from __future__ import annotations

from claimkit.web.app import build_payload, create_app

__all__ = ["build_payload", "create_app"]
