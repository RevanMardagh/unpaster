"""PyInstaller entry script.

The frozen entry module runs as ``__main__`` with no package context, so
``unpaster/main.py`` cannot be the entry point directly -- its relative
imports would fail. This wrapper imports the package normally instead.
"""

from unpaster.main import main

if __name__ == "__main__":
    raise SystemExit(main())
