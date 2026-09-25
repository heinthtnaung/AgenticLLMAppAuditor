"""Run one step of the council evaluation: `python measurements/council_eval <step> ...`."""

import sys
from pathlib import Path

# The package sits beside the other measurement scripts, not in `src/`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from council_eval.commands import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
