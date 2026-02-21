# ABOUTME: Entry point for `python -m storyboard_gen.gui`.
# ABOUTME: Launches the GUI application with optional project directory argument.

import sys

from storyboard_gen.gui.app import run


def main() -> int:
    """CLI entry point for storyboard-gen-gui.

    Accepts an optional positional argument: the project directory to open.

    Returns:
        Application exit code.
    """
    project_dir = sys.argv[1] if len(sys.argv) > 1 else None
    return run(project_dir=project_dir)


sys.exit(main())
