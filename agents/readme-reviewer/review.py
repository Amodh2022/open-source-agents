"""One-command runner: python review.py <folder>   (see readme_reviewer/cli.py)."""

import sys

from readme_reviewer.cli import main

if __name__ == "__main__":
    sys.exit(main())
