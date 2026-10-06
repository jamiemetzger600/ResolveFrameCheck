#!/usr/bin/env python
# Entry point for Workspace > Scripts. Installed as a symlink by install.sh.
# Resolve runs scripts via exec(), so __file__ is undefined; use the project path directly.
import sys

HERE = "__INSTALL_DIR__"  # replaced by install.sh
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from framecheck import ui  # noqa: E402

ui.run(resolve, fusion, bmd)  # noqa: F821  (globals provided by Resolve)
