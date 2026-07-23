"""Tests for generic ``add-node`` / ``add-edge`` authoring and profile recording."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.kg.persistence import load_graph

runner = CliRunner()


def _init(tmp_path, *, profile: str | None = None):
    """Initialise a graph, optionally recording a profile.

    Args:
        tmp_path: Pytest temporary directory fixture.
        profile: Profile name to record, or None.

    Returns:
        The graph file path.

    """
    path = tmp_path / "g.json"
    args = ["init", str(path), "--article-id", "a"]
    if profile is not None:
        args += ["--profile", profile]
    assert runner.invoke(app, args).exit_code == 0
    return path


def test_init_records_profile(tmp_path):
    """`init --profile` stores the profile in graph metadata."""
    path = _init(tmp_path, profile="article")
    assert load_graph(path).metadata["profile"] == "article"


def test_init_rejects_unknown_profile(tmp_path):
    """An unknown profile name fails init."""
    result = runner.invoke(app, ["init", str(tmp_path / "g.json"), "--profile", "nope"])
    assert result.exit_code == 1
    assert "Unknown profile" in result.stderr


def test_add_node_of_profile_type(tmp_path):
    """add-node creates a node of an article-profile type with properties."""
    path = _init(tmp_path, profile="article")
    result = runner.invoke(
        app,
        ["add-node", str(path), "--type", "summary_point", "--text", "s", "--id", "sp1", "--prop-json", "order=0"],
    )
    assert result.exit_code == 0
    node = load_graph(path).nodes["sp1"]
    assert node.type == "summary_point"
    assert node.properties["order"] == 0


def test_add_node_rejects_unknown_type(tmp_path):
    """A type outside the active profile is rejected with the allowed list."""
    path = _init(tmp_path, profile="article")
    result = runner.invoke(app, ["add-node", str(path), "--type", "bogus", "--text", "x"])
    assert result.exit_code == 1
    assert "Unknown node type" in result.stderr


def test_add_node_requires_profile_properties(tmp_path):
    """Required properties (evidence needs kind+reference) are enforced."""
    path = _init(tmp_path)  # research profile by default
    result = runner.invoke(app, ["add-node", str(path), "--type", "evidence", "--id", "e"])
    assert result.exit_code == 1
    assert "requires properties" in result.stderr


def test_add_edge_validates_endpoints(tmp_path):
    """add-edge enforces the profile's endpoint-type rule."""
    path = _init(tmp_path, profile="article")
    runner.invoke(app, ["add-node", str(path), "--type", "article", "--id", "art"])
    runner.invoke(app, ["add-node", str(path), "--type", "quantity", "--id", "q"])
    ok = runner.invoke(app, ["add-node", str(path), "--type", "summary_point", "--id", "sp"])
    assert ok.exit_code == 0
    good = runner.invoke(app, ["add-edge", str(path), "art", "sp", "--type", "contains"])
    assert good.exit_code == 0
    bad = runner.invoke(app, ["add-edge", str(path), "art", "q", "--type", "contains"])
    assert bad.exit_code == 1
    assert "target may not be" in bad.stderr


def test_add_edge_missing_source(tmp_path):
    """A missing source node is rejected."""
    path = _init(tmp_path, profile="article")
    runner.invoke(app, ["add-node", str(path), "--type", "summary_point", "--id", "sp"])
    result = runner.invoke(app, ["add-edge", str(path), "ghost", "sp", "--type", "summarizes"])
    assert result.exit_code == 1
    assert "No such source node" in result.stderr


def test_add_edge_cross_article_target(tmp_path):
    """A cross-article global-id target is accepted without local resolution."""
    path = _init(tmp_path, profile="article")
    runner.invoke(app, ["add-node", str(path), "--type", "claim", "--id", "c", "--prop", "status=valid"])
    result = runner.invoke(app, ["add-edge", str(path), "c", "other#n", "--type", "cites"])
    assert result.exit_code == 0


def test_doctor_uses_recorded_profile(tmp_path):
    """Doctor validates against the recorded profile without --profile."""
    path = _init(tmp_path, profile="project")
    runner.invoke(app, ["add-node", str(path), "--type", "question", "--id", "q0", "--text", "why?"])
    result = runner.invoke(app, ["doctor", str(path)])
    assert result.exit_code == 0
    assert "No problems found" in result.stdout
