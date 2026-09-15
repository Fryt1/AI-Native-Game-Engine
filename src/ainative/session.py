"""Console entrypoint for the Agent acceptance loop: ``python -m ainative.session``."""

import sys

from ainative.cli.commands import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
