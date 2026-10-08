import sys
import types
import wave

import pytest

from video_report_agent.asr import AsrError
from video_report_agent.faster_whisper_asr import (
    DEFAULT_FASTER_WHISPER_MODEL,
    FasterWhisperBackend,
    _transcribe_faster_whisper,
)


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "audio.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\x00\x00" * 16000)
    return path


class _Word:
    def __init__(self, start, end, word):
        self.start = start
        self.end = end
        self.word = word


class _Segment:
    def __init__(self, start, end, text, words=()):
        self.start = start
        self.end = end
        self.text = text
        self.words = list(words)


class _Info:
    language = "zh"
    duration = 1.0


def _install_fake_faster_whisper(monkeypatch, segments):
    created = []

    class FakeModel:
        def __init__(self, model, device=None, compute_type=None):
            created.append({"model": model, "device": device, "compute_type": compute_type})

        def transcribe(self, path, **kwargs):
            assert kwargs["language"] == "zh"
            assert kwargs["word_timestamps"] is True
            return iter(segments), _Info()

    module = types.SimpleNamespace(WhisperModel=FakeModel)
    monkeypatch.setitem(sys.modules, "faster_whisper", module)
    return created


def test_faster_whisper_normalizes_to_shared_contract(audio, monkeypatch):
    created = _install_fake_faster_whisper(
        monkeypatch,
        [
            _Segment(0.0, 0.8, "第一句", [_Word(0.0, 0.4, "第一"), _Word(0.4, 0.8, "句")]),
            _Segment(0.8, 1.6, "第二句"),
        ],
    )
    result = _transcribe_faster_whisper(audio, model="small", language="zh")
    assert created == [{"model": "small", "device": "cpu", "compute_type": "int8"}]
    assert result.engine == "faster-whisper"
    assert result.backend == "faster-whisper"
    assert result.provider == "local"
    assert result.model == "small"
    assert [(s.start_ms, s.end_ms, s.text) for s in result.segments] == [
        (0, 800, "第一句"),
        (800, 1600, "第二句"),
    ]
    payload = result.to_dict()
    assert payload["raw_segment_count"] == 2
    assert payload["segments"][0]["words"][0]["word"] == "第一"


def test_backend_dispatches_with_default_model(audio, monkeypatch):
    created = _install_fake_faster_whisper(monkeypatch, [_Segment(0.0, 0.5, "内容")])
    backend = FasterWhisperBackend()
    assert backend.default_model == DEFAULT_FASTER_WHISPER_MODEL
    result = backend.transcribe(audio)
    assert created[0]["model"] == DEFAULT_FASTER_WHISPER_MODEL
    assert result.segments[0].text == "内容"


def test_missing_package_raises_environment_error(audio, monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    # Force the import to fail even if faster-whisper happens to be installed.
    import builtins

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "faster_whisper":
            raise ImportError("No module named 'faster_whisper'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(AsrError, match="faster-whisper is not installed"):
        _transcribe_faster_whisper(audio, model="small")


def test_non_chinese_language_rejected(audio):
    with pytest.raises(AsrError, match="explicit Chinese ASR"):
        _transcribe_faster_whisper(audio, model="small", language="en")


def test_missing_audio_rejected(tmp_path):
    with pytest.raises(AsrError, match="missing or empty"):
        _transcribe_faster_whisper(tmp_path / "nope.wav", model="small")
