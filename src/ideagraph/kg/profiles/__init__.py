"""Built-in knowledge-graph profiles.

Importing this package registers the bundled profiles (currently ``research``)
so they are available via :func:`ideagraph.kg.profile.get_profile`.
"""

from __future__ import annotations

from ideagraph.kg.profiles.research import RESEARCH

__all__ = ["RESEARCH"]
