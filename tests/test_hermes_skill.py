from pathlib import Path

ROOT = Path(__file__).parents[1]
HERMES_SKILL = ROOT / "skills" / "video-report"
SOURCE_SKILL = ROOT / "src" / "video_report_agent" / "skills" / "video-report"


def test_hermes_skill_has_self_contained_support_files():
    source_files = {
        path.relative_to(SOURCE_SKILL)
        for directory in ("assets", "modes", "references")
        for path in (SOURCE_SKILL / directory).rglob("*")
        if path.is_file()
    }
    hermes_files = {
        path.relative_to(HERMES_SKILL)
        for directory in ("assets", "modes", "references")
        for path in (HERMES_SKILL / directory).rglob("*")
        if path.is_file()
    }
    assert hermes_files == source_files
    for relative in source_files:
        assert (HERMES_SKILL / relative).read_bytes() == (SOURCE_SKILL / relative).read_bytes()


def test_hermes_skill_declares_linux_and_terminal_dependency():
    content = (HERMES_SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "platforms: [linux]" in content
    assert "requires_toolsets: [terminal]" in content
    assert "scripts/prepare-video.sh" in content
    assert "[[as_document]]" in content


def test_hermes_scripts_are_portable_sh_without_privileged_install():
    setup = (HERMES_SKILL / "scripts" / "setup-linux.sh").read_text(encoding="utf-8")
    prepare = (HERMES_SKILL / "scripts" / "prepare-video.sh").read_text(encoding="utf-8")
    assert setup.startswith("#!/bin/sh\nset -eu")
    assert prepare.startswith("#!/bin/sh\nset -eu")
    assert "sudo " not in setup
    assert "RUN_DIR=" in prepare
