"""The built-in ``project`` profile: tracking a research project as a graph.

Extends the ``article`` profile with the two node types a project graph needs
beyond representing literature — a ``question`` it sets out to answer and the
``hypothesis`` nodes proposed against it — plus the edges that wire the
question -> hypothesis -> test -> answer loop:

* ``hypothesis -addresses-> question``
* ``activity  -tests----> hypothesis``
* ``result|finding -answers-> question``

Discourse and support edges are widened again so questions and hypotheses can
participate (a hypothesis ``supported_by`` evidence, a hypothesis
``depends_on`` a claim, and so on).
"""

from __future__ import annotations

from ideagraph.kg.profile import EdgeRule, NodeRule, Profile, register_profile
from ideagraph.kg.profiles.article import ARTICLE, DETAIL_TYPES, _widen

#: The research question a project sets out to answer.
QUESTION = "question"
#: A proposed answer to be tested.
HYPOTHESIS = "hypothesis"

#: Node types added by this profile on top of ``article``.
PROJECT_NODE_TYPES = (QUESTION, HYPOTHESIS)

#: Detail types (article details plus question / hypothesis) for edge rules.
PROJECT_DETAIL_TYPES = DETAIL_TYPES | {QUESTION, HYPOTHESIS}


def _build_profile() -> Profile:
    """Construct the project profile.

    Returns:
        The project profile.

    """
    node_types = dict(ARTICLE.node_types)
    for node_type in PROJECT_NODE_TYPES:
        node_types[node_type] = NodeRule(node_type)

    edge_types = dict(ARTICLE.edge_types)
    edge_types["addresses"] = EdgeRule(
        "addresses", source_types=frozenset({HYPOTHESIS}), target_types=frozenset({QUESTION})
    )
    edge_types["answers"] = EdgeRule(
        "answers", source_types=frozenset({"result", "finding"}), target_types=frozenset({QUESTION})
    )
    edge_types["tests"] = EdgeRule("tests", source_types=frozenset({"activity"}), target_types=frozenset({HYPOTHESIS}))
    _widen(edge_types, PROJECT_DETAIL_TYPES)
    return Profile(name="project", node_types=node_types, edge_types=edge_types)


PROJECT = register_profile(_build_profile())
