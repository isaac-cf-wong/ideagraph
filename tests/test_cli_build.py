"""Tests for the ``ideagraph init`` and ``ideagraph add-claim`` commands."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.kg.persistence import load_graph

runner = CliRunner()


def test_init_creates_empty_graph(tmp_path):
    """Init writes a loadable empty graph file.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    result = runner.invoke(app, ["init", str(path)])
    assert result.exit_code == 0
    assert path.exists()
    assert load_graph(path).nodes == {}


def test_init_refuses_overwrite(tmp_path):
    """Init refuses to clobber an existing file without --force.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    path.write_text("sentinel", encoding="utf-8")
    result = runner.invoke(app, ["init", str(path)])
    assert result.exit_code == 1
    assert "Refusing to overwrite" in result.stderr
    assert path.read_text(encoding="utf-8") == "sentinel"


def test_init_force_overwrites(tmp_path):
    """Init --force overwrites an existing file.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    path.write_text("sentinel", encoding="utf-8")
    result = runner.invoke(app, ["init", str(path), "--force"])
    assert result.exit_code == 0
    assert load_graph(path).nodes == {}


def test_add_claim_prints_generated_id(tmp_path):
    """add-claim stores the claim and prints its generated id.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    runner.invoke(app, ["init", str(path)])
    result = runner.invoke(app, ["add-claim", str(path), "Water boils at 100C."])
    assert result.exit_code == 0
    claim_id = result.stdout.strip()
    assert len(claim_id) == 32
    graph = load_graph(path)
    assert graph.nodes[claim_id].text == "Water boils at 100C."


def test_add_claim_with_id_and_tags(tmp_path):
    """add-claim honours an explicit id and repeated tags.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    runner.invoke(app, ["init", str(path)])
    result = runner.invoke(
        app,
        ["add-claim", str(path), "A", "--id", "c1", "--tag", "phys", "--tag", "thermo"],
    )
    assert result.exit_code == 0
    assert result.stdout.strip() == "c1"
    node = load_graph(path).nodes["c1"]
    assert node.tags == ["phys", "thermo"]


def test_add_claim_duplicate_id_rejected(tmp_path):
    """add-claim refuses to reuse an existing claim id.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    runner.invoke(app, ["init", str(path)])
    runner.invoke(app, ["add-claim", str(path), "A", "--id", "c1"])
    result = runner.invoke(app, ["add-claim", str(path), "B", "--id", "c1"])
    assert result.exit_code == 1
    assert "already exists" in result.stderr
    # The original claim is untouched.
    assert load_graph(path).nodes["c1"].text == "A"


def test_add_claim_missing_file(tmp_path):
    """add-claim on a missing file exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(app, ["add-claim", str(tmp_path / "nope.json"), "A"])
    assert result.exit_code == 1
    assert "No such file" in result.stderr


def test_add_claim_persists_across_calls(tmp_path):
    """Multiple add-claim calls accumulate in the file.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    runner.invoke(app, ["init", str(path)])
    runner.invoke(app, ["add-claim", str(path), "A", "--id", "c1"])
    runner.invoke(app, ["add-claim", str(path), "B", "--id", "c2"])
    assert set(load_graph(path).nodes) == {"c1", "c2"}
