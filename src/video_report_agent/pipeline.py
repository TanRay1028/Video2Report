"""Deterministic URL → audio → ASR → transcript preparation pipeline."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

from .asr import transcribe_audio
from .audio import extract_audio
from .douyin_download import download_douyin_video
from .ingest import (
    DouyinSource,
    download_bilibili_video,
    validate_source_url,
)
from .media_config import resolve_media_config
from .reuse import reuse_asr, reuse_download, reuse_transcript
from .transcript import build_transcript
from .transcript_foundation import parse_roi


def write_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def create_run(
    root: Path,
    url: str,
    *,
    report_mode="standard",
    transcript_mode="asr-only",
    ocr_mode="off",
    ocr_roi=None,
    subtitle_file=None,
    asr_backend=None,
    asr_model=None,
    ocr_backend=None,
    cookies_from_browser=None,
    cookies_file=None,
) -> Path:
    if report_mode not in ("standard", "brief"):
        raise ValueError("report_mode must be standard or brief")
    if transcript_mode not in {"asr-only", "fused"}:
        raise ValueError("transcript_mode must be asr-only or fused")
    if ocr_mode == "on":
        ocr_mode = "roi"
    if ocr_mode not in {"off", "auto", "roi"}:
        raise ValueError("ocr_mode must be off, auto or roi")
    if transcript_mode == "fused" and ocr_mode == "roi":
        parse_roi(ocr_roi)
    media_config = resolve_media_config(asr_backend, asr_model, ocr_backend)
    source = validate_source_url(url)
    run = root.resolve() / uuid.uuid4().hex
    run.mkdir(parents=True)
    write_json(
        run / "input.json",
        {
            **(
                {"cookies_from_browser": cookies_from_browser}
                if cookies_from_browser
                else {}
            ),
            **({"cookies_file": str(cookies_file)} if cookies_file else {}),
            **media_config,
            "url": source.canonical_url,
            "video_id": source.video_id,
            "report_mode": report_mode,
            "transcript_mode": transcript_mode,
            "ocr_mode": ocr_mode,
            "ocr_roi": ocr_roi,
            "subtitle_file": "subtitle" + Path(subtitle_file).suffix if subtitle_file else None,
        },
    )
    write_json(
        run / "status.json",
        {
            "run_id": run.name,
            "state": "QUEUED",
            "stage": "QUEUED",
            "started_at": time.time(),
        },
    )
    if subtitle_file:
        import shutil

        shutil.copy2(subtitle_file, run / ("subtitle" + Path(subtitle_file).suffix))
    return run


def _prepare_transcript(run, metadata, status, update, trace) -> None:
    """Download, transcribe, and build the transcript consumed by the calling Agent."""

    transcript_source = reuse_transcript(run, metadata)
    status["download_reused_from"] = None
    if transcript_source is None:
        update("DOWNLOADING")
        with trace.span("download", input={"video_id": metadata["video_id"]}) as detail:
            source = validate_source_url(metadata["url"])
            request_subtitles = metadata.get("transcript_mode") == "fused"
            audio_only = metadata.get("transcript_mode", "asr-only") == "asr-only"
            downloaded, download_source = reuse_download(
                source,
                run,
                request_subtitles=request_subtitles,
                audio_only=audio_only,
            )
            if downloaded is None:
                if isinstance(source, DouyinSource):
                    # Douyin blocks yt-dlp's web detail API; use the play endpoint instead.
                    downloaded = download_douyin_video(source, run)
                else:
                    downloaded = download_bilibili_video(
                        source,
                        run,
                        request_subtitles=request_subtitles,
                        audio_only=audio_only,
                        cookies_from_browser=metadata.get("cookies_from_browser"),
                        cookies_file=metadata.get("cookies_file"),
                    )
            detail.update(
                output={"media": downloaded.media_path.name}, reused_from=download_source,
            )
        status["download_reused_from"] = download_source
        metadata.update(
            download_audio_only=audio_only,
            title=downloaded.title,
            uploader=downloaded.uploader,
            attribution=downloaded.attribution,
        )
    write_json(run / "input.json", metadata)
    status["title"] = metadata.get("title")
    status["transcript_reused_from"] = transcript_source
    if transcript_source is None:
        update("TRANSCRIBING")
        with trace.span("ffmpeg", input={"media": downloaded.media_path.name}) as detail:
            audio = extract_audio(downloaded.media_path, run / "audio.wav")
            detail.update(output={
                "audio": audio.path.name, "duration_ms": audio.probe.duration_ms,
            })
        with trace.span(
            "asr", backend=metadata["asr_backend"], model=metadata["asr_model"],
            input={"audio": audio.path.name},
        ) as detail:
            asr_source = reuse_asr(run, metadata)
            status["asr_reused_from"] = asr_source
            if asr_source is None:
                asr = transcribe_audio(
                    audio.path,
                    model=metadata["asr_model"],
                    backend=metadata["asr_backend"],
                    base_url=metadata["asr_base_url"],
                    language=metadata["asr_language"],
                    parameters=metadata["asr_parameters"],
                    task_path=run / "asr-task.json",
                )
                write_json(run / "asr.json", asr.to_dict())
                segments = len(asr.segments)
            else:
                stored = json.loads((run / "asr.json").read_text(encoding="utf-8"))
                segments = len(stored["segments"])
            detail.update(
                output={"artifact": "asr.json", "segments": segments},
                reused_from=asr_source,
            )
        with trace.span("transcript") as detail:
            options = argparse.Namespace(
                transcript_mode=metadata.get("transcript_mode", "asr-only"),
                ocr_mode=metadata.get("ocr_mode", "off"),
                ocr_roi=metadata.get("ocr_roi"),
                ocr_backend=metadata["ocr_backend"],
                subtitle_file=(
                    run / metadata["subtitle_file"] if metadata.get("subtitle_file") else None
                ),
            )
            build, _, _ = build_transcript(
                options,
                source_path=downloaded.media_path,
                artifact_root=run,
                asr_path=run / "asr.json",
                source_duration_ms=audio.probe.duration_ms,
                manifest=metadata,
            )
            transcript = [f"# {downloaded.title}", downloaded.attribution, ""]
            transcript.extend(
                f"[{u.unit_id} | {u.start_ms / 1000:.3f}–{u.end_ms / 1000:.3f}s] "
                f"{u.canonical_text}"
                for u in build.canonical_units
            )
            (run / "transcript.md").write_text("\n".join(transcript), encoding="utf-8")
            detail.update(output={
                "artifact": "transcript.md", "units": len(build.canonical_units),
            })
    else:
        with trace.span("transcript") as detail:
            detail.update(reused_from=transcript_source, output={"artifact": "transcript.md"})
