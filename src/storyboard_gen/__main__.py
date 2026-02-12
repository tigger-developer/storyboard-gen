# ABOUTME: Entry point for `python -m storyboard_gen`.
# ABOUTME: Delegates to the CLI main function.

import sys

from storyboard_gen.cli import main

sys.exit(main())
