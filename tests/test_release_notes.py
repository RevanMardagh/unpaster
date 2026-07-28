import pytest

from tools import release_notes

CHANGELOG = """# Changelog

Preamble text that must never reach a release note.

## 0.2.0 - 2026-08-01

### New

- Second release thing.

### Fixed

- A bug.

## 0.1.0 - 2026-07-29

First release.

### New

- First release thing.
"""


def test_section_returns_only_the_requested_version():
    body = release_notes.section("0.2.0", CHANGELOG)
    assert "Second release thing." in body
    assert "First release thing." not in body
    assert "Preamble text" not in body


def test_section_keeps_the_headings_inside_it():
    body = release_notes.section("0.2.0", CHANGELOG)
    assert "### New" in body
    assert "### Fixed" in body


def test_section_drops_the_version_heading_itself():
    assert not release_notes.section("0.2.0", CHANGELOG).startswith("## 0.2.0")


def test_the_last_section_runs_to_the_end_of_the_file():
    body = release_notes.section("0.1.0", CHANGELOG)
    assert "First release thing." in body
    assert "Second release thing." not in body


def test_a_leading_v_is_accepted():
    assert release_notes.section("v0.1.0", CHANGELOG) == release_notes.section("0.1.0", CHANGELOG)


def test_an_unknown_version_raises():
    with pytest.raises(release_notes.MissingVersion):
        release_notes.section("9.9.9", CHANGELOG)


def test_this_repository_has_notes_for_its_current_version():
    from tools import check_version

    body = release_notes.section(check_version.pyproject_version())
    assert "### New" in body


def test_compose_puts_the_download_preamble_before_the_changelog():
    note = release_notes.compose("0.1.0", CHANGELOG)
    assert note.index("unpaster.exe.sha256") < note.index("First release thing.")
    assert "Get-FileHash" in note


def test_main_writes_the_note_to_a_file(tmp_path):
    target = tmp_path / "notes.md"
    assert release_notes.main(["--version", "v0.1.0", "--output", str(target)]) == 0
    assert "### New" in target.read_text(encoding="utf-8")


def test_main_fails_on_a_version_with_no_entry(tmp_path, capsys):
    target = tmp_path / "notes.md"
    assert release_notes.main(["--version", "v9.9.9", "--output", str(target)]) == 1
    assert "9.9.9" in capsys.readouterr().out
    assert not target.exists()
