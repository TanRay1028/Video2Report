import json
import re
from pathlib import Path


def test_synthetic_smoke_cases_have_source_anchors():
    root = Path(__file__).parents[1] / "evals/report-review"
    cases = json.loads((root / "manifest.json").read_text())["cases"]
    assert len(cases) == 3
    for case in cases:
        material = root / case["material"]
        ids = set(re.findall(r"^\[([^ |]+) \|", (material / "transcript.md").read_text(), re.M))
        assert ids
        for check in case["review_checks"]:
            assert set(check["source_ids"]) <= ids
        metadata = json.loads((material / "input.json").read_text())
        assert set(metadata) <= {"title", "url", "video_id", "uploader", "attribution"}
