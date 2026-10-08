"""Local faster-whisper ASR backend for Windows, Linux and GPU hosts.

The backend mirrors the mlx-whisper contract: explicit Chinese ASR, raw
timestamped segments preserved, and normalization shared with the other
backends via :func:`video_report_agent.asr.normalize_asr_segments`.
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from .asr import AsrError, AsrRun, normalize_asr_segments

DEFAULT_FASTER_WHISPER_MODEL = "small"


def _transcribe_faster_whisper(
    audio_path: Path,
    *,
    model: str,
    language: str = "zh",
    device: str = "cpu",
    compute_type: str = "int8",
) -> AsrRun:
    """Run faster-whisper explicitly in Chinese and retain its original result."""

    if not audio_path.is_file() or audio_path.stat().st_size == 0:
        raise AsrError(f"audio input is missing or empty: {audio_path}")
    if language != "zh":
        raise AsrError("local ASR only permits explicit Chinese ASR")

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise AsrError(
            "faster-whisper is not installed in this project environment "
            "(install the 'faster-whisper' extra)"
        ) from exc

    started_at = perf_counter()
    try:
        whisper = WhisperModel(model, device=device, compute_type=compute_type)
        segments_iter, info = whisper.transcribe(
            str(audio_path),
            language=language,
            word_timestamps=True,
            beam_size=5,
        )
        raw_segments: list[dict[str, Any]] = [
            {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "words": [
                    {"start": word.start, "end": word.end, "word": word.word}
                    for word in (segment.words or [])
                ],
            }
            for segment in segments_iter
        ]
    except AsrError:
        raise
    except Exception as exc:
        raise AsrError(f"faster-whisper transcription failed: {type(exc).__name__}") from exc
    elapsed_ms = round((perf_counter() - started_at) * 1000)

    raw_result: dict[str, Any] = {
        "segments": raw_segments,
        "language": getattr(info, "language", language),
        "duration": getattr(info, "duration", None),
        "raw_segment_count": len(raw_segments),
    }
    normalized = normalize_asr_segments(raw_segments)
    return AsrRun(
        engine="faster-whisper",
        model=model,
        language=language,
        elapsed_ms=elapsed_ms,
        segments=normalized.segments,
        raw_result=raw_result,
        backend="faster-whisper",
        provider="local",
        usage={"audio_duration_s": getattr(info, "duration", None)},
        dropped_empty_raw_segment_ordinals=normalized.dropped_empty_raw_segment_ordinals,
        dropped_non_positive_raw_segment_ordinals=(
            normalized.dropped_non_positive_raw_segment_ordinals
        ),
        dropped_unrepresentable_raw_segment_ordinals=(
            normalized.dropped_unrepresentable_raw_segment_ordinals
        ),
    )


class FasterWhisperBackend:
    """Local ASR backend; timestamps are relative to the audio input."""

    default_model = DEFAULT_FASTER_WHISPER_MODEL

    def __init__(
        self,
        model: str = DEFAULT_FASTER_WHISPER_MODEL,
        *,
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self.model = model
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, audio_path: Path, language: str = "zh") -> AsrRun:
        # prepare runs as a one-shot CLI, so transcription stays in-process;
        # unlike the mlx web-service path there is no long-lived process to shield.
        return _transcribe_faster_whisper(
            audio_path,
            model=self.model,
            language=language,
            device=self.device,
            compute_type=self.compute_type,
        )
