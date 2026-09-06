"""Renders the local-vs-hosted comparison as a page a human can read.

Separate from the audit's `report.html` on purpose: that artifact is generated
from `report.md` and published as byte-identical run to run. A hosted model's
answer is neither reproducible nor available without a key, so putting it there
would break the guarantee and mix the tool with the study that evaluates it.
Same renderer, so the two pages look alike and sit side by side.

**Every count here carries its denominator.** A model's flagged count is out of
the subjects *that arm* saw, not the union across arms, and the agreement line
is printed beside the two buckets that were not compared -- otherwise a run that
asked nobody anything reads as unanimity.
"""

from agreement import (INTERPOLATES_NOTHING, MIXED_REASONS, MODEL_ANSWERED_UNUSABLY,
                       MODEL_UNREACHABLE, TEXT_NOT_LITERAL)
from reporting.markdown_html import to_html

TITLE = "Local vs hosted model — semantic probe"

# The probe reports a template as a finding only on `confirmed`.
FLAGGED = "confirmed"

# How each exclusion reads on the page. The vocabulary is `agreement.py`'s; this
# is only its wording, kept here so the study's data and its prose stay apart.
REASON_WORDING = {
    TEXT_NOT_LITERAL: "the template's text is not written literally at that line",
    INTERPOLATES_NOTHING:
        "the template interpolates nothing, so there is no runtime value to judge",
    MODEL_UNREACHABLE: "a model could not be reached",
    MODEL_ANSWERED_UNUSABLY: "a model answered neither VULNERABLE nor SAFE",
    MIXED_REASONS: "no model answered, and the models were stopped by different things",
}


def _verdict_summary(result: dict) -> list[str]:
    """One line per model: what it flagged out of what it saw, how long, what it sent.

    A list, not a table: `reporting/markdown_html.py` refuses to render tables
    rather than flatten one into a paragraph, and it is right to.
    """
    lines = []
    for arm in result["arms"]:
        flagged = sum(1 for v in arm["verdicts"].values() if v == FLAGGED)
        lines.append(f"- **`{arm['model']}`** — flagged {flagged} of "
                     f"{len(arm['verdicts'])} it examined, {arm['seconds']}s, "
                     f"{arm['exposure']['bytes_sent']} bytes over "
                     f"{arm['exposure']['requests']} request(s)")
    return lines


def _counts(result: dict) -> list[str]:
    """All four buckets on one line, so no number is quoted without the rest."""
    return ["", f"Of {result['subjects_seen']} template(s): "
                f"{len(result['agreements'])} agreed, "
                f"{len(result['disagreements'])} disagreed, "
                f"{len(result['not_put_to_a_model'])} never put to a model, "
                f"{len(result['not_examined_by_every_arm'])} not seen by every model.", ""]


def _not_compared(result: dict) -> list[str]:
    """The templates no verdict can be read from, and what settled each instead."""
    excluded, absent = result["not_put_to_a_model"], result["not_examined_by_every_arm"]
    if not excluded and not absent:
        return []
    lines = ["", "## Templates the comparison could not use", "",
             "Excluded from the agreement counts above: either no model answered, or "
             "not every model was shown the template. Comparing these would set a "
             "verdict against the absence of one.", ""]
    lines += [f"- `{row['subject']}` — {REASON_WORDING[row['reason']]}"
              for row in excluded]
    lines += [f"- `{row['subject']}` — examined by {', '.join(row['examined_by']) or 'no model'}, "
              f"not by {', '.join(row['absent_from'])}" for row in absent]
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
        lines += _verdicts_on(result["arms"], subject)
    return lines


def _verdicts_on(arms: list[dict], subject: str) -> list[str]:
    """Every arm's verdict and reasoning for one template."""
    lines = []
    for arm in arms:
        verdict = arm["verdicts"].get(subject, "not examined by this model")
        mark = "flagged" if verdict == FLAGGED else verdict
        lines += [f"**{arm['model']}** — {mark}", "",
                  f"> {arm['details'].get(subject, '(no reasoning recorded)')}", ""]
    return lines


def _exposure(result: dict) -> list[str]:
    """What left the machine, summed over every arm rather than read off the last one."""
    requests = sum(arm["exposure"]["requests"] for arm in result["arms"])
    sent = sum(arm["exposure"]["bytes_sent"] for arm in result["arms"])
    kinds = sorted({kind for arm in result["arms"]
                    for kind in arm["exposure"]["field_kinds_transmitted"]})
    return ["", "## What left the machine", "",
            f"{requests} request(s) over {len(result['arms'])} model(s), {sent} bytes in "
            "total. Transmitted:", ""] + [f"- {kind}" for kind in kinds] + [
            "", "**Cannot be measured from here**, and stated rather than dressed up:", ""
            ] + [f"- {item}" for item in result["unmeasurable_exposure"]]


def to_markdown(result: dict, disagreement_note: str = "") -> str:
    """The whole comparison as Markdown."""
    lines = [f"# {TITLE}", "",
             f"Repository: `{result['repository']}` — "
             f"{result['subjects_seen']} prompt template(s) seen.", "",
             "## Summary", ""] + _verdict_summary(result) + _counts(result)
    if disagreement_note:
        lines += [disagreement_note, ""]
    lines += _not_compared(result)
    lines += ["", "## Every template, and what each model said"] + _per_template(result)
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
