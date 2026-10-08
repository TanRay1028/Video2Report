import json
from types import SimpleNamespace

import pytest

from video_report_agent import douyin_download
from video_report_agent.ingest import UrlIngestError, validate_douyin_url

DOUYIN_VIDEO_URL = "https://www.douyin.com/video/7688660484593532378"
PAGE_BODY = (
    '{"video":{"play_addr":{"uri":"abc123def456"}},"desc":"测试作品标题",'
    '"author":{"nickname":"测试作者"},"statistics":{}}'
)


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_bytes(self, chunk_size=8192):
        yield from self._chunks


def _patch_httpx(
    monkeypatch, page_body=PAGE_BODY, video_chunks=(b"fake-video-data",), seen=None
):
    monkeypatch.setattr(
        douyin_download.httpx, "get",
        lambda *a, **k: SimpleNamespace(
            raise_for_status=lambda: None, text=page_body
        ),
    )
    def stream(method, url, *args, **kwargs):
        if seen is not None:
            seen["video_url"] = url
        return _FakeStream(video_chunks)

    monkeypatch.setattr(douyin_download.httpx, "stream", stream)


def test_download_douyin_video_writes_media_and_metadata(tmp_path, monkeypatch):
    seen = {}
    _patch_httpx(monkeypatch, seen=seen)
    monkeypatch.setattr(douyin_download, "_duration_seconds", lambda path: 65.0)
    source = validate_douyin_url(DOUYIN_VIDEO_URL)
    result = douyin_download.download_douyin_video(source, tmp_path)
    assert result.media_path.is_file()
    assert result.media_path.read_bytes() == b"fake-video-data"
    info = json.loads(result.info_path.read_text(encoding="utf-8"))
    assert info["title"] == "测试作品标题"
    assert info["uploader"] == "测试作者"
    assert info["duration"] == 65.0
    assert result.title == "测试作品标题"
    assert result.uploader == "测试作者"
    assert result.attribution.startswith("抖音；测试作者；《测试作品标题》；")
    assert "ratio=360p" in seen["video_url"]


def test_download_douyin_video_falls_back_when_fields_missing(tmp_path, monkeypatch):
    _patch_httpx(monkeypatch, page_body='{"video":{"play_addr":{"uri":"x1"}}}')
    monkeypatch.setattr(douyin_download, "_duration_seconds", lambda path: 30.0)
    source = validate_douyin_url(DOUYIN_VIDEO_URL)
    result = douyin_download.download_douyin_video(source, tmp_path)
    assert result.title == "抖音作品 7688660484593532378"
    assert result.uploader == "抖音作者"


def test_page_text_falls_back_to_browser_on_js_challenge(monkeypatch):
    monkeypatch.setattr(
        douyin_download.httpx, "get",
        lambda *a, **k: SimpleNamespace(
            raise_for_status=lambda: None, text="<html>js-challenge-shell</html>"
        ),
    )
    seen = {}

    def fake_browser(url):
        seen["url"] = url
        return PAGE_BODY

    monkeypatch.setattr(douyin_download, "_browser_page_text", fake_browser)
    assert douyin_download._page_text(DOUYIN_VIDEO_URL) == PAGE_BODY
    assert seen["url"] == DOUYIN_VIDEO_URL


def test_page_text_skips_browser_when_html_is_real(monkeypatch):
    monkeypatch.setattr(
        douyin_download.httpx, "get",
        lambda *a, **k: SimpleNamespace(
            raise_for_status=lambda: None, text=PAGE_BODY
        ),
    )
    monkeypatch.setattr(
        douyin_download,
        "_browser_page_text",
        lambda url: pytest.fail("browser should not be used for real HTML"),
    )
    assert douyin_download._page_text(DOUYIN_VIDEO_URL) == PAGE_BODY


def test_rendered_page_text_retries_during_navigation():
    class Page:
        def __init__(self):
            self.calls = 0

        def content(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("Page.content: page is navigating and changing the content")
            return PAGE_BODY

        def wait_for_timeout(self, milliseconds):
            return None

    page = Page()
    assert douyin_download._rendered_page_text(page, timeout_seconds=1) == PAGE_BODY
    assert page.calls == 2


def test_download_douyin_video_rejects_image_posts(tmp_path, monkeypatch):
    _patch_httpx(monkeypatch, page_body='{"desc":"图集作品"}')
    source = validate_douyin_url(DOUYIN_VIDEO_URL)
    with pytest.raises(UrlIngestError, match="图集"):
        douyin_download.download_douyin_video(source, tmp_path)


def test_download_douyin_video_rejects_empty_stream(tmp_path, monkeypatch):
    _patch_httpx(monkeypatch, video_chunks=())
    monkeypatch.setattr(douyin_download, "_duration_seconds", lambda path: 30.0)
    source = validate_douyin_url(DOUYIN_VIDEO_URL)
    with pytest.raises(UrlIngestError, match="为空"):
        douyin_download.download_douyin_video(source, tmp_path)
