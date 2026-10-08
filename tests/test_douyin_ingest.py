import json

import pytest

from video_report_agent import pipeline
from video_report_agent.ingest import (
    UrlIngestError,
    validate_douyin_url,
    validate_source_url,
)

DOUYIN_MODAL_URL = "https://www.douyin.com/jingxuan?modal_id=7688660484593532378"
DOUYIN_VIDEO_URL = "https://www.douyin.com/video/7688660484593532378"
DOUYIN_SHORT_URL = "https://v.douyin.com/abc123/"


def test_douyin_jingxuan_modal_id_is_validated():
    source = validate_douyin_url(DOUYIN_MODAL_URL)
    assert source.platform == "抖音"
    assert source.item_id == "7688660484593532378"
    assert source.video_id == "douyin-7688660484593532378"
    assert source.cache_key == "7688660484593532378"
    assert source.canonical_url == DOUYIN_VIDEO_URL
    assert source.submitted_url == DOUYIN_MODAL_URL


def test_douyin_video_path_is_validated():
    source = validate_douyin_url(DOUYIN_VIDEO_URL + "/")
    assert source.item_id == "7688660484593532378"
    assert source.canonical_url == DOUYIN_VIDEO_URL


def test_douyin_share_text_and_markdown_are_supported():
    shared = "【标题】来抖音看我作品 https://www.douyin.com/video/7688660484593532378"
    assert validate_douyin_url(shared).item_id == "7688660484593532378"
    markdown = "[视频](https://www.douyin.com/jingxuan?modal_id=7688660484593532378)"
    assert validate_douyin_url(markdown).item_id == "7688660484593532378"


def test_douyin_short_link_resolves_to_canonical_video(monkeypatch):
    class Response:
        url = DOUYIN_VIDEO_URL + "?previous_page=web_code_link"

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr("video_report_agent.ingest.httpx.get", lambda *a, **k: Response())
    source = validate_douyin_url("2.07 share text " + DOUYIN_SHORT_URL + " copy")
    assert source.item_id == "7688660484593532378"
    assert source.canonical_url == DOUYIN_VIDEO_URL
    assert source.submitted_url.endswith("copy")


@pytest.mark.parametrize(
    "value",
    [
        "http://www.douyin.com/video/7688660484593532378",
        "https://www.douyin.com/video/7688660484593532378#frag",
        "https://www.douyin.com/video/abc",
        "https://www.douyin.com/jingxuan",
        "https://www.douyin.com/jingxuan?modal_id=123&modal_id=456",
        "https://www.example.com/video/7688660484593532378",
        "not a url",
    ],
)
def test_douyin_invalid_urls_are_rejected(value):
    with pytest.raises(UrlIngestError):
        validate_douyin_url(value)


def test_validate_source_url_dispatches_by_host():
    bilibili = validate_source_url("https://www.bilibili.com/video/BV1oFaZ6gEtm/")
    assert bilibili.video_id == "bilibili-BV1oFaZ6gEtm-p1"
    douyin = validate_source_url(DOUYIN_MODAL_URL)
    assert douyin.video_id == "douyin-7688660484593532378"
    with pytest.raises(UrlIngestError):
        validate_source_url("https://www.example.com/watch?v=1")


def test_create_run_accepts_douyin_url(tmp_path):
    run = pipeline.create_run(tmp_path, DOUYIN_MODAL_URL)
    metadata = json.loads((run / "input.json").read_text(encoding="utf-8"))
    assert metadata["video_id"] == "douyin-7688660484593532378"
    assert metadata["url"] == DOUYIN_VIDEO_URL


def test_cookies_from_browser_is_threaded_into_download_command(tmp_path):
    from types import SimpleNamespace

    from video_report_agent import ingest

    captured = {}

    def fake_runner(command, **kwargs):
        captured["command"] = command
        download_dir = tmp_path / "run" / "download"
        (download_dir / "source.m4a").write_bytes(b"media")
        (download_dir / "source.info.json").write_text(
            json.dumps({"duration": 60, "title": "T", "uploader": "U"}), encoding="utf-8"
        )
        return SimpleNamespace(
            returncode=0, stdout=str(download_dir / "source.m4a"), stderr=""
        )

    run = tmp_path / "run"
    (run / "download").mkdir(parents=True)
    source = validate_douyin_url(DOUYIN_VIDEO_URL)
    ingest.download_bilibili_video(
        source,
        run,
        runner=fake_runner,
        audio_only=True,
        cookies_from_browser="chrome",
    )
    command = captured["command"]
    assert "--cookies-from-browser" in command
    assert command[command.index("--cookies-from-browser") + 1] == "chrome"
    assert command[-1] == DOUYIN_VIDEO_URL


def test_cookies_file_is_threaded_into_download_command(tmp_path):
    from types import SimpleNamespace

    from video_report_agent import ingest

    captured = {}

    def fake_runner(command, **kwargs):
        captured["command"] = command
        download_dir = tmp_path / "run" / "download"
        (download_dir / "source.m4a").write_bytes(b"media")
        (download_dir / "source.info.json").write_text(
            json.dumps({"duration": 60, "title": "T", "uploader": "U"}), encoding="utf-8"
        )
        return SimpleNamespace(
            returncode=0, stdout=str(download_dir / "source.m4a"), stderr=""
        )

    run = tmp_path / "run"
    (run / "download").mkdir(parents=True)
    source = validate_douyin_url(DOUYIN_VIDEO_URL)
    ingest.download_bilibili_video(
        source, run, runner=fake_runner, audio_only=True, cookies_file="cookies.txt"
    )
    command = captured["command"]
    assert "--cookies" in command
    assert command[command.index("--cookies") + 1] == "cookies.txt"
