import json

import pytest

from video_report_agent.asr import AsrRun
from video_report_agent.audio import AudioExtraction, AudioProbe
from video_report_agent.ingest import DownloadResult
from video_report_agent.media_config import resolve_media_config
from video_report_agent.schemas import AsrSegment

URL = "https://www.bilibili.com/video/BV1cZ8x6sEhF/"


@pytest.fixture
def env(monkeypatch):
    for key in ("ASR_MODEL", "ASR_BACKEND", "DASHSCOPE_BASE_URL", "OCR_BACKEND"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    return monkeypatch


def test_faster_whisper_config_is_local_and_needs_no_cloud_key(env):
    config = resolve_media_config("faster-whisper")
    assert config["asr_backend"] == "faster-whisper"
    assert config["asr_provider"] == "local"
    assert config["asr_model"] == "small"
    assert config["asr_parameters"] == {}
    assert config["asr_base_url"] is None
    config = resolve_media_config("faster-whisper", asr_model="medium")
    assert config["asr_model"] == "medium"


def test_faster_whisper_rejects_blank_model(env):
    with pytest.raises(ValueError, match="non-empty model"):
        resolve_media_config("faster-whisper", asr_model="   ")


def _stub_pipeline_stages(monkeypatch, tmp_path, *, asr_run=None, fail_download=False):
    """Replace download/ffmpeg/ASR with local fixtures; return the stub ASR run."""
    from video_report_agent import pipeline

    media = tmp_path / "source.m4a"
    media.write_bytes(b"audio")

    def fake_download(source, run_dir, **kwargs):
        if fail_download:
            from video_report_agent.ingest import UrlIngestError

            raise UrlIngestError("DOWNLOAD_ERROR", "yt-dlp failed")
        info = run_dir / "download" / "source.info.json"
        info.parent.mkdir(parents=True, exist_ok=True)
        info.write_text(
            json.dumps({"duration": 2, "title": "标题", "uploader": "UP主"}),
            encoding="utf-8",
        )
        return DownloadResult(
            source=source,
            media_path=media,
            info_path=info,
            title="标题",
            uploader="UP主",
            attribution=f"Bilibili；UP主；《标题》；{source.canonical_url}",
            command=(),
        )

    if asr_run is None:
        asr_run = AsrRun(
            engine="faster-whisper",
            model="small",
            language="zh",
            elapsed_ms=10,
            segments=(
                AsrSegment(ordinal=0, start_ms=0, end_ms=900, text="第一句话"),
                AsrSegment(ordinal=1, start_ms=900, end_ms=1800, text="第二句话"),
            ),
            raw_result={"segments": []},
            backend="faster-whisper",
            provider="local",
        )

    monkeypatch.setattr(pipeline, "download_bilibili_video", fake_download)
    monkeypatch.setattr(
        pipeline,
        "extract_audio",
        lambda media_path, output_path: AudioExtraction(
            path=output_path,
            command=(),
            probe=AudioProbe(path=output_path, channels=1, sample_rate_hz=16000,
                             duration_ms=1800),
        ),
    )
    monkeypatch.setattr(pipeline, "transcribe_audio", lambda *a, **k: asr_run)
    return asr_run


def test_prepare_produces_transcribed_run_without_pi_or_report(env, monkeypatch, tmp_path):
    from video_report_agent.pipeline import create_run
    from video_report_agent.prepare import prepare

    runs = tmp_path / "runs"
    run = create_run(runs, URL, asr_backend="faster-whisper")
    _stub_pipeline_stages(monkeypatch, tmp_path)

    status = prepare(run)

    assert status["state"] == "TRANSCRIBED"
    assert status["stage"] == "TRANSCRIBED"
    assert status["finished_at"]
    stored = json.loads((run / "status.json").read_text(encoding="utf-8"))
    assert stored["state"] == "TRANSCRIBED"
    for name in ("input.json", "status.json", "asr.json", "transcript.md"):
        assert (run / name).is_file(), name
    assert not (run / "report.html").exists()
    assert not (run / "report.png").exists()
    metadata = json.loads((run / "input.json").read_text(encoding="utf-8"))
    assert metadata["asr_backend"] == "faster-whisper"
    assert metadata["title"] == "标题"
    transcript = (run / "transcript.md").read_text(encoding="utf-8")
    assert "# 标题" in transcript
    assert "第一句话" in transcript and "第二句话" in transcript
    assert "[unit-000001 | 0.000–0.900s]" in transcript
    assert "[unit-000002 | 0.900–1.800s]" in transcript
    asr_payload = json.loads((run / "asr.json").read_text(encoding="utf-8"))
    assert asr_payload["backend"] == "faster-whisper"
    assert asr_payload["provider"] == "local"


def test_prepare_failure_marks_failed_and_no_transcript(env, monkeypatch, tmp_path):
    from video_report_agent.pipeline import create_run
    from video_report_agent.prepare import prepare

    runs = tmp_path / "runs"
    run = create_run(runs, URL, asr_backend="faster-whisper")
    _stub_pipeline_stages(monkeypatch, tmp_path, fail_download=True)

    status = prepare(run)

    assert status["state"] == "FAILED"
    stored = json.loads((run / "status.json").read_text(encoding="utf-8"))
    assert stored["state"] == "FAILED"
    assert stored["error_category"] == "EXTERNAL_API_FAILURE"
    assert not (run / "transcript.md").exists()
    assert not (run / "report.html").exists()


def test_prepare_reuses_prior_transcript_across_runs(env, monkeypatch, tmp_path):
    from video_report_agent.pipeline import create_run
    from video_report_agent.prepare import prepare

    runs = tmp_path / "runs"
    first = create_run(runs, URL, asr_backend="faster-whisper")
    _stub_pipeline_stages(monkeypatch, tmp_path)
    assert prepare(first)["state"] == "TRANSCRIBED"

    second = create_run(runs, URL, asr_backend="faster-whisper")
    # Real download/ASR must not run again for the same video and ASR config.
    monkeypatch.setattr(
        "video_report_agent.pipeline.download_bilibili_video",
        lambda *a, **k: pytest.fail("download must be reused"),
    )
    monkeypatch.setattr(
        "video_report_agent.pipeline.transcribe_audio",
        lambda *a, **k: pytest.fail("ASR must be reused"),
    )
    status = prepare(second)
    assert status["state"] == "TRANSCRIBED"
    # A reused transcript short-circuits the whole download stage.
    assert status["download_reused_from"] is None
    assert status["transcript_reused_from"] == first.name
    assert (second / "transcript.md").read_text(encoding="utf-8") == (
        first / "transcript.md"
    ).read_text(encoding="utf-8")
