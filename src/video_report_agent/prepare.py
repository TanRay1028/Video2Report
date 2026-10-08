"""URL → download → audio → ASR → transcript, stopping before report generation.

`prepare` produces the same local artifacts as the front half of
:func:`video_report_agent.pipeline.generate` (``asr.json`` and
``transcript.md``) but never starts Pi, never renders a report and never
requires Pi or cloud credentials. The final status is ``TRANSCRIBED``.
"""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

from .asr import AsrError
from .audio import AudioExtractionError
from .failures import asr_failure
from .ingest import UrlIngestError
from .paraformer import CloudAsrError
from .pipeline import _prepare_transcript, write_json
from .retention import cleanup_media
from .trace import RunTrace


def prepare(run: Path) -> dict:
    metadata = json.loads((run / "input.json").read_text(encoding="utf-8"))
    status = json.loads((run / "status.json").read_text(encoding="utf-8"))
    status.update(video_id=metadata["video_id"])

    def update(stage: str, **fields):
        if stage in {"TRANSCRIBED", "FAILED"}:
            fields["finished_at"] = time.time()
        status.update(state=stage, stage=stage, **fields)
        write_json(run / "status.json", status)

    trace = RunTrace(run)
    try:
        _prepare_transcript(run, metadata, status, update, trace)
        update("TRANSCRIBED")
    except Exception as exc:
        if isinstance(exc, CloudAsrError):
            write_json(run / "asr-error.json", exc.to_dict())
            (run / "failure.log").write_text(str(exc), encoding="utf-8")
        else:
            (run / "failure.log").write_text(traceback.format_exc(), encoding="utf-8")
        if isinstance(exc, CloudAsrError):
            category = "EXTERNAL_API_FAILURE"
        elif isinstance(exc, UrlIngestError):
            category = (
                "ENVIRONMENT_FAILURE" if "unavailable" in str(exc) else "EXTERNAL_API_FAILURE"
            )
        elif isinstance(exc, (AsrError, AudioExtractionError, OSError)):
            category = "ENVIRONMENT_FAILURE"
        else:
            category = "IMPLEMENTATION_FAILURE"
        code, message = category, str(exc)
        diagnostics = {}
        if isinstance(exc, CloudAsrError):
            code, message = asr_failure(exc)
            diagnostics = {"http_status": exc.http_status, "provider_code": exc.provider_code,
                           "failed_stage": exc.stage}
        elif isinstance(exc, UrlIngestError):
            code = exc.category
            if code in {"VIDEO_DURATION_INVALID", "URL_INVALID"}:
                category = "INPUT_REJECTED"
            elif code == "DOWNLOAD_ERROR" and str(exc) == "yt-dlp failed":
                message = "视频下载失败，可能是视频不可访问或下载服务异常，请稍后重试。"
        update("FAILED", error_category=category, error_code=code, error=message, **diagnostics)
    cleanup_media(run.parent)
    return status
