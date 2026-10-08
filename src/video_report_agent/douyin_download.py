"""Douyin download via the unauthenticated iesdouyin play endpoint.

Douyin blocks yt-dlp's web detail API (HTTP 403), so Douyin sources bypass
yt-dlp: fetch the mobile-rendered page with an Android UA, regex out the
play_addr uri, then stream the video from the signature-free play endpoint.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import httpx

from .ingest import (
    MAX_VIDEO_SECONDS,
    DouyinSource,
    DownloadResult,
    UrlIngestError,
    _metadata,
)

_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 "
    "(KHTML, like Gecko) SamsungBrowser/14.2 Chrome/87.0.4280.141 Mobile Safari/537.36"
)
_PLAY_ADDR_PATTERN = re.compile(r'"video":\{"play_addr":\{"uri":"([a-zA-Z0-9]+)"')
_PLAY_URL_TEMPLATE = "https://www.iesdouyin.com/aweme/v1/play/?video_id=%s&ratio=360p&line=0"
_NICKNAME_PATTERN = re.compile(r'"nickname":\s*"([^"]+)"')
_DESC_PATTERN = re.compile(r'"desc":\s*"([^"]*)"')


def _http_page_text(url: str) -> str:
    try:
        response = httpx.get(
            url, headers={"User-Agent": _MOBILE_UA}, timeout=15, follow_redirects=True
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise UrlIngestError(
            "DOWNLOAD_ERROR", "抖音页面请求失败，请检查链接或稍后重试"
        ) from exc
    return response.text


def _browser_page_text(url: str) -> str:
    """Render the page with headless Chromium when Douyin serves a JS challenge."""

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise UrlIngestError(
            "DOWNLOAD_ERROR", "抖音页面需要浏览器渲染，但未安装 playwright"
        ) from exc
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(user_agent=_MOBILE_UA, locale="zh-CN")
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                deadline = time.time() + 20
                while time.time() < deadline:
                    content = page.content()
                    if _PLAY_ADDR_PATTERN.search(content):
                        return content
                    page.wait_for_timeout(500)
                return page.content()
            finally:
                browser.close()
    except Exception as exc:  # playwright raises its own timeout/network errors
        raise UrlIngestError("DOWNLOAD_ERROR", "抖音页面浏览器渲染失败") from exc


def _page_text(url: str) -> str:
    body = _http_page_text(url)
    if _PLAY_ADDR_PATTERN.search(body) or _DESC_PATTERN.search(body):
        return body
    # Anti-bot shell page: the real markup only appears after JS runs.
    return _browser_page_text(url)


def _play_uri(body: str) -> str:
    match = _PLAY_ADDR_PATTERN.search(body)
    if match is None:
        raise UrlIngestError(
            "DOWNLOAD_ERROR",
            "抖音页面未返回视频地址：作品可能是图集、已下架或需要 App 内查看",
        )
    return match.group(1)


def _download_stream(url: str, target: Path) -> None:
    try:
        with httpx.stream(
            "GET", url, headers={"User-Agent": _MOBILE_UA}, timeout=30, follow_redirects=True
        ) as response:
            response.raise_for_status()
            with target.open("wb") as handle:
                for chunk in response.iter_bytes(chunk_size=1024 * 256):
                    handle.write(chunk)
    except (httpx.HTTPError, OSError) as exc:
        target.unlink(missing_ok=True)
        raise UrlIngestError("DOWNLOAD_ERROR", "抖音视频下载失败，请稍后重试") from exc
    if not target.is_file() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise UrlIngestError("DOWNLOAD_ERROR", "抖音视频下载结果为空")


def _duration_seconds(media_path: Path) -> float:
    executable = shutil.which("ffprobe")
    if executable is None:
        raise UrlIngestError("DOWNLOAD_ERROR", "ffprobe is unavailable")
    try:
        completed = subprocess.run(
            [
                executable,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(media_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            shell=False,
            timeout=120,
        )
        duration = json.loads(completed.stdout)["format"]["duration"]
        seconds = float(duration)
    except (OSError, subprocess.SubprocessError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise UrlIngestError("DOWNLOAD_ERROR", "无法确认视频时长，不能处理此视频。") from exc
    if seconds <= 0 or seconds > MAX_VIDEO_SECONDS:
        raise UrlIngestError(
            "VIDEO_TOO_LONG", "单个视频最长支持 3 小时。"
        )
    return seconds


def download_douyin_video(source: DouyinSource, run_dir: Path) -> DownloadResult:
    """Download a Douyin aweme into the run workspace and write yt-dlp-style metadata."""

    download_dir = run_dir.resolve() / "download"
    try:
        download_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UrlIngestError("DOWNLOAD_ERROR", "download directory is unavailable") from exc

    body = _page_text(source.canonical_url)
    play_url = _PLAY_URL_TEMPLATE % _play_uri(body)
    media_path = download_dir / "source.mp4"
    _download_stream(play_url, media_path)

    title_match = _DESC_PATTERN.search(body)
    uploader_match = _NICKNAME_PATTERN.search(body)
    info = {
        "title": (title_match.group(1) if title_match else "") or f"抖音作品 {source.item_id}",
        "uploader": (uploader_match.group(1) if uploader_match else "") or "抖音作者",
        "duration": _duration_seconds(media_path),
    }
    info_path = download_dir / "source.info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    title, uploader, attribution = _metadata(info_path, source)
    return DownloadResult(
        source=source,
        media_path=media_path,
        info_path=info_path.resolve(),
        title=title,
        uploader=uploader,
        attribution=attribution,
        command=("douyin-play", source.canonical_url),
    )
