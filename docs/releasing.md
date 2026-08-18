# Building and releasing

Two things are described here: building `unpaster.exe` on your own machine, and cutting a
release, which is a tag push that makes GitHub Actions build and publish the binary.

Every command uses `.venv\Scripts\python.exe`. Bare `python` may be a different interpreter
without the project installed.

## Set up the environment once

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

`dev` adds pytest, PyInstaller and PyYAML. The runtime dependency is PySide6 alone.

## Build

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm unpaster.spec
```

The executable lands in `dist\unpaster.exe`, self-contained, no installer. `--clean` discards
the previous PyInstaller cache; without it a stale analysis can survive a change.

What `unpaster.spec` pins, and why not to change it casually:

- The entry point is `run_unpaster.py`, **not** `unpaster/main.py`. PyInstaller runs the entry
  module as `__main__` with no package context, so `from . import config` inside `main.py`
  would raise `ImportError` in the frozen build.
- `upx=False`. Compressed executables trip antivirus heuristics, and this program already
  looks suspicious to scanners because it installs a keyboard hook and calls `SendInput`.
- `console=False` — tray application, no console window.
- `icon='assets/unpaster.ico'`. That file is **committed**, so the build needs nothing
  generated first. When the drawing in `unpaster/ui/icon.py` changes, rerun
  `.venv\Scripts\python.exe -m tools.make_icon` and commit the result.
- `version='version_info.txt'` stamps the Windows version resource into the binary.

To run from source without building:

```powershell
.venv\Scripts\python.exe -m unpaster.main
```

Set `QT_QPA_PLATFORM=offscreen` to reproduce what CI sees when a test behaves differently
locally.

## Where the version lives

The version is recorded in five places:

| File | Occurrences |
|---|---|
| `pyproject.toml` | `project.version`, the source of truth |
| `version_info.txt` | `filevers`, `prodvers`, `FileVersion`, `ProductVersion` — four-part, so `0.1.1` becomes `0.1.1.0` |

A bump in one file and not the other ships a binary whose Windows properties lie about which
build it is. `tools/check_version.py` compares all five, and the test suite runs it, so drift
fails a normal `pytest` run rather than a release.

```powershell
.venv\Scripts\python.exe -m tools.check_version
```

The release workflow calls the same tool with `--tag`, which additionally requires the pushed
tag to match. `v0.1.1` and `0.1.1` are both accepted for the tag.

## Release, step by step

### 1. Bump the version

Edit `pyproject.toml` and all four fields in `version_info.txt`.

### 2. Turn `## Unreleased` into the release section

`CHANGELOG.md` collects entries under `## Unreleased` during development. Rename that heading
to the version and date:

```markdown
## 0.1.1 - 2026-08-18
```

The heading must start with the bare version — `tools/release_notes.py` searches for
`^##\s+0.1.1\b` and takes everything up to the next `##`. A tag whose version has no section
fails the workflow, on purpose. Keep the `### New` / `### Changed` / `### Fixed` subheadings;
those become the release note body.

### 3. Check locally before pushing anything

```powershell
.venv\Scripts\python.exe -m tools.check_version
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m tools.release_notes --version 0.1.1 --output dist\RELEASE_NOTE.md
```

The third command is the one CI runs; running it yourself is how you find a missing or
misspelled changelog heading before the tag exists. Read `dist\RELEASE_NOTE.md` — that text
is what people see on the release page.

### 4. Commit and tag

```powershell
git commit -am "Release 0.1.1"
git tag -a v0.1.1 -m "unpaster 0.1.1"
```

Annotated tag, `v` prefix. The workflow triggers on `v*`; a tag without the prefix does
nothing at all.

### 5. Push

```powershell
git push origin master v0.1.1
```

Push the branch and the tag together. A tag pushed alone points at a commit GitHub does not
have on any branch, and the release would be built from a commit nobody can see on `master`.

## What the workflow does with the tag

`.github/workflows/release.yml`, on `windows-latest`, Python 3.13:

1. **Check the tag matches the recorded version** — `tools.check_version --tag`, before
   installing anything, so a mislabelled tag fails in seconds.
2. **Install** `pip install -e ".[dev]"`.
3. **Test** — the full suite with `QT_QPA_PLATFORM=offscreen`.
4. **Build** — `PyInstaller --clean --noconfirm unpaster.spec`.
5. **Checksum** — `dist\unpaster.exe.sha256`, in `sha256sum` format (lowercase hash, two
   spaces, filename), so both `sha256sum -c` and `Get-FileHash` verify it.
6. **Assemble the note** — `tools.release_notes`, i.e. the download preamble plus this
   version's changelog entries.
7. **Publish** — `softprops/action-gh-release@v2` creates the release, uploads `unpaster.exe`
   and the `.sha256`, and appends its own generated commit list under the note body.

The job declares `permissions: contents: write`; workflow jobs are read-only otherwise and
publishing a release is a write.

Any failing step stops the release. Nothing is published, and the tag stays where it is —
fix, delete the tag locally and remotely, and push a new one, or bump to the next patch
version if the bad tag was already public.

### Never put `${{ }}` inside a `run:` script

`${{ }}` is substituted textually before the shell runs, and git permits `; & | $ ( )` in a
ref name, so `${{ github.ref_name }}` in a script is a command injection — a tag named
`v0.1.0;whoami` would execute as two commands. Pass values through `env:` and read them as
`$env:NAME`, which is what the tag check does. `tests/test_workflows.py` enforces this, so
breaking the rule fails the suite.

## The other workflow

`.github/workflows/tests.yml` runs the suite on pushes to `master`, on every pull request,
and on manual dispatch. Matrix: Python 3.12 (declared minimum) and 3.13 (what releases are
built with), `windows-latest` only — every module reaches Windows APIs through `ctypes`.

## Reading the run

`gh` is not installed here, so run status cannot be read from a terminal session; the
repository being private also makes the unauthenticated API return 404. Either watch the
Actions tab, or install the CLI:

```powershell
winget install --id GitHub.cli
gh run watch
```

## Before the first public release

`docs/manual-test.md` is the checklist for what CI cannot cover: a real RDP or VNC session,
key tokens against a live target, autostart across a reboot, corrupt-file recovery, and the
elevated-window error path.
