"""No run the README documents asks for a council, so its live check reads no operator settings.

`test_readme_live.py` runs each marked block in a child process, and `cli.audit`
reads the operator's `.env` for a run asking for a council. `tests/conftest.py`
keeps those settings out of this process only, so a council run marked here
would carry them into the check. The usage guide holds its own runs to the same
in `test_usage_runs.py`.

Page parsing only -- no corpus, no scanners, no network -- so it runs in the
ordinary suite.
"""

from doc_pages import README, read
from doc_runs import councils_asked_for


def test_no_documented_run_asks_for_a_council_so_none_reads_the_operator_s_settings():
    """The live check runs each block in a child process, which reads `.env` for a council run."""
    assert councils_asked_for(read(README)) == []
