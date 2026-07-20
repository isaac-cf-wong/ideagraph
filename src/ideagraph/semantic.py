"""Pluggable embeddings for semantic search over the library.

Lexical search (FTS) is always available; *semantic* search — finding ideas by
meaning rather than wording, the basis of cross-article gap discovery — is an
opt-in layer. It is deliberately pluggable: any object with an ``embed`` method
and a ``name`` can drive it, so a project can point at whatever model it already
runs (a local server, an API) without ideagraph bundling a heavy dependency.

The bundled default, :class:`SentenceTransformerEmbedder`, needs the
``[semantic]`` extra (``pip install ideagraph[semantic]``) and runs a small
sentence-transformer locally, offline, on CPU. Vectors are stored normalised in
the library index, so cosine similarity is a dot product; the store math is pure
Python, keeping the base package dependency-free and the logic testable with a
fake embedder.
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from ideagraph.core.staleness import compute_digest

#: The default sentence-transformer model — small, offline, CPU-friendly.
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@runtime_checkable
class Embedder(Protocol):
    """Anything that can turn texts into vectors.

    Attributes:
        name: A stable identifier for the model (stored alongside vectors so a
            change of model invalidates them).
    """

    name: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""
        ...


def normalize(vector: list[float]) -> list[float]:
    """Return the L2-normalised vector (unchanged direction, unit length).

    Args:
        vector: The vector to normalise.

    Returns:
        The unit vector, or the input unchanged if its norm is zero.
    """
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return list(vector)
    return [x / norm for x in vector]


def cosine(a: list[float], b: list[float]) -> float:
    """Return the cosine similarity of two vectors.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        The cosine similarity in [-1, 1] (0 if either is empty or zero-norm).
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def text_hash(text: str) -> str:
    """Return a stable digest of statement text, for embedding-staleness checks.

    Args:
        text: The statement text.

    Returns:
        A ``sha256:``-prefixed digest.
    """
    return compute_digest(text.encode("utf-8"))


class SentenceTransformerEmbedder:
    """The bundled default embedder, backed by ``sentence-transformers``.

    The model is loaded lazily on first use, so importing this class is cheap and
    does not require the ``[semantic]`` extra until an embedding is actually
    requested.
    """

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        """Create an embedder for a named sentence-transformer model.

        Args:
            model: The model name to load.
        """
        self.name = model
        self._model = None

    def _load(self):  # type: ignore[no-untyped-def]
        """Load (and cache) the underlying model, or raise a helpful error."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer  # noqa: PLC0415 - optional [semantic] dep
            except ModuleNotFoundError as exc:
                raise ModuleNotFoundError(
                    "semantic search needs the optional dependency; install it with "
                    "`pip install ideagraph[semantic]` or pass a custom embedder"
                ) from exc
            self._model = SentenceTransformer(self.name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts with the loaded model, returning normalised vectors.

        Args:
            texts: The texts to embed.

        Returns:
            One unit vector per input text.
        """
        model = self._load()
        vectors = model.encode(list(texts), normalize_embeddings=True)
        return [[float(x) for x in v] for v in vectors]
