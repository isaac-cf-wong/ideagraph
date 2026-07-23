"""Compatibility shim: ``claimkit`` was renamed to :mod:`ideagraph`.

This distribution exists only to keep old installs working. Installing
``claimkit`` pulls in ``ideagraph``; importing ``claimkit`` (or any
``claimkit.*`` submodule) transparently returns the matching ``ideagraph``
module and emits a :class:`DeprecationWarning` once. Migrate to ``ideagraph``:
this shim will not be updated.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType

_OLD = "claimkit"
_NEW = "ideagraph"

#: Version of this compatibility shim (independent of the ideagraph it wraps).
__version__ = "2.0.0"

warnings.warn(
    "The 'claimkit' package has been renamed to 'ideagraph'. This 'claimkit' "
    "distribution is a compatibility shim that re-exports the installed "
    "'ideagraph'; please `pip install ideagraph` and import 'ideagraph' instead.",
    DeprecationWarning,
    stacklevel=2,
)


class _AliasLoader(importlib.abc.Loader):
    """Load a ``claimkit[.x]`` name by returning the matching ``ideagraph`` module."""

    def __init__(self, target: str) -> None:
        self._target = target

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        """Return the target ``ideagraph`` module for a ``claimkit`` spec.

        Args:
            spec: The import spec for the ``claimkit`` name.

        Returns:
            The already-imported ``ideagraph`` module.
        """
        module = importlib.import_module(self._target)
        sys.modules[spec.name] = module
        return module

    def exec_module(self, module: ModuleType) -> None:
        """No-op: the aliased module is already fully initialised."""


class _AliasFinder(importlib.abc.MetaPathFinder):
    """Redirect ``claimkit`` and ``claimkit.*`` imports to ``ideagraph``."""

    def find_spec(
        self,
        name: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        """Return a spec redirecting a ``claimkit`` name to ``ideagraph``.

        Args:
            name: The fully-qualified module name being imported.
            path: Unused (parent ``__path__`` for submodule imports).
            target: Unused (module being reloaded, if any).

        Returns:
            A spec whose loader returns the matching ``ideagraph`` module, or
            None if ``name`` is not a ``claimkit`` name.
        """
        if name != _OLD and not name.startswith(_OLD + "."):
            return None
        target_name = _NEW + name[len(_OLD) :]
        return importlib.util.spec_from_loader(name, _AliasLoader(target_name))


# Install the finder and re-export the top-level ideagraph API onto this module.
if not any(isinstance(f, _AliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

_ideagraph = importlib.import_module(_NEW)
for _name in getattr(_ideagraph, "__all__", []):
    globals()[_name] = getattr(_ideagraph, _name)
