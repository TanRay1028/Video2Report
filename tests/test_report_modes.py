"""Report-mode metadata used by the directly invoking Agent."""

import json
from pathlib import Path

import pytest

from video_report_agent import cli
from video_report_agent.pipeline import create_run


@pytest.mark.parametrize("mode", ["standard", "brief"])
def test_create_run_saves_mode(tmp_path, mode):
    run = create_run(tmp_path, "BV1aTtb6uE7d", report_mode=mode)
    assert json.loads((run / "input.json").read_text(encoding="utf-8"))["report_mode"] == mode


@pytest.mark.parametrize("mode", ["auto", "", None, ["brief"]])
def test_invalid_mode_does_not_create_run(tmp_path, mode):
    with pytest.raises(ValueError, match="report_mode"):
        create_run(tmp_path, "BV1aTtb6uE7d", report_mode=mode)
    assert not list(tmp_path.iterdir())


def test_cli_prepare_passes_mode(tmp_path, monkeypatch):
    captured = []
    monkeypatch.setattr("sys.argv", [
        "video-report", "--runs", str(tmp_path), "prepare", "BV1aTtb6uE7d",
        "--report-mode", "brief",
    ])

    def prepare(run):
        metadata = json.loads((run / "input.json").read_text(encoding="utf-8"))
        captured.append(metadata["report_mode"])
        return {"state": "TRANSCRIBED"}

    monkeypatch.setattr("video_report_agent.prepare.prepare", prepare)
    assert cli.main() == 0
    assert captured == ["brief"]


def test_packaged_modes_have_separate_guides_and_templates():
    skill = Path(__file__).parents[1] / "src/video_report_agent/skills/video-report"
    assert (skill / "modes/standard.md").is_file()
    assert (skill / "modes/brief.md").is_file()
    assert (skill / "assets/report-template.html").is_file()
    assert (skill / "assets/brief-report-template.html").is_file()
