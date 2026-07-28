from tools import check_version

PYPROJECT = """
[project]
name = "unpaster"
version = "0.1.0"
"""

VERSION_INFO = """
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(0, 1, 0, 0),
    prodvers=(0, 1, 0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('FileVersion', '0.1.0.0'),
         StringStruct('ProductVersion', '0.1.0.0')])
    ]),
  ]
)
"""


def test_the_files_in_this_repository_agree():
    assert check_version.problems() == []


def test_matching_texts_have_no_problems():
    assert check_version.problems(PYPROJECT, VERSION_INFO) == []


def test_pyproject_version_is_read():
    assert check_version.pyproject_version(PYPROJECT) == "0.1.0"


def test_missing_pyproject_version_is_a_problem():
    found = check_version.problems('[project]\nname = "unpaster"\n', VERSION_INFO)
    assert len(found) == 1
    assert "pyproject.toml" in found[0]


def test_file_version_string_drift_is_caught():
    drifted = VERSION_INFO.replace("'FileVersion', '0.1.0.0'", "'FileVersion', '0.2.0.0'")
    found = check_version.problems(PYPROJECT, drifted)
    assert len(found) == 1
    assert "FileVersion" in found[0]


def test_filevers_tuple_drift_is_caught():
    drifted = VERSION_INFO.replace("filevers=(0, 1, 0, 0)", "filevers=(0, 9, 0, 0)")
    found = check_version.problems(PYPROJECT, drifted)
    assert len(found) == 1
    assert "filevers" in found[0]


def test_every_drifted_field_is_reported_at_once():
    drifted = (VERSION_INFO
               .replace("filevers=(0, 1, 0, 0)", "filevers=(0, 9, 0, 0)")
               .replace("prodvers=(0, 1, 0, 0)", "prodvers=(0, 9, 0, 0)"))
    assert len(check_version.problems(PYPROJECT, drifted)) == 2


def test_a_matching_tag_is_accepted():
    assert check_version.problems(PYPROJECT, VERSION_INFO, tag="v0.1.0") == []


def test_a_tag_without_the_v_prefix_is_accepted():
    assert check_version.problems(PYPROJECT, VERSION_INFO, tag="0.1.0") == []


def test_a_tag_that_disagrees_with_the_version_is_caught():
    found = check_version.problems(PYPROJECT, VERSION_INFO, tag="v0.2.0")
    assert len(found) == 1
    assert "v0.2.0" in found[0]
    assert "0.1.0" in found[0]


def test_main_reports_success_for_this_repository(capsys):
    assert check_version.main([]) == 0
    assert "0.1.0" in capsys.readouterr().out


def test_main_fails_on_a_bad_tag(capsys):
    assert check_version.main(["--tag", "v9.9.9"]) == 1
    assert "v9.9.9" in capsys.readouterr().out
