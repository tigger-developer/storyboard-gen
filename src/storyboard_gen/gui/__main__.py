# ABOUTME: Entry point for `python -m storyboard_gen.gui`.
# ABOUTME: Launches the GUI application with optional project directory and verbose flag.

import argparse
import sys

from storyboard_gen.gui.app import run


def main() -> int:
    """CLI entry point for storyboard-gen-gui.

    Accepts an optional positional argument: the project directory to open.
    Use -v/--verbose to enable stderr logging for debugging.

    Returns:
        Application exit code.
    """
    parser = argparse.ArgumentParser(
        description="Launch the storyboard-gen GUI.",
    )
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=None,
        help="Project directory to open on launch.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose stderr logging for debugging.",
    )
    args = parser.parse_args()
    return run(project_dir=args.project_dir, verbose=args.verbose)


sys.exit(main())
