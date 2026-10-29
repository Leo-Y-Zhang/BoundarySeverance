# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""The manuscript gate must reject incomplete inputs before writing output."""
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def render(tmp_path, monkeypatch):
    # These small committed result files are inputs, not a network/analysis run.
    for source in ROOT.glob("*.json"):
        (tmp_path / source.name).write_bytes(source.read_bytes())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TECTONIC", "/nonexistent/tectonic")
    monkeypatch.setenv("PAPER_DATE", "30 August 2026")

    def run(template):
        (tmp_path / "paper_template.tex").write_text(template)
        runpy.run_path(str(ROOT / "make_paper.py"))
        return (tmp_path / "paper.tex").read_text()

    return run


def test_manuscript_accepts_known_values(render):
    assert render("Count: <<max_targets>>; date: <<date>>") == "Count: 40; date: 30 August 2026"


def test_manuscript_rejects_missing_template_value(render):
    with pytest.raises(KeyError, match="not_computed"):
        render("Count: <<not_computed>>")
    assert not Path("paper.tex").exists()


def test_manuscript_rejects_malformed_placeholder(render):
    with pytest.raises(SystemExit, match="unfilled placeholders"):
        render("Count: <<missing-value>>")
    assert not Path("paper.tex").exists()


@pytest.mark.parametrize("corruption", ["missing_key", "truncated"])
def test_manuscript_rejects_corrupt_result_file(render, corruption):
    path = Path("facts.json")
    if corruption == "truncated":
        path.write_text('{"n_west_landmarks":')
        expected = json.JSONDecodeError
    else:
        facts = json.loads(path.read_text())
        del facts["n_west_landmarks"]
        path.write_text(json.dumps(facts))
        expected = KeyError
    with pytest.raises(expected):
        render("Count: <<n_west>>")
    assert not Path("paper.tex").exists()
