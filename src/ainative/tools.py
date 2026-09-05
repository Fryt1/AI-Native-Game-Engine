"""Console entrypoint for project Tool CLI: ``python -m ainative.tools``."""

import sys

from ainative.cli.runner import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
