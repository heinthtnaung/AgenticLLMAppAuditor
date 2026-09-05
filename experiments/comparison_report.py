"""Renders the local-vs-hosted comparison as a page a human can read.

Separate from the audit's `report.html` on purpose: that artifact is generated
from `report.md` and published as byte-identical run to run. A hosted model's
answer is neither reproducible nor available without a key, so putting it there
would break the guarantee and mix the tool with the study that evaluates it.
Same renderer, so the two pages look alike and sit side by side.
"""

from reporting.markdown_html import to_html

TITLE = "Local vs hosted model — semantic probe"

# The probe reports a template as a finding only on `confirmed`.
FLAGGED = "confirmed"


def _verdict_summary(result: dict) -> list[str]:
    """One line per model: what it flagged, how long it took, what it sent.

    A list, not a table: `reporting/markdown_html.py` refuses to render tables
    rather than flatten one into a paragraph, and it is right to.
    """
    lines = []
    for arm in result["arms"]:
        flagged = sum(1 for v in arm["verdicts"].values() if v == FLAGGED)
        lines.append(f"- **`{arm['model']}`** — flagged {flagged} of "
                     f"{result['templates_examined']}, {arm['seconds']}s, "
                     f"{arm['exposure']['bytes_sent']} bytes sent")
    return lines


def _per_template(result: dict) -> list[str]:
    """Each template, each model's verdict, and the reasoning it gave.

    The reasoning is the point. A verdict alone cannot show *why* two models
    disagree, and on the measured case the disagreement is the result.
    """
    lines = []
    subjects = sorted({s for arm in result["arms"] for s in arm["verdicts"]})
    for subject in subjects:
        lines += ["", f"### `{subject}`", ""]
        for arm in result["arms"]:
            verdict = arm["verdicts"].get(subject, "not examined")
            mark = "flagged" if verdict == FLAGGED else verdict
            lines += [f"**{arm['model']}** — {mark}", "",
                      f"> {arm['details'].get(subject, '(no reasoning recorded)')}", ""]
    return lines


def _exposure(result: dict) -> list[str]:
    """What left the machine, and what cannot be known about where it went."""
    sent = result["arms"][-1]["exposure"]
    return ["", "## What left the machine", "",
            f"{sent['requests']} request(s), {sent['bytes_sent']} bytes. Transmitted:",
            ""] + [f"- {kind}" for kind in sent["field_kinds_transmitted"]] + [
            "", "**Cannot be measured from here**, and stated rather than dressed up:", ""
            ] + [f"- {item}" for item in result["unmeasurable_exposure"]]


def to_markdown(result: dict, disagreement_note: str = "") -> str:
    """The whole comparison as Markdown."""
    lines = [f"# {TITLE}", "",
             f"Repository: `{result['repository']}` — "
             f"{result['templates_examined']} prompt template(s) examined.", "",
             "## Summary", ""] + _verdict_summary(result) + [
             "", f"The models agree on {len(result['agreements'])} and disagree on "
             f"{len(result['disagreements'])}.", ""]
    if disagreement_note:
        lines += [disagreement_note, ""]
    lines += ["## Every template, and what each model said"] + _per_template(result)
    lines += _exposure(result)
    lines += ["", "## How to read this", "",
              "A verdict is not a score. The static checks use no model at all, so this "
              "compares the only model-dependent detection the auditor has. Latency is "
              "confounded by network and provider queue. The hosted model has no `seed`, "
              "so its column is a sample, not a guarantee."]
    return "\n".join(lines) + "\n"


def to_page(result: dict, disagreement_note: str = "") -> str:
    """The comparison as a standalone HTML page, rendered like the audit report."""
    return to_html(to_markdown(result, disagreement_note), TITLE)
